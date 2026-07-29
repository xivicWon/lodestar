# EVL — Answer-Shape v0 스키마 & 검증 계약

> 작성일: 2026-07-29
> 이슈: #103 `[EVL] answer-shape 스키마 + 검증 계약` · 에픽: **#104 Evidence Validation Layer** · 마일스톤: **Evidence Validation Layer**
> 상태: **확정** — 본 문서 머지 시점부터 answer-shape v0 계약이 발효된다.
> 리뷰어/승인권자: **@xivicWon**
> 기계 판독 스키마: [`schemas/answer-shape.v0.schema.json`](schemas/answer-shape.v0.schema.json) · 픽스처: [`schemas/examples/manifest.json`](schemas/examples/manifest.json) · 적합성 확인기: [`schemas/validate.py`](schemas/validate.py)
> 선행 계약: [M0 / I1 기준선 계약](2026-07-29-m0-i1-baseline-contract.md) (이하 **I1**)

Evidence Validation Layer가 AI 에이전트에게 돌려주는 **형식화된 응답**의 모양과, 각 필드를 **무엇으로 검증하는지**를 못박는다.
이 문서에 없는 필드로 응답하거나, 여기 정의된 불변식을 어긴 응답은 **형식 위반**이며 정확도 측정 대상이 아니다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

| | 내용 | 소유 |
|---|---|---|
| ✅ 확정 | answer-shape v0 필드 구조·타입·통제어휘 | 본 문서 §2 + JSON Schema |
| ✅ 확정 | 구조 불변식 A1~A18 (스키마 강제 / 검증기 강제 구분) | 본 문서 §4 |
| ✅ 확정 | 필드별 **검증 방법**과 "실패 = 무엇인가"의 정의 | 본 문서 §5 |
| ✅ 확정 | confidence를 **함수**로 취급한다는 계약(신호 노출 의무) | 본 문서 §3 |
| ✅ 확정 | abstention 발동 조건의 **형식**(경고 코드 체계) | 본 문서 §6 |
| ✅ 확정 | 어떤 지표가 무조건 게이트이고 어떤 것이 잠정인지 | 본 문서 §7 |
| ✅ 확정 | #99(I2) Gold Set에 추가로 요구되는 케이스 종류 | 본 문서 §8 |
| ⛔ 미확정 | **confidence 함수 계수** `f(finality, freshness, authority, corroboration, contradicted)` | baseline 후 비준 (§3.3) |
| ⛔ 미확정 | calibration·conflict precision/recall의 **목표 수치** | baseline 후 비준 (§7.2) |
| ⛔ 미확정 | **제품** 검증기 구현, CI 연결, API/MCP 서빙, UI | 하위 이슈 (§9) |
| ⛔ 미확정 | abstention 임계값의 **수치** | baseline 후 비준 (§6.3) |

**비범위:** 실제 confidence 계수 확정 · UI · 검색/랭킹 알고리즘 · 프롬프트 설계.

---

## 1. 위치 — 이 층은 무엇의 출력인가

```
L0 수집(#88) → L1 사실(#89) → L2 관계(#90) → L3 지식·이력(#91) → [answer-shape] → API/MCP
```

- **입력:** L1 `Observation`, L2 `IdentityLink`(`confidence`·`status`), L3 `Claim`(`evidenceIds`·`supersedes`·`status`).
- **출력:** 본 문서의 answer-shape.
- I1 §3.3의 **confidence 상한 전파**는 이 층에서 끝나지 않고 응답에 드러나야 한다 → `audit.ceilingApplied` + 상한 사유 경고 (A15).
- I1 §6.1의 "근거는 원본에서 재확인 가능한 좌표를 가진다"는 여기서 `evidence[].ref.{sourceId, locator, revision}` **필수**로 나타난다.

**이 층의 자기적용:** 우리가 죽이려는 것이 "거짓 확신"이므로, 이 층 자체의 confidence도 보정되지 않은 채로는 게이트가 될 수 없다. 캘리브레이션 전의 `confidence_overall`은 **기록 대상이지 주장 근거가 아니다.**

---

## 2. Answer-Shape v0

정규 정의는 [`schemas/answer-shape.v0.schema.json`](schemas/answer-shape.v0.schema.json)이며, 아래 표와 스키마가 다르면 **스키마가 우선**한다.

### 2.1 최상위

| 필드 | 필수 | 타입 | 계약 |
|---|---|---|---|
| `schemaVersion` | ✅ | `"answer-shape/v0"` | 개정 전후 실행을 구분하기 위한 고정 상수. 없으면 그 응답은 어느 계약을 따르는지 불명 = 측정 불가 |
| `task` | ✅ | object | 해석된 질문 의도와 대상 |
| `evidence` | ✅ | array | **랭킹된** 증거. 배열 순서가 랭킹이다. 빈 배열 허용(→ ABSTAIN 필수) |
| `conflicts` | ✅ | array | 빈 배열도 **명시**한다. 필드를 생략하면 "충돌 없음"과 "충돌 탐지 안 함"이 구분되지 않는다 |
| `coverage` | ✅ | object | 소스 클래스별 존재/부재 |
| `confidence_overall` | ✅ | 0.0~1.0 | |
| `warnings` | ✅ | array | abstention 트리거. 빈 배열 명시 |
| `audit` | ✅ | object | 역추적 로그 |

### 2.2 `task`

