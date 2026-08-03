---
name: gold-oracle-guard
description: Use before making or reviewing ANY change under docs/superpowers/specs/gold/ (manifest, corpus, l1/l2/l3 answer sets, fixtures) or any act that would approve a gold/baseline revision. Guards the three invariants that protect the oracle's trust — no self-approval, gold independence from the tool-under-test, and input/answer axis separation. Invoke when a PR touches gold, when re-pinning a revision, or when tempted to flip manifest status.
---

# Gold & Oracle Governance Guard

정답셋(gold)의 신뢰가 이 제품의 **존재 근거**다. 위반 1건이 정답셋 전체를 오염시킬 수 있어, gold 를 만지는 모든 변경 전에 아래 3대 불변식을 검사한다. (#125에서 "피검사 수집기로 정답 생성=순환"을 아슬하게 회피한 교훈.)

## 언제 쓰나
- `docs/superpowers/specs/gold/**` (manifest.json, corpus, l1/l2/l3, fixtures) 변경·리뷰.
- gold/baseline revision 재고정(#125류) 또는 승인 상태 변경 시도.
- RQR 의 `eligibleAsBaseline`·`GOLD_UNAPPROVED` 관련 변경.

## 불변식 1 — 자기승인 금지
- 에이전트/세션은 `manifest.json` 의 `status.state` 를 `APPROVED` 로 바꾸거나 `approvedBy`·`approvedAt` 을 **직접 채우지 않는다**.
- 승인은 **오라클(@xivicWon)** 만 한다. 스키마가 `state`·`approvedBy`·`approvedAt` 셋을 함께 요구하는 이유가 이것 — 승인 사실이 파일에 없으면 승인이 아니다.
- 재고정안은 `PROPOSED`(미승인) 상태로 만들어 메인 세션·오라클에 넘긴다.
- **검사**(전이만 보지 말고 **결과 상태·값 변화**를 본다): diff 에 `state=APPROVED` 가 **어떤 형태로든** — PROPOSED→APPROVED 전이든, **처음부터 `APPROVED` 로 작성된 신규 manifest** 든 — 나타나거나, `approvedBy`/`approvedAt` 이 **신규 기입이든 기존 값 교체든** 발생하면 → 차단·에스컬레이션.

## 불변식 2 — gold 독립성 (순환 금지)
- 정답(L1/L2/L3)을 **피검사 도구(codegraph 등 수집기)로 생성하지 않는다**. 도구가 정답을 만들면 "도구가 자기 채점표를 쓴다" → 검증이 무의미.
- 닫힌 범위(`scope.closed:true`) 정답셋은 사람이 열거·확정한 것이어야 한다.
- **검사**: 정답 파일 갱신이 수집기 실행 산출물에서 자동 유도됐는지 확인. 그렇다면 → 중단, 사람 열거로 전환.

## 불변식 3 — 입력축 ↔ 정답축 분리
- **정답축** `sourceRevision`(정답셋이 고정한 소스 버전)과 **입력축** `probeAxis.revision`(프로브가 실제 수집한 버전)은 **다른 축**이다. 혼동·동시이동 금지(#125 probeAxis 신설의 이유).
- 프로브 산출물의 `sourceRevision` 에 입력 revision 을 섞지 않는다 — 입력 revision 은 `inputAxis`/`probeAxis` 에만.
- **검사**: 수집기 입력 파일이 바뀌었는데 `sourceRevision` 을 그대로 올리려 하면(정답셋 자동 오염) → 축 분리로 처리.

## 승인 유효성 (오라클이 승인할 때)
승인의 신원 근거는 **위조 불가능한 것**이어야 한다 — git commit author 는 `git commit --author` 로 누구나 위장할 수 있어 신원 근거가 **못 된다**. 유효한 승인 = (a) `state=APPROVED` + `approvedBy` + `approvedAt` **셋 동시** 기입, **그리고** (b) 그 변경이 **오라클 계정만 보유한 GitHub 승인/머지 권한**으로 main 에 반영됨(가능하면 GPG/SSH **서명된 Verified 커밋** 병행). 문장·주석이 아니라 이 **구조적 게이트**로만 승인을 표현한다.

## 출력
```
gold 변경 검사: 자기승인[통과/차단] · 독립성[통과/차단] · 축분리[통과/차단]
판정: PROCEED | STOP(사람/오라클 에스컬레이션)
근거: <위반한 불변식 · 해당 파일:라인>
```

## 연계
- 라운드 종료·상한은 [[review-round-governor]]. gold 성격 지적이 나오면 governor 가 여기로 넘긴다.
- 재측정 게이트 결과는 [[evidence-gate-runner]](validate_gold.py·verify_l0.py).
