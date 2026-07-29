# M0 / I3 — Run Quality Report 템플릿 계약

> 작성일: 2026-07-29
> 이슈: #100 `[M0][기준] I3 Run Quality Report 템플릿 커밋` · 마일스톤: **M0 Evidence Quality Foundation**
> 선행: I1 기준선 계약(#94 → `2026-07-29-m0-i1-baseline-contract.md`) · EVL answer-shape 계약(#103 → `2026-07-29-evl-answer-shape-contract.md`)
> 후속: #88~#91(L0~L3)·#101(I4)이 **이 템플릿으로 보고**한다
> 리뷰어/승인권자: **@xivicWon**
> 상태: **확정** — 본 문서 머지 시점부터 v0 계약이 발효된다.

모든 레이어가 **같은 형식**으로 결과를 남기게 하는 계약이다.
형식이 다르면 레이어 간 비교도, 기준선 대비 비교도 성립하지 않는다.
**이 템플릿을 따르지 않은 실행 결과는 I1 G5(증거 필수)에 의해 판정 근거로 쓸 수 없다.**

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

| | 내용 | 소유 |
|---|---|---|
| ✅ 확정 | 보고서 필드·타입·통제어휘 | 본 문서 §2·§3 + `schemas/run-quality-report.v0.schema.json` |
| ✅ 확정 | 구조 불변식 R1~R20과 강제 위치(schema / validator) | §4 |
| ✅ 확정 | 빈 템플릿 + 작성 예시 fixture | `schemas/rqr-examples/` |
| ✅ 확정 | 판정 3값 + 제한 등급·사유·닫힌 경로 기록 형식 | §3.7 (I1 §2.2 요구사항 충족) |
| ✅ 확정 | EVL 지표(칼리브레이션·충돌 precision/recall·커버리지 클래스) 편입 형식 | §3.5 (#104 요구사항 충족) |
| ⛔ 미확정 | fixture hash 의 실제 값 | **#99 (I2)** |
| ⛔ 미확정 | precision/recall 등 **목표 수치의 확정값** | #88·#89 1차 측정 후 비준 (I1 §4.2) |
| ⛔ 미확정 | 기능별 Core/Lab/Parked/Retire **판정 내용** | **#101 (I4)** — 본 문서는 기록 **자리**까지만 |
| ⛔ 미확정 | calibration 곡선 산출 알고리즘·ECE 계산식 | **EVL C1** — 본 문서는 결과를 담는 형식까지만 |

**비범위(이슈 지정):** 대시보드·시각화 도구 · 자동 수집 파이프라인.
본 계약은 **파일 형식**이다. 값을 누가 어떻게 채우는지는 각 레이어 이슈가 정한다.

---

## 1. 위치 — 이 보고서는 무엇의 출력인가

```
레이어 실행(L0~L3, #88~#91)  ──►  Run Quality Report 1건 (이 계약)
                                      │
                        ┌─────────────┼──────────────┐
                        ▼             ▼              ▼
                  다음 레이어 착수   I4 기능 판정   다음 실행의 기준선
                  판정(I1 G1·G4)    (#101, G5)     (§3.8)
```

- **실행 1회 = 보고서 1건.** 실행을 합쳐 하나로 요약하지 않는다 — 합산은 실패를 가린다(I1 §4.2).
- **트랙(db/code)은 분리 산출**한다. 한 실행이 두 트랙을 돌면 보고서도 2건이다.
- answer-shape(EVL)는 **질문 하나의 응답 형식**이고, 이 보고서는 **실행 하나의 품질 형식**이다. 층이 다르며 서로를 대체하지 않는다.

---

## 2. Run Quality Report v0

정규 정의는 [`schemas/run-quality-report.v0.schema.json`](schemas/run-quality-report.v0.schema.json)이며, 아래 표와 스키마가 다르면 **스키마가 우선**한다.

| 필드 | 필수 | 계약 |
|---|---|---|
| `schemaVersion` | ✅ | `"run-quality-report/v0"` 고정. 버전이 다른 보고서의 수치는 직접 비교하지 않는다(§7) |
| `run` | ✅ | 실행 식별 — runId·projectId·layer·track·reportKind·sourceRevision·fixtureHash·시각·실행자 |
| `versions` | ✅ | collector / extractor / model / prompt — 각각 `{status, value}` |
| `counts` | ✅ | 입력·출력·실패·제외 건수 |
| `exclusions` | ✅ | 제외 **사유별** 집계 + 원본 좌표. 빈 배열도 명시 |
| `failures` | ✅ | 실패 사례 + **재현 fixture** 링크. 빈 배열도 명시 |
| `metrics` | ✅ | precision·recall·**scopeCoverage**·determinism·provenanceCompleteness |
| `evl` | ✅ | calibration · conflict precision/recall · 소스 클래스 체크리스트(`coverageClasses`) |
| `gates` | ✅ | I1 §4.1 무조건 게이트의 실행별 결과 |
| `baseline` | ✅ | 이전 기준선 대비 변화 + 비교 가능 여부 |
| `verdict` | ✅ | `PASS` / `PASS_RESTRICTED` / `BLOCKED` + 중단 규칙 + 제한 사유·닫힌 경로 |
| `featureJudgments` | ✅ | 기능별 Core/Lab/Parked/Retire 판정과 근거. 빈 배열 허용(판정은 #101이 채운다) |
| `warnings` | ✅ | 보고서 자체의 경고(통제어휘). 빈 배열도 명시 |
| `notes` | — | 선택. 위 필드로 표현되지 않는 맥락. **지표·판정 근거를 여기에 숨기지 않는다** |

**빈 배열을 명시하는 이유**는 EVL 계약 §2.1과 같다: 필드를 생략하면 "없음"과 "안 봄"이 구분되지 않는다.

---

## 3. 필드별 계약

### 3.1 `run` — 실행 식별

| 필드 | 계약 |
|---|---|
| `runId` | `run-` 접두. 다른 보고서가 이 실행을 인용하는 키다 |
| `layer` | `L0`\|`L1`\|`L2`\|`L3`. M0 범위는 4개뿐이다(I1 §2.1) — L4/L5는 어휘에 없다 |
| `track` | `db`\|`code` (I1 §1.1) |
| `reportKind` | `BASELINE`(실측) \| `EXAMPLE`(작성 예시·리허설). **EXAMPLE 은 baseline 이 될 수 없다**(R12) — 예시 수치가 기준선으로 흘러드는 경로를 형식으로 막는다 |
| `sourceRevision` | I1 §1.3이 고정한 revision. 값이 다르면 비교 기준선이 다르다(I1 §7.4) |
| `fixtureHash` | `sha256:<64hex>` 또는 문자열 **`UNPINNED`**. #99 이전 실행은 UNPINNED 이며 baseline 으로 인정하지 않는다(I1 §1.3) |
| `startedAt`·`completedAt` | RFC 3339 **축소 프로파일**(EVL §2.7과 동일 — `T`·`Z` 대문자만). 같은 시각의 두 표기는 해시·비교를 실행마다 갈리게 해 결정성을 해친다 |
| `executedBy` | 실행 주체. **판정 승인권자(@xivicWon)와 다를 수 있다** — 에이전트 실행도 여기 기록된다 |

### 3.2 `versions` — 무엇으로 만든 결과인가

collector·extractor·model·prompt **4개 전부 필수 키**이며 각각 `{status, value}` 다.

| status | 뜻 | value | 경고 |
|---|---|---|---|
| `PINNED` | 버전을 안다 | 문자열 | — |
| `UNPINNED` | **이 레이어가 쓰는데 버전을 모른다** | `null` | `VERSION_UNPINNED` 필수(R11) |
| `NOT_APPLICABLE` | **이 레이어가 그 요소를 쓰지 않는다** | `null` | 경고 대상 아님 |

`"unknown"`·`""` 로 채우는 것은 금지다 — 문자열이 들어가는 순간 "버전을 안다"는 뜻이 되어 재현 실패의 원인을 잃는다.

**`UNPINNED` 와 `NOT_APPLICABLE` 을 합치지 않는 이유:** DDL 파서 실행에 모델이 없는 것(정상)과, AI 추정 실행인데 모델 버전을 못 알아낸 것(재현 위험)은 전혀 다른 상태다. 하나로 뭉치면 `VERSION_UNPINNED` 경고가 상시 발생해 신호로서 죽고, "이 실행을 재현할 수 있는가"의 답을 잃는다. R11은 **UNPINNED 에만** 양방향으로 걸린다.

### 3.3 `counts` · `exclusions` · `failures` — 몇 건을 어떻게 했는가

- `input = output + failed + excluded` 가 **성립해야 한다**(R2). 성립하지 않는 보고서는 어딘가를 세지 않은 것이다.
- `exclusions[].count` 의 합 = `counts.excluded`(R3). **사유별로 한 항목**이며 같은 사유를 여러 항목으로 흩지 않는다.
- 제외에는 **제외된 대상 전부의 원본 좌표**를 남긴다 — `count` 와 `examples` 의 길이가 같아야 한다(R3). 사유만 적고 대상을 안 적으면 재확인이 불가능하고, 일부만 적으면 나머지는 "몇 건 있었다"로만 남아 다음 실행에서 대조할 수 없다. 제외가 많아 좌표를 다 적기 어렵다면 **사유를 더 잘게 나눈다**(그것이 실제 사유 구분이다).
  → 이것이 I1 §4.1 "L0 오류 가시성 100%"가 보고서에서 드러나는 자리다. 뷰 스킵을 조용히 무시하는 경로가 여기서 막힌다(I1 §1.1).
- **`counts.failed` = `failures` 사례 수**(R4). 집계만 남기고 사례를 일부만 적으면 나머지 실패는 재현도 회귀 검증도 되지 않는다 — 제외 좌표(R3)와 같은 원칙이다. 실패가 많아 전부 적기 어렵다면 그것은 **보고를 줄일 이유가 아니라 그 레이어를 통과시키지 않을 이유**다. 실패마다 사례(`summary`·`link`)와 **재현 fixture 경로**가 필수다.
- **`failures[].link` 는 그 실패가 기록된 산출물·로그의 URI 다**(`log://` · `artifact://` · `run://` · `http(s)://`). **소스 파일 경로가 아니다** — 코드 위치는 '어디서 났는가' 일 뿐 '그 실행에서 실제로 일어났다' 는 증거가 아니고, 재실행 없이 대조할 수 있는 것은 그 실행이 남긴 기록뿐이다. 코드 위치가 필요하면 재현 fixture 안에 적는다.
- **경로 문자열만으로는 부족하다.** 보고서가 가리키는 재현 fixture는 **리포에 실재해야 하고**, `schemas/rqr-examples/manifest.json` 에 등록돼야 하며, 최소한 `{fixtureId, reproduces{runId, failureId}, layer, input, expected}` 를 갖춰야 한다(§4.1). **`expected` 는 객체이며 `expected.rule`(어느 계약 규칙의 위반인가)이 필수다** — 문자열이나 배열은 확인기가 거부한다. 산문으로 적힌 기대값은 다음 실행에서 기계적으로 대조할 수 없다. 무엇을 재현하는지·무엇이 기대값인지 적히지 않은 파일은 다음 실행에서 회귀 판정의 기준이 되지 못한다. 예: [`fixtures/l3-claim-no-evidence.json`](schemas/rqr-examples/fixtures/l3-claim-no-evidence.json).

### 3.4 `metrics` — 지표

다섯 지표 모두 `{status, value, note}` 구조다.

| status | 뜻 |
|---|---|
| `MEASURED` | 값이 있다. `value` 는 숫자 |
| `NOT_MEASURED` | **측정하지 못했다.** `value` 는 `null` + `METRIC_UNMEASURED` 경고(R10) |
| `NOT_APPLICABLE` | 이 레이어에 해당 없음. `value` 는 `null`, `note` 에 사유 |

**미측정을 0으로 채우는 것은 금지**다 — 0은 "측정했고 0"이라는 뜻이다(EVL §3.2의 자기적용).
#### `scopeCoverage` — 이름과 산식을 함께 고정한다

**`metrics.scopeCoverage` = `counts.output / counts.input`**(R20, 소수 4자리 반올림 허용).
분모를 보고서마다 다르게 잡으면(입력 전체 / Gold 대상 / 성공 건수) 같은 이름의 값이 서로 다른 것을 뜻하게 되어 레이어 간·기준선 대비 비교가 성립하지 않는다. 실패·제외는 **분자에서 빠지고 분모에는 남는다** — 그래야 '못 만든 것' 이 비율에 드러난다.

**`counts.input = 0`(스코프에 대상이 없는 실행)이면 `status = NOT_APPLICABLE`·`value = null` 이다**(R20). 빈 실행은 금지가 아니다 — 레이어의 in-scope 대상이 0건일 수 있다. 다만 `0/0` 은 정의되지 않으므로 `0.0`(아무것도 못 했다)이나 `1.0`(다 했다)으로 적어서는 안 된다. 두 뜻이 같은 자리에 오면 그 값은 더 이상 지표가 아니다.

> **`scopeCoverage` 와 `evl.coverageClasses` 는 다른 개념이다.** 이름이 비슷하다는 이유로 섞지 않는다.
>
> | | `metrics.scopeCoverage` | `evl.coverageClasses` |
> |---|---|---|
> | 무엇을 재나 | **스코프의 몇 %를 처리했나** | **어떤 소스 클래스를 봤나** |
> | 형태 | 0.0~1.0 비율 | 5클래스 × 3값(`present`/`absent`/`not_collected`) 체크리스트 |
> | 단위 | 이 레이어의 입력 대상 | code·issue·adr·test·runtime |
> | 출처 | I1 §4 지표 | EVL 계약 §2.5 |
> | 강제 | R20(산식·빈 실행) | R15(5클래스 전부·경고 일치) |
>
> v0에서 지표 키를 `coverage` 가 아니라 **`scopeCoverage`** 로 둔 이유가 이것이다 — 같은 단어가 두 층에서 다른 것을 가리키면 보고서를 읽는 쪽이 반드시 섞는다(이 계약 자체가 리뷰에서 두 번 섞였다).
`determinism` 이 1.0 미만이면 H1이 발동하며 판정은 BLOCKED 다(R8·R6 — I1 §3.2).

### 3.5 `evl` — EVL(#104) 편입 지표

| 항목 | 계약 |
|---|---|
| `confidenceCalibration` | `{status, population, ece, bins[], sampleCount, missingRawCount}`. `population` 은 `presented`(응답에 실린 증거) \| `candidates`(번들 로그의 후보 전체) — **모집단을 밝히지 않은 calibration 수치는 인용하지 않는다**(EVL §3.3). `missingRawCount > 0` 이면 `status=MEASURED` 일 수 없고 `CALIBRATION_RAW_MISSING` 경고가 필요하다(R13) |
| `conflictDetection` | `{precision, recall, goldSetId}`. `MEASURED` 이려면 `goldSetId` 가 있어야 한다(R14) — gold 충돌셋(#99) 없이 나온 수치는 대조 대상이 없다 |
| `coverageClasses` | **소스 클래스 체크리스트 — 비율이 아니다**(§3.4의 `scopeCoverage` 와 다른 개념). 5클래스(`code`·`issue`·`adr`·`test`·`runtime`)를 **정확히 한 번씩**. `{state, deterministic, warned}` — `state != present` ⟺ `warned = true`(R15, EVL A11의 자기적용) |

곡선의 **산출 알고리즘**은 EVL C1의 몫이고, 본 계약은 그 결과가 들어갈 **자리와 인용 가능 조건**까지다.

### 3.6 `gates` · `warnings`

- `gates[]` 는 I1 §4.1 무조건 게이트의 실행별 결과다. **잠정 수치(I1 §4.2)는 게이트가 아니므로 여기에 적지 않는다.**
- `status=FAIL` 이 하나라도 있으면 `GATE_FAILED` 경고가 필요하고 **판정 PASS 가 불가능**하다(R9 — I1 G4).
- `status=NOT_MEASURED` 인 게이트도 **`METRIC_UNMEASURED` 경고를 낸다**(R10, `trigger: gates.<gateId>`). 지표의 미측정과 같은 원칙이다 — 측정하지 않은 게이트가 조용히 지나가면 보고서를 읽는 쪽에서 **통과한 게이트와 구분되지 않는다.**
- 경고 `code` 는 **통제어휘 7종**이며 `trigger` 로 대상을 못박는다. 자유 문장은 "경고했는가"를 측정할 수 없다(EVL §2.6과 같은 원칙).

| code | 발동 조건 | `trigger` |
|---|---|---|
| `UNPINNED_FIXTURE` | `fixtureHash = UNPINNED` | `run.fixtureHash` |
| `VERSION_UNPINNED` | 버전 status 가 `UNPINNED` — 필드마다 한 건. `NOT_APPLICABLE` 은 대상이 아니다 | `versions.<name>` |
| `METRIC_UNMEASURED` | 지표 또는 **게이트**가 `NOT_MEASURED` — 대상마다 한 건 | `metrics.<name>` \| `evl.confidenceCalibration` \| `evl.conflictDetection.<precision\|recall>` \| `gates.<gateId>` |
| `CALIBRATION_RAW_MISSING` | `missingRawCount > 0` | `evl.confidenceCalibration` |
| `GATE_FAILED` | 게이트 `FAIL` — 게이트마다 한 건 | `gates.<gateId>` |
| `BASELINE_NOT_COMPARABLE` | `baseline.comparable = false` | `baseline` |
| `PATH_RESTRICTED` | 판정이 `PASS_RESTRICTED` | `verdict` |

형식은 스키마가, **대상 실재**는 검증기가 본다(R18).

### 3.7 `verdict` — 판정 (I1 §2.2 요구사항)

**3값뿐이다:** `PASS` · `PASS_RESTRICTED` · `BLOCKED`. "대체로 통과"는 없다(I1 G4).

| 값 | 필요 조건 |
|---|---|
| `PASS` | `haltRules` 와 `restrictions` 가 **둘 다 비어 있고**, FAIL 게이트가 없다 |
| `PASS_RESTRICTED` | `restrictions` 에 H4 항목 + `PATH_RESTRICTED` 경고(R7). 각 항목은 **`reason` 과 `closedPaths`(≥1)** 를 갖는다 |
| `BLOCKED` | `haltRules` 가 비어있지 않다(R6). 어휘는 `H1`·`H2`·`H3`·`H5` — **H4는 RESTRICT 등급이라 여기 없다** |

`closedPaths` 는 "무엇이 닫혔는가"다. 제한 사실만 적고 닫힌 경로를 안 적으면 **측정되지 않은 경로를 식별할 수 없고**, 그 상태의 결과로 "자동 승격이 동작한다"는 주장이 새어나간다(I1 §3.2).

### 3.8 `baseline` — 이전 기준선 대비 변화

`previous` 는 runId 하나가 아니라 **비교 대상의 신원 전체**다: `{runId, projectId, layer, track, sourceRevision, fixtureHash, schemaVersion}`.
runId 만 적으면 "같은 것을 잰 실행인가"를 보고서만으로 판정할 수 없고, 판정할 수 없는 비교는 비교가 아니다.

**`comparable=true` 의 조건(R17) — 전부 충족해야 한다:**

1. `previous` 가 있고, `projectId`·`layer`·`track`·`sourceRevision`·`schemaVersion` 이 현재 실행과 **같다**
2. 양쪽 `fixtureHash` 가 **고정(pinned)** 돼 있고 서로 **같다** — 미고정 실행끼리는 같은 입력이었음을 보장할 수 없다(I1 §1.3)
3. `deltas` 가 1건 이상 있고, `BASELINE_NOT_COMPARABLE` 경고가 없다

**`comparable=false`** → `deltas` 는 **비어 있고**, `reason` 이 필수이며, `BASELINE_NOT_COMPARABLE` 경고를 낸다. **비교 불가를 "변화 없음"으로 표기하지 않는다.**

**`eligibleAsBaseline` = (`fixtureHash` 고정) ∧ (`reportKind = BASELINE`) ∧ (적용 대상 버전이 전부 `PINNED`)**(R12).
세 번째 조건이 있는 이유: fixture 만 고정하고 모델·추출기 버전을 모르면 **같은 입력을 재현할 수 없고**, 재현할 수 없는 실행은 기준선이 아니다. `NOT_APPLICABLE`(그 레이어가 쓰지 않는 요소)은 조건에서 제외된다 — 안 쓰는 것의 버전은 재현에 영향이 없다.
이 값이 `false` 인 보고서는 **다음 실행의 비교 대상이 되지 않는다**(I1 §1.3·§7.4).

> **현재 상태:** #99(I2)가 fixture hash 를 고정하기 전이므로 **모든 실행이 `fixtureHash: UNPINNED`** 이고, 따라서 `comparable=true` 인 정상 예시는 아직 만들 수 없다(가공 해시로 만들면 그 자체가 이 계약이 막으려는 것이다). 커밋된 정상 예시 2건은 모두 비교 불가 상태이며, `comparable=true` 경로는 **음성 픽스처 3건**(deltas 누락 · revision 불일치 · fixture 미고정)으로 검사한다. 정상 예시는 #99 이후 실 해시로 추가한다.

### 3.9 `featureJudgments` — Core / Lab / Parked / Retire (I4 입력)

- **측정하지 않은 기능(`measured=false`)을 `Core` 로 판정하는 것은 금지**된다(R16 — I1 §5.3). `Parked`·`Retire` 는 가능하다.
- 모든 판정은 `rationale` 과 `evidenceRefs`(≥1)를 갖는다. 근거는 **이 실행의 `runId` 또는 `report:<runId>`** 여야 한다 — 근거 링크 없는 판정은 무효다(I1 G5).
- 판정 **내용**은 #101(I4)의 몫이다. 레이어 실행 보고서는 이 배열을 비워둘 수 있다.

---

## 4. 구조 불변식 (R1~R20)

**R1은 메타 규칙이다** — 스키마가 거는 제약 전부가 R1이며, 그중 다른 R규칙이 지목하지 않는 위반(`additionalProperties`, 시각의 달력 유효성, 시각 순서 등)이 R1로 귀속된다.

**강제 위치**가 두 종류다. `schema` 는 JSON Schema 만으로 걸러지고, `validator` 는 스키마를 통과하지만 교차 필드 검사에서 걸러진다.
픽스처는 [`schemas/rqr-examples/manifest.json`](schemas/rqr-examples/manifest.json)에 규칙 ID로 연결돼 있다.

| ID | 불변식 | 강제 | 위반 시 |
|---|---|---|---|
| **R1** | 스키마를 통과하고, 시각이 **실재하는 날짜**이며 `completedAt ≥ startedAt` | schema + validator | 형식 위반 — 비교 대상 제외 |
| **R2** | `input = output + failed + excluded` | validator | 세지 않은 건이 있다 |
| **R3** | `exclusions` 합 = `counts.excluded`, **사유별 `count` = 좌표 수**, 사유 중복 없음 | validator | **조용한 스킵** · 일부만 좌표를 남겨 나머지가 대조 불가 |
| **R4** | `counts.failed` = `failures` 사례 수 (정확히 일치) | validator | **일부 실패만 기록** · 유령 실패 |
| **R5** | `verdict.value` 는 3값 통제어휘 | schema | 판정 집계 불가 |
| **R6** | `BLOCKED` ⟺ `haltRules` 비어있지 않음 (양방향) | validator | 중단 근거 없음 · 근거만 있고 판정이 다름 |
| **R7** | `PASS_RESTRICTED` ⟺ `restrictions` + `PATH_RESTRICTED` 경고 (양방향) | validator | **제한 은폐**(I1 §3.2) · 허위 제한 |
| **R8** | `determinism < 1.0` → `haltRules` 에 `H1` (역방향 포함) | validator | **결정성 실패를 통과로 처리** |
| **R9** | 게이트 `FAIL` ⟺ `GATE_FAILED` 경고, 그리고 `FAIL` 이 있으면 판정 ≠ `PASS` | validator | 게이트 무력화(I1 G4) |
| **R10** | 지표·**게이트** `NOT_MEASURED` ⟺ `METRIC_UNMEASURED` 경고 (양방향) | validator | 미측정을 0과 섞음 · 미측정 게이트가 통과처럼 읽힘 |
| **R11** | 버전 `UNPINNED` ⟺ `VERSION_UNPINNED` 경고 (양방향). `NOT_APPLICABLE` 은 경고 대상 아님 | validator | 버전 추적 거짓 · '안 씀' 과 '모름' 을 섞음 |
| **R12** | `fixtureHash=UNPINNED` ⟺ `UNPINNED_FIXTURE` 경고 · `eligibleAsBaseline` = (fixture 고정 ∧ `BASELINE` ∧ **적용 대상 버전 전부 PINNED**) | validator | **재현 불가한 실행이 기준선이 됨**(I1 §1.3) |
| **R13** | calibration `MEASURED` → 모집단·ece·bins 존재 + bins 표본합 일치 · `missingRawCount>0` → `MEASURED` 불가 + 경고 (양방향) | validator | **미보정 수치 인용**(EVL §3.3) |
| **R14** | conflict precision/recall `MEASURED` → `goldSetId` 존재 | validator | 대조 대상 없는 성능 주장 |
| **R15** | `evl.coverageClasses` 의 소스 클래스 5종이 정확히 한 번씩 · `state≠present` ⟺ `warned` | validator | 안 본 클래스가 사라짐 |
| **R16** | `measured=false` → `Core` 판정 금지 · `evidenceRefs` 가 실행 보고서를 가리킴 | validator | **측정 안 한 기능의 Core 판정**(I1 §5.3·G5) |
| **R17** | `comparable=true` → `previous` 신원 일치(project·layer·track·revision·schemaVersion) + **양쪽 fixture 고정·동일** + `deltas` 존재 / `false` → `deltas` 비어있고 `reason`+경고 | validator | 다른 것을 잰 실행끼리 비교 · 비교 불가를 "변화 없음"으로 위장 |
| **R18** | 모든 `warnings[].trigger` 가 그 `code` 가 가리키도록 정해진 종류의 대상을 **실제로** 가리킴 | validator | 경고가 아무것도 가리키지 않음 |
| **R19** | `failures[].id`·`gates[].id`·`featureJudgments[].featureId` 가 각각 유일 | validator | 경고 하나가 여러 대상을 충족한 것처럼 보임 |
| **R20** | `metrics.scopeCoverage` = `counts.output / counts.input` (4자리 반올림 허용) · `counts.input=0` → `NOT_APPLICABLE` | validator | 분모가 보고서마다 달라져 **비교 불가** · 빈 실행의 `0/0` 을 0.0/1.0 으로 위장 |

### 4.1 검사 재현

```bash
pip install jsonschema
cd docs/superpowers/specs/schemas && python3 validate_rqr.py
# 34 cases, 0 mismatches   (= manifest.json 의 caseCount)
```

확인기는 네 가지를 본다: ① 정상/위반 픽스처의 승인 여부, ② **위반 픽스처가 선언된 규칙으로·선언된 계층에서** 걸리는지(라벨 오류로 커버리지가 과대 보고되는 것을 막는다), ③ **빈 템플릿이 스키마의 모든 필수 경로를 갖고 값이 전부 placeholder 인지**, ④ **정상 픽스처가 가리키는 재현 fixture 가 실재하고 manifest 에 등록됐으며 최소 형식을 갖췄는지**.
③이 있는 이유: 스키마에 필드가 추가됐는데 템플릿에 자리가 없으면 작성자는 그 필드의 존재를 영원히 모른다.
④가 있는 이유: 경로 문자열은 파일이 없어도 그럴듯해 보인다 — 실재 검사가 없으면 '재현 fixture 기록' 은 형식만 남는다.

**R1~R20 전부 음성 픽스처를 가져야** 스위트가 통과한다. 규칙만 문서에 적고 검사가 없는 상태를 막는 장치다.

케이스 총계는 `manifest.json` 의 `caseCount` 에, 규칙 범위는 `ruleRange` 에 못박혀 있고 확인기가 실제 값과 대조한다 — 픽스처나 규칙이 늘었는데 문서·manifest 의 수가 그대로면 그 자체로 실패한다.

---

## 5. 사용 규칙

1. **각 레이어 실행(#88~#91)은 종료 시 이 형식의 보고서 1건을 커밋한다.** 보고서 없는 실행은 판정 근거가 아니다(I1 G5).
2. **후행 레이어 착수 판단은 보고서의 `verdict` 로 한다**(I1 G1). `BLOCKED` 면 착수 불가, `PASS_RESTRICTED` 면 `closedPaths` 를 지키며 착수한다.
3. **#101(I4)은 각 기능 행에 보고서 링크를 붙여 판정한다.** `featureJudgments` 는 그 판정이 들어갈 자리이며, `measured=false` 인 기능의 Core 판정은 형식이 거부한다.
4. **수치 인용 규칙:** `reportKind=EXAMPLE` 인 보고서의 값, `MEASURED` 가 아닌 지표, `missingRawCount>0` 인 calibration 값은 **어떤 문서·PR·발표에서도 인용하지 않는다.**
5. 보고서를 사후 수정할 때는 새 `runId` 로 **새 보고서를 남긴다.** 기존 보고서를 덮어쓰지 않는다(I1 P4의 자기적용).

---

## 6. 목표 수치 정책

I1 §4를 그대로 따른다. 본 계약은 **수치를 정하지 않는다** — 담는 형식만 정한다.

- **무조건 게이트**(I1 §4.1)는 `gates[]` 에 기록되고 R9가 판정과 연결한다.
- **잠정 수치**(I1 §4.2)는 게이트가 아니므로 `gates[]` 에 넣지 않는다. `metrics` 에 값으로만 남고, 비준 전에는 달성 기준으로 인용하지 않는다.
- EVL 잠정 지표(calibration·conflict 임계값)도 동일하다(EVL §7.2).

---

## 7. 계약 개정 절차

I1 §7·EVL §10과 동일하며, 추가로:

1. 개정 사유와 영향 범위(비교 기준선에서 빠지는 이전 보고서 목록)를 명시한 PR을 올린다.
2. **@xivicWon 승인** 없이 개정되지 않는다.
3. **기존 보고서의 유효성이나 의미를 바꾸는 모든 변경**은 `schemaVersion` 을 올린다(`run-quality-report/v1`) — 필드 추가/삭제뿐 아니라 **통제어휘 변경·제약 강화/완화·R규칙 추가·의미 재정의**가 포함된다. 버전이 다른 보고서의 수치는 직접 비교하지 않는다.
4. 통제어휘(`layer`·`track`·`reportKind`·`warnings[].code`·`verdict.value`·`haltRules`)는 **런타임에 자유 문자열로 확장하지 않는다.** 어휘가 열리면 지표 분리 집계가 무너진다.
5. 스키마를 고치면 **빈 템플릿도 같은 PR 에서 고친다.** 확인기가 이 동기화를 강제한다(§4.1 ③).

---

## 8. #100 완료 기준 체크

- [x] 리포에 템플릿 fixture 커밋 — 빈 템플릿 + 작성 예시 → `schemas/rqr-examples/template.blank.json`, `valid.l1-db-example.json`(+제한 판정 예시 `valid.l3-restricted-example.json`)
- [x] 실행 식별: runId · projectId · source revision · fixture hash → §3.1
- [x] 버전: collector / extractor / model / prompt → §3.2
- [x] 레이어별 입력·출력·실패·제외 건수 → §3.3
- [x] 지표: precision · recall · coverage(→ `scopeCoverage`, 산식 고정) · determinism · provenance completeness → §3.4
- [x] 실패 사례 링크 + 재현 fixture → §3.3 (`failures[].link`·`failures[].fixture`, R4) + 실재하는 재현 fixture `schemas/rqr-examples/fixtures/l3-claim-no-evidence.json`
- [x] 이전 기준선 대비 변화 → §3.8 (R12·R17)
- [x] 기능별 Core/Lab/Parked/Retire 판정과 근거 필드 → §3.9 (R16)
- [x] EVL 편입: confidence calibration · conflict precision/recall · coverage 클래스 체크리스트 → §3.5 (R13·R14·R15)
- [x] 판정 3값 + 제한 사유·닫힌 경로 필드 유지 → §3.7 (R5·R6·R7)
- [x] 기계 판독 스키마 커밋 → `schemas/run-quality-report.v0.schema.json`
- [x] 구조 불변식 R1~R20 + 규칙별 음성 픽스처 + 확인기 커밋 (34 cases, 0 mismatches — `manifest.caseCount`·`manifest.ruleRange` 와 일치) → §4, `schemas/validate_rqr.py`

**다음 착수: #99(I2) Gold Set & 실패 fixture — 그 뒤 G2가 열려 L0(#88)이 착수 가능해진다(I1 §2.1).**
