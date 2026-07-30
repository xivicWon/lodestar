# L0 Source 벤치 (#88 baseline · #112·#114 재측정)

고정 revision `3c27259` 의 입력으로 수집기를 돌려 I1 §4.1 의 L0 무조건 게이트를 측정한 증거다.
계약·판정·발견은 [`../../2026-07-30-m0-l0-source-validation.md`](../../2026-07-30-m0-l0-source-validation.md)
(#88 baseline)과 [`../../2026-07-30-m0-l0-fix-error-visibility.md`](../../2026-07-30-m0-l0-fix-error-visibility.md)
(#114 오류 가시성 수정 후 재측정)에 있다.

같은 고정 입력을 수집기 버전만 바꿔가며 잰 실행들이 **사슬**로 이어진다: 이전 실행을 덮어쓰지 않고 새
runId 로 남기고(I3 §5.5), 새 실행이 이전 것을 `baseline.previous` 로 인용해 변화량을 `deltas` 에 적는다.

```
probe_code.py     코드 트랙 프로브 (lodestar_codegraph 를 서브프로세스로 실행)
build_report.py   프로브 산출물 → Run Quality Report v0 (프로브의 순수 함수)
verify_l0.py      커밋된 증거의 적합성 확인기 V1~V14 + 결함 주입 31케이스
test_bench_l0.py  **계측기 자체의 단위 테스트** — 귀속·게이트 산식·확인기 규칙이 거짓을 무는가
manifest.json     규칙 범위·케이스 총계 고정
runs/run-l0-db-3c27259-001/     probe-db.json · report.json    (#88 실측 — 보고율 0.0)
runs/run-l0-db-3c27259-002/     probe-db.json · report.json    (#114 재측정 — 보고율 1.0 · 현행)
runs/run-l0-code-3c27259-001/   probe-code.json · report.json  (#88 실측 — 결정성 0.3333 · H1)
runs/run-l0-code-3c27259-002/   probe-code.json · report.json  (#112 재측정 — 결정성 1.0)
runs/run-l0-code-3c27259-003/   probe-code.json · report.json  (#114 재측정 — 보고율 1.0 · 현행)
```

**현행 실행**은 db `002` · code `003` 이다(`build_report.RUNS` · `probe_code.RUN_DIR`). 각 트랙의 직전
실행이 `PREVIOUS` 이며 새 보고서가 그것을 `baseline.previous` 로 인용한다 — 덮어쓰지 않는다(I3 §5.5).

DB 트랙 프로브는 수집기가 Kotlin 이므로 백엔드 테스트가 겸한다 —
`backend/src/test/kotlin/com/ontostudio/rdb/L0DbSourceProbeTest.kt`.

두 프로브 모두 **현재 수집기**로 현행 실행을 재생성하고 커밋된 산출물과 대조한다. 지난 실행의 산출물은
그 시점 수집기의 측정이라 지금 코드로 다시 만들 수 없다 — 증거로 동결하고, 현행 보고서가 그것을 읽어
비교한다(V2 는 현행 보고서를 프로브에서 재생성해 대조하므로 손으로 고친 수치는 여전히 걸린다).
코드 트랙 `-003` 은 수집 범위를 작업 트리가 아니라 **고정 revision 의 blob 에서 재구성**해 측정한다 —
수집기를 고치면 작업 트리의 `backend/src/main/kotlin` 이 곧 바뀌기 때문이다.

## 재현

```bash
pip install jsonschema
pip install -e codegraph                      # tree-sitter 수집기 의존성

# 1) 프로브 재실행 + 커밋된 산출물 표류 검사 (모든 명령은 리포 루트에서 실행한다)
#    서브셸로 격리한다 — `cd backend && ... && cd ..` 는 gradle 이 실패하면 backend 에 남아
#    이후 docs/... 경로가 전부 어긋난다.
( cd backend && ./gradlew test --tests 'com.ontostudio.rdb.L0DbSourceProbeTest' )
python3 docs/superpowers/specs/bench/l0/probe_code.py --check

# 2) 보고서 재생성 (프로브에서 결정적으로 파생된다 — diff 가 나오면 근거가 표류했다)
python3 docs/superpowers/specs/bench/l0/build_report.py
git diff --exit-code docs/superpowers/specs/bench/l0/runs

# 3) 증거 적합성 확인
python3 docs/superpowers/specs/bench/l0/verify_l0.py
# 31 cases, 0 mismatches

# 4) 계측기 자체의 테스트 (실측 없이 합성 입력으로 돈다)
python3 -m pytest docs/superpowers/specs/bench/l0/test_bench_l0.py -q
```

새 runId 를 처음 만들 때만 DB 프로브를 부트스트랩한다 — 그 외에는 커밋된 산출물이 없으면 테스트가 실패한다.

```bash
( cd backend && ./gradlew test --tests '*L0DbSourceProbeTest' -DL0_PROBE_BOOTSTRAP=true )
```

프로브를 다시 돌려 수치가 달라지면 보고서를 덮어쓰지 않고 **새 runId 로 새 보고서를 남긴다**(I3 §5.5).
#88 때는 `determinismObserved` 가 프로세스마다 달라져 표류 검사에서 제외했지만, #112 로 그 원인이
사라져 예외를 없앴다 — 이제 `--check` 는 산출물 전체의 표류에 더해 **결정성 1.0** 과
`determinismControl.seedIndependent`(PYTHONHASHSEED 를 바꿔도 동일)를 요구한다.
