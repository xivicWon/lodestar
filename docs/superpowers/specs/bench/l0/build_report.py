#!/usr/bin/env python3
"""#88 L0 Source — 프로브 산출물 → Run Quality Report v0.

보고서는 **프로브 산출물의 순수 함수**다(시각 제외). 손으로 고친 수치가 근거와 어긋나는 경로를
막기 위해, `verify_l0.py` 가 같은 함수로 보고서를 다시 만들어 커밋된 보고서와 대조한다.

    python3 docs/superpowers/specs/bench/l0/build_report.py            # 두 트랙 보고서 생성
    python3 docs/superpowers/specs/bench/l0/build_report.py --stdout db

계약: ../../2026-07-29-m0-i3-run-quality-report-contract.md (I3) · ../../2026-07-30-m0-l0-source-validation.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
GOLD = REPO / "docs/superpowers/specs/gold"
SCHEMAS = REPO / "docs/superpowers/specs/schemas"

PROBE_NAME = {"db": "probe-db.json", "code": "probe-code.json"}
TRACKS = ("db", "code")

# 실행 집합. `baseline`(#88)은 수정 전 수집기의 실측이고 `l0fix`(#114)는 같은 고정 입력으로
# 다시 잰 실측이다. 이전 실행을 덮어쓰지 않고 새 runId 로 남긴다(I3 §5.5) — 그래서 두 집합이
# 나란히 검증된다. 시각은 RFC 3339 축소 프로파일로 못박는다(재생성이 흔들리면 안 된다).
RUN_SETS = {
    "baseline": {
        "db": {"runId": "run-l0-db-3c27259-001",
               "times": ("2026-07-30T09:05:00Z", "2026-07-30T09:07:00Z"),
               "collector": "DdlParser+SampleLegacyDb@3c27259"},
        "code": {"runId": "run-l0-code-3c27259-001",
                 "times": ("2026-07-30T09:10:00Z", "2026-07-30T09:16:00Z"),
                 "collector": "lodestar-codegraph@0.1.0+3c27259"},
    },
    "l0fix": {
        "db": {"runId": "run-l0-db-3c27259-002",
               "times": ("2026-07-30T12:40:00Z", "2026-07-30T12:42:00Z"),
               "collector": None},   # 프로브가 잰 수집기 해시를 그대로 인용한다
        "code": {"runId": "run-l0-code-3c27259-002",
                 "times": ("2026-07-30T12:45:00Z", "2026-07-30T12:51:00Z"),
                 "collector": None},
    },
}
# 이 집합의 각 트랙이 비교하는 이전 실행
PREVIOUS_SET = {"l0fix": "baseline"}

# 하위 호환 별칭 — 기존 호출부(외부 스크립트)가 baseline 집합을 가리킨다.
RUNS = {t: HERE / "runs" / RUN_SETS["baseline"][t]["runId"] for t in TRACKS}
RUN_ID = {t: RUN_SETS["baseline"][t]["runId"] for t in TRACKS}
TIMES = {t: RUN_SETS["baseline"][t]["times"] for t in TRACKS}


def run_dir(run_set: str, track: str) -> pathlib.Path:
    return HERE / "runs" / RUN_SETS[run_set][track]["runId"]


def measurement(status: str, value, note: str) -> dict:
    return {"status": status, "value": value, "note": note}


def probe(track: str, run_set: str = "baseline") -> dict:
    return json.loads((run_dir(run_set, track) / PROBE_NAME[track]).read_text())


def _db_facts(p: dict) -> dict:
    acq = p["acquisition"]
    fixtures = p["failureFixtures"]
    should_report = acq["excluded"] + acq["failed"] + sum(f["expectedReported"] for f in fixtures)
    # 보고 건수는 프로브가 잰 **귀속** 이다. v1 프로브에는 이 자리가 없었으므로(반환형에 채널이
    # 없어 구조적으로 0) 없으면 0 으로 읽는다 — 그것이 그 실행의 측정 결과다.
    reported = acq.get("reported", 0) + sum(f.get("actualReported", 0) for f in fixtures)
    ingest_values = sum(c["retrievableValues"] for c in p["ingestStore"]["piiShapedColumns"])
    return {
        "input": p["statementInventory"]["total"],
        "output": acq["acquired"],
        "failed": acq["failed"],
        "excluded": acq["excluded"],
        "exclusions": acq["exclusions"],
        "determinism": p["determinism"]["rate"],
        "provenance": p["provenance"]["rate"],
        "shouldReport": should_report,
        "reported": reported,
        "partial": acq.get("partial", 0),
        "silentPartialRecovery": sum(
            len(f["unexpectedExtracted"]) for f in fixtures if not f.get("markedAsPartial")),
        "piiPositives": p["pii"]["positives"],
        "piiMasked": p["pii"]["masked"],
        "piiUnmasked": len(p["pii"]["unmaskedInArtifact"]),
        "piiNotCollected": len(p["pii"]["notCollected"]),
        "ingestUnmaskedValues": ingest_values,
    }


def _code_facts(p: dict) -> dict:
    inv = p["inventory"]
    fixtures = p["failureFixtures"]
    return {
        "input": inv["input"],
        "output": inv["parsed"],
        "failed": 0,
        "excluded": inv["excludedByExtensionFilter"],
        "exclusions": inv["exclusions"],
        "determinism": p["determinismObserved"]["rate"],
        "provenance": p["provenance"]["rate"],
        "shouldReport": (inv["excludedByExtensionFilter"] + inv.get("failedReportedByCollector", 0)
                         + sum(f["expectedReported"] for f in fixtures)),
        "reported": inv.get("reported", 0) + sum(f.get("actualReported", 0) for f in fixtures),
        "partial": inv.get("partialReportedByCollector", 0),
        "markedFullySucceeded": sum(1 for f in fixtures if f["markedAsFullySucceeded"]),
        "piiPositives": p["pii"]["positives"],
        "piiMasked": p["pii"]["masked"],
        "piiUnmasked": len(p["pii"]["unmaskedInArtifact"]),
        "piiNotCollected": len(p["pii"]["notCollected"]),
    }


def gates(track: str, p: dict, f: dict) -> list[dict]:
    """I1 §4.1 의 L0 무조건 게이트 4종 — 이 레이어에 해당하는 항목만 적는다(I3 §3.6)."""
    # 보고율 = 보고된 항목 / 보고돼야 하는 항목. 분모가 0 이면(제외·실패가 없는 실행) 1.0 이다.
    err_visibility = round(f["reported"] / f["shouldReport"], 4) if f["shouldReport"] else 1.0
    if track == "db":
        sec_observed = (
            f"코퍼스 양성 {f['piiPositives']}건 중 마스킹 {f['piiMasked']}건 "
            f"(미마스킹 {f['piiUnmasked']}건 · 미수집 {f['piiNotCollected']}건) · "
            f"샘플 적재 경로에 미마스킹 PII 형태 값 {f['ingestUnmaskedValues']}건"
        )
    else:
        sec_observed = (
            f"코퍼스 양성 {f['piiPositives']}건 중 마스킹 {f['piiMasked']}건 "
            f"(미마스킹 {f['piiUnmasked']}건 · 미수집 {f['piiNotCollected']}건 — 수집 확장자가 아니어서 walked=0)"
        )
    return [
        {
            "id": "gate-determinism",
            "name": "결정성 (동일 입력 3회 일치율)",
            "required": 1.0,
            "observed": f["determinism"],
            "status": "PASS" if f["determinism"] >= 1.0 else "FAIL",
        },
        {
            "id": "gate-l0-metadata-completeness",
            "name": "L0 메타데이터 완전성 (projectId·sourceId·revision·contentHash·collectorVersion)",
            "required": 1.0,
            "observed": f["provenance"],
            "status": "PASS" if f["provenance"] >= 1.0 else "FAIL",
        },
        {
            "id": "gate-error-visibility",
            "name": "L0 오류 가시성 (실패·제외 보고율)",
            "required": 1.0,
            "observed": err_visibility,
            "status": "PASS" if err_visibility >= 1.0 else "FAIL",
        },
        {
            "id": "gate-security-masking",
            "name": "L0 보안 (테스트 시크릿·PII 미마스킹 0건)",
            "required": "0건",
            "observed": sec_observed,
            "status": "FAIL",
        },
    ]


def halt_rules(gs: list[dict]) -> list[str]:
    """I1 §3.2 — 결정성 실패는 H1, L0 보안 미통과는 H2. 애매하면 HALT 쪽으로 읽는다(I1 §3.2)."""
    by_id = {g["id"]: g for g in gs}
    rules = []
    if by_id["gate-determinism"]["status"] != "PASS":
        rules.append("H1")
    if by_id["gate-security-masking"]["status"] != "PASS":
        rules.append("H2")
    return rules


def coverage_classes(track: str, p: dict) -> list[dict]:
    """`deterministic` 은 **state 의 3회 안정성**이며 산출물 해시 결정성이 아니다(EVL §7.1 · I3 §3.5).

    code 트랙의 산출물 결정성은 실패했지만(H1) 'code 클래스를 봤다' 는 state 는 3회 모두 같았다 —
    두 값을 한 필드에 섞으면 어느 쪽도 측정할 수 없게 된다. 그래서 프로브가 state 를 따로 재고
    여기서는 그 측정을 옮겨 적는다(하드코딩 금지).
    """
    if track == "code":
        cs = p["coverageState"]
        measured = {"code": (cs["codeState"], cs["codeStateStable"])}
    else:
        # db 트랙 실행은 DDL 만 봤다 — 5클래스 어느 것도 수집하지 않았고, 3회 실행에서 동일했다.
        measured = {}
    out = []
    for c in ["code", "issue", "adr", "test", "runtime"]:
        state, stable_ = measured.get(c, ("not_collected", True))
        out.append({"class": c, "state": state, "deterministic": stable_,
                    "warned": state != "present"})
    return out


def feature_judgments(track: str, run_id: str, f: dict, run_set: str = "baseline") -> list[dict]:
    if run_set == "l0fix":
        return fix_feature_judgments(track, run_id, f)
    if track == "db":
        return [
            {
                "featureId": "P-ddl-parser",
                "judgment": "Lab",
                "measured": True,
                "rationale": (
                    "고정 입력에서 CREATE TABLE 27건을 빠짐없이 수집하고 3회 실행이 동일했다(결정성 1.0). "
                    f"그러나 필수 식별 필드 {int(f['provenance'] * 5)}/5, 제외·실패 보고율 0.0 이며 "
                    f"부분 복구를 조용히 수행한 사례 {f['silentPartialRecovery']}건(TB_BAD_MIDDLE — 컬럼 1개만 살려 추출)이 "
                    "확인됐다. 추적 가능성과 정직성 게이트를 통과하지 못해 Core 로 올릴 수 없고, 수집 능력 자체는 "
                    "쓸 만하므로 Retire 도 아니다."
                ),
                "evidenceRefs": [run_id],
            },
            {
                "featureId": "E1",
                "judgment": "Lab",
                "measured": True,
                "rationale": (
                    "샘플 적재 경로(SampleLegacyDb)는 CREATE 뿐 아니라 INSERT 까지 전 문장을 실행해 행 데이터를 "
                    f"저장소에 원문으로 남긴다 — 미마스킹 PII 형태 값 {f['ingestUnmaskedValues']}건이 질의로 회수됐다. "
                    "L0 최소저장 원칙과 보안 게이트를 통과하지 못한다. 벤치 입력 픽스처로서의 가치는 유지되므로 Lab."
                ),
                "evidenceRefs": [run_id],
            },
        ]
    return [
        {
            "featureId": "E17",
            "judgment": "Lab",
            "measured": True,
            "rationale": (
                f"수집 범위 {f['input']}개 파일을 전량 파싱했고 노드·엣지·좌표는 재현됐다. 그러나 동일 입력 3회 "
                f"실행의 산출물이 서로 달라 결정성 {f['determinism']} (군집 라벨 비결정 — cluster.py 의 집합 순회 "
                "순서). H1 이 발동하는 상태이므로 Core 판정 불가, 원인이 국소적이고 수정 가능하므로 Retire 도 아니다."
            ),
            "evidenceRefs": [run_id],
        },
    ]


def fix_feature_judgments(track: str, run_id: str, f: dict) -> list[dict]:
    """#114 재측정의 판정. 오류 가시성은 해소됐지만 남은 게이트가 실패라 Core 는 여전히 형식이 거부한다(§7 V8)."""
    if track == "db":
        return [
            {
                "featureId": "P-ddl-parser",
                "judgment": "Lab",
                "measured": True,
                "rationale": (
                    f"같은 고정 입력에서 CREATE TABLE 27건을 빠짐없이 수집하고 3회 실행이 동일했다"
                    f"(결정성 {f['determinism']}). #114 로 제외·실패·부분수집이 반환형에 실려 보고율 "
                    f"{f['reported']}/{f['shouldReport']} 이고 조용한 부분 복구는 {f['silentPartialRecovery']}건이다 "
                    f"— TB_BAD_MIDDLE 은 부분 복구를 버리고 실패로 보고한다. 그러나 필수 식별 필드가 여전히 "
                    f"{int(f['provenance'] * 5)}/5 라 추적 가능성 게이트를 통과하지 못한다(L0-fix-2). Core 불가, "
                    "수집 능력은 쓸 만하므로 Retire 도 아니다."
                ),
                "evidenceRefs": [run_id],
            },
            {
                "featureId": "E1",
                "judgment": "Lab",
                "measured": True,
                "rationale": (
                    "샘플 적재 경로(SampleLegacyDb)는 이번 수정 대상이 아니다 — CREATE 뿐 아니라 INSERT 까지 "
                    f"전 문장을 실행해 행 데이터를 원문으로 남기며, 미마스킹 PII 형태 값 "
                    f"{f['ingestUnmaskedValues']}건이 질의로 회수됐다. 보안·최소저장 게이트 미통과로 Lab 유지"
                    "(L0-fix-5)."
                ),
                "evidenceRefs": [run_id],
            },
        ]
    return [
        {
            "featureId": "E17",
            "judgment": "Lab",
            "measured": True,
            "rationale": (
                f"고정 revision 에서 재구성한 범위 {f['input']}개 파일을 전량 파싱했고, #114 로 제외·실패·"
                f"부분수집이 meta.issues 에 사유·좌표와 함께 실려 보고율 {f['reported']}/{f['shouldReport']} 이다. "
                f"파싱 오류가 있는 파일은 status 로 표시되어 완전 성공으로 위장된 실패 픽스처가 "
                f"{f['markedFullySucceeded']}건이다. 그러나 동일 입력 3회 실행의 산출물이 여전히 서로 달라 "
                f"결정성 {f['determinism']}(군집 라벨 비결정 — cluster.py 의 집합 순회 순서)이며 H1 이 열려 있다. "
                "Core 불가, 원인이 국소적이고 수정 가능하므로 Retire 도 아니다(L0-fix-1)."
            ),
            "evidenceRefs": [run_id],
        },
    ]