| 필드 | 필수 | 값 |
|---|---|---|
| `intent` | ✅ | `LOCATE` \| `EXPLAIN` \| `IMPACT` \| `HISTORY` \| `VERIFY` |
| `target.kind` | ✅ | `TABLE` \| `COLUMN` \| `CLASS` \| `FILE` \| `METHOD` \| `RELATION` \| `CLAIM` |
| `target.ref` | ✅ | 대상 식별자 |
| `target.raw` | — | 사용자 질문 원문(감사용). target 해석의 근거가 아니다 |

> `intent` 어휘는 **v0 잠정**이다. #99(I2) Gold Set의 실제 질문 유형으로 검증한 뒤 확정한다. 목록 밖 의도가 필요하면 자유 문자열로 우겨넣지 말고 **계약 개정(§10)** 으로 추가한다. 통제어휘를 열어두면 intent별 정확도 분리 측정이 불가능해진다.

### 2.3 `evidence[]`

| 필드 | 필수 | 계약 |
|---|---|---|
| `id` | ✅ | 응답 내 유일 |
| `source` | ✅ | `code` \| `issue` \| `adr` \| `test` \| `runtime` — **`coverage`의 키 집합과 정확히 동일**(A4) |
| `ref` | ✅ | `{sourceId, locator, revision}` 필수, `contentHash`·`observedAt` 선택. 좌표 없는 인용은 증거가 아니다 |
| `confidence` | ✅ | 0.0~1.0. **소스 타입 상수가 아니라 `signals`의 함수값**(§3) |
| `signals` | ✅ | 5개 키 전부. 값은 `0.0~1.0` **또는 `null`**. 미측정을 0으로 채우는 것 금지(0은 "측정했고 낮다"는 뜻) — **미측정은 `null`** 로 두고 `SIGNAL_UNMEASURED` 경고를 `trigger: "<evidenceId>.signals.<name>"` 로 함께 낸다(A17, 양방향) |
| `reason[]` | ✅ (≥1) | `{text, basis[]}`. `basis`는 `{layer: L1\|L2\|L3, id}` **≥1개**. 근거 없는 이유 = 산문 = 계약 위반 |
| `stance` | ✅ | `supports` \| `contradicts`. **기본값 없음** — 반대 증거는 1급이므로 생산자가 명시해야 한다 |

> **reason 은 그 증거의 `ref` 로 재확인 가능해야 한다.** 다른 파일·다른 행을 인용해야 한다면 그건 **별도 evidence** 다 — 하나의 `ref` 아래 여러 좌표의 주장을 묶으면 `locator` 로 검증할 수 없는 문장이 생긴다. 이 규칙의 준수 여부는 gold 대조가 필요하므로 A규칙이 아니라 **C2(reason 근거 검증)** 에서 측정한다.

### 2.4 `conflicts[]`

| 필드 | 필수 | 계약 |
|---|---|---|
| `id` | ✅ | |
| `between[]` | ✅ (≥2) | 실재하는 `evidence[].id`만(A6) |
| `claim` | ✅ | 무엇이 충돌하는지. 예: `"JWT vs Session"` |
| `status` | ✅ | `NEEDS_CHECK`(미해결·기본) \| `COEXIST`(둘 다 참, 예: 버전별 상이) \| `RESOLVED` |
| `resolvedBy` | `RESOLVED`일 때 ✅ · **그 외에는 금지** | `{layer, id}`. 근거 없는 해소 = 덮어쓰기 = I1 **P4 위반**. 반대로 `NEEDS_CHECK`·`COEXIST`에 해소 근거가 붙어 있으면 상태와 근거가 모순이므로 이것도 위반이다 |

### 2.5 `coverage`

키 5개(`code`·`issue`·`adr`·`test`·`runtime`) 각각 다음 3값 중 하나:

| 값 | 의미 |
|---|---|
| `present` | 찾았다 |
| `absent` | **찾아봤는데** 없다 |
| `not_collected` | **수집 자체를 하지 않았다** |

- **퍼센트·점수 금지.** 미지 전체를 모르는 상태에서 "70% 커버"는 위장이다.
- `absent`와 `not_collected`를 합치면 "없음"과 "안 봄"이 구분되지 않는다. 이것이 이 층이 제거하려는 거짓 확신의 전형이므로 **3값을 유지**한다.

### 2.6 `warnings[]`

`{code, message, trigger}` — **세 필드 모두 필수**. `code`는 통제어휘다 — **자유 문장은 "경고했는가"를 측정할 수 없다.**

`trigger`가 필수인 이유: 여러 클래스가 동시에 `not_collected`일 때 공통 코드 하나만으로는 **어느 클래스에 경고했는지 판정할 수 없다.** `trigger`로 대상을 못박아야 A11이 결정론이 된다.

형식은 **code별로 스키마가 고정**한다(아래 표) — 임의 문자열을 허용하면 `trigger`를 필수로 만든 의미가 사라진다. 가리키는 대상이 실재하는지는 검증기가 확인한다(A18).

| code | 발동 조건 | `trigger` 형식 |
|---|---|---|
| `NO_CODE` / `NO_ISSUE` / `NO_ADR` / `NO_TEST` / `NO_RUNTIME` | 해당 클래스 `absent` | `coverage.<key>` |
| `NOT_COLLECTED` | 해당 클래스 `not_collected` — **클래스마다 한 건씩** | `coverage.<key>` |
| `CONFLICT_UNRESOLVED` | `NEEDS_CHECK` 충돌 잔존 — **충돌마다 한 건씩** | `<conflictId>` |
| `LOW_CORROBORATION` | 교차확인 부족 (임계값 §6.3) | `<evidenceId>` |
| `STALE_EVIDENCE` | 근거 노후 (임계값 §6.3) | `<evidenceId>` |
| `SIGNAL_UNMEASURED` | 신호값이 `null` — 0으로 채우는 것의 **유일한 대체 경로** | `<evidenceId>.signals.<name>` |
| `DEGRADED_SOURCE` | 하위 레이어 실패 전파 (I1 §3.3) | `<evidenceId>` |
| `ABSTAIN` | 답변 보류 (§6) | **성립한 조건을 가리킨다** — 조건 1이면 `evidence`, 조건 2면 `coverage.<key>`(부재한 핵심 클래스), 조건 3이면 `<conflictId>` |

