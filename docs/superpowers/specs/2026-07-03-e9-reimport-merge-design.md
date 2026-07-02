# Lodestar E9 — 재임포트 병합 (확정 라벨 자동 복원) 설계

> 작성일: 2026-07-03
> 상태: **설계 승인됨 (구현 전)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: E8(세이브포인트 + 그라운딩). 운영 모델 ②③의 마지막 조각.

## 0. 배경 & 목적

E8에서 확정(세이브포인트)을 온톨로지와 분리된 저장소에 영속했다. 이제 **스키마가 바뀌어 재임포트(재스캔)해도 승인했던 의미가 유지**되도록, 임포트 직후 확정 저장소를 새 온톨로지에 IRI로 매칭해 라벨을 자동 복원한다. 결정론적 IRI(baseIri+slug)가 매칭 키다.

## 1. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 병합 = **임포트 시 자동** (connection/ddl/sample 모두) | "재스캔해도 승인 의미 유지"의 무마찰 경험. IRI 결정론적이라 같은 소스만 매칭 |
| D2 | 미매칭 확정 = **저장소 보존 + 리포트** (자동 삭제 안 함) | 재임포트가 늘 삭제는 아님(부분 스캔/오타/환경차). 확정은 값진 사람 노력. 수동 DELETE로 정리 |
| D3 | 매칭 대상 = **클래스 라벨 확정** (kind="class") | 관계 확정 병합은 다음 슬라이스 |

## 2. 구조 & 흐름

```
RdbImportController.ingest(source):
   ont = schemaMapper.build(source.extract(), baseIri)
   holder.replace(ont, baseIri)
   merge = ConfirmationMerger.merge()          ← 신규
      for fact in ConfirmationStore.all() where kind == "class":
         if 새 온톨로지에 class IRI 존재 → ClassService.setLabel(fact.iri, fact.label); reapplied++
         else → stale++ (저장소에 그대로 보존)
   return ImportResult{ meta = ontologyMapper.meta(), merge = {reapplied, stale, staleIris} }
```

## 3. 컴포넌트 (경계 명확)

- **`MergeSummary`** (신규 DTO) — `reapplied: Int, stale: Int, staleIris: List<String>`.
- **`ImportResult`** (신규 DTO) — `meta: OntologyMetaDto, merge: MergeSummary`.
- **`ConfirmationMerger`** (신규, `com.ontostudio.savepoint`, @Service) — `merge(): MergeSummary`.
  `ConfirmationStore.all()` 순회: `kind=="class"` 이고 `holder.ontology.containsClassInSignature(IRI.create(iri))` 면 `ClassService.setLabel(iri, label)` 재적용(reapplied), 아니면 stale(저장소 보존). 의존: ConfirmationStore, ClassService, OntologyHolder.
- **`RdbImportController.ingest` 확장** — `holder.replace` 후 `merger.merge()` 호출, `ImportResult` 반환. 세 엔드포인트(`/import/connection`, `/import/ddl`, `/import/sample`) 반환 타입이 `OntologyMetaDto` → `ImportResult`로 변경.
  - 기존 프론트 import 액션은 반환값을 사용하지 않고 `refresh()`만 하므로 **무해**. 병합 요약만 새로 캡처.
- **프론트** — `ImportResult`/`MergeSummary` 타입. import 액션(`importSample/importDdl/importConnection`)이 응답에서 `lastMerge` 캡처. 작은 알림 표시("확정 N건 복원 · 미매칭 M건"), 복원 0·미매칭 0이면 숨김.

## 4. 테스트 (결정론적, 실 AI 없이)

- **`ConfirmationMergerTest`**: (임시 confirmations 파일) TB_CUST_MST 클래스 IRI를 확정 → sample 임포트/빌드로 그 클래스가 존재하는 상태에서 `merge()` → 해당 클래스 라벨이 확정 라벨로 바뀌고 `reapplied>=1`. 존재하지 않는 IRI 확정 → `stale` 카운트, 저장소에 보존(여전히 isConfirmed), 미적용.
- **통합**(@SpringBootTest, @DynamicPropertySource 임시 파일): `POST /api/rdb/import/sample` → `POST /api/enrich/confirm {TB_CUST_MST, "거래처 마스터"}` → **다시** `POST /api/rdb/import/sample` → 응답 `merge.reapplied>=1`, 그리고 `GET /api/classes` 의 TB_CUST_MST 라벨이 "거래처 마스터"(재임포트로 원복되지 않음).
- **프론트**: import 액션이 `lastMerge` 세팅(mock) + 알림 컴포넌트가 카운트 표시/0일 때 숨김.
- **기존 테스트 갱신 (필수)**: import 응답이 `OntologyMetaDto` → `ImportResult`로 감싸지므로, 기존 import 응답을 검증하는 테스트의 JSON 경로를 `$.counts.classes` → `$.meta.counts.classes`로 수정해야 한다(예: `RdbImportControllerTest`, `SampleImportControllerTest`). 프론트 import 액션은 반환값 미사용이라 타입만 `ImportResult`로 갱신.

## 5. 성공 기준

1. 확정 후 같은 소스를 재임포트하면 확정 라벨이 **자동 복원**된다(원본 테이블명으로 원복되지 않음).
2. 임포트 응답에 `reapplied / stale` 요약이 실리고 UI에 표시된다.
3. 미매칭 확정은 저장소에 보존된다(자동 삭제 없음).
4. 병합 로직은 결정론적 테스트로 검증된다.

## 6. 범위 밖 (다음)

- 관계(E2) 확정의 병합(현재 라벨=클래스만).
- 이름변경 테이블 퍼지/스마트 매칭(현재 정확 IRI 매칭만).
- 프로젝트별 확정 분리, 병합 이력.
