---
name: review-round-governor
description: Use when driving ANY review-response loop in the Lodestar pipeline — the worker's pre-push self-review (cap 3) or the main session's post-push AI-review loop (cap 5). Enforces round caps, dedupes findings by CONTENT across renumbered IDs, detects divergence, and HALTs with escalation. Invoke before starting a new review round or when a loop feels like it is not converging.
---

# Review-Round Governor

리뷰-응답 루프가 **수렴하지 못하고 폭주**하는 것을 막는다. (#115가 17라운드·문서 8552줄, #99가 7라운드로 폭주한 실패의 재발 방지.)

## 언제 쓰나
- 워커의 **push 전 자체리뷰** 루프(상한 3, `pre-push-review.md`).
- 메인 세션의 **push 후 AI 리뷰** 대응 루프(상한 5, `review-loop.md`).
- 루프가 "고쳤는데 또 지적이 올라온다"처럼 안 끝나는 느낌일 때.

## 왜 폭주하나 (근본 원인)
리뷰 지적의 **ID가 라운드마다 새로 부여**된다(LOD-130 ↔ LOD-133 ↔ LOD-145 = 같은 자리). 그래서 "재발 0"처럼 보이지만 **내용상 중복**이다. 새 ID를 새 findings 로 착각하면 루프가 끝나지 않는다.

## 절차

### 1. 라운드 카운트
- 워커 자체리뷰: 지금까지 돈 자체리뷰 횟수.
- AI 리뷰 루프: 해당 PR의 `AI 코드 리뷰 완료` 코멘트 수.

### 2. 내용 기준 dedup (ID 무시)
각 finding 을 **정규화 키**로 접는다:
```
key = normalize(file_path) + ":" + nearest_symbol_or_line_bucket + ":" + normalized_claim
normalized_claim = 소문자화 · 공백/구두점 축약 · ID(LOD-\d+, FP-\w+) 제거 · 동의어 통일
```
- 같은 key 가 이전 라운드에도 있었으면 **재지적(중복)** 으로 표시.
- 라운드의 "신규 finding" = 이전 라운드 key 집합에 **없는** 것만.

### 3. 수렴 판정
- **수렴 중**: 라운드마다 신규 finding 이 줄고, 재지적 비율이 는다 → 계속 가되 곧 종료.
- **발산(위험)**: 신규가 안 줄거나, 직전 확정 수정이 **같은 뿌리를 다시** 만든다 → 즉시 종료 검토.
- 마지막 라운드의 확정 findings 중 **제품/대상 코드 결함이 0**이고 나머지가 문서·테스트·단언강도면 → 종료 신호(게이트로 마감).

### 4. 상한 집행 (하드 규칙)
- 자체리뷰 **round > 3**, AI 리뷰 **round > 5** → **HALT**.
- HALT 시: 자동 수정·강행 머지 **금지**. 다음을 보고: 라운드 이력, dedup 요약(뿌리 몇 개인지), 남은 쟁점, 권고.
- 남은 IN-SCOPE 이 있으면 **후속 이슈로 이관**하고 진행(무한 금지).

### 5. 판정은 게이트로
리뷰 통과 ≠ 계약 준수. 종료 근거는 **게이트 그린**(evidence-gate-runner)이지 "리뷰어가 만족"이 아니다.

## 출력
```
round N/CAP · 신규 X · 재지적 Y(뿌리 Z개) · 수렴|발산
결정: CONTINUE | STOP(게이트로 마감) | HALT(에스컬레이션)
근거: <dedup 요약 · 발산 여부 · 게이트 상태>
이관: <후속 이슈로 넘긴 항목>
```

## 경계
- gold/정답/정책 성격 지적은 governor 가 판단하지 말고 **오라클에 에스컬레이션**([[gold-oracle-guard]]).
- 오탐 판정은 [[adversarial-finding-verifier]]에 위임 — governor 는 "얼마나/언제 멈출지", verifier 는 "이 지적이 진짜인지".
