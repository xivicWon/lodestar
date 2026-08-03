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
verify_l0.py      커밋된 증거의 적합성 확인기 V1~V15 + 결함 주입 40케이스
test_bench_l0.py  **계측기 자체의 단위 테스트** — 귀속·게이트 산식·확인기 규칙이 거짓을 무는가
manifest.json     규칙 범위·케이스 총계 고정
runs/run-l0-db-3c27259-001/     probe-db.json · report.json    (#88 실측 — 보고율 0.0)
runs/run-l0-db-3c27259-002/     probe-db.json · report.json    (#114 재측정 — 보고율 1.0)
runs/run-l0-db-3c27259-003/     probe-db.json · report.json    (#115 재측정 — 수집기에 마스킹 단계 · 수치 변화 없음)
runs/run-l0-db-3c27259-004/     probe-db.json · report.json    (#115 경계 문자 통합 수정 — 수치 변화 없음)
runs/run-l0-db-aad4382-001/     probe-db.json · report.json    (#125 입력 축 재고정 후 재측정)
runs/run-l0-db-aad4382-002/     probe-db.json · report.json    (#126 수집 모델에 소속(schema) 신설 ·
                                                               프로브 v4 가 그 필드를 정규화에 포함 —
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

아래가 **정본 재현 절차**다. `.github/workflows/verify.yml` 이 PR·main push 에서 이 명령을 글자 그대로
돌린다(#124). 둘이 갈라지면 CI 그린이 재현을 보장하지 않으므로, 그 동일성은
[`../ci/verify_ci.py`](../ci/verify_ci.py) 의 W3 이 검사한다 — 아래 블록의 `<!-- ci-parity -->` 표시가
그 대조 대상이라는 뜻이다. **명령을 고치면 워크플로도 같이 고쳐야 한다**(안 고치면 CI 가 붉어진다).

모든 명령은 리포 루트에서 실행한다. 서브셸로 격리한다 — `cd backend && ... && cd ..` 는 gradle 이
실패하면 backend 에 남아 이후 `docs/...` 경로가 전부 어긋난다.

<!-- ci-parity -->
```bash
pip install jsonschema pyyaml pytest
pip install -e codegraph                      # tree-sitter 수집기 의존성

# 1) 코드 트랙 수집기 + 프로브 재실행·표류 검사
#    현행 실행은 **main 워킹트리에서 그린이어야 한다**(#125 로 입력 축을 재고정해 그렇게 됐다).
#    실패하면 입력(backend/src/main/kotlin)이나 수집기가 축 이후로 움직인 것이다 — 그때는 새 runId 로 남긴다.
( cd codegraph && python3 -m pytest -q )
python3 docs/superpowers/specs/bench/l0/probe_code.py --check

# 2) 보고서 재생성 (프로브에서 결정적으로 파생된다 — diff 가 나오면 근거가 표류했다)
python3 docs/superpowers/specs/bench/l0/build_report.py
git diff --exit-code docs/superpowers/specs/bench/l0/runs

# 3) 증거 적합성 확인 (워킹트리와 무관 — 커밋된 산출물만 읽는다)
python3 docs/superpowers/specs/bench/l0/verify_l0.py
# 40 cases, 0 mismatches   (= bench/l0/manifest.json 의 caseCount)
#   내역: 24(#88) + 5(#112 V12~V13) + 2(#114 V14) + 4(#125 입력 축·승인 경고)
#         + 5(#123 V15 — 범위 선언 · 다른 환경에서 측정 · 판정 안 한 조건부 의존성
#            · 선언 블록 누락 · 수집기 신원 없는 선언) = 40
#   숫자를 생략하면 합이 맞는지 읽는 쪽이 검산할 수 없다. manifest 가 정본이고 확인기가
#   실제 케이스 수와 대조하므로, 이 주석이 틀리면 주석만 틀린 것이다.

# 4) 계측기 자체의 테스트 (실측 없이 합성 입력으로 돈다)
python3 -m pytest docs/superpowers/specs/bench/l0/test_bench_l0.py -q
python3 docs/superpowers/specs/bench/l0/metadata_completeness.py

# 5) 마스킹 증거 (#115)
python3 docs/superpowers/specs/bench/masking/probe_masking.py --check
python3 docs/superpowers/specs/bench/masking/build_masking_report.py --check
python3 docs/superpowers/specs/bench/masking/verify_masking.py

# 6) 계약 스키마·픽스처·문서 수치 정합
python3 docs/superpowers/specs/schemas/validate.py
python3 docs/superpowers/specs/schemas/validate_rqr.py
python3 docs/superpowers/specs/schemas/fuzz.py
python3 docs/superpowers/specs/schemas/sweep.py
python3 docs/superpowers/specs/verify_i1_counts.py

# 7) 게이트가 CI 에 실제로 걸려 있는가 (자동 실행 계약 자신 — W1~W6)
python3 docs/superpowers/specs/bench/ci/verify_ci.py

# 8) DB 트랙 — L0 DB 프로브를 겸하는 백엔드 스위트
( cd backend && ./gradlew test )
```

DB 프로브만 좁혀 돌리려면 `( cd backend && ./gradlew test --tests 'com.ontostudio.rdb.L0DbSourceProbeTest' )`
로 줄일 수 있다. 다만 CI 는 전체 스위트를 돌린다 — 좁힌 실행이 그린이라고 전체가 그린은 아니다.

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
현재 브랜치에서도 그대로 40 cases / 0 mismatches 여야 한다.

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

## 런타임 의존성 고정과 교차 버전 확인 (#123)

`codegraph.json` 의 바이트는 수집기 코드만으로 정해지지 않는다. 군집 배정은
`networkx.community.louvain_communities` 가 만들고, 파스 트리는 tree-sitter 문법이 만든다. #112 가
없앤 것은 **같은 환경 안에서** 프로세스마다 갈리는 비결정(PYTHONHASHSEED)이고, **환경이 달라질 때의
재현성**은 선언으로만 막힌다 — 그런데 `versions.collector: PINNED` 도 `probe_code.py --check` 의
바이트 대조도 의존성 버전은 보지 않는다. 그 사각지대를 닫은 것이 #123 이다.

- 정책: `codegraph/pyproject.toml` 의 **런타임 의존성은 전부 `==` 고정**이다(상한 있는 범위도 쓰지
  않는다 — 상한 안에서 구현이 바뀔 자리가 남는다). 정책 구현은 `codegraph/src/lodestar_codegraph/deps.py`,
  검사는 `codegraph/tests/test_deps.py`.
- 기록: 프로브의 `collector.dependencies` 블록에 **선언**이 실린다(`dependencyPins` ·
  `unpinnedDependencies` · `conditionalDependencies` · `installedMatchesDeclared`). 설치된 버전
  문자열은 싣지 않는다 — 그것을 실으면 환경마다 산출물 바이트가 달라져 표류 검사와 충돌한다.
  마커가 붙어 이 환경에서 설치 여부를 판정하지 않은 선언은 `conditionalDependencies` 로 남는다:
  마커를 평가하지 않은 채 '설치 없음' 으로 세면 정상 환경이 불일치로 뒤집히고, 조용히 건너뛰면
  고정되지 않은 의존성이 검사 밖으로 사라진다.
- 확인: `verify_l0.py` **V15** 가 커밋된 증거에서 이 선언을 검사한다 — 판정은 프로브의 순수 함수
  `environment_errors()` 를 그대로 쓴다(규칙을 두 번 쓰면 `--check` 와 확인기의 통과 기준이 갈린다).
  결함 주입 5건: 범위 선언 · 선언과 다른 환경에서 측정 · 판정하지 않은 조건부 의존성 ·
  선언 블록 누락 · 수집기 신원 없이 남은 선언.
- 설치 방식과 무관: 선언은 소스 트리의 `pyproject.toml` 이 정본이고, 소스 트리 밖(휠 설치)에서는
  **이 모듈을 담고 있는 설치본**의 `Requires-Dist` 를 읽는다(`provenance._version()` 과 같은 순서).
  같은 이름의 다른 설치본의 선언은 쓰지 않는다 — 남의 선언을 재현 대상으로 적으면 그 기록은 이
  산출물을 만든 코드를 가리키지 않는다.

`run-l0-code-aad4382-001` 의 `probe-code.json` 은 이 선언 블록이 더해지면서 갱신됐다. **측정은 그대로**
이며(결정성 1.0 · 인벤토리 · 귀속 전부 동일, diff 는 `collector.dependencies` 추가 13줄뿐) 보고서는
바이트가 바뀌지 않아 새 runId 를 만들지 않았다.

### 다른 networkx 버전에서 산출물이 달라지는가

의존성을 올릴 때(또는 올려도 되는지 볼 때) 돌린다. 워킹트리의 인터프리터를 건드리지 않도록 venv 로
격리하고, 입력은 gold 입력 축의 blob 에서 재구성한다 — 작업 트리를 입력으로 쓰면 수집기를 고치는
순간 비교의 두 항이 함께 움직인다.

```bash
WORK=$(mktemp -d)
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install -q -e codegraph          # 고정 버전이 설치된다
mkdir -p "$WORK/scope"
git archive aad4382 backend/src/main/kotlin | tar -x -C "$WORK/scope"   # gold probeAxis.revision

canon() {  # meta.source_root 만 뺀 정규화 해시 — probe_code.canonical 과 같은 규칙이다
  python3 -c 'import json,hashlib,sys; d=json.load(open(sys.argv[1])); d["meta"].pop("source_root",None);
print(hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest())' "$1"
}

"$WORK/venv/bin/python" -m lodestar_codegraph "$WORK/scope/backend/src/main/kotlin" -o "$WORK/pinned.json"
"$WORK/venv/bin/pip" install -q "networkx==3.1"       # 비교할 다른 버전
"$WORK/venv/bin/python" -m lodestar_codegraph "$WORK/scope/backend/src/main/kotlin" -o "$WORK/other.json"
diff <(canon "$WORK/pinned.json") <(canon "$WORK/other.json") && echo "동일" || echo "산출물이 달라진다"
```

**실측(2026-08-03, 입력 축 `aad4382`)**: networkx `3.6.1` 과 `3.1` 의 정규화 해시가
`sha256:c50c10f6013a2f1218e71bc8b344002399a1710f489d20b7dbd59efbb7f9af89` 로 **같았다**(노드 410 ·
엣지 865 · 군집 29).

**다만 그 결론은 이 입력에만 해당한다.** 같은 비교를 프로브 전체(범위 + 실패 픽스처 + PII 코퍼스)로
돌리면 networkx `3.1` 은 산출물이 다른 정도가 아니라 **아예 죽는다**:

```
File ".../networkx/algorithms/community/quality.py", line 240, in modularity
    norm = 1 / deg_sum**2
ZeroDivisionError: division by zero
```

엣지가 하나도 없는 입력(수집 대상 확장자가 없는 PII 코퍼스, 단일 파일 픽스처)에서 `louvain_communities`
가 빈 그래프를 처리하지 못한다. 3.6.1 은 같은 입력에서 정상적으로 군집 0건을 낸다. 즉 `networkx>=3.0`
이라는 범위 선언은 **이미 거짓이었다** — 이슈가 인용한 "#112 리뷰에서 두 버전의 산출물이 같았다" 는
관측은 엣지가 있는 하나의 입력에서만 성립한다. 이 사실이 고정의 근거를 강하게 만든다.

그래서 선언과 다른 환경에서는 프로브가 **수집기를 돌리기 전에** 멈춘다.

```
$ /tmp/other-venv/bin/python docs/superpowers/specs/bench/l0/probe_code.py --check
[FAIL] 측정 환경이 선언한 고정과 다르다: ['networkx: 선언 3.6.1 / 설치 3.1'] — 표류의 원인이
코드가 아니라 환경이다. `pip install -e codegraph` 로 맞춘다
```

판정은 `probe_code.environment_errors()` 라는 순수 함수이고(`determinism_errors` 와 같은 이유 —
`main(--check)` 안에만 두면 그 판정 자체는 아무도 검사하지 않는다), 확인기 V15 가 커밋된 증거에 같은
함수를 건다. 같은 venv 에서 `"$WORK/venv/bin/python" -m lodestar_codegraph.deps` 를 돌리면 불일치 항목을 그대로
볼 수 있다. 임시 venv 는 `$WORK` 째로 버리면 되고, 별도 정리가 필요 없다. 다만 비교하느라 **메인
환경**의 버전을 바꿨다면(위 절차는 그러지 않는다) 리포 루트에서 `pip install -e codegraph` 로
되돌린다 — 이 한 줄만 venv 접두어가 없는 이유다.

의존성을 올려 산출물이 달라지면 그때는 의존성 인상이 곧 산출물 변경이므로 새 runId 로 재측정한다
(I3 §5.5).

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