### 2.7 `audit`

`{bundleId, promptHash, evidenceIds[], revision, createdAt, ceilingApplied}` **전부 필수** + `ceilingReasons`(`ceilingApplied=true`일 때 필수).

- **재현의 정의:** `audit`만으로 응답 본문을 복원한다는 뜻이 아니다. `bundleId`로 저장된 번들을 조회하고 `revision`·`promptHash`로 **같은 입력이었음을 확인한 뒤 재실행해 같은 결과가 나오는지** 보는 것이다(결정성 — I1 H1). 복원에 필요한 것은 좌표이지 본문 사본이 아니다.
- **시각 필드(`createdAt`·`observedAt`)**: `format: date-time` 과 함께 RFC 3339 `pattern` 을 병기한다. draft 2020-12 의 `format` 은 기본이 annotation 이라 검증기 설정에 따라 통과가 갈리기 때문이다. 다만 정규식은 **자릿수와 범위까지만** 막는다(`2026-13-01` 거부, `2026-02-30` 통과) — 달력 유효성까지 요구하므로 **계약 검증기는 `format` assertion 을 반드시 켠다**(C0 요구사항).
- `promptHash` — 프롬프트 **원문 대신 해시**. 원문 저장은 PII·시크릿 유출 경로다(I1 §4.1 보안 게이트). 형식을 `sha256:` + hex 64자로 **고정**한다 — 임의 문자열을 허용하면 원문을 그대로 넣어도 통과해 이 계약이 무너진다.
- `evidenceIds` — 번들에 포함된 **전체 후보**. 응답에 실린 `evidence[].id`의 **상위집합**이며(A13은 `⊆`이지 `=`가 아니다), **탈락한 후보를 일부러 남긴다** — 왜 그것이 안 쓰였는지 역추적하기 위해서다. 따라서 `evidence[]`에 없는 id가 여기 있는 것은 **정상이며 위반이 아니다**.
- `ceilingReasons` — 상한 사유를 **코드로 명시**하고 실제 `warnings`와 대조한다(A15). `ceilingApplied=false`면 이 필드를 두지 않는다 — 적용하지 않은 상한의 사유는 사유가 아니다.
- `ceilingApplied` — 상한 적용 **사실**의 기록. **선택이 아니라 필수**다: 선택으로 두면 필드를 생략하는 것만으로 상한 적용을 은폐할 수 있고, 그러면 A15가 무력화된다. 상한 수치는 미확정이나 기록 자체는 I1 §3.3의 게이트다.

---

## 3. confidence = 함수 (핵심)

### 3.1 prior는 시작점일 뿐이다

`release/main=1.0, develop=0.8, 2년 전 Jira=0.2, Slack=0.3` 같은 소스 타입별 상수는 **prior**다.
같은 Jira라도 **모듈이 그 뒤로 무변경이면** 유효하고, Slack이라도 **그것이 결정 출처면** 권위가 있다.

### 3.2 계약: 단일 스칼라 금지, 구성요소 노출 의무

```
confidence = f(finality, freshness, authority, corroboration, contradicted)
```

- 5개 신호를 **전부 노출**한다(A8). "왜 그 점수인지"를 소비자가 재계산할 수 있어야 한다.
- `contradicted`는 **방향이 반대인 유일한 신호**다 — 높을수록 confidence를 낮춘다. 스키마에 이 방향을 명시했다.
- 신호를 측정하지 못했으면 **0으로 채우지 않는다.** 0은 "측정했고 낮다"는 뜻이다. 미측정은 값 자체를 **`null`** 로 두고 `SIGNAL_UNMEASURED` 경고를 함께 낸다(§2.6·A17) — 이것이 신호 누락을 표현하는 **유일한 합법 경로**이며, 둘 중 하나만 있으면 위반이다.

### 3.3 계수는 지금 정하지 않는다

`f`의 형태와 가중치는 **#99 Gold Set 기반 calibration 측정 후 비준**한다(I1 §4.2와 동일 절차).
비준 전까지:

1. `confidence` 값은 **기록·측정 대상**이지 게이트가 아니다.
2. 어떤 문서·PR·발표에서도 "confidence 0.8 = 80% 정확"이라고 **인용하지 않는다**.
3. 다만 **곡선의 원자료는 매 실행 남긴다** — 비준의 재료다.

**"곡선을 매 실행 기록한다"는 표현은 폐기한다(§11).** 응답 시점에는 정답을 모르므로 곡선을 그릴 수 없다. 실제로 나뉘는 것은 다음 두 단계다.

| 단계 | 무엇을 | 어디에 | 소유 |
|---|---|---|---|
| **실행 시점** | 곡선의 **원자료** — 응답별 `confidence`·`signals`·`evidence[].id`·`bundleId`·`revision`. **answer-shape 안에 이미 전부 있다** — 별도 형식을 새로 정의하지 않는다 | 번들 로그(`bundleId`로 조회) | **C5** (로깅 완전성·누락 검증) |
| **사후 평가** | 원자료 × #99 Gold 정답 → **신뢰도 곡선·ECE** | Run Quality Report(#100 템플릿) | **C1** (산출 형식·누락 시 실패 판정) |

