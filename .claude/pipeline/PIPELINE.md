# 작업 파이프라인 (이슈 중심 · cmux 병렬 · PR 리뷰 게이트)

메인 세션은 **감독**(이슈 관리 + PR 리뷰 + 승인)만. 구현은 이슈별 격리 cmux 세션이 한다.

```
 ┌─────────────────────────────── 메인 세션 (감독) ───────────────────────────────┐
 │                                                                                 │
 │  1. 이슈 등록/관리   gh issue …  (마일스톤·라벨·Epic)                              │
 │  2. /issue-start N   ─────────────┐  디스패치(결정론)                             │
 │  4. /pr-review N     ◀──PR──┐     │                                              │
 │  5. 사용자 승인 → 머지·정리   │     │                                              │
 └──────────────────────────────┼─────┼──────────────────────────────────────────┘
                                │     ▼
                    ┌───────────┴───────────── cmux 세션 issue-N (구현) ──────────┐
                    │  worktree ../lodestar-issue-N + 브랜치 feat/N-slug           │
                    │  .claude-brief.md 읽고 TDD 구현 → push 전 자체리뷰(6렌즈·≤3회) → push → PR │
                    │  (Closes #N)  · 머지는 안 함                                  │
                    └──────────────────────────────────────────────────────────────┘
```

## 명령
| 단계 | 명령 | 하는 일 |
|---|---|---|
| 디스패치 | `/issue-start <N> [slug]` | worktree+브랜치 생성, 브리프 기록, cmux 세션 기동 |
| 리뷰·승인 | `/pr-review <N>` | 수용조건 대조 + 품질게이트 + **로컬 리뷰-응답 루프** → (승인) 머지·정리 |
| 엔진 | `.claude/pipeline/dispatch.sh <N>` | 위 디스패치의 결정론 부분 |
| push 전 자체리뷰 | `.claude/pipeline/pre-push-review.md` | 워커가 push 전 6렌즈(버그·보안·성능·유지보수·SOLID·호환성) 자가리뷰 → 범주 안 수정(≤3회)·범주 밖 코멘트+후속이슈 |
| 리뷰 루프 | `.claude/pipeline/review-loop.md` | (push 후) AI 리뷰 대응: fan-out 로컬 리뷰 → FIX/COMMENT 분기 → 5회 상한·강도↑ |

## 채용 스킬·에이전트 (.claude/skills, .claude/agents)
| 이름 | 유형 | 쓰임 |
|---|---|---|
| `review-round-governor` | Skill | 리뷰 루프 상한·내용 dedup·발산 판정·HALT (자체리뷰 3 / AI리뷰 5) |
| `evidence-gate-runner` | Agent | 변경 범위→L0~L3·결정성·빌드/테스트 게이트 PASS/FAIL 매트릭스 |
| `adversarial-finding-verifier` | Agent | 리뷰 지적 1건을 반증 우선으로 검증 → CONFIRMED/오탐 |
| `gold-oracle-guard` | Skill | gold 변경 전 자기승인·순환·축분리 3대 불변식 검사 |

## AI 리뷰 대응 루프 (요약)
```
AI 리뷰 도착 → 로컬 fan-out 리뷰(서브에이전트 K개, 넓은 시야)
   ├─ COMMENT_ONLY → 답변 코멘트 → 승인 → 다음 작업
   └─ FIX → 수정 방향 브리프 → cmux 세션 push → 재리뷰 (round+1)
round > 5 → HALT (자동중단·사람 에스컬레이션).  라운드 오를수록 리뷰어 수·adversarial 강도↑
```

## 규칙
- **이슈 하나 = 브랜치 하나 = cmux 세션 하나.**
- main 직접 push 금지. PR 머지로만 main 갱신.
- 메인 세션은 구현하지 않는다(리뷰·판단·승인만). 수정은 cmux 세션에 되돌린다.
- 승인은 사용자. **단 예외**: `COMMENT_ONLY`(코드 수정 없이 답변으로 끝나는) 단순 케이스는 에이전트 자동 승인 허용(규칙2). 다회 수정·정답/정책 성격은 사용자 승인.
- 의존 있는 이슈는 선행 PR 머지 후 착수(예: aira 이슈는 #81 먼저).

## 정리
머지 후: `git worktree remove ../lodestar-issue-N` + `cmux close-workspace --workspace issue-N`.