def baseline_block(track: str, p: dict, f: dict, gs: list[dict], run_set: str) -> dict:
    """이전 기준선 대비 변화(I3 R17). 비교 가능성은 runId 가 아니라 **신원**으로 판정한다."""
    prev_set = PREVIOUS_SET.get(run_set)
    if prev_set is None:
        return {
            "previous": None,
            "comparable": False,
            "reason": "L0 첫 실측이라 비교 대상이 없다. fixtureHash 는 I2(#99) 승인으로 고정됐고 적용 대상 "
                      "버전이 전부 PINNED 이므로 이 보고서는 다음 실행의 기준선이 될 수 있다(I3 R12).",
            "eligibleAsBaseline": True,
            "deltas": [],
        }
    prev_probe = probe(track, prev_set)
    prev_facts = _db_facts(prev_probe) if track == "db" else _code_facts(prev_probe)
    prev_gates = {g["id"]: g for g in gates(track, prev_probe, prev_facts)}
    cur_gates = {g["id"]: g for g in gs}

    def delta(metric: str, prev, cur):
        d = None if prev is None or cur is None else round(cur - prev, 4)
        return {"metric": metric, "previous": prev, "current": cur, "delta": d}

    return {
        "previous": {
            "runId": RUN_SETS[prev_set][track]["runId"],
            "projectId": "lodestar",
            "layer": "L0",
            "track": track,
            "sourceRevision": prev_probe["sourceRevision"][:7],
            "fixtureHash": prev_probe["fixtureHash"],
            "schemaVersion": "run-quality-report/v0",
        },
        "comparable": True,
        "reason": "입력(고정 revision 의 같은 원본)·fixtureHash·schemaVersion 이 같고 수집기만 바뀌었다 — "
                  "그래서 이 비교는 수집기 변경의 효과를 잰다(I1 §7.4).",
        "eligibleAsBaseline": True,
        "deltas": [
            delta("gates.gate-error-visibility",
                  prev_gates["gate-error-visibility"]["observed"],
                  cur_gates["gate-error-visibility"]["observed"]),
            delta("counts.failed", prev_facts["failed"], f["failed"]),
            delta("metrics.determinism", prev_facts["determinism"], f["determinism"]),
            delta("metrics.provenanceCompleteness", prev_facts["provenance"], f["provenance"]),
            delta("metrics.scopeCoverage",
                  round(prev_facts["output"] / prev_facts["input"], 4) if prev_facts["input"] else None,
                  round(f["output"] / f["input"], 4) if f["input"] else None),
        ],
    }