- 연결 키는 **`bundleId`** 다. 곡선의 각 점은 그것을 만든 번들로 역추적 가능해야 하며, 역추적되지 않는 점은 곡선에서 제외하고 그 사실을 보고서에 남긴다.
- **누락 검증:** 평가 대상 응답 중 원자료가 없는 건수를 Run Quality Report에 기록한다. 0건이 아니면 그 실행의 calibration 수치는 인용하지 않는다(§7.1 audit 완전성의 적용).
- 즉 이 층이 지금 확정하는 것은 **원자료가 응답 안에 다 들어있다는 사실**이고, 곡선의 저장 형식은 #100 템플릿과 C1의 몫이다.

---

## 4. 구조 불변식 (A1~A18)

**강제 위치**가 두 종류다. `schema`는 JSON Schema만으로 걸러지고, `validator`는 스키마를 통과하지만 교차 필드 검사에서 걸러진다.
픽스처는 [`schemas/examples/manifest.json`](schemas/examples/manifest.json)에 규칙 ID로 연결돼 있다.

| ID | 불변식 | 강제 | 위반 시 |
|---|---|---|---|
| **A1** | 응답은 JSON Schema를 통과한다 | schema | 형식 위반 — 측정 대상 제외 |
| **A2** | `schemaVersion`이 명시된다 | schema | 어느 계약인지 불명 |
| **A3** | 모든 `reason`은 `basis` ≥1개를 가진다 | schema | **무근거 이유** |
| **A4** | `coverage` 키 집합 = `evidence[].source` 어휘, 값은 3값 열거 | schema | %·점수 위장 |
| **A5** | `source=X` 증거가 존재 ⟺ `coverage[X] = present` | validator | **없는 걸 있다고 함** |
| **A6** | `conflicts[].between` ⊆ `evidence[].id` | validator | 유령 충돌 |
| **A7** | `status=RESOLVED` **⟺** `resolvedBy` 존재 (비-RESOLVED에 붙는 것도 위반) | schema | 근거 없는 해소 = 덮어쓰기(I1 P4) · 상태와 근거의 모순 |
| **A8** | `signals` 5개 전부 존재 | schema | 근거 없는 스칼라 |
| **A9** | 모든 `confidence` 값과 **`null`이 아닌** 신호값이 0.0~1.0 (`null`은 미측정을 뜻하는 합법 값 — A17) | schema | 범위 이탈 |
| **A10** | 모든 증거가 `stance`를 명시 | schema | 반대 증거 은폐 |
| **A11** | coverage 경고와 상태가 **양방향 일치**한다(`absent`/`not_collected` 클래스마다 `trigger="coverage.<key>"` 인 대응 경고가 있고, 반대로 그 경고가 있으면 상태도 그래야 한다). `CONFLICT_UNRESOLVED` 경고와 `NEEDS_CHECK` 충돌도 마찬가지로 양방향 일치한다 | validator | **경고 안 함** · 경고가 상태와 모순(무엇을 못 찾았는지가 거짓이 됨) |
| **A12** | `audit` 6개 필드(`ceilingApplied` 포함) 전부 존재 + 모든 `warnings` 항목이 `code`·`message`·`trigger`를 갖는다 | schema | 역추적 불가 · 경고 대상 불명 |
| **A13** | `evidence[].id` **⊆** `audit.evidenceIds` (등호 아님 — 탈락 후보가 더 있는 것은 정상, §2.7) | validator | 감사 로그 불완전 |
| **A14** | 모든 `contradicts` 증거는 **자기 자신이** 어떤 `conflicts[].between`에 들어 있고, 그 충돌이 `supports` 증거도 함께 참조한다. "충돌이 하나라도 있으면 통과"가 아니다 | validator | **충돌 미탐지 = 거짓 확신** · 반대 증거가 어디에도 연결되지 않음 |
| **A15** | `ceilingApplied=true` ⟺ `ceilingReasons`가 비어있지 않고, 그 모든 코드가 **상한 사유 통제어휘**(`DEGRADED_SOURCE`·`CONFLICT_UNRESOLVED`·`NOT_COLLECTED`·`NO_*`)에 속하며 **실제 `warnings`에 존재**한다. `false`면 필드를 두지 않는다 | schema + validator | 상한 은폐 · 사유를 사후에 지어냄 (I1 §3.3) |
| **A16** | §6.2의 abstention 조건 1~3(근거 0건 · 핵심 클래스 부재 · 미해결 충돌 존재) 중 하나라도 성립하면 `ABSTAIN` 경고가 존재하고, 그 **`trigger`가 성립한 조건을 실제로 가리킨다**(§2.6) | validator | 근거 없이 단정 · 보류 사유를 기계적으로 집계할 수 없음 |
| **A17** | `signals`의 값이 `null`(미측정)이면 `SIGNAL_UNMEASURED` 경고가 `trigger="<evidenceId>.signals.<name>"` 로 존재하고, 그 역도 성립한다 | validator | 미측정을 조용히 숨김 |
| **A18** | 모든 `warnings[].trigger`가 실재 대상을 가리킨다 — `coverage.<key>`는 해당 키, 그 외는 실재하는 `evidence[].id`·`conflicts[].id`·`<evidenceId>.signals.<name>`. **예약 리터럴 `evidence`는 항상 유효**하다(근거 0건 abstention은 가리킬 개별 증거가 없으므로 배열 자체를 가리킨다) | validator | 경고가 아무것도 가리키지 않음 |

