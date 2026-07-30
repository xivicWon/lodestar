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

metadata_completeness.py        #113 게이트 재측정 (코드 트랙 실측 + DB 트랙 결과 확인)
metadata/completeness-{db,code}.json   그 결과
```

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
`determinismObserved` 블록만은 프로세스마다 값이 달라지므로 표류 검사에서 제외한다 — 대신 같은 프로브가
`determinismRootCause`(시드 통제 실험)를 남기고 확인기가 그 재현을 요구한다.

## baseline 프로브의 재현 조건 (#113 이후)

코드 트랙 프로브의 **입력이 `backend/src/main/kotlin` 그 자체**다. 그래서 L0-fix 로 백엔드 코드가
바뀌면 워킹트리에서의 `probe_code.py --check` 는 더 이상 3c27259 를 재지 못하고 실패한다 — 고장이
아니라 그 프로브가 **입력 신원을 검사하고 있다는 증거**다. baseline 을 재현하려면 그 revision 을 꺼낸다.

```bash
git worktree add /tmp/l0-baseline 3c27259
( cd /tmp/l0-baseline && python3 docs/superpowers/specs/bench/l0/probe_code.py --check )
```

커밋된 증거 자체의 적합성(`verify_l0.py`)은 워킹트리와 무관하다 — 커밋된 산출물만 읽으므로
현재 브랜치에서도 그대로 24 cases / 0 mismatches 여야 한다.

## #113 게이트 재측정

`gate-l0-metadata-completeness` 하나만 다시 잰다. **#88 의 baseline 산출물은 손대지 않는다.**

```bash
( cd backend && ./gradlew test --tests '*L0DbMetadataCompletenessTest' )   # DB 트랙
python3 docs/superpowers/specs/bench/l0/metadata_completeness.py           # 코드 트랙 + 두 트랙 판정
# [ok] gate-l0-metadata-completeness — db 5/5 · code 5/5
```

최초 생성은 각각 `-DL0_METADATA_BOOTSTRAP=true` · `--bootstrap` 이다. 두 결과의 `volatile` 블록은
입력 내용·리비전에 따라 달라지므로 표류 검사에서 제외한다.

L0 **전체 판정**은 여전히 `BLOCKED` 이다 — 결정성(H1)·PII 마스킹(H2)·오류 가시성이 남아 있다.
전체 판정을 움직이려면 그것들까지 고친 뒤 **새 runId 로 전 트랙을 다시 재는** 별도 실행이 필요하다.
