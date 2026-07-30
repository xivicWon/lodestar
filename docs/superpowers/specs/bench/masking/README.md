# 마스킹 벤치 (#115) — 재현 절차

마스킹 단계가 **무엇을 몇 건 가렸는가**를 증거에서 산출한다. 규칙은 리포 단일 원본
[`specs/security/masking-rules.v0.json`](../../security/masking-rules.v0.json) 이 정하고, 두 엔진
(Kotlin `com.ontostudio.security.MaskingEngine` · Python `lodestar_codegraph.mask`)이 그 사본을 읽는다.

## 1. 증거 생성

```bash
# (a) Kotlin 엔진 증거 + DB 적재 경로 증거 — 백엔드 테스트가 겸한다
(cd backend && ./gradlew test)                 # 증거가 표류하면 붉어진다
# 최초 생성/의도한 갱신일 때만:
(cd backend && ./gradlew test -DMASK_EVIDENCE_BOOTSTRAP=true) \
  && cp backend/build/masking/engine-kotlin.json docs/superpowers/specs/bench/masking/runs/run-mask-gold-001/ \
  && cp backend/build/masking/ingest-db.json     docs/superpowers/specs/bench/masking/runs/run-mask-ingest-001/

# (b) Python 엔진 증거 + 코드 산출 경로 증거
python3 docs/superpowers/specs/bench/masking/probe_masking.py
python3 docs/superpowers/specs/bench/masking/probe_masking.py --check   # 표류 검사

# (c) 보고서 — 증거의 순수 함수
python3 docs/superpowers/specs/bench/masking/build_masking_report.py            # 결과가 다르면 실패
python3 docs/superpowers/specs/bench/masking/build_masking_report.py --update   # 의도한 갱신
python3 docs/superpowers/specs/bench/masking/build_masking_report.py --check
```

## 2. 확인기

```bash
python3 docs/superpowers/specs/bench/masking/verify_masking.py
# 10 rules, 26 cases, 0 mismatches   (= manifest.json 의 ruleRange·caseCount)
```

규칙 M1~M10 과 결함 주입 26케이스는 [`verify_masking.py`](verify_masking.py) 상단에 선언돼 있고,
판정·정책·잔여 위험은 [`specs/2026-07-30-m0-l0-fix5-masking.md`](../../2026-07-30-m0-l0-fix5-masking.md)
에 있다.

## 3. 증거 파일

| 파일 | 무엇의 증거 |
|---|---|
| `runs/run-mask-gold-001/engine-kotlin.json` | Kotlin 엔진이 gold 코퍼스에서 만든 스팬·마스킹 결과 해시 |
| `runs/run-mask-gold-001/engine-python.json` | 같은 실행의 Python 엔진 결과 (두 증거의 일치 = M2) |
| `runs/run-mask-gold-001/gold-verdicts.json` | gold 항목 44건의 항목별 판정(양성 28 · 음성 16) |
| `runs/run-mask-ingest-001/ingest-db.json` | DB 적재·DDL 텍스트 경로의 마스킹 집계와 컬럼별 관측 |
| `runs/run-mask-code-001/emit-code.json` | codegraph 산출 단계(emit)의 마스킹 관문 관측 |
| `report.json` | 위 증거에서 파생된 마스킹 실행 보고서 |

증거에는 **원문을 적지 않는다**(#85) — 좌표·규칙 id·클래스·건수·해시만 남기며, 그것을
확인기 M9 가 전수 대조한다.

> 이 벤치는 Run Quality Report(I3)를 산출하지 않는다. L0 레이어 판정은 #88 의 보고서가 유지하며,
> 재측정은 gold `sourceRevision` 재고정과 승인이 선행된다(I2 §10.4 · I1 §7.4).
