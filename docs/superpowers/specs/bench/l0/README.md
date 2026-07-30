# L0 Source 벤치 (#88)

고정 revision `3c27259` 의 입력으로 **기존 수집기**를 돌려 I1 §4.1 의 L0 무조건 게이트를 측정한 증거다.
새 수집기를 만들지 않고, 있는 것을 재기만 한다. 계약·판정·발견은
[`../../2026-07-30-m0-l0-source-validation.md`](../../2026-07-30-m0-l0-source-validation.md) 에 있다.

```
probe_code.py     코드 트랙 프로브 (lodestar_codegraph 를 서브프로세스로 실행)
build_report.py   프로브 산출물 → Run Quality Report v0 (프로브의 순수 함수)
verify_l0.py      커밋된 증거의 적합성 확인기 V1~V10 + 결함 주입 20케이스
manifest.json     규칙 범위·케이스 총계 고정
runs/run-l0-db-3c27259-001/     probe-db.json · report.json
runs/run-l0-code-3c27259-001/   probe-code.json · report.json  (#88 실측 — 결정성 0.3333 · H1)
runs/run-l0-code-3c27259-002/   probe-code.json · report.json  (#112 재측정 — 결정성 1.0 · 현행)
```

코드 트랙의 **현행 실행은 002** 다(`build_report.RUNS` · `probe_code.RUN_DIR`). 001 은 기준선으로 남겨
002 가 `baseline.previous` 로 인용한다 — 덮어쓰지 않는다(I3 §5.5).

DB 트랙 프로브는 수집기가 Kotlin 이므로 백엔드 테스트가 겸한다 —
`backend/src/test/kotlin/com/ontostudio/rdb/L0DbSourceProbeTest.kt`.

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
# 24 cases, 0 mismatches
```

새 runId 를 처음 만들 때만 DB 프로브를 부트스트랩한다 — 그 외에는 커밋된 산출물이 없으면 테스트가 실패한다.

```bash
( cd backend && ./gradlew test --tests '*L0DbSourceProbeTest' -DL0_PROBE_BOOTSTRAP=true )
```

프로브를 다시 돌려 수치가 달라지면 보고서를 덮어쓰지 않고 **새 runId 로 새 보고서를 남긴다**(I3 §5.5).
#88 때는 `determinismObserved` 가 프로세스마다 달라져 표류 검사에서 제외했지만, #112 로 그 원인이
사라져 예외를 없앴다 — 이제 `--check` 는 산출물 전체의 표류에 더해 **결정성 1.0** 과
`determinismControl.seedIndependent`(PYTHONHASHSEED 를 바꿔도 동일)를 요구한다.
