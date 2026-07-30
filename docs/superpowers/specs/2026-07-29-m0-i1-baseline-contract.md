# M0 / I1 — 기준선 계약 (Baseline Contract)

> 작성일: 2026-07-29
> 이슈: #94 `[M0][기준] I1 기준선 계약 확정` · 마일스톤: **M0 Evidence Quality Foundation**
> 상태: **확정** — 본 문서 머지 시점부터 **I1 계약이 발효**된다.
> 발효는 착수 허가가 아니다: 실제 L0 벤치 착수는 **I2(#99)·I3(#100)가 커밋된 뒤에만** 가능하다 (G2 · §2.1).
> 리뷰어/승인권자: **@xivicWon**

L0~L3 벤치를 실행하기 전에 **모든 고정 요소를 못박는 선행 게이트**다.
이 문서에 적히지 않은 요소로 벤치를 실행하면 그 실행 결과는 무효다.

---

## 개정 이력

수치·revision 변경은 **이전 값과 함께** 남긴다. 덮어쓰기는 개정이 아니다(§7.3 · P4 자기적용).

### R1 — 2026-07-30 · §1.1 DB 트랙 `CREATE TABLE` **28 → 27** (이슈 #116)

| 항목 | 이전 값 | 개정 값 |
|---|---|---|
| §1.1 DB 실측 규모 | `CREATE TABLE` **28** | `CREATE TABLE` **27** |
| §1.1 FK 서술 | "**28**테이블 중 명시 FK 1건" | "**27**테이블 중 명시 FK 1건" |

- **사유:** 초판의 28 은 `grep -ci 'create table'` 결과였고, 그 28번째 일치는 픽스처 L221~L222의
  한국어 주석이다. 테이블 수는 `CREATE TABLE` **문장**만 세야 한다(gold R-DB-1).
  이 오탐은 gold 음성 항목 `L1.DB.TABLE.NEG.만` 이 잡으려는 실패와 **정확히 같은 실패**다.
- **근거 (둘 다 27):**
  - #99 Gold Set — `docs/superpowers/specs/gold/l1/db.json` `counts.TABLE = 27`
    (`COLUMN` 119 · `PRIMARY_KEY` 27 · `FOREIGN_KEY` 1 · `VIEW` 1), 제안은 I2 §8.1.
  - #88 L0 실측 — `docs/superpowers/specs/bench/l0/runs/run-l0-db-3c27259-001/`
    (동일 revision 3회 수집 결과 동일, 결정성 1.0), 확인 기록은 L0 검증 문서 §8.3(F10).
- **영향 범위(§7.1) — 무효화되는 이전 실행: 없다.**
  - `run-l0-db-3c27259-001` 은 테이블 수 주장을 27로 실측했고 `fixtureHash` 도 gold 와 같다.
    28 을 인용한 baseline-적격 실행은 존재하지 않는다(L0 판정은 BLOCKED, RQR 예시는 `EXAMPLE`).
  - source revision(`3c27259`)·Gold Set 은 바뀌지 않는다 → §7.4의 기준선 제외 조항 비해당.
  - I3(#100) RQR 예시의 L1 db `counts` 는 이 값에서 파생되므로 함께 정정했다
    (`input` 29 → **28**, `output` 28 → **27**; 28 = 테이블 27 + 뷰 1, 뷰 1건은 제외 사유로 보고).
  - #99 gold EVL 충돌 항목 `CF1.TABLE_COUNT`(27 vs 28)는 `docsRevision: 7d3db3e`(개정 이전)에
    고정돼 있어 **그 revision 기준으로는 여전히 유효**하다. 이 개정은 그 항목의 `resolutionPath`가
    말한 해소 경로 자체이며, gold 를 `RESOLVED` 로 바꾸는 것은 gold 개정 절차(#99 §10.4 — `--rehash`·
    G1~G14 재통과·승인)를 따르는 **별건**이다. 이 PR 은 gold 를 건드리지 않는다.
- **자동 확인:** `python3 docs/superpowers/specs/verify_i1_counts.py` (C1~C5 — 원문 실측·문서 내부
  정합·gold·RQR 예시·개정 이력 보존).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

| | 내용 | 소유 |
|---|---|---|
| ✅ 확정 | 대상 프로젝트·트랙·리뷰어·source revision | 본 문서 (§1) |
| ✅ 확정 | 레이어 의존 순서와 게이트 규칙 | 본 문서 (§2) |
| ✅ 확정 | 승격/중단 규칙 | 본 문서 (§3) |
| ✅ 확정 | 목표 수치 **정책**(무엇이 무조건 게이트이고 무엇이 잠정인지) | 본 문서 (§4) |
| ✅ 확정 | 기능 인벤토리 초안 (E1~E17 → 레이어 매핑) | 본 문서 (§5) |
| ✅ 확정 | 참고자료 편입 — 이슈 지정 계약 요소 매핑 (aira POC 데이터는 폐기) | 본 문서 (§6) |
| ⛔ 미확정 | Gold Set 내용, 실패 fixture, **fixture hash** | **#99 (I2)** |
| ⛔ 미확정 | Run Quality Report 필드 스키마·템플릿 파일 | **#100 (I3)** |
| ⛔ 미확정 | precision/recall 등 **목표 수치의 확정값** | #88·#89 1차 baseline 측정 후 비준 (§4) |
| ⛔ 미확정 | 기능별 Core/Lab/Parked/Retire **판정** | **#101 (I4)** — 본 문서는 인벤토리와 매핑까지만 |

**비범위:** 구현 변경 · 신규 데이터 커넥터 · 다중 프로젝트 통합.

---

## 1. 고정 요소 (Fixed Baseline)

### 1.1 대상 프로젝트 — Lodestar (self / dogfood), 2트랙

| 트랙 | 벤치 대상 | 실측 규모 (@`3c27259`) | 커버 레이어 |
|---|---|---|---|
| **코드** | `backend/src/main/kotlin` (실제 Kotlin) | `.kt` 59개, 17개 패키지 | L1 코드관찰, L2 코드↔코드 |
| **DB** | `backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql` | `CREATE TABLE` 27, `CREATE VIEW` 1, 명시 `FOREIGN KEY` 1 | L0 수집, L1 명시사실, L2 암시관계, L3 의미 |

> 테이블 수는 **`CREATE TABLE` 문장**만 센다(gold R-DB-1). 주석 안의 같은 문자열은 세지 않는다 —
> 초판의 28 은 L221 주석("`DdlParser` 는 `CREATE TABLE` 만 처리하므로 스킵되어야 함")을 함께 센
> `grep -ci` 결과였다. 개정 이력 R1 참조.

DB 트랙 픽스처가 레거시 벤치 대상으로 적합한 이유(실제 성질):

- **FK가 사실상 없음** — 27테이블 중 명시 FK는 `TB_ORD_MEMO → TB_ORD_HD` **단 1건**. 나머지 관계는 전부 이름 기반 암시관계 → **L2 INFERRED 링크의 정직한 시험대**.
- **복합키 다수** — `TB_CUST_ADDR(CUST_NO, ADDR_SEQ)`, `TB_STOK_QTY(WH_CD, ITEM_CD)`, `TB_ORD_DTL(ORD_NO, ORD_SEQ)`, `TB_ATTND(EMP_NO, WRK_DT)`, `TB_COMM_CD(GRP_CD, CD)` 등 → **L1 PK 추출 정확도**.
- **뷰 1건 존재** — `VW_ORD_SUMMARY`. 현 `DdlParser`는 `CREATE TABLE`만 처리 → **스킵을 "조용히 무시"하지 않고 제외 사유로 보고하는지**가 L0/L1 오류 가시성 시험 항목.
- **암호명 컬럼** — `TB_CUST_MST`, `CUST_NO`, `VNDR_CD` 등 → **L3 의미 Claim(AI 추정)** 대상.

### 1.2 리뷰어

**@xivicWon** — Gold Set 제작·채점 **확정 권한**. 에이전트는 **초안 작성·자동 비교 보조**만 한다.
에이전트가 만든 Gold 항목은 리뷰어 승인 전까지 정답으로 사용할 수 없다.

### 1.3 source revision (고정)

```
3c27259  (3c27259fe6c979e00912c5e3686c611a28cb977e)
feat(e17): 코드 소스 수집기 — 소스코드→정적 codegraph.json (tree-sitter) (#80)
```

- M0의 **모든** 레이어 실행은 이 revision을 입력으로 한다. 벤치 도중 revision을 올리지 않는다.
- revision 변경이 필요하면 **본 문서를 개정하고 이전 실행 결과를 무효 처리**한다(§7).
- **fixture hash는 여기서 고정하지 않는다** — Gold Set과 함께 **#99(I2)** 에서 고정한다.
  (fixture hash 없이 실행된 결과는 Run Quality Report에서 `fixtureHash: UNPINNED`로 표기되며 baseline으로 인정하지 않는다.)

### 1.4 자기참조(self-reference) 주의 — 명시적 한계

코드 트랙은 **Lodestar 한 앱**만 대표한다. 단일 언어(Kotlin)·단일 아키텍처·단일 저자다.
따라서 M0의 코드 트랙 결과는 **"이 도구가 이런 성격의 코드에서 동작한다"** 까지만 주장할 수 있다.
다른 성격 프로젝트로의 일반화 주장은 **금지**하며, **M1+에서 별도 대상으로 재검토**한다.

---

## 2. 레이어 의존 순서와 게이트 규칙

### 2.1 실행 순서 (직렬 · 병렬 금지)

```
기반(선행):  I1(#94, 본 문서)  →  I2 Gold Set(#99)  →  I3 Report 템플릿(#100)
레이어(직렬): L0(#88)  →  L1(#89)  →  L2(#90)  →  L3(#91)
판정(종료):  I4 기능 판정(#101, L0~L3 한정)
```

L4 Advice(#92) / L5 Confirmation(#93)은 **M0 범위 밖**이며 각각 M3 / M2 상위 트래킹으로 이관한다.
(구 완료기준의 "6개 레이어"는 폐기 — M0는 **L0~L3 4개 레이어**다.)

### 2.2 게이트 규칙 — "통과 = 다음 착수"

| 규칙 | 내용 |
|---|---|
| **G1 선행 완결** | 선행 레이어가 **`PASS` 또는 `PASS (RESTRICTED)` 판정된 Run Quality Report를 남기기 전**에는 후행 레이어 벤치를 착수하지 않는다. |
| **G2 기반 선행** | I2(#99) Gold Set과 I3(#100) 템플릿이 커밋되기 전에는 L0(#88)도 착수하지 않는다. 측정 기준 없는 실행은 baseline이 아니다. |
| **G3 단일 방향** | 후행 레이어 결과로 선행 레이어의 판정을 뒤집지 않는다. 선행 판정 변경은 **선행 레이어 재실행**으로만 한다. |
| **G4 부분 통과 금지** | "대체로 통과"는 통과가 아니다. §3.2의 **HALT 조건**에 하나라도 걸리면 **BLOCKED**이며 후행 착수 불가. **유일한 예외는 RESTRICT 등급(H4)** — 후행 착수는 허용되나 제한된 경로로만 진행하고 판정을 `PASS (RESTRICTED)`로 기록한다(§3.2). |
| **G5 증거 필수** | 모든 판정은 Run Quality Report(#100 템플릿) 링크를 근거로 갖는다. 보고서 없는 판정은 무효. |

**레이어 판정값은 3종이다:** `PASS` · `PASS (RESTRICTED)` · `BLOCKED`.
→ **#100(I3) 요구사항:** Run Quality Report 템플릿은 이 3값과 함께 **제한 등급·제한 사유·닫힌 경로**를 기록할 필드를 포함해야 한다.

### 2.3 레이어별 입출력 계약 (요약 · 상세는 각 이슈)

| 레이어 | 입력 | 출력 필수값 | 절대 하지 않는 것 |
|---|---|---|---|
| **L0 Source** (#88) | 고정 revision의 원본 | `projectId`, `sourceId`, `revision`, `contentHash`, `collectorVersion`, 포함/제외 범위 + 제외 사유 | 원본 쓰기, 최소 범위 초과 저장, 실패·제외 은폐 |
| **L1 Observation** (#89) | L0 통과 revision | `observationId`, `type`, `normalizedValue`, `sourceLocation`, `sourceRevision`, `contentHash`, `extractorVersion` | 추론 관계·AI 추정 라벨을 Observation에 저장 |
| **L2 Identity** (#90) | L1 Observation + provenance | `identityLinkId`, `leftObservationId`, `rightObservationId`, `status`(EXTRACTED/INFERRED/AMBIGUOUS), `evidenceIds`, `method`, `confidence` | 이름 유사도만으로 확정, 모호함 임의 해소 |
| **L3 Knowledge** (#91) | L1 Observation + L2 Link | `claimId`, `subject`, `predicate`, `object`, `evidenceIds`, `status`, `method`, `confidence`, `validFrom`, `validTo`, `createdAt`, `supersedes` | 무근거 Claim 생성, 충돌 덮어쓰기, 확인 이력 소실 |

---

## 3. 승격 / 중단 규칙 (Promotion & Halt)

### 3.1 승격 금지 규칙 (하드)

| ID | 규칙 | 위반 시 |
|---|---|---|
| **P1** | **무근거 Claim 금지** — 모든 L3 Claim은 하나 이상의 L1 Observation 또는 L2 Link를 `evidenceIds`로 참조한다. | 해당 Claim 무효 + L3 BLOCKED |
| **P2** | **INFERRED ↛ EXTRACTED** — 추론으로 만든 링크·Claim을 명시 사실로 승격하지 않는다. 사람 확인은 `HUMAN_CONFIRMED`로 가며 **EXTRACTED가 되지 않는다**. | 해당 레코드 무효 + 레이어 BLOCKED |
| **P3** | **모호함 보존** — 근거가 부족하거나 후보가 복수면 확정하지 않고 `AMBIGUOUS`로 남긴다(abstention). | L2 BLOCKED |
| **P4** | **충돌 무보고 덮어쓰기 금지** — 상충 Claim은 병존 또는 `supersedes` 관계로 보존한다. | L3 BLOCKED |
| **P5** | **레이어 건너뛰기 금지** — L0을 거치지 않은 원본, L1을 거치지 않은 사실로 상위 산출물을 만들지 않는다. | 해당 산출물 무효 |

### 3.2 중단 규칙 (Halt / Restrict)

중단 조건은 **두 등급**으로 나뉜다. 등급이 후행 레이어의 착수 가능 여부를 결정한다.

| ID | 등급 | 조건 | 조치 |
|---|---|---|---|
| **H1** | **HALT** | **결정성 실패** — 동일 revision 3회 실행 결과가 다르다 | **즉시 상위 레이어 전면 중단.** 결정성이 회복될 때까지 어떤 정확도 수치도 인용하지 않는다. |
| **H2** | **HALT** | L0 결정성·보안(PII·시크릿 마스킹) 미통과 | L1 이상 진행 금지 |
| **H3** | **HALT** | L1 명시 사실 정확도 부족 | L2/L3 벤치 중단 + **새로운 추론·AI 기능 추가 금지** |
| **H4** | **RESTRICT** | L2 고신뢰 오연결 위험이 높음 | **L3 벤치는 진행하되 자동 승격 경로를 닫는다.** L2 링크에서의 Claim 자동 확정 금지, `HUMAN_CONFIRMED` 경로만 측정 대상. L3 판정은 `PASS (RESTRICTED)`로 기록하고 제한 사유·범위를 Run Quality Report에 남긴다. |
| **H5** | **HALT** | Gold Set을 만들 수 없음 | 대상 프로젝트 또는 평가 질문을 재선정 (I1 개정 — §7) |

**등급의 의미**

- **HALT** — 후행 레이어 **착수 불가**. 판정은 `BLOCKED`(G4).
- **RESTRICT** — 후행 레이어 착수는 **허용되나 경로가 제한**된다. **G4의 유일한 예외**이며, 제한 사실·범위를 보고서에 명시하지 않으면 그 자체가 실패 항목이다(§3.3). 제한 상태에서 나온 결과로 **"자동 승격이 동작한다"고 주장할 수 없다** — 측정되지 않은 경로이기 때문이다.
- 등급 판단이 애매하면 **HALT로 처리**한다. 통과 쪽으로 기우는 해석은 금지.
- RESTRICT는 §3.3의 confidence 상한 전파가 **판정 등급으로 드러난 형태**다. 두 규칙은 같은 원칙의 다른 표현이며 서로 충돌하지 않는다.

### 3.3 하위 실패의 상위 전파 (Confidence Ceiling)

하위 레이어의 실패·누락은 **조용히 사라지지 않고 상위 confidence의 상한으로 전파**된다.

```
L0 수집 실패·부분 성공  →  해당 sourceId를 근거로 삼는 L1 Observation에 degraded 표시
L1 파싱 실패·누락       →  그 Observation을 쓰는 L2 Link의 confidence 상한 적용
L2 AMBIGUOUS / 저신뢰   →  그 Link를 쓰는 L3 Claim은 자동 확정 불가 (HUMAN_CONFIRMED 경로만)
근거 삭제·노후화        →  참조하는 Claim의 status·confidence를 갱신 (무시 금지)
```

- 상한의 **구체 수치**는 #88·#89 baseline 측정 후 §4 절차로 비준한다. 그 전까지는 "상한이 적용된다"는 **사실 자체를 Run Quality Report에 기록**하는 것이 게이트다.
- 전파를 구현하지 않아 상위가 하위 실패를 모르는 경우, 그것 자체가 해당 레이어의 **실패 항목**이다.

---

## 4. 목표 수치 정책

### 4.1 무조건 게이트 (사전 확정 · 협상 불가)

| 지표 | 값 | 근거 |
|---|---|---|
| **결정성** (동일 입력 3회 일치율) | **100%** | 재현 불가한 측정은 측정이 아니다 (H1) |
| L0 메타데이터 완전성 (필수 식별 필드) | 100% | 추적 불가한 수집은 근거가 아니다 |
| L0 오류 가시성 (실패·제외 보고율) | 100% | 은폐는 정확도보다 먼저 실격 |
| L0 보안 (테스트 시크릿 미마스킹) | **0건** | 오탐률은 별도 기록(게이트 아님) |
| L1 `sourceLocation`·`revision` 연결률 | 100% | 원본 역추적 불가 = Observation 아님 |
| L1 무보고 파싱 실패 | 0건 | |
| L2 근거·방법·양쪽 위치 연결률 | 100% | |
| L2 모호 사례 AMBIGUOUS 처리율 | 100% | P3 |
| L3 근거 연결률 / 무근거 Claim | 100% / **0건** | P1 |
| L3 충돌 무보고 덮어쓰기 | 0건 | P4 |
| L3 재수집 후 확인 이력 보존율 | 100% | |

> 위 지표들의 공통점: **정확도가 아니라 정직성**이다. 성능이 나쁜 것은 baseline이지만, 실패를 숨기는 것은 실격이다.

### 4.2 잠정 수치 (baseline 측정 후 비준)

각 이슈에 선언된 아래 값은 **잠정(provisional) 목표**다. 현재 구현 성능을 모르는 상태에서 선언된 값이므로 **게이트로 사용하지 않는다.**

| 레이어 | 잠정값 |
|---|---|
| L1 | 명시 사실 precision ≥99%, recall ≥95% |
| L2 | 링크 precision ≥95%, recall ≥80%, 고신뢰 오연결률 ≤1% |
| L3 | 표현 간(OWL↔SQLite) Gold Query 결과 일치율 ≥95% |

**비준 절차:**

1. #88·#89를 **잠정값을 게이트로 쓰지 않고** 1차 실행 → 현재값을 Run Quality Report에 기록한다.
2. 리뷰어(@xivicWon)가 현재값과 잠정값의 격차를 검토한다.
3. 확정 목표치를 정하고 **본 문서를 개정**한다(§7). 이때 비로소 게이트가 된다.
4. 비준 전에는 어떤 문서·PR·발표에서도 잠정값을 "달성 기준"으로 인용하지 않는다.

지표는 **DB 트랙과 코드(codegraph) 트랙을 분리 산출**한다. 합산 평균은 실패를 가린다.

---

## 5. 기능 인벤토리 초안 (E1~E17 → 벤치 레이어 매핑)

> **판정(Core/Lab/Parked/Retire)은 #101(I4)의 몫**이다. 아래 "1차 분류"는 마일스톤 M0 설명문의 후보 분류를 옮긴 **가설**이며, 벤치 결과로 검증·확정된다. 구현량은 판정 근거가 아니다.

### 5.1 에픽 단위

| 에픽 | 기능 | 주요 앵커 | 벤치 레이어 | 1차 분류(가설) |
|---|---|---|---|---|
| **E1** Reality Harness | 레거시 샘플 DDL/데이터 픽스처 + 주입 | `rdb/legacy-sample.sql`, `rdb/` | **L0** (본 벤치의 DB 트랙 입력 그 자체) | Core 후보 |
| **E2** Implicit Relationship Recovery | FK 없는 관계 휴리스틱 발굴 | `rel/RelationService.kt` | **L2** (INFERRED 링크 precision/recall) | Lab |
| **E3** AI Semantic Enrichment | 이름+컬럼 → AI 의미 라벨/설명 후보 | `ai/AiAdvisor.kt`, `ai/SemanticEnricher.kt` | **L3** (method=AI Claim, 근거·confidence) | Lab |
| **E4** Impact Analysis | 그래프 도달성 영향도 | `impact/` | **L4** (M0 비범위 — M3 상위 트래킹) | Lab / 판정 보류 |
| **E5** Persistence | 온톨로지 프로젝트 저장/로드 | `project/`, `io/` | **L0/L3 부수** (저장·재현성) | Core 후보 |
| **E6** AI Chat | 온톨로지 자연어 Q&A | `ai/ChatService.kt` | **L4** (M0 비범위) | Lab / 판정 보류 |
| **E7** Inference Confidence | N회 합의율 기반 확률적 신뢰도 | `ai/ConsensusScorer.kt`, `ai/ScoredEnricher.kt` | **L3** (confidence 산정) + **결정성(H1) 직격** | Lab |
| **E8** Savepoint & Grounding | 세이브포인트 + 그라운딩 | `savepoint/ConfirmationStore.kt` | **L3** (HUMAN_CONFIRMED, 확인 이력 보존) | Core 후보 |
| **E9** Re-import Merge | 재임포트 시 확정 라벨 복원 | `savepoint/ConfirmationMerger.kt` | **L2**(stable identity 유지/분리/병합) + **L3**(재수집 후 이력 보존) | Core 후보 |
| **E10** AI Relation Judgment | 관계 후보 노이즈 필터 | `rel/RelationJudge.kt` | **L2** (오연결 억제, AMBIGUOUS 유지) | Lab |
| **E11** Class Trash | 2단계 폐기(휴지통) | `trash/` | **L3** (삭제·재등장 시나리오) | Lab |
| **E12** Ontology Enrich | 실 DB 대상 AI 의미추정 | `ai/`, `ontology/` | **L3** | Lab |
| **E13** Relation Evidence Card | 관계 판단 근거 카드 (#57) | `rel/`, frontend | **L2** (`evidenceIds`·method 표시) | Core 후보(근거 표시) |
| **E14** Screen Redesign | 그래프 기본화면 + side panel | frontend | **UI — M0 비범위** | Parked 후보 |
| **E15** Ontology Alignment | 참조 온톨로지 + SKOS 정렬 | `align/`, `reference/` | **외부 ontology — M0 비범위** | Parked 후보 |
| **E16-0** Provenance 통일 | kind/tier/confidence 통일 | `provenance/ProvenanceVocab.kt` | **L2 status + L3 provenance 전반** (계약의 뼈대) | Core 후보 |
| **E16-1** Read-model 투영 | OWL→SQLite read-model | `readmodel/ReadModelProjector.kt` | **L3** (표현 간 일치율·정보 손실) | Lab |
| **E16-2** MCP 공개 | (미착수) | — | **M0 비범위** | Parked 후보 |
| **E17** Code Source Collector | 소스코드→정적 codegraph.json (tree-sitter) | `codegraph/` (Python) | **L0**(코드 수집) + **L1**(파일·타입·메서드·명시 호출) + **L2**(calls 해석) | Lab |

### 5.2 P 페이즈 잔여 기능 (에픽 번호 없음 · 판정 대상)

| 기능 | 앵커 | 벤치 레이어 | 1차 분류(가설) |
|---|---|---|---|
| RDB→OWL 매핑 | `rdb/SchemaToOwlMapper.kt`, `core/OntologyMapper.kt` | **L1→L3 변환 경로** (명시 사실 보존 여부) | Lab |
| DDL 파서 | `rdb/DdlParser` | **L1** (뷰 스킵 보고 포함) | Core 후보 |
| Reasoner (HermiT) | `reasoner/` | **L3** (추론 Claim, INFERRED 표시) | Lab |
| 클래스 편집 UI | frontend | **M0 비범위** | Parked 후보 |
| 다중 벤더 커넥터 (MySQL 등) | `rdb/` | **신규 커넥터 — M0 비범위** | Parked 후보 |

> **인벤토리에서 제외된 항목:** Decision Ledger(aira, 에픽 #87 / 이슈 #81~#86)는 리포에 코드가 존재하지 않고(로컬 POC 데이터는 2026-07-29 폐기 — §6), 제품 범위 밖이므로 **M0 판정 대상에서 제외**한다. #101(I4)에서도 다루지 않는다.

### 5.3 인벤토리 사용 규칙

- #101(I4)은 이 표의 각 행에 **Run Quality Report 링크**를 붙여 판정한다. 근거 링크 없는 판정은 무효.
- "M0 비범위"로 표시된 기능은 M0에서 **측정하지 않는다**. 측정하지 않은 기능을 Core로 판정하는 것은 금지되며, Parked/Retire 판정은 가능하다.
- M0 종료 상태 = **Core 범위 + 재검토할 Lab만 열린 채로 남김**.

---

## 6. 참고자료 편입 — 이슈 #94 지정 계약 요소 매핑

> **폐기 기록 (2026-07-29, @xivicWon 지시):** 로컬에만 존재하던 `aira/` POC 데이터는 **임의 프로젝트 분석 산출물로 판정되어 폐기**했다(리포에 커밋된 적 없음 — `git ls-files aira` 공백). 따라서 그 폴더 실물을 근거로 삼았던 항목(anchor 문법, weight_formula·guard_gate, sync.py·ask.py 동작, source/generated 분리, schema_version)은 **본 계약에서 제외**한다.
> 아래에 남는 것은 **이슈 #94 본문이 직접 지정한 매핑**과, **리포에 실재하는 코드**(`backend/src/main/kotlin/com/ontostudio/provenance/ProvenanceVocab.kt`)로 검증되는 매핑뿐이다.

### 6.1 핵심 매핑

| 계약 요소 | 레이어 계약 대응 | 편입 내용 | 출처 |
|---|---|---|---|
| `evidence[].uuid` (근거의 원본 좌표) | **L1 `sourceLocation` + `sourceRevision`** | 근거는 **원본에서 재확인 가능한 좌표**를 가져야 한다. L1 Observation은 "값 + 좌표"를 함께 보관한다. 인용만 있고 좌표가 없으면 Observation이 아니다. | 이슈 #94 지정 |
| `supersedes` / `status` | **L3 `supersedes` · `status` · `validFrom`/`validTo`** | 정정은 **덮어쓰기가 아니라 링크**다. 이전 레코드는 남고 대체 관계로 연결되며 active와 이력이 분리 조회된다 → L3의 충돌 보존(P4)·시간 필드 계약. 사람이 확정한 것과 추정한 것은 status로 구분한다(`HUMAN_CONFIRMED` vs `INFERRED`). | 이슈 #94 지정 |
| provenance `Provenance` (`EXTRACTED`/`INFERRED`/`AMBIGUOUS`) | **L2 `status`** | 확실성 등급을 값으로 남긴다. `AMBIGUOUS`는 실패가 아니라 **정직한 출력**(P3). 휴리스틱·AI로 만든 링크는 `EXTRACTED`가 될 수 없다(P2). | `ProvenanceVocab.kt` (실측) |
| provenance `RelationKind` (`FK`/`NAMEPATTERN`/`AI`/`MANUAL`) | **L2 `method`** | 링크를 만든 **방법**을 등급과 분리해 기록한다. `FK`=명시 키, `NAMEPATTERN`=휴리스틱, `AI`=모델 판단, `MANUAL`=사람. | `ProvenanceVocab.kt` (실측) |

### 6.2 편입 결론

- 위 4개 매핑은 **L1~L3 계약 요소로 확정**한다. E16-0에서 통일된 `kind`/`provenance`/`confidence` 어휘가 L2 계약의 뼈대이며, 벤치는 이 어휘를 그대로 측정한다.
- 계약 요소를 새로 추가할 때는 **리포에 실재하는 코드 또는 이슈 본문**을 출처로 요구한다. 리포 밖 로컬 산출물은 계약 근거로 인정하지 않는다(이번 폐기 건의 교훈 — P1 "무근거 금지"의 자기적용).

---

## 7. 계약 개정 절차

이 문서의 고정 요소를 바꾸는 것은 **baseline을 바꾸는 것**이다.

1. 개정 사유와 영향 범위(무효화되는 이전 실행 목록)를 명시한 PR을 올린다.
2. **리뷰어 @xivicWon 승인** 없이는 개정되지 않는다.
3. 개정 시 문서 상단에 `개정 이력`을 추가하고 revision/수치 변경은 **이전 값과 함께** 남긴다(덮어쓰기 금지 — P4의 자기적용).
4. source revision 또는 Gold Set이 바뀌면, 그 이전에 나온 Run Quality Report는 **비교 기준선에서 제외**하고 보고서에 명시한다.

---

## 8. I1 완료 기준 체크

- [x] 대상 프로젝트 1개(2트랙) + 리뷰어 확정 → §1.1, §1.2
- [x] source revision 고정 (`3c27259`) · fixture hash는 #99로 위임 명시 → §1.3
- [x] 레이어 의존 순서(L0→L1→L2→L3)와 "통과=다음 착수" 게이트 규칙 확정 → §2
- [x] 승격/중단 규칙 확정 (무근거 Claim 금지 / INFERRED↛EXTRACTED / 결정성 실패 시 상위 중단 / 하위 실패의 상위 confidence 제한) → §3
- [x] 기능 인벤토리 초안: E1~E17 → 벤치 레이어 매핑 (판정은 #101) → §5
- [x] 참고자료 편입: 이슈 지정 매핑(evidence.uuid↔L1 `sourceLocation`, supersedes/status↔L3 `supersedes`·`validFrom`/`validTo`, provenance↔L2 `status`) 확정 → §6
      *(단, 로컬 `aira/` POC 데이터는 임의 분석 산출물로 폐기 — 그 실물을 근거로 한 항목은 계약에서 제외. §6 폐기 기록 참조)*
- [x] 고정 요소가 전부 문서로 남음 → 본 문서
- [x] 범위를 L0~L3로 축소, L4(#92)/L5(#93)는 M2/M3 상위 트래킹으로 이관 명시 → §2.1

**다음 착수: #99 (I2 Gold Set & 실패 fixture) — 소유자 @xivicWon.**