def build(track: str, run_set: str = "baseline") -> dict:
    return build_from(track, probe(track, run_set), run_set)


def build_from(track: str, p: dict, run_set: str = "baseline") -> dict:
    f = _db_facts(p) if track == "db" else _code_facts(p)
    spec = RUN_SETS[run_set][track]
    run_id = spec["runId"]
    started, completed = spec["times"]
    gs = gates(track, p, f)
    halts = halt_rules(gs)

    scope_cov = round(f["output"] / f["input"], 4) if f["input"] else None
    warnings = [
        {
            "code": "GATE_FAILED",
            "message": f"무조건 게이트 실패: {g['name']}",
            "trigger": f"gates.{g['id']}",
        }
        for g in gs if g["status"] == "FAIL"
    ]
    prev_set = PREVIOUS_SET.get(run_set)
    if prev_set is None:
        warnings.append({
            "code": "BASELINE_NOT_COMPARABLE",
            "message": "L0 첫 실측이라 비교 대상 실행이 없다 — 변화량을 산출하지 않았다",
            "trigger": "baseline",
        })

    if track == "db":
        collector_version = spec["collector"] or p["collector"]["citedVersion"]
        notes = (
            "L0 DB 트랙 실측. 프로브 산출물: probe-db.json (backend/src/test/kotlin/com/ontostudio/rdb/"
            "L0DbSourceProbeTest.kt 가 생성하며 표류 시 테스트가 실패한다). "
            f"counts.input 은 고정 입력의 SQL 문장 {f['input']}건이다 — 행 데이터(INSERT) 8건은 L0 최소저장 "
            "원칙상 제외이지만 분모에 남긴다(I3 R20). 제외가 설계상 정당하더라도 사유·좌표를 보고하지 않으면 "
            "오류 가시성 게이트는 통과하지 않는다. 수집기는 제외·실패를 실을 자리(반환형)가 없어 보고율이 "
            "구조적으로 0 이다. 게이트 판정이 애매한 구간(미마스킹 0건이지만 마스킹 단계 부재)은 I1 §3.2 에 "
            "따라 HALT 쪽으로 읽었다."
        )
        if run_set == "l0fix":
            notes = (
                "L0 DB 트랙 **재측정**(#114 — 오류 가시성 수정 후). 입력·fixture 는 run-l0-db-3c27259-001 과 "
                "같은 고정값이고 수집기만 바뀌었으므로 두 실행은 직접 비교된다. 프로브 산출물: probe-db.json "
                "(L0DbSourceProbeTest.kt 가 생성하며 표류 시 테스트가 실패한다). "
                f"counts.input 은 고정 입력의 SQL 문장 {f['input']}건이다 — 행 데이터(INSERT) 8건은 L0 최소저장 "
                "원칙상 제외이지만 분모에 남기고(I3 R20) 이제 사유·좌표와 함께 보고된다. 보고율은 "
                f"{f['reported']}/{f['shouldReport']} 이며, 실패 픽스처의 기대 보고 항목은 사유코드·좌표 "
                "겹침으로 귀속해 셌다(건수만 맞추는 통과 경로를 막는다). 조용한 부분 복구는 "
                f"{f['silentPartialRecovery']}건이다 — TB_BAD_MIDDLE 은 부분 복구를 버리고 실패로 보고한다. "
                "여전히 실패인 게이트는 식별 필드(L0-fix-2)와 마스킹(L0-fix-5)이며 둘 다 이 이슈 범위 밖이다."
            )
    else:
        collector_version = spec["collector"] or p["collector"]["citedVersion"]
        notes = (
            "L0 코드 트랙 실측. 프로브 산출물: probe-code.json (probe_code.py --check 로 표류·근본 원인 재현). "
            "determinism 은 기본 인터프리터 설정 3회 실행의 최대 동일 그룹/3 이다. PYTHONHASHSEED 를 고정하면 "
            "동일해지고 시드를 바꾸면 달라진다는 통제 실험이 프로브에 함께 남아 있어, 이 수치는 재실행 시 "
            "우연히 0.6667 로 보일 수 있어도 '재현 보장 없음' 이라는 사실은 바뀌지 않는다. "
            "precision/recall 은 L1(#89)의 몫이라 NOT_APPLICABLE 이다."
        )
        if run_set == "l0fix":
            notes = (
                "L0 코드 트랙 **재측정**(#114 — 오류 가시성 수정 후). 수집 범위를 고정 revision 의 blob 에서 "
                "재구성해 측정했다 — 수집기를 고치면 작업 트리의 backend/src/main/kotlin 이 곧 바뀌므로, "
                "작업 트리를 입력으로 삼는 동안에는 '고정 revision 을 쟀다' 가 성립하지 않는다. "
                f"보고율은 {f['reported']}/{f['shouldReport']} 이며 분모는 확장자 제외 "
                f"{f['excluded']}건과 실패 픽스처 3건의 기대 보고 항목이다. 산출물은 이제 파일마다 "
                "status(parsed|partial|failed)를 싣고 파싱 오류 구간과 겹치는 선언은 사실로 내지 않는다 — "
                f"'완전 성공으로 표시된 실패 픽스처' {f['markedFullySucceeded']}건. determinism 은 여전히 "
                "cluster.py 의 집합 순회 순서 때문에 재현되지 않는다(L0-fix-1 — 이 이슈 범위 밖, H1 유지). "
                "precision/recall 은 L1(#89)의 몫이라 NOT_APPLICABLE 이다."
            )

    report = {
        "schemaVersion": "run-quality-report/v0",
        "run": {
            "runId": run_id,
            "projectId": "lodestar",
            "layer": "L0",
            "track": track,
            "reportKind": "BASELINE",
            "sourceRevision": p["sourceRevision"][:7],
            "fixtureHash": p["fixtureHash"],
            "startedAt": started,
            "completedAt": completed,
            "executedBy": "claude-code agent (Claude Opus 4.8) — 판정 승인권자는 @xivicWon (I1 §1.2)",
        },
        "versions": {
            "collector": {"status": "PINNED", "value": collector_version},
            "extractor": {"status": "NOT_APPLICABLE", "value": None},
            "model": {"status": "NOT_APPLICABLE", "value": None},
            "prompt": {"status": "NOT_APPLICABLE", "value": None},
        },
        "counts": {
            "input": f["input"], "output": f["output"],
            "failed": f["failed"], "excluded": f["excluded"],
        },
        "exclusions": f["exclusions"],
        "failures": [],
        "metrics": {
            "precision": measurement("NOT_APPLICABLE", None,
                                     "L0 은 사실을 산출하지 않는다 — 명시 사실 정확도는 L1(#89)에서 잰다"),
            "recall": measurement("NOT_APPLICABLE", None,
                                  "L0 은 사실을 산출하지 않는다 — 재현율은 L1(#89)에서 잰다"),
            "scopeCoverage": measurement(
                "MEASURED" if scope_cov is not None else "NOT_APPLICABLE", scope_cov,
                f"counts.output/counts.input = {f['output']}/{f['input']}"),
            "determinism": measurement(
                "MEASURED", f["determinism"],
                "동일 revision 3회 실행 산출물 해시의 최대 동일 그룹 / 3"),
            "provenanceCompleteness": measurement(
                "MEASURED", f["provenance"],
                "필수 식별 5필드(projectId·sourceId·revision·contentHash·collectorVersion) 중 "
                "산출물에서 소스 단위로 조회 가능한 비율"),
        },
        "evl": {
            "confidenceCalibration": {
                "status": "NOT_APPLICABLE", "population": None, "ece": None,
                "bins": [], "sampleCount": 0, "missingRawCount": 0,
            },
            "conflictDetection": {
                "precision": measurement("NOT_APPLICABLE", None, "L0 은 충돌 판정을 만들지 않는다"),
                "recall": measurement("NOT_APPLICABLE", None, "L0 은 충돌 판정을 만들지 않는다"),
                "goldSetId": p["goldSetId"],
            },
            "coverageClasses": coverage_classes(track, p),
        },
        "gates": gs,
        "baseline": baseline_block(track, p, f, gs, run_set),
        "verdict": {
            "value": "BLOCKED" if halts else "PASS",
            "haltRules": halts,
            "restrictions": [],
        },
        "featureJudgments": feature_judgments(track, run_id, f, run_set),
        "warnings": warnings,
        "notes": notes,
    }
    return report


