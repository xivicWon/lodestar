# L0 Source 벤치 (#88 baseline · #112·#114 재측정 · #125 입력 축 재고정)

gold 가 고정한 **L0 수집 입력 축**(`probeAxis.revision` = `aad4382`)의 입력으로 수집기를 돌려
I1 §4.1 의 L0 무조건 게이트를 측정한 증거다. `-3c27259-` 실행들은 그 축이 생기기 전, gold 정답 축을
입력으로 쓰던 시절의 측정이며 **보존한다**(I3 §5.5).
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
runs/run-l0-db-3c27259-002/     probe-db.json · report.json    (#114 재측정 — 보고율 1.0)
runs/run-l0-db-3c27259-003/     probe-db.json · report.json    (#115 재측정 — 수집기에 마스킹 단계 · 수치 변화 없음)
runs/run-l0-db-3c27259-004/     probe-db.json · report.json    (#115 경계 문자 통합 수정 — 수치 변화 없음)
runs/run-l0-db-aad4382-001/     probe-db.json · report.json    (#125 입력 축 재고정 후 재측정)
runs/run-l0-db-aad4382-002/     probe-db.json · report.json    (#126 수집 모델에 소속(schema) 신설 —
                                                               수치 변화 없음 · 현행)
runs/run-l0-code-3c27259-001/   probe-code.json · report.json  (#88 실측 — 결정성 0.3333 · H1)
runs/run-l0-code-3c27259-002/   probe-code.json · report.json  (#112 재측정 — 결정성 1.0)
runs/run-l0-code-3c27259-003/   probe-code.json · report.json  (#114 재측정 — 보고율 1.0)
runs/run-l0-code-aad4382-001/   probe-code.json · report.json  (#125 입력 축 재고정 후 재측정 · 현행 —
                                                               메타데이터 5/5 PASS 가 이 실행에 기록된다)

test_bench_l0.py                계측기 자체의 단위 테스트 (합성 입력)
metadata_completeness.py        #113 게이트 재측정 (코드 트랙 실측 + DB 트랙 결과 확인)
metadata/completeness-{db,code}.json   그 결과```

**현행 실행**은 db 가 `aad4382-002`, code 가 `aad4382-001` 이다
(`build_report.RUNS` · `probe_code.RUN_DIR`). 두 트랙의 runId 가 갈린 것은 #126 이 DB 수집기만
고쳤기 때문이다 — 입력 축은 둘 다 `aad4382` 로 같다. 각 트랙의
직전 실행이 `PREVIOUS` 이며 새 보고서가 그것을 `baseline.previous` 로 인용한다 — 덮어쓰지 않는다(I3 §5.5).
현행 두 실행은 gold 입력 축이 아직 **미승인**(PROPOSED)이라 `eligibleAsBaseline: false` 이고
`GOLD_UNAPPROVED` 경고를 싣는다 — 승인 전에는 다음 실행의 비교 기준선이 아니다(I3 R12 · I1 §7).

DB 트랙 프로브는 수집기가 Kotlin 이므로 백엔드 테스트가 겸한다 —
`backend/src/test/kotlin/com/ontostudio/rdb/L0DbSourceProbeTest.kt`.

두 프로브 모두 **현재 수집기**로 현행 실행을 재생성하고 커밋된 산출물과 대조한다. 지난 실행의 산출물은
그 시점 수집기의 측정이라 지금 코드로 다시 만들 수 없다 — 증거로 동결하고, 현행 보고서가 그것을 읽어
비교한다(V2 는 현행 보고서를 프로브에서 재생성해 대조하므로 손으로 고친 수치는 여전히 걸린다).
코드 트랙은 `-003` 부터 수집 범위를 작업 트리가 아니라 **고정 revision 의 blob 에서 재구성**해 측정한다 —
수집기를 고치면 작업 트리의 `backend/src/main/kotlin` 이 곧 바뀌기 때문이다. `aad4382-001` 은 그 revision 을
gold 의 **입력 축**에서 읽는다(정답 축이 아니다 — I2 §6).

## 재현

```bash
pip install jsonschema
pip install -e codegraph                      # tree-sitter 수집기 의존성

# 1) 프로브 재실행 + 커밋된 산출물 표류 검사 (모든 명령은 리포 루트에서 실행한다)
#    서브셸로 격리한다 — `cd backend && ... && cd ..` 는 gradle 이 실패하면 backend 에 남아
#    이후 docs/... 경로가 전부 어긋난다.
( cd backend && ./gradlew test --tests 'com.ontostudio.rdb.L0DbSourceProbeTest' )
# 현행 실행은 **main 워킹트리에서 그린이어야 한다**(#125 로 입력 축을 재고정해 그렇게 됐다).
# 실패하면 입력(backend/src/main/kotlin)이나 수집기가 축 이후로 움직인 것이다 — 그때는 새 runId 로 남긴다.
python3 docs/superpowers/specs/bench/l0/probe_code.py --check

# 2) 보고서 재생성 (프로브에서 결정적으로 파생된다 — diff 가 나오면 근거가 표류했다)
python3 docs/superpowers/specs/bench/l0/build_report.py
git diff --exit-code docs/superpowers/specs/bench/l0/runs

# 3) 증거 적합성 확인 (워킹트리와 무관 — 커밋된 산출물만 읽는다)
python3 docs/superpowers/specs/bench/l0/verify_l0.py
# 35 cases, 0 mismatches   (= bench/l0/manifest.json 의 caseCount. #88 의 24 는 #112 가 V12~V13 을,
#                            #114 가 V14 를, #125 가 입력 축·승인 경고 케이스 4건을 더하며 35 로 올렸다 —
#                            manifest 가 정본이고 확인기가 대조한다)

# 4) 계측기 자체의 테스트 (실측 없이 합성 입력으로 돈다)
python3 -m pytest docs/superpowers/specs/bench/l0/test_bench_l0.py -q```

새 runId 를 처음 만들 때만 DB 프로브를 부트스트랩한다 — 그 외에는 커밋된 산출물이 없으면 테스트가 실패한다.

```bash
( cd backend && ./gradlew test --tests '*L0DbSourceProbeTest' -DL0_PROBE_BOOTSTRAP=true )
```

프로브를 다시 돌려 수치가 달라지면 보고서를 덮어쓰지 않고 **새 runId 로 새 보고서를 남긴다**(I3 §5.5).
#88 때는 `determinismObserved` 가 프로세스마다 달라져 표류 검사에서 제외했지만, #112 로 그 원인이
사라져 예외를 없앴다 — 이제 `--check` 는 산출물 전체의 표류에 더해 **결정성 1.0** 과
`determinismControl.seedIndependent`(PYTHONHASHSEED 를 바꿔도 동일)를 요구한다.

## 기존 실행의 재현 조건

코드 트랙 프로브의 **입력이 `backend/src/main/kotlin` 그 자체**다. 그래서 L0-fix 로 백엔드 코드가
바뀌면 그 이전 실행은 워킹트리에서 재현되지 않는다 — 고장이 아니라 그 프로브가 **입력 신원을
검사하고 있다는 증거**다. 기존 실행을 재현하려면 **그 실행을 만든 커밋**을 꺼낸다. 입력만이 아니라
수집기까지 그 시점이어야 한다 — run-001 은 `lodestar-codegraph@0.1.0`, run-002 는 `0.1.1` 이 잰 것이다.

```bash
RUN_COMMIT=3944e50            # 그 실행을 만든 커밋 (run-002 는 #112 머지 커밋)
git worktree add /tmp/l0-run "$RUN_COMMIT"
python3 -m venv /tmp/l0-run-venv               # 격리된 인터프리터에서 돌린다
/tmp/l0-run-venv/bin/pip install -q -e /tmp/l0-run/codegraph
( cd /tmp/l0-run && /tmp/l0-run-venv/bin/python docs/superpowers/specs/bench/l0/probe_code.py --check )
```

venv 를 쓰는 이유: 현재 워킹트리에서 `pip install -e codegraph` 를 해 두면 editable 설치의 import
훅이 `sys.path` 보다 먼저 걸려, **역사적 입력에 현재 수집기**를 물릴 수 있다. 그러면 재현이 아니다.

커밋된 증거 자체의 적합성(`verify_l0.py`)은 워킹트리와 무관하다 — 커밋된 산출물만 읽으므로
현재 브랜치에서도 그대로 35 cases / 0 mismatches 여야 한다.

### 코드 트랙 재측정과 gold 입력 축 (#125 — 해소)

#113~#115 동안 `probe_code.py --check` 는 main 에서 상시 실패했다. 원인은 프로브의 입력 revision 이
gold 의 **정답 축**(`sourceRevision` = 3c27259)에 묶여 있었다는 것이다 — 그 축을 옮기려면 `l1/code.json`
의 닫힌 범위(전수 등재된 L1 코드 정답)까지 함께 옮겨야 해서, L0 재측정이 L1 정답 재열거를 인질로 잡고
있었다.

#125 로 gold 에 **L0 수집 입력 축**(`probeAxis.revision` = `aad4382`)을 신설해 그 매듭을 풀었다. 정답 축은
승인된 3c27259 에 그대로 있고, "L0 이 무엇을 입력으로 쟀는가" 만 새 축이 고정한다(I2 §6 · §14 R1).
그 결과:

- `probe_code.py --check` 가 **main 워킹트리에서 그린**으로 돌아왔다.
- `maskingCapability.exists` 가 `false → true` 로 뒤집힌 사실(#115)이 현행 코드 실행에 증거로 남는다.
  다만 `gate-security-masking` 은 여전히 FAIL 이다 — gold 코퍼스의 PII 양성 28건이 전부
  `.sql/.properties/.log` 라 코드 수집기가 읽는 확장자 밖이고(walked=0), 마스킹 **동작**은 이 gold 로
  잴 수 없다. 미측정을 통과로 적지 않는다(gold 픽스처 보강은 I2 개정 안건으로 남아 있다).
- `gate-l0-metadata-completeness` 5/5 PASS 가 별도 측정이 아니라 **현행 보고서의 게이트**로 기록된다.

입력 축은 아직 **승인 전(PROPOSED)** 이다. 그래서 현행 두 실행은 `eligibleAsBaseline: false` +
`GOLD_UNAPPROVED` 경고를 달고 있고, 승인되면 그 산식이 바뀌므로 **새 runId 로 다시 남긴다**(I3 §5.5).

`metadata_completeness.py` 는 계속 별도로 돈다. 프로브는 *고정 입력의 실측*, 이쪽은 *지금 수집기가
계약을 지키는가* 로 목적이 다르다 — 후자는 워킹트리를 직접 재므로 입력 축과 무관하게 움직인다.

## #113 게이트 재측정

`gate-l0-metadata-completeness` 하나만 다시 잰다. **#88 의 baseline 산출물은 손대지 않는다.**

```bash
( cd backend && ./gradlew test --tests '*L0DbMetadataCompletenessTest' )   # DB 트랙
python3 docs/superpowers/specs/bench/l0/metadata_completeness.py           # 코드 트랙 + 두 트랙 판정
# [ok] gate-l0-metadata-completeness — db 5/5 · code 5/5
```

최초 생성은 각각 `-DL0_METADATA_BOOTSTRAP=true` · `--bootstrap` 이다. 두 결과의 `volatile` 블록은
입력 내용·리비전에 따라 달라지므로 표류 검사에서 제외한다. 기준을 갱신할 때만 `--force` 를 쓴다 —
#125 에서 코드 트랙 결과를 한 번 갱신했다(#113 측정 이후 #115 가 `meta.masking` 을 더하고 범위 파일이
60→62 로 늘어 표류하고 있었다. 완전성은 그대로 5/5 다).

L0 **전체 판정**은 여전히 `BLOCKED` 이다 — 결정성(#112)·오류 가시성(#114)·메타데이터(#113)는 현행
실행에서 모두 PASS 지만 보안 게이트(H2)가 남아 있다. 그 게이트를 움직이려면 코드 수집 확장자 안에
PII 양성을 둔 gold 픽스처가 필요하고(I2 개정 안건), 그 뒤 **새 runId 로 전 트랙을 다시 재는** 실행이
있어야 한다.
