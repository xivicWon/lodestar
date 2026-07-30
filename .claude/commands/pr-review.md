---
description: 이슈의 PR을 리뷰하고, 사용자 승인이 있으면 머지·정리 — 메인 세션 전용
argument-hint: "<이슈번호 또는 PR번호>"
allowed-tools: Bash, Read, Grep, Task
---

# /pr-review — PR 리뷰 → (사용자 승인) → 머지·정리

## 절차
1. **PR 찾기**: `gh pr list --state open --search "Closes #$ARGUMENTS" --json number,headRefName,url`
   (안 잡히면 head 브랜치 `feat/$ARGUMENTS-*` 로 매칭). PR 번호 확정.
2. **수용조건 대조**: `gh issue view <이슈>` 의 체크리스트 ↔ `gh pr diff <PR>`. 각 항목 충족 여부를 표로.
3. **품질 게이트**: worktree(`../lodestar-issue-<N>`)에서 변경 범위에 맞는 게이트 실행:
   - backend 변경 → `cd backend && ./gradlew test`
   - frontend 변경 → `cd frontend && npx vitest run && npx vue-tsc -b`
   - 스크립트/문서만 → 해당 스모크(예: `python3 <검증기>`).
4. **AI 리뷰 대응 = 로컬 리뷰-응답 루프**: AI 리뷰가 달리면 `.claude/pipeline/review-loop.md`를 따른다 —
   로컬 **fan-out 리뷰(서브에이전트 병렬)**로 수정 방향을 넓은 시야에서 판정 → `COMMENT_ONLY`면 답변·승인, `FIX`면 세션에 수정 지시·push → 재리뷰. **라운드 상한 5**(초과 시 HALT·사람 에스컬레이션), 라운드마다 강도↑.
5. **승인 게이트**: `COMMENT_ONLY` 단순 케이스만 자동 승인. **다회 수정·정답/정책 성격은 사용자 승인** 전 머지 금지.
6. **머지·정리**(승인 후에만):
   ```bash
   gh pr merge <PR> --squash --delete-branch
   # 실제 worktree 경로를 조회해 제거(고정 경로 가정 금지 — head 브랜치로 매칭)
   WT=$(git worktree list --porcelain | awk -v b="refs/heads/feat/<N>-" '/^worktree /{p=substr($0,10)} /^branch /{if(index($0,b))print p}')
   [ -n "$WT" ] && git worktree remove "$WT"
   /Applications/cmux.app/Contents/Resources/bin/cmux close-workspace --workspace issue-<N>
   ```
7. **후속**: 이슈 자동 close 확인(Closes #). Epic 체크리스트 갱신 필요 시 안내.

## 원칙
- 메인 세션은 리뷰·판단만. 구현 수정은 cmux 세션에 되돌려 시킨다.
- 승인=사용자. 나(에이전트)는 승인을 대신하지 않는다.