def validate(report: dict) -> list[str]:
    sys.path.insert(0, str(SCHEMAS))
    from jsonschema import Draft202012Validator  # noqa: E402
    import validate_rqr  # noqa: E402

    schema = json.loads((SCHEMAS / "run-quality-report.v0.schema.json").read_text())
    errs = [f"[schema] {e.json_path}: {e.message}"
            for e in Draft202012Validator(schema).iter_errors(report)]
    errs += [f"[R] {e}" for e in validate_rqr.cross_field_errors(report)]
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", choices=["db", "code"])
    ap.add_argument("--set", dest="run_set", choices=sorted(RUN_SETS), default=None,
                    help="특정 실행 집합만 생성한다 (기본: 전부)")
    args = ap.parse_args()

    rc = 0
    sets = [args.run_set] if args.run_set else sorted(RUN_SETS)
    for run_set in sets:
        for track in (list(TRACKS) if not args.stdout else [args.stdout]):
            rc |= build_one(run_set, track, args.stdout is not None)
    return rc


def build_one(run_set: str, track: str, to_stdout: bool) -> int:
    report = build(track, run_set)
    errs = validate(report)
    if errs:
        print(f"[FAIL] {run_set}/{track}: 보고서가 I3 계약을 위반한다")
        for e in errs:
            print("  " + e)
        return 1

    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if to_stdout:
        print(text, end="")
        return 0

    out = run_dir(run_set, track) / "report.json"
    # 보고서는 프로브의 순수 함수이므로 재생성은 멱등이다. 내용이 달라졌다면 근거가 바뀐 것이며,
    # 그때 기존 보고서를 덮어쓰면 이전 실행이 사라진다 — 새 runId 로 남긴다(I3 §5.5).
    if out.exists() and out.read_text() != text:
        print(f"[FAIL] {out.relative_to(REPO)} 를 덮어쓰지 않았다 — 재생성 결과가 커밋된 보고서와 "
              f"다르다. 근거가 바뀌었으면 RUN_SETS 에 새 runId 를 추가해 새 보고서로 남긴다(I3 §5.5).")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"[ok] {out.relative_to(REPO)} — verdict={report['verdict']['value']} "
          f"halt={report['verdict']['haltRules']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
