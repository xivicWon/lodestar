#!/usr/bin/env bash
# cmux 세션에서 코딩 에이전트를 기동한다. dispatch.sh 가 --command 로 호출.
# - ccp 는 ~/.zshrc 의 zsh 함수다(내부적으로 claude --dangerously-skip-permissions "$@").
#   함수라서 bash/비대화형 셸에는 정의가 없다 → ~/.zshrc 를 읽는 '대화형' zsh 로 실행해야 한다.
# - cwd 는 cmux --cwd 로 이미 이슈 worktree 로 설정돼 있어 .claude-brief.md 가 곁에 있다.
# - 인라인이 아닌 스크립트로 분리한 이유: cmux --command 인라인 전달의 첫 글자 누락(race)과
#   따옴표 이스케이프 취약성을 피하고, 기동 방식을 한 곳에서 관리하기 위함.
PROMPT='Read .claude-brief.md and follow it strictly. Korean OK in output.'

# -i: 대화형 → ~/.zshrc 로드(ccp 함수 정의). exec 로 zsh 가 이 프로세스를 대체한다.
exec zsh -ic "ccp '${PROMPT}'"