> **A14는 gold 대조 없이도 검사 가능한 하한선**이다. 실제 충돌 탐지 성능은 §5의 precision/recall로 별도 측정한다.

---

## 5. 필드별 검증 계약

각 행의 "실패 = "는 **그 필드가 왜 존재하는지**를 뒤집어 쓴 것이다. 실패 정의가 없는 필드는 검증할 수 없으므로 필드가 아니다.

| 필드 | 검증 방법 | 산출 지표 | 실패 = | 소유 |
|---|---|---|---|---|
| **confidence** | **calibration** — gold에서 "c로 주장한 것이 실제로 ~c 비율로 적중"하는지 신뢰도 곡선으로 검증. 구간별 bin 집계 | ECE(Expected Calibration Error), bin별 (주장 c, 실적중률), 곡선 | **미보정 confidence = 거짓 확신.** 0.9라고 해놓고 실제 0.5면 이 층의 존재 이유가 무너진다 | 하위 이슈 C1 |
| **signals** | 각 신호가 confidence와 **단조 관계**인지, 특히 `contradicted`가 역방향인지 회귀 검사. 신호 제거 시 성능 변화(ablation) | 신호별 기여도, 방향 위반 건수 | 노출만 하고 실제로 쓰이지 않는 장식 신호 | 하위 이슈 C1 |
| **reason** | 각 `basis.id`가 **실재하는 L1/L2/L3 레코드**인지 조회 검증 + 그 레코드가 `text` 주장을 실제로 뒷받침하는지 gold 대조 | 무근거 이유 건수, 근거 불일치 건수 | **무근거 이유.** "관련 있습니다" 류 산문 | 하위 이슈 C2 |
| **conflicts** | gold 충돌셋과 대조한 **precision / recall** | precision, recall, 미탐지 목록, 과탐지 목록 | 미탐지 = 거짓 확신 / 과탐지 = 경보 피로. **둘 다 실패다** — 한쪽만 보고하는 것도 실패 | 하위 이슈 C3 |
| **coverage** | 클래스 존재/부재의 **결정론 검증** — ADR·test·log를 실제로 찾았는지 gold와 1:1 대조. 동일 입력 3회 일치(I1 H1) | 클래스별 정오표(present/absent/not_collected 오분류 건수), 결정성 일치율 | **없는 걸 있다고 함.** %로 위장 | 하위 이슈 C4 |
| **warnings / abstention** | 커버리지 미달·핵심 클래스 부재·미해결 충돌 시 **경고했는가**를 A11로, **보류했는가**를 A16으로 기계 검사 + gold의 "경고해야 하는 케이스" 재현율 | 경고 누락 건수, 경고 재현율, 오경고율 | **"찾았다"면서 30%만 찾음.** 경고 없이 자신 있게 틀리는 것이 최악 | 하위 이슈 C4 |
| **audit** | 모든 번들이 로깅되는지(완전성) + `bundleId`로 번들을 조회해 **같은 입력으로 재실행했을 때 같은 결과**가 나오는지(재현성 — §2.7의 정의) | 로깅 누락 건수, 재현 성공률 | **역추적 불가.** 틀렸을 때 왜 틀렸는지 말할 수 없음 | 하위 이슈 C5 |
| **task.intent** | #99 실제 질문이 통제어휘로 **손실 없이** 분류되는지 | 미분류 질문 비율 | 어휘가 현실을 못 담음 → 개정 신호 | #99 + 본 계약 개정 |

---

## 6. Abstention (답변 보류)

### 6.1 형식

abstention은 별도 필드가 아니라 **`warnings`에 `code: "ABSTAIN"`이 존재하는 상태**로 표현한다.
경고 체계 안에 두어야 "경고했는가" 측정과 abstention 측정이 같은 계기로 이뤄진다.

### 6.2 발동 조건 (형식 확정)

다음 중 하나면 `ABSTAIN`을 낸다:

1. `evidence`가 비어 있다.
2. 질문 intent가 요구하는 **핵심 클래스**가 전부 `absent`/`not_collected`다.
   (v0 매핑: `EXPLAIN`→`adr`·`issue` · `VERIFY`→`test`·`runtime` · `IMPACT`·`LOCATE`→`code` · `HISTORY`→`issue`)
3. **`NEEDS_CHECK` 충돌이 하나라도 존재**한다.
4. `confidence_overall`이 임계값 미만이다.

**조건 1~3은 지금 확정**된다(현재 필드만으로 결정론적 판정 가능). **조건 4의 임계값은 §6.3**.

> **조건 3이 "미해결 충돌 전부"인 이유:** `NEEDS_CHECK`는 문자 그대로 **"아직 모른다"** 는 뜻이다. 모른다고 기록해두고 확신에 찬 답을 내놓는 것이 이 층이 죽이려는 거짓 확신 그 자체다.
> 보류하지 않고 답하려면 충돌을 **닫아야** 한다 — 근거를 갖춰 `RESOLVED`로 만들거나(§2.4 `resolvedBy` 필수), 둘 다 참인 경우 `COEXIST`로 선언하면 된다. 즉 **비보류 경로는 이미 계약 안에 있고**, 그 경로를 쓰지 않은 채 답하는 것만 막는다.
> *(v0 초안은 "충돌이 랭킹 1위 증거를 포함할 때"로 좁혔으나 폐기했다 — 자체 정상 픽스처에서 질문 자체를 다투는 충돌이 하위 순위에 걸려 "주변부"로 오판정됐다. 랭킹은 중요도의 대리값이 되지 못한다. §11)*

