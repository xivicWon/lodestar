# Lodestar E13 — 관계 후보 판단 근거(Evidence) 카드 설계

> 작성일: 2026-07-03
> 상태: **설계 승인됨 (스코프=풀 근거 카드)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: E2(이름 패턴 관계 발굴), E10(AI 관계 판정), E12(현재 온톨로지 의미추정)

## 0. 배경 & 문제

관계 발굴/판정 카드가 최소 정보만 노출한다:

```
은행자산 마스터 → 사용자그룹-자산   via GROUP_CD   0.60   hasGroup
```

운영자가 승인/거부를 결정할 근거가 화면에 없다. 특히 E2 휴리스틱은
**대상 "테이블 이름"의 토큰**만 보고 매칭한다(대상에 실제 조인 컬럼이 있는지
확인하지 않음). 위 예에서 0.60은 `GROUP_CD`의 스템 `GROUP`이 대상명
`user_group_asset`의 토큰 `group`과 겹쳐 나온 값일 뿐이다. 이 사실이 카드에
드러나지 않아 노이즈를 걸러낼 수 없다.

## 1. 목표

각 관계 후보에 **판단 근거(evidence)** 를 배치 응답으로 함께 실어, 카드에서
펼쳐 볼 수 있게 한다. **실 DB 재접속 없이 현재 온톨로지 메타데이터만** 사용한다
(read-only 원칙). N+1 호출 없음 — suggest 1회 계산으로 모든 근거를 만든다.

## 2. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 근거 원천 = 온톨로지 메타데이터(컬럼명·range 타입·functional·클래스 라벨)뿐 | read-only, 재접속·자격증명 불필요 |
| D2 | evidence 를 `RelationCandidate`에 필드로 추가 → `JudgedCandidate`로 전파 | suggest/judged 두 경로 모두 근거 노출 |
| D3 | "모호성(대안 대상)"은 **같은 (소스클래스, 소스컬럼)** 매칭 그룹에서 산출 | suggest 이중 루프가 이미 만드는 정보 재사용 |
| D4 | 카디널리티는 **휴리스틱 추정치**로 명시(단정 아님) | functional/대상 성격 신호만으로 추정, 오해 방지 |
| D5 | 카드 기본 접힘 + "상세 근거 ▾" 토글 | 후보 수백 개여도 목록 가독성 유지 |

## 3. 데이터 모델 (백엔드)

```kotlin
data class AltTarget(
    val toIri: String,
    val toLabel: String,
    val confidence: Double,
    val matchType: String,   // "exact" | "token"
)

data class RelationEvidence(
    val matchType: String,            // "exact"(0.9) | "token"(0.6)
    val matchStem: String,            // 예: "GROUP" (viaColumn 스템)
    val matchedOn: String,            // 매칭된 대상 코어/토큰 (예: "group")
    val viaType: String?,             // via 컬럼 range 짧은 이름 (예: "string"), 없으면 null
    val viaFunctional: Boolean,       // via 컬럼 functional 여부
    val targetHasSameColumn: Boolean, // 대상에 viaColumn 과 같은 이름 컬럼이 있나
    val targetSimilarKeys: List<String>, // 대상에서 같은 스템을 가진 컬럼(자기 이름 제외) 예: GROUP_SEQ
    val cardinality: String,          // "N:1 추정" 등
    val cardinalityReason: String,    // 추정 근거 한 줄
    val alternatives: List<AltTarget>,// 같은 소스 컬럼이 매칭한 다른 대상들(자기 제외)
    val fromLabel: String,
    val toLabel: String,
    val fromColumns: List<String>,    // 소스 전체 컬럼(짧은 이름)
    val toColumns: List<String>,      // 대상 전체 컬럼(짧은 이름)
)
```

`RelationCandidate`에 `val evidence: RelationEvidence` 추가.
`JudgedCandidate`에도 `val evidence: RelationEvidence` 추가(기존 필드 복사 시 함께 전달).

### 산출 규칙 (RelationService.suggest 확장)

1. 기존 이중 루프로 매칭을 만들되, **(aIri, colName) 그룹**으로 모아둔다.
   각 그룹의 모든 매칭이 서로의 `alternatives` 후보가 된다.
