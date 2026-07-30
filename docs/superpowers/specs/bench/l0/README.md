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
runs/run-l0-code-3c27259-001/   probe-code.json · report.json
```

DB 트랙 프로브는 수집기가 Kotlin 이므로 백엔드 테스트가 겸한다 —
`backend/src/test/kotlin/com/ontostudio/rdb/L0DbSourceProbeTest.kt`.

## 재현

```bash
pip install jsonschema
pip install -e codegraph                      # tree-sitter 수집기 의존성

# 1) 프로브 재실행 + 커밋된 산출물 표류 검사
cd backend && ./gradlew test --tests 'com.ontostudio.rdb.L0DbSourceProbeTest' && cd ..
python3 docs/superpowers/specs/bench/l0/probe_code.py --check

# 2) 보고서 재생성 (프로브에서 결정적으로 파생된다 — diff 가 나오면 근거가 표류했다)
python3 docs/superpowers/specs/bench/l0/build_report.py
git diff --exit-code docs/superpowers/specs/bench/l0/runs

# 3) 증거 적합성 확인
python3 docs/superpowers/specs/bench/l0/verify_l0.py
# 20 cases, 0 mismatches
```

프로브를 다시 돌려 수치가 달라지면 보고서를 덮어쓰지 않고 **새 runId 로 새 보고서를 남긴다**(I3 §5.5).
`determinismObserved` 블록만은 프로세스마다 값이 달라지므로 표류 검사에서 제외한다 — 대신 같은 프로브가
`determinismRootCause`(시드 통제 실험)를 남기고 확인기가 그 재현을 요구한다.