### 6.3 임계값은 지금 정하지 않는다

`confidence_overall` 임계값, `LOW_CORROBORATION`·`STALE_EVIDENCE`의 경계값은 **calibration 전에는 의미가 없다.**
보정되지 않은 스칼라에 임계값을 걸면 그 임계값 자체가 거짓 확신이다.
→ #99 기반 1차 측정 후 §10 절차로 비준한다. 그 전까지는 **조건 1~3만으로 abstention을 운용**한다.

---

## 7. 목표 수치 정책

I1 §4의 정책을 이 층에 그대로 적용한다: **정직성은 무조건 게이트, 정확도는 baseline 후 비준.**

### 7.1 무조건 게이트 (사전 확정 · 협상 불가)

| 지표 | 값 | 근거 |
|---|---|---|
| 스키마 적합률(A1) | 100% | 형식 위반은 측정 이전의 문제 |
| 무근거 이유(A3) | **0건** | 산문 금지 |
| `stance` 명시율(A10) | 100% | 반대 증거 1급 |
| 커버리지 결정론 (동일 입력 3회 일치) | 100% | I1 H1 |
| 커버리지 허위 `present`(A5) | **0건** | 없는 걸 있다고 하는 것은 정확도 이전의 실격 |
| 경고 누락(A11) | **0건** | 경고 안 하고 틀리는 것이 최악 |
| `audit` 완전성·재현성(A12·A13) | 100% | 역추적 불가 = 검증 불가 |
| 상한 적용 기록(A15) | 100% | I1 §3.3 |

> 공통점은 I1과 같다: **정확도가 아니라 정직성**이다. 성능이 낮은 것은 baseline이지만, 실패를 숨기는 것은 실격이다.

### 7.2 잠정 (baseline 측정 후 비준)

| 지표 | 상태 |
|---|---|
| confidence calibration (ECE 등) | 목표값 **미정** — 1차 곡선 측정 후 비준 |
| conflict 탐지 precision / recall | 목표값 **미정** — gold 충돌셋 1차 측정 후 비준 |
| abstention 임계값 | **미정** (§6.3) |
| confidence 함수 계수 | **미정** (§3.3) |

**비준 절차는 I1 §4.2와 동일**: ① 잠정값을 게이트로 쓰지 않고 1차 측정 → ② @xivicWon 검토 → ③ 본 문서 개정으로 확정 → ④ 비준 전 인용 금지.

---

## 8. #99 (I2 Gold Set)에 추가로 요구되는 것

I1은 Gold Set을 "사실 추출" 중심으로 남겨두었다. 이 층을 측정하려면 **다음 케이스 종류가 #99에 포함되어야 한다.**

| 케이스 종류 | 필요한 이유 | 없으면 |
|---|---|---|
| **confidence calibration bin 케이스** — 정답/오답이 알려진 증거를 신뢰도 구간별로 충분히 | 곡선을 그리려면 각 bin에 최소 표본이 필요 | calibration 측정 불가 → confidence 영구 미검증 |
| **충돌 gold 셋** — 실제로 상충하는 소스 쌍(예: 코드=Session vs 이슈=JWT)과 **상충하지 않는 유사 쌍** | precision과 recall을 동시에 재려면 양성·음성 모두 필요 | 과탐지를 측정할 수 없다 |
| **커버리지 gold** — 각 질문마다 5개 클래스의 실제 존재/부재 정답 | A5·결정론 검증의 기준 | 허위 `present`를 잡을 수 없다 |
| **abstention 케이스** — 근거가 실제로 부족해서 **보류가 정답인** 질문 | "경고했는가"의 양성 케이스 | 자신 있게 틀리는 실패를 못 잡는다 |
| **반대 증거 케이스** — `contradicts` 증거가 존재하는 질문 | A14·stance 검증 | 반대 증거 은폐를 못 잡는다 |

→ 이 표는 **#99의 요구사항**이며, #99가 이를 반영하지 않으면 본 계약의 §5 지표 중 calibration·conflict·coverage·abstention은 **측정 불가 상태로 남는다**(그 사실을 Run Quality Report에 기록해야 한다).

---

## 9. 하위 이슈 분할 (에픽 #104)

본 문서는 **정의까지**다. 아래는 이 계약의 어느 절을 구현·측정하는지의 매핑이며, 에픽 #104의 "후속(설계 확정 후 분할)"에 대응한다.

