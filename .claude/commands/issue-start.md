---
description: 이슈 하나를 새 cmux 세션(worktree+브랜치)으로 디스패치 — 메인은 감독만
argument-hint: "<이슈번호> [slug]"
allowed-tools: Bash
---

# /issue-start — 이슈를 cmux 작업 세션으로 넘김

메인 세션은 **감독**만 한다. 실제 구현은 이 명령이 여는 격리된 cmux 세션이 수행.

## 절차
1. **선행 확인**: 대상 이슈가 미착수 리포 자산에 의존하면(예: aira 이슈들은 #81 머지 필요) 먼저 그게 main에 있는지 확인. 없으면 사용자에게 알리고 중단.
2. **디스패치 실행**:
   ```bash
   bash .claude/pipeline/dispatch.sh $ARGUMENTS
   ```
   → worktree(`../lodestar-issue-<N>`) + 브랜치(`feat/<N>-<slug>`) 생성, 이슈 본문을 `.claude-brief.md`로 기록, cmux 워크스페이스 `issue-<N>` 에서 claude 자동 기동(브리프를 읽고 착수).
3. **사용자 안내**: cmux GUI에서 `issue-<N>` 탭으로 이동하라고 알림. 진행 확인은
   `read-screen --workspace issue-<N> --scrollback` 로 가능하다고 안내.
4. **메인은 대기**: 여기서 구현하지 말 것. PR이 올라오면 `/pr-review <N>` 로 넘어간다.

## 주의
- 병렬 착수 가능(이슈=브랜치=세션, 의존 없을 때). 의존 있으면 순서대로.
- 세션이 PR을 올리되 **머지는 안 한다**(메인 승인 전용).
