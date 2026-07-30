#!/usr/bin/env bash
# dispatch.sh <issue-number> [slug]
# 메인 세션이 이슈 하나를 [worktree + cmux 세션]으로 넘긴다. (결정론·재사용)
set -euo pipefail

N="${1:?사용법: dispatch.sh <issue-number> [slug]}"
SLUG="${2:-}"
# 리포 루트를 스크립트 위치(.claude/pipeline/)에서 파생 — 이식 가능
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CMUX="/Applications/cmux.app/Contents/Resources/bin/cmux"
CLAUDE="claude --dangerously-skip-permissions"

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
if git -C "$ROOT" worktree list | grep -q "lodestar-issue-${N}"; then
  echo "ℹ️  worktree 재사용: $WT"
else
  git -C "$ROOT" fetch origin --quiet 2>/dev/null || true
  git -C "$ROOT" worktree add "$WT" -b "$BRANCH" origin/main 2>/dev/null \
    || git -C "$ROOT" worktree add "$WT" -b "$BRANCH"
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

## 마무리 (필수)
1. 커밋 후: git push -u origin (현재 브랜치)
2. gh pr create --fill --base main   (본문 첫 줄 Closes #<이슈>, 말미:
   🤖 Generated with [Claude Code](https://claude.com/claude-code))
3. 생성된 PR URL 을 화면에 출력.
4. 머지 금지 — 메인 세션이 리뷰·승인한다.
5. .claude-brief.md 는 커밋하지 말 것.
RULES
} > "${WT}/.claude-brief.md"

# cmux 세션 — 초기 프롬프트는 짧은 ASCII 로 직접 전달(파일 읽으라고만)
$CMUX new-workspace --name "$WS" --cwd "$WT" \
  --command "${CLAUDE} 'Read .claude-brief.md and follow it strictly. Korean OK in output.'" >/dev/null

cat <<EOF
✅ 이슈 #${N} 디스패치 완료
   worktree : ${WT}
   branch   : ${BRANCH}
   cmux     : ${WS}   (cmux GUI에서 해당 탭으로 이동)
   진행확인 : ${CMUX} read-screen --workspace ${WS} --scrollback --lines 60
EOF