| 하위 | 범위 | 계약 근거 | 선행 |
|---|---|---|---|
| **C0 검증기** | `validate.py`의 규칙(A5·A6·A11·A13·A14·A15·A16·A17·A18) **전부**를 백엔드 언어로 옮기고 실행 경로·CI에 연결, `examples/manifest.json`을 테스트 스위트로 사용 | §2·§4 | 없음 (지금 착수 가능) |
| **C1 confidence / calibration** | `f(signals)` 구현 + **곡선·ECE 산출 형식 확정**(#100 템플릿에 편입) + 원자료 누락 건수 보고 + 계수 비준 | §3.3·§5 | #99, C0, C5 |
| **C2 reason 근거 연결** | `basis` 실재성 검증 + 산문 탐지 | §5 | C0 |
| **C3 conflict 탐지** | 탐지기 + gold 대조 precision/recall | §5·§8 | #99, C0 |
| **C4 coverage / abstention** | 클래스 존재/부재 결정론 판정 + 경고·보류 발동 | §2.5·§6 | #99, C0 |
| **C5 audit log** | 번들 로깅 + 재현 검증 + **calibration 원자료 보존·누락 검증**(`bundleId` 연결) | §2.7·§3.3·§5 | C0 |
| **C6 API / MCP 서빙** | answer-shape 반환 엔드포인트 | §2 전체 | C0~C5 |

> **C0가 먼저다.** 검증기 없이 C1~C5를 만들면 각 하위가 자기 형식을 자기 기준으로 검사하게 되고, 계약이 코드마다 갈라진다.

---

## 10. 계약 개정 절차

I1 §7과 동일하며, 추가로:

1. 개정 사유·영향 범위(무효화되는 이전 측정)를 명시한 PR을 올린다.
2. **@xivicWon 승인** 없이 개정되지 않는다.
3. **기존 응답의 유효성이나 의미를 바꾸는 모든 변경**은 `schemaVersion`을 올린다(`answer-shape/v1`) — 필드 구조뿐 아니라 **통제어휘 변경·스키마 제약 강화/완화·교차 필드 불변식(A규칙) 추가·의미 재정의**가 전부 포함된다. 어제 통과하던 응답이 오늘 거부되거나 그 반대가 되는데 같은 `answer-shape/v0`로 식별되면, 버전 필드가 하는 일이 없다. v0로 생성된 응답은 v0 계약으로 평가하고 버전 간 수치를 직접 비교하지 않는다.
   *(본 문서 머지 전 리뷰 반영분은 v0 **발효 이전**이므로 상승 대상이 아니다 — §11에 이력으로 남긴다.)*
4. 통제어휘(`intent`·`source`·`warning.code`·`status`) 추가는 개정 사항이다. **런타임에 자유 문자열로 확장하지 않는다** — 어휘가 열리는 순간 지표 분리 집계가 무너진다.
5. 수치 비준(§3.3·§6.3·§7.2)도 개정으로 처리하며 이전 값과 함께 남긴다(덮어쓰기 금지 — I1 P4의 자기적용).

---

## 11. 개정 이력

머지 전 리뷰 반영분이므로 v0 발효 이전의 변경이나, 무엇이 왜 바뀌었는지는 남긴다(I1 §7.3 자기적용).

| 항목 | 이전 | 현재 | 사유 |
|---|---|---|---|
| `warnings[].trigger` | 선택 | **필수** | 여러 클래스가 동시에 `not_collected`일 때 공통 코드만으로는 클래스별 경고 여부를 판정할 수 없어 A11이 결정론이 아니었다 |
| `audit.ceilingApplied` | 선택 | **필수** | 선택이면 필드 생략만으로 상한 적용을 은폐할 수 있어 A15가 무력화된다 |
| `SIGNAL_UNMEASURED` | 없음 | 경고 코드 추가 | "미측정 신호를 0으로 채우지 말고 경고로 보고"를 요구하면서 대응 코드가 없어 준수 경로가 존재하지 않았다 |
| abstention 조건 3 | "`NEEDS_CHECK` 충돌이 **핵심 주장**에 걸려 있다" | "`NEEDS_CHECK` 충돌의 `between`에 **`evidence[0]`**이 포함된다" | "핵심 주장"은 응답 필드로 표현되지 않아 검증기마다 판정이 갈렸다 |
| A16 | 없음 | 추가 | abstention 조건이 §6에만 있고 불변식 표에 없어 검사 대상에서 빠질 수 있었다 |
| `signals` 값 타입 | `number` 필수 | `number` **또는 `null`** | "미측정을 0으로 채우지 말라"면서 필수 숫자만 허용해 표현할 값이 없었다 |
| A17·A18 | 없음 | 추가 | null 신호를 조용히 숨기는 경로, trigger 가 아무것도 안 가리키는 경로가 열려 있었다 |
| `trigger` 형식 | 느슨한 정규식(`foo` 허용) | code별 형식 고정 | 임의 문자열을 허용하면 `trigger` 필수화의 의미가 사라진다 |
| A16 표 렌더링 | 빈 줄로 표 밖에 표시 | 표 내부 행 | 서식 오류 |
| abstention 조건 3 | "충돌이 `evidence[0]`을 포함" | **"`NEEDS_CHECK` 충돌 존재"** | 랭킹이 중요도의 대리값이 되지 못했다 — 자체 정상 픽스처에서 질문 자체를 다투는 충돌이 하위 순위라는 이유로 비보류 판정됐다. 비보류 경로는 `RESOLVED`/`COEXIST`로 이미 존재한다 |
| `ABSTAIN` trigger | `evidence` 또는 `<conflictId>` | **성립한 조건을 가리킬 것**(+`coverage.<key>`) | 핵심 클래스 부재로 보류할 때 원인을 가리킬 어휘가 없었고, 무관한 증거 id 로도 통과했다 |
| A14 | "충돌이 하나라도 있으면 통과" | 반대 증거 **자신이** supports 와 함께 연결 | 반대 증거와 무관한 충돌 하나로 통과할 수 있었다 |
| `validate.py` 예외 처리 | 함수 전체를 `try` | **규칙별 격리** | 구조 결손으로 예외가 나면 그 전에 검출된 위반까지 전부 버려졌다 |
| `schemaVersion` 상승 대상 | 필드 구조 변경 | **유효성·의미를 바꾸는 모든 변경** | 어휘·제약·A규칙이 바뀌어도 같은 v0 로 식별됐다 |
| §3.3 "곡선을 매 실행 기록" | 곡선 | **원자료(실행) / 곡선(사후 평가)** 2단계 | 응답 시점에는 정답을 몰라 곡선을 그릴 수 없다 — 기록 대상·시점·소유·누락 검증이 없어 적합성 판정이 불가능했다 |
| 시각 초 범위 | `[0-5]\d` | `([0-5]\d\|60)` | RFC 3339 가 허용하는 윤초를 거부했다 |
| A11 coverage 방향 | 단방향 | **양방향** | `coverage.code=present` 인데 `NO_CODE` 경고를 붙여도 통과했다 |
| `expectedError` | schema 케이스만 | **모든 invalid 케이스** | validator 케이스는 메시지가 틀려도 통과했다 |
| A9 문언 | 모든 신호값 0.0~1.0 | `null` 제외 | A17·스키마가 허용하는 미측정 응답을 A9 가 거부하는 모순이었다 |
| A18 유효 대상 | id·coverage 키만 | + 예약 리터럴 `evidence` | 근거 0건 abstention 을 표현할 방법이 문언상 없었다 |
| 시각 `pattern` | 자릿수만 | 범위까지 + `format` assertion 의무화 | `2026-99-99T99:99:99Z` 가 통과했다 |
| `validate.py` 계층 대조 | 없음 | `enforcedBy` 와 실제 검출 계층 일치 요구 | 선언과 다른 계층에서 걸려도 통과했다 |
| `promptHash` | 임의 문자열 | `sha256:` + hex 64자 | 원문을 그대로 넣어도 통과해 '원문을 남기지 않는다'는 계약을 스키마가 보장하지 못했다 |
| `ceilingReasons` 어휘 | 모든 warning code | **상한 사유 8종** | 아무 경고나 사유로 끌어다 쓸 수 있었다 |
| `ceilingApplied=false` + 사유 | 스키마 허용 / 검증기 거부 | **양쪽 금지** | 스키마와 검증기가 상반된 판정을 했다 |
| `validate.py` 단일 위반 | 오류 **건수** 1 | 규칙 **종류** 1 | 같은 규칙을 두 계층이 이중으로 잡는 정상 상황을 실패로 판정했다 |
| A15 | "상한 사유 경고가 1개 이상 존재" | `audit.ceilingReasons` **명시 + 실제 경고와 대조** | 사유 집합이 넓어 사실상 위반이 불가능했고, 회귀 테스트로 고정되지 않았다 |
| `createdAt`·`observedAt` | `format` only | `format` + `pattern` | draft 2020-12의 `format`은 기본이 annotation이라 검증기 설정에 따라 통과가 갈렸다 |
| `validate.py` 교차 검사 | 스키마 오류 시 생략 | 가능한 한 **항상 실행** | 스키마 위반 픽스처에 숨은 2차 위반이 있어도 드러나지 않았다(실제로 2건 발견) |
| `resolvedBy` | `RESOLVED`일 때 필수(그 외 무제한) | `RESOLVED` **⟺** `resolvedBy` | 비-RESOLVED 에 해소 근거가 붙어도 통과해, 상태와 근거가 모순된 응답이 승인됐다 |
| A11 `CONFLICT_UNRESOLVED` | 단방향(미해결 → 경고) | **양방향** | 해결된 충돌에 경고가 남아 있어도 통과했다 |
| A5·A11 음성 픽스처 | 한 방향만 | 양방향 모두 | evidence 를 숨기는 coverage, `not_collected` 경고 누락을 검사하지 않았다 |
| `validate.py` 스키마 케이스 | 첫 오류만 대조 | **오류 1건** + 메시지 대조 | 복수 스키마 위반 픽스처가 단일 위반으로 승인될 수 있었다 |
| C0 이식 목록 | A5~A16 | A5~A18 | A17·A18 이 빠져 참조 검증기와 제품 검증기가 분화될 수 있었다 |
| 정상 픽스처 reason 좌표 | `ev-1`의 reason 이 다른 행(L80-L87)을 인용 | 별도 evidence 로 분리 | 그 증거의 `locator` 로 재확인할 수 없는 문장이었다 |
| 정상 픽스처 좌표 | 가공 예시(`payment_tx`·존재하지 않는 코드 행) | 리포 실좌표(`legacy-sample.sql`·`RelationService.kt`·`RelationJudgeTest.kt` @`3c27259`) | 계약이 "재확인 가능한 좌표"를 요구하는데 예제가 그것을 어겼다 — P1 자기적용 |

---

## 12. #103 완료 기준 체크

- [x] answer-shape v0 필드·타입·통제어휘 확정 → §2 + JSON Schema
- [x] 기계 판독 스키마 커밋 → `schemas/answer-shape.v0.schema.json`
- [x] 구조 불변식 A1~A18 확정 + 스키마/검증기 강제 위치 구분 → §4
- [x] 필드별 검증 계약(검증 방법·지표·"실패 = ") 확정 → §5
- [x] confidence를 함수로 취급하는 계약(신호 노출 의무·계수 미확정 명시) → §3
- [x] abstention 형식·발동 조건 확정, 임계값은 비준으로 위임 → §6
- [x] 게이트 / 잠정 지표 분리 → §7
- [x] #99(I2)에 추가 요구되는 gold 케이스 명시 → §8
- [x] 검증 픽스처(정상 3 + 위반 27) 커밋 + 규칙 ID·강제 위치·기대 오류 연결 → `schemas/examples/manifest.json`
- [x] 픽스처 적합성 확인기 커밋(30/30 재현 가능, 규칙 동일성·검출 계층·기대 메시지까지 대조) → `schemas/validate.py`
- [x] 하위 이슈 분할안 → §9

**다음 착수: C0 검증기 (§9)** — 픽스처 스위트와 참조 규칙 구현이 이미 있으므로 실패 테스트부터 시작할 수 있다.
