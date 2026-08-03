#!/usr/bin/env bash
# dispatch.sh <issue-number> [slug]
# 메인 세션이 이슈 하나를 [worktree + cmux 세션]으로 넘긴다. (결정론·재사용)
set -euo pipefail

N="${1:?사용법: dispatch.sh <issue-number> [slug]}"
[[ "$N" =~ ^[0-9]+$ ]] || { echo "❌ 이슈번호는 정수여야 함: '$N'"; exit 1; }  # 주입 방지
SLUG="${2:-}"
# 리포 루트를 스크립트 위치(.claude/pipeline/)에서 파생 — 이식 가능
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CMUX="/Applications/cmux.app/Contents/Resources/bin/cmux"
LAUNCH=".claude/pipeline/agent-launch.sh"   # 에이전트(ccp) 기동 런처 — 인라인 대신 스크립트

command -v gh >/dev/null || { echo "❌ gh 필요"; exit 1; }
[ -x "$CMUX" ] || { echo "❌ cmux 없음: $CMUX"; exit 1; }
gh issue view "$N" --json number >/dev/null 2>&1 || { echo "❌ 이슈 #$N 없음"; exit 1; }

TITLE=$(gh issue view "$N" --json title -q .title)
BODY=$(gh issue view "$N" --json body -q .body)
if [ -z "$SLUG" ]; then
  SLUG=$(gh issue view "$N" --json labels \
    -q '[.labels[].name]|map(select(.!="enhancement" and .!="bug" and .!="documentation" and .!="epic"))|.[0]//"task"')
fi
SLUG=$(printf '%s' "$SLUG" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')
BRANCH="feat/${N}-${SLUG}"
WT="${ROOT}/../lodestar-issue-${N}"
WS="issue-${N}"

# worktree (origin/main 기준, 없으면 로컬 main)
if git -C "$ROOT" worktree list --porcelain | grep -qE "^worktree .*/lodestar-issue-${N}$"; then
  echo "ℹ️  worktree 재사용: $WT"
else
  git -C "$ROOT" fetch origin --quiet 2>/dev/null || true
  if git -C "$ROOT" show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    # 브랜치가 이미 있으면(중단·정리된 세션 복구) 새로 만들지 말고 연결
    git -C "$ROOT" worktree add "$WT" "$BRANCH"
  else
    # 시작점 고정: origin/main → 로컬 main → 없으면 중단 (현재 HEAD 오염 방지)
    if   git -C "$ROOT" show-ref --verify --quiet refs/remotes/origin/main; then base=origin/main
    elif git -C "$ROOT" show-ref --verify --quiet refs/heads/main;          then base=main
    else echo "❌ origin/main·로컬 main 기준을 찾을 수 없음"; exit 1; fi
    git -C "$ROOT" worktree add "$WT" -b "$BRANCH" "$base"
  fi
fi

# 브리프 (긴 한글은 파일로 — cmux 인라인 truncation 회피)
{
  echo "# 작업 브리프 — 이슈 #${N}: ${TITLE}"
  echo "브랜치: ${BRANCH} (이미 체크아웃됨) · 원격: github.com/xivicWon/lodestar"
  echo "PR 본문에 반드시 포함: Closes #${N}"
  echo
  echo "## 이슈 내용"
  echo "${BODY}"
  cat <<'RULES'

## 작업 규칙 (CLAUDE.md 준수)
- TDD: 실패 테스트 → 구현 → 통과.
- 품질 게이트(해당 시): backend는 ./gradlew test, frontend는 npx vitest run && npx vue-tsc -b.
- 커밋 접두어 feat/fix/docs/refactor/test + 말미 한 줄:
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
- main 직접 push 금지. 이 브랜치에서만.

## push 전 자체 코드리뷰·검증 (필수 — 상세: .claude/pipeline/pre-push-review.md)
커밋을 push 하기 전에 변경 diff(git diff origin/main...HEAD)를 스스로 리뷰한다.
1. 6개 렌즈로 점검: 버그 · 보안 · 성능 · 유지보수 · SOLID · 호환성.
   (가능하면 렌즈별 서브에이전트 병렬로 넓게 — 각자 근거 수집 후 판정.)
2. findings 분류:
   - 이 이슈 수정범주 안(이번 변경이 도입/직접 건드림) → 고친다.
   - 범주 밖(기존 결함·타 서브시스템·대규모 리팩터·정책) → 고치지 말고
     PR 코멘트 + 후속 GitHub 이슈로 등록(gh issue create, 라벨·근거·이 PR 참조).
   판단: "이 변경을 되돌리면 그 결함도 사라지나?" → 그렇다=범주 안.
3. 범주 안 수정 후 재리뷰. **최대 3회.** 3회 후 남으면: minor 는 후속 이슈로 이관·진행, blocking/major 가 남으면 HALT·사람 에스컬레이션(강행 push 금지). 무한 금지.
4. 게이트 그린 + 자체리뷰 통과(범주 안 blocking/major 0)라야 push.
- 이 이슈가 이 범주에 부적합(문서 단독·정책)이면 해당 없는 렌즈는 건너뛰고 발견은 전부 코멘트+후속이슈.
- gold/정답/정책 성격은 자체리뷰가 판단 말고 메인 세션·오라클에 넘긴다(자기승인 금지).

## 마무리 (필수)
1. 커밋 후: git push -u origin (현재 브랜치)   ※ 위 '자체 코드리뷰·검증' 통과가 선행
2. gh pr create --fill --base main   (본문 첫 줄 Closes #<이슈>, 말미:
   🤖 Generated with [Claude Code](https://claude.com/claude-code))
3. 생성된 PR URL 을 화면에 출력.
4. 머지 금지 — 메인 세션이 리뷰·승인한다.
5. .claude-brief.md 는 커밋하지 말 것.
RULES
} > "${WT}/.claude-brief.md"

# cmux 세션 — 런처 스크립트를 실행(ccp 기동). worktree(.claude-brief.md 곁)에서 돈다.
# 선행 공백: cmux --command 가 첫 키 입력을 종종 삼킨다(관측: 'claude'→'laude').
# 맨 앞 공백을 미끼로 두면 삼켜도 뒤 명령이 온전하다(zsh 는 선행 공백 무시).
$CMUX new-workspace --name "$WS" --cwd "$WT" \
  --command " bash ${ROOT}/${LAUNCH}" >/dev/null

cat <<EOF
✅ 이슈 #${N} 디스패치 완료
   worktree : ${WT}
   branch   : ${BRANCH}
   cmux     : ${WS}   (cmux GUI에서 해당 탭으로 이동)
   진행확인 : ${CMUX} read-screen --workspace ${WS} --scrollback --lines 60
EOF