2. `matchType` = exact ? "exact" : "token"; `confidence`는 기존(0.9/0.6) 유지.
3. `matchStem` = `stemOf(colName)`; `matchedOn` = exact면 대상 코어, 아니면 매칭된 대상 토큰.
4. `viaType` = via dataProperty 의 `range` 짧은 이름(`#`/`/` 뒤); `viaFunctional` = dp.functional.
5. `targetHasSameColumn` = 대상 컬럼 목록에 `colName`(대소문자 무시) 존재.
6. `targetSimilarKeys` = 대상 컬럼 중 `stemOf(col)==matchStem`(대소문자 무시)이고 이름이 `colName`과 다른 것.
7. `cardinality`/`cardinalityReason`:
   - via functional → `"N:1 추정"`, 사유 `"조인 컬럼이 함수형(소스당 1값)"`.
   - 아니고 대상명이 code/master/group/type/cd로 끝남 → `"N:1 추정"`, 사유 `"대상이 코드/마스터 성격"`.
   - 그 외 → `"불명"`, 사유 `"함수형·대상 성격 신호 없음"`.
8. `alternatives` = 같은 그룹의 다른 매칭들 → `AltTarget(toIri,toLabel,confidence,matchType)`,
   confidence 내림차순.
9. `fromLabel`/`toLabel` = `mapper.labelOf` 있으면 그것, 없으면 shortName.
10. `fromColumns`/`toColumns` = 각 클래스가 domain 인 dataProperty 짧은 이름 정렬.

`RelationJudge.judge`는 `RelationCandidate.evidence`를 그대로 `JudgedCandidate.evidence`로 전달.

## 4. 프론트 (RelationSuggestPanel)

- `types.ts`: `AltTarget`, `RelationEvidence` 추가; `RelationCandidate`/`JudgedCandidate`에 `evidence` 필드.
- 카드 요약줄(기존)은 유지. 아래에 `상세 근거 ▾/▴` 토글 버튼.
- 펼치면 evidence 블록 렌더:
  - **매칭**: matchType(완전/부분일치) + `matchStem→matchedOn` + 부분일치면 ⚠ 경고.
  - **조인컬럼**: viaColumn · 타입 · functional; `targetHasSameColumn=false`면 ⚠ + `targetSimilarKeys`.
  - **카디널리티**: cardinality + reason.
  - **모호성**: alternatives 목록(라벨·confidence·완전/부분); 완전일치 대안이 있으면 강조.
  - **소스컬럼(n)/대상컬럼(m)**: 앞 N개 + 총 개수.
- 펼침 상태는 카드별 로컬(`ref<Set>` 또는 per-row reactive). 기본 접힘.

## 5. 테스트 (결정론적, 실 AI/DB 없이)

- **RelationServiceEvidenceTest**:
  - 대상 이름 토큰 부분일치 케이스 → `matchType="token"`, `confidence=0.6`,
    `targetHasSameColumn=false`, `targetSimilarKeys`에 같은 스템 컬럼, `alternatives`에
    완전일치(0.9) 대상 포함, `cardinality`/컬럼 목록 채워짐.
  - 완전일치 케이스 → `matchType="exact"`, `confidence=0.9`.
  - functional 컬럼 → `cardinality="N:1 추정"`, 사유 함수형.
- **RelationJudge**: evidence 가 JudgedCandidate 로 전파됨(페이크 advisor).
- **회귀**: 기존 RelationService/RelationJudge/컨트롤러 테스트 유지(필드 추가 후 시그니처 갱신).
- **프론트 RelationSuggestPanel.test**: evidence 있는 후보를 store에 주입 → 토글 클릭 시
  매칭/조인컬럼/모호성/컬럼목록 텍스트 렌더 확인.

## 6. 성공 기준

1. `GROUP_CD 0.60` 카드에서 "상세 근거"를 펼치면 왜 0.60인지(토큰 부분일치),
   대상에 동일 컬럼이 없다는 점, 더 유력한 완전일치 대안이 있다는 점이 보인다.
2. 새 DB 접속·자격증명 없음(온톨로지 메타데이터만).
3. suggest 1회로 모든 근거 산출(N+1 없음).
4. 백엔드/프론트 품질 게이트 그린.

## 7. 범위 밖 (다음)

- 실제 데이터 행 통계(값 분포·조인 성공률) — read-only 명시 동의 옵션 필요.
- 근거 기반 자동 랭킹/임계값 튜닝.
- 카디널리티 정밀화(유니크 인덱스 메타 활용).
