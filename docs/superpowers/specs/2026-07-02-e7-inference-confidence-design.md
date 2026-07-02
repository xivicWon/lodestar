# Lodestar E7 — 추론 제안의 확률적 신뢰도 (자기일관성) 설계

> 작성일: 2026-07-02
> 상태: **설계 승인됨 (구현 전)**
> 제품명: Lodestar · 리포 코드네임: onto-studio

## 0. 배경 & 기조

E3(AI 의미 추정)의 해자는 실증됐으나 **품질이 측정되지 않았다** — "정확도 55%"는 1회 표본에 불과했다.

**제품 기조(운영 모델):**
1. **추론은 "제안"일 뿐** — AI가 관계·의미와 그 근거를 추론해 *제안*한다(확정 아님).
2. **운영자가 승인하면 "고정"된다** — 승인된 추론은 세이브포인트로 저장돼 확정 사실이 된다. (향후 에픽: E5 위 확장)
3. **다음 추론은 저장된 추론을 기조로 확장** — 확정 앵커를 컨텍스트로 삼아 그 위에서 추론한다. (향후 에픽)

**이 스펙의 범위(슬라이스 A):** ①의 *제안*에 **근거 있는 신뢰도**를 붙인다.
정답표(oracle)를 두지 않는다 — "증거도 추론"이라는 기조에 따라, **같은 추론을 여러 번 반복해 그 합의(self-consistency)를 신뢰도로 삼는다.** 승인/세이브포인트(②③)는 이후 에픽.

## 1. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 신뢰도 = **N회 반복 추론의 합의율**(agreement) | 비결정론적 AI에서 1회는 표본 1개. 분포로 평가해야 근거가 됨 |
| D2 | **고정 정답표 없음** | 레거시 의미엔 확정 정답이 없음. "출력끼리 얼마나 뭉치나"(자기일관성)를 측정 |
| D3 | 라벨 군집화는 **결정론적**(정규화+토큰 중첩) | "정답 채점"이 아니라 "출력 응집도" 측정이라 결정론적이어도 기조와 무충돌. 신호 변동은 오직 생성 AI에서 나옴 |
| D4 | 트리거형 엔드포인트 (일반 테스트 스위트 미포함) | 실제 claude를 N회 호출 → 느리고 비결정론적. 채점/집계 로직만 결정론 단위테스트 |

## 2. 동작 & 데이터 흐름

```
ScoredEnricher.scoredEnrich(runs=N)
   │  repeat N: candidates = SemanticEnricher.enrichSample()   ← 기존 재사용 (실제 claude -p)
   │  테이블(targetIri)별로 라벨 N개 수집
   ▼
ConsensusScorer.score(labels: List<String>)  ← 순수·결정론적
   │  정규화(공백·괄호·구두점 제거, 소문자) → 토큰 Jaccard ≥ 0.5 로 군집
   │  최빈 군집 → consensusLabel(그 군집의 대표=최다 원문), agreement = 최빈군집수/N
   ▼
ScoredCandidate{ targetIri, currentName, consensusLabel, description, agreement, n, variants[{label,count}] }
   ▼
POST /api/ai/enrich/sample/scored?runs=5  → List<ScoredCandidate>  (agreement 오름차순: 흔들리는 것 먼저)
   ▼
EnrichPanel: agreement 배지(예 ≥0.8 초록 "확신", ≥0.5 주황 "보통", <0.5 빨강 "재확인"), 승인 시 consensusLabel 반영
```

## 3. 컴포넌트 (경계 명확)

- **`ConsensusScorer`** (신규, 순수) — `score(labels: List<String>): Consensus`.
  `Consensus(consensusLabel: String, agreement: Double, variants: List<Variant>)`, `Variant(label, count)`.
  정규화 후 토큰 Jaccard ≥ 0.5 로 군집화, 최빈 군집의 대표 라벨과 agreement 산출. 라이브러리·AI 무관 → 단위테스트 핵심.
- **`ScoredEnricher`** (신규) — 기존 `SemanticEnricher`를 N회 호출, targetIri별 라벨 수집, `ConsensusScorer`로 집계해 `ScoredCandidate` 리스트 반환. description은 consensus 군집의 대표 후보 것. 신규 AI 로직 없음(반복+집계).
- **`ScoredEnrichController`** (신규) — `POST /api/ai/enrich/sample/scored?runs=N` (runs 기본 5, 상한 예: 10).
- **프론트**: store `scoredEnrichSample(runs)` + `scoredCandidates` 상태; `EnrichPanel`에 agreement 배지 + 흔들림 우선 정렬. 승인은 기존 `applyEnrichment(targetIri, consensusLabel)` 재사용.

## 4. 테스트 (결정론적, 실 AI 없이)

- **`ConsensusScorerTest`** (순수): 
  - 동일 라벨 5개 → agreement 1.0, consensusLabel 그 라벨.
  - "고객 마스터" 3 + "거래처 정보" 2 (토큰 겹침 낮음) → 최빈군집 3/5, agreement 0.6.
  - "거래처(고객) 마스터" 와 "고객 마스터" 정규화·토큰중첩으로 같은 군집에 묶이는지.
  - 빈 리스트 → agreement 0.0, consensusLabel "".
- **`ScoredEnricherTest`**: 호출마다 다른 JSON을 회전 반환하는 **페이크 AiAdvisor**(호출 카운터)로 비결정론 시뮬 → 특정 테이블 agreement가 기대치(예 2/3)와 일치.
- **컨트롤러 테스트**: `@MockitoBean AiAdvisor` 고정응답 → `POST /scored?runs=3` 200 + agreement 필드 존재.
- **프론트**: 스토어 `scoredEnrichSample`(mock) + `EnrichPanel` 배지/정렬 컴포넌트 테스트.

## 5. 성공 기준

1. 샘플을 N회 돌리면 각 제안에 **agreement(합의율) 신뢰도**가 붙는다.
2. **흔들리는 제안**(낮은 agreement)이 UI에서 식별·상단 정렬된다.
3. 승인 시 consensus 라벨이 온톨로지에 반영된다(기존 경로 재사용).
4. 집계/군집 로직은 결정론적 단위테스트로 검증된다(실 AI 불필요).

## 6. 범위 밖 (다음 에픽)

- 세이브포인트(②): 승인된 의미만 확정 저장 + 재임포트/다음 추론 컨텍스트 주입(그라운딩). E5 확장.
- E2 관계 발굴/E3 라벨의 하드코딩 confidence(0.6/0.9)를 반복추론 합의로 소급 대체.
- 사람 seed 보정(calibration)으로 자기참조 완화.
- 골드 라벨 대비 절대 정확도(정답표 방식) — 기조상 채택 안 함.
