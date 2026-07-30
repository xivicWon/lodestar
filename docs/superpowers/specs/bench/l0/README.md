# L0 Source 벤치 (#88 baseline · #114 재측정)

고정 revision `3c27259` 의 입력으로 수집기를 돌려 I1 §4.1 의 L0 무조건 게이트를 측정한 증거다.
계약·판정·발견은 [`../../2026-07-30-m0-l0-source-validation.md`](../../2026-07-30-m0-l0-source-validation.md)
(#88 baseline)과 [`../../2026-07-30-m0-l0-fix-error-visibility.md`](../../2026-07-30-m0-l0-fix-error-visibility.md)
(#114 오류 가시성 수정 후 재측정)에 있다.

실행 집합은 둘이다: `-001` = 수정 전 기준선, `-002` = 같은 고정 입력으로 다시 잰 실측. 이전 실행은
덮어쓰지 않고 새 runId 로 남긴다(I3 §5.5) — 확인기는 두 집합을 각각 검증한다.

```
probe_code.py     코드 트랙 프로브 (lodestar_codegraph 를 서브프로세스로 실행)
build_report.py   프로브 산출물 → Run Quality Report v0 (프로브의 순수 함수)
verify_l0.py      커밋된 증거의 적합성 확인기 V1~V12 + 결함 주입 26케이스 (두 실행 집합)
manifest.json     규칙 범위·케이스 총계 고정
runs/run-l0-db-3c27259-001/     probe-db.json · report.json   (baseline · #88)
runs/run-l0-code-3c27259-001/   probe-code.json · report.json (baseline · #88)
runs/run-l0-db-3c27259-002/     probe-db.json · report.json   (l0fix · #114)
runs/run-l0-code-3c27259-002/   probe-code.json · report.json (l0fix · #114)
```

DB 트랙 프로브는 수집기가 Kotlin 이므로 백엔드 테스트가 겸한다 —
`backend/src/test/kotlin/com/ontostudio/rdb/L0DbSourceProbeTest.kt`.

두 프로브 모두 **현재 수집기**로 `-002` 를 재생성하고 커밋된 산출물과 대조한다. `-001` 산출물은 그 시점
수집기의 측정이라 지금 코드로 다시 만들 수 없다 — 증거로 동결하고 확인기가 계속 검증한다(V2 는 보고서를
프로브에서 재생성해 대조하므로 손으로 고친 수치는 여전히 걸린다). 코드 트랙 `-002` 는 수집 범위를
작업 트리가 아니라 **고정 revision 의 blob 에서 재구성**해 측정한다.

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
# 26 cases, 0 mismatches
```

새 runId 를 처음 만들 때만 DB 프로브를 부트스트랩한다 — 그 외에는 커밋된 산출물이 없으면 테스트가 실패한다.

```bash
( cd backend && ./gradlew test --tests '*L0DbSourceProbeTest' -DL0_PROBE_BOOTSTRAP=true )
```

프로브를 다시 돌려 수치가 달라지면 보고서를 덮어쓰지 않고 **새 runId 로 새 보고서를 남긴다**(I3 §5.5).
`determinismObserved` 블록만은 프로세스마다 값이 달라지므로 표류 검사에서 제외한다 — 대신 같은 프로브가
`determinismRootCause`(시드 통제 실험)를 남기고 확인기가 그 재현을 요구한다.
