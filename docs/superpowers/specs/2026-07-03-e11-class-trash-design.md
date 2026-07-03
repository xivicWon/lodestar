# Lodestar E11 — 클래스 휴지통 (2단계 폐기) 설계

> 작성일: 2026-07-03
> 상태: **설계 승인됨 (구현 전)**
> 제품명: Lodestar · 리포 코드네임: onto-studio

## 0. 배경 & 목적

실 DB 임포트 결과엔 무의미한 임의 테이블(백업 스냅샷 `*_20230822`, 임시 테이블 등)이 섞인다. 이를 정리하되, **즉시 영구삭제는 위험**하므로 2단계 폐기(휴지통)로 안전하게 한다: 삭제=휴지통 이동(soft), 이후 복구 또는 완전삭제.

## 1. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 삭제 = **2단계**: ①휴지통 이동(soft) ②완전삭제/복구 | 오삭제 복구 가능 |
| D2 | 이동 시 **관련 정보 일괄**(컬럼·관계·확정·subclass/annotation) 함께 이동 | "관련 정보 일괄" 요구 |
| D3 | 관계 **상대편 클래스는 미삭제** | 연쇄 폭주 방지 |
| D4 | 보존기간 초과 항목 **lazy 자동 완전삭제** (목록 조회 시) | 스케줄러 없이 "일정시간 뒤 완전삭제" 충족 |
| D5 | 제거 축을 **Turtle로 직렬화 보관** → 복구 시 재추가 | OWL API 재사용, 정확 복원 |

## 2. 구조 & 흐름

```
[1단계] POST /api/trash {iri}   (툴바 "삭제" → 확인 후)
   collect: 대상 클래스의 referencing axioms
          + 소유 DataProperty(도메인이 이 클래스뿐)의 전체 축
          + 이 클래스가 domain/range 인 ObjectProperty 의 전체 축
   remove: 위 축을 활성 온톨로지에서 제거
   hold:   제거 축으로 임시 OWLOntology 구성 → Turtle 직렬화
   store:  TrashEntry{iri, label, trashedAt(ms), turtle, confirmed} 를 휴지통(파일) 에 저장
   confirmation: 해당 iri 확정 있으면 제거하고 entry.confirmed=true 로 기록
   반환: {iri, columns:Int, relations:Int}

[2단계]
   GET  /api/trash               → List<TrashEntryDto{iri,label,trashedAt}>  (조회 시 보존기간 초과분 lazy purge)
   POST /api/trash/restore?iri=  → 보관 Turtle 파싱 → 활성 온톨로지에 축 추가(+confirmed면 확정 복원) → entry 제거
   DELETE /api/trash?iri=        → entry 제거(완전삭제)
```

## 3. 컴포넌트 (경계 명확)

- **`TrashEntry`** (신규) — `iri, label, trashedAt: Long, turtle: String, confirmed: Boolean`.
- **`TrashService`** (신규, `com.ontostudio.trash`, @Service) — 의존: OntologyHolder, OntologyMapper, ConfirmationStore, (IoService 스타일 직렬화).
  - `trash(iri): TrashResult(iri,columns,relations)`:
    - 존재 확인(없으면 404). 소유 DataProperty = `dataPropertiesInSignature` 중 도메인 집합이 `{iri}` 인 것. 관계 = `objectPropertiesInSignature` 중 domain 또는 range 에 iri 포함.
    - 제거 축: 클래스 referencingAxioms + 각 소유 DataProperty referencingAxioms + 각 관계 referencingAxioms (중복 제거).
    - 임시 OWLOntology 에 제거 축 추가 → Turtle 바이트 → String. 활성에서 `removeAxioms`.
    - ConfirmationStore.isConfirmed(iri) 면 remove + confirmed=true.
    - TrashEntry 저장(파일 영속, 원자적 쓰기 — E8 ConfirmationStore 패턴 준용).
  - `list(): List<TrashEntry>` — 호출 시 `trashedAt + retentionMs < now` 인 항목 purge 후 반환. retention = `@Value lodestar.trash.retention-days:30`. (현재시각은 `System.currentTimeMillis()`.)
  - `restore(iri)`: entry 의 turtle 파싱해 활성 온톨로지에 축 추가; confirmed 면 ConfirmationStore.confirm 재등록(label 은 entry.label); entry 제거.
  - `purge(iri)`: entry 제거.
  - 파일 영속: JSON(List<Map>) 원자적 저장(임시파일+ATOMIC_MOVE), 손상 파일 백업(E8 교훈 반영). `@Value lodestar.trash.file:./data/trash.json`.
- **`TrashController`** — POST /api/trash, GET /api/trash, POST /api/trash/restore, DELETE /api/trash.
- **프론트** — 툴바 "삭제": 선택 클래스에 대해 확인창(`"휴지통으로 이동 — 컬럼·관계 포함"`) → store.trashClass(iri) → refresh. 새 "🗑 휴지통" 토글 패널(TrashPanel.vue): store.trash 목록(이름·이동시각) + [복구](restoreTrash) [완전삭제](purgeTrash). store: trash ref, fetchTrash/trashClass/restoreTrash/purgeTrash.

## 4. 테스트 (결정론적)

- **`TrashServiceTest`**: 온톨로지를 SchemaToOwlMapper 로 구성(예: TB_A(2컬럼)+TB_B, FK로 A→B 관계). `trash(A)` → 활성에서 A·A컬럼·A관계 사라짐, columns/relations 카운트 정확, 휴지통 목록에 A. `restore(A)` → A·컬럼·관계 **원상복구**(classesInSignature 다시 포함). `purge` 후 목록 비고 복구 불가. 보존기간 0 설정 시 list()가 즉시 lazy purge. 파일에 쓴 뒤 새 인스턴스 재로드로 목록 유지.
- **`TrashController` 통합**(@SpringBootTest, @DynamicPropertySource temp file): 샘플 임포트 → POST /api/trash{한 클래스} → GET /api/classes 에서 사라짐, GET /api/trash 에 등장 → restore → 다시 등장.
- **프론트**: store trashClass/restoreTrash/purgeTrash(mock) + TrashPanel 컴포넌트(목록·복구·완전삭제 버튼 호출) + Toolbar 삭제가 확인 후 trashClass 호출.

## 5. 성공 기준

1. 임의 테이블 "삭제" → 컬럼·관계까지 휴지통으로 이동(활성에서 제거), 이동 요약(컬럼/관계 수) 표시.
2. 휴지통에서 **복구** 시 클래스·컬럼·관계가 원상복구된다.
3. **완전삭제** 시 영구 제거되어 복구 불가.
4. 보존기간 초과 항목은 목록 조회 시 자동 완전삭제.
5. 휴지통은 파일 영속(재기동 유지), 저장은 원자적.

## 6. 범위 밖 (다음)

- 스케줄러 기반 백그라운드 자동삭제(현재 lazy).
- 관계 상대편 클래스 연쇄 이동.
- 개별 컬럼/관계 단위 휴지통.
- 휴지통 항목의 원본 소스/사유 메타.
