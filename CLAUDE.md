# Lodestar — 프로젝트 작업 규칙

> 제품: **Lodestar** (레거시 DB 지식 복원 & 시맨틱 데이터 인텔리전스 플랫폼)
> 리포 코드네임: `onto-studio` · 원격: github.com/xivicWon/lodestar

## 작업 흐름 (필수)

모든 작업은 아래 순서를 따른다.

1. **마일스톤 단위 설계**
   - 작업은 **마일스톤(에픽) + 이슈** 단위로 먼저 설계·정리한다.
   - 에픽 = 큰 목표(예: "P7 AI Chat"). 그 아래 실행 가능한 **이슈**들로 쪼갠다.
   - 설계 문서(`docs/superpowers/specs/`)와 플랜(`docs/superpowers/plans/`)을 만든 뒤, 그 플랜의 태스크를 GitHub 이슈로 등록한다.

2. **이슈 기반 구현**
   - 구현은 항상 **이슈를 기준**으로 진행한다. 이슈 없는 임의 작업 금지.
   - 이슈 하나 = 브랜치 하나. 브랜치명 예: `feat/<issue-번호>-<슬러그>`.

3. **main 직접 반영 금지**
   - **어떤 작업도 `main`에 직접 커밋/푸시할 수 없다.**
   - 모든 변경은 이슈 브랜치에서 이루어진다.
   - **강제 방식:** 리포에 `.githooks/pre-push`(main 직접 푸시 차단)를 둔다. 클론 후 1회 활성화:
     ```
     git config core.hooksPath .githooks
     ```
   - (리포가 프라이빗+무료라 GitHub 서버측 브랜치 보호/룰셋은 미사용. 공개 전환 또는 Pro 업그레이드 시 서버측 보호로 승격 권장.)

4. **기본 GitHub 배포 방식 (GitHub Flow)**
   - `main`에서 이슈 브랜치를 딴다 → 브랜치에서 구현·커밋 → 푸시.
   - 작업 완료 시 **PR(Pull Request)** 로 `main`에 반영한다. PR 본문에 관련 이슈(`Closes #N`)를 연결한다.
   - PR 머지로만 `main`이 갱신된다.

## 커밋/PR 규약

- 커밋 메시지 말미: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- PR 본문 말미: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
- 커밋 접두어: `feat` / `fix` / `docs` / `refactor` / `test` (+ 페이즈 태그, 예: `feat(p7): ...`).

## 품질 게이트 (PR 전 필수)

- 백엔드: `cd backend && ./gradlew test` 그린.
- 프론트: `cd frontend && npx vitest run && npx vue-tsc -b` 그린.
- 구현은 TDD(실패 테스트 → 구현 → 통과)로 진행한다.

## 로컬 실행 주의

- 로컬에서 Docker가 포트 8080/8081을 점유하는 경우가 있다. 백엔드 수동 기동 시 다른 포트를 쓴다.
- Vite dev 프록시 타깃은 `http://localhost:8090` (프론트에서 `/api` 호출 시). 백엔드를 8090으로 띄운다.

## 기술 스택

- 백엔드: Kotlin + Spring Boot, OWL API 5.5, HermiT, JSqlParser, PostgreSQL JDBC (테스트 H2).
- 프론트: Vue 3 + TS + Pinia, vis-network, Vitest.
