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
import functools
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
GOLD = REPO / "docs/superpowers/specs/gold"
SCHEMAS = REPO / "docs/superpowers/specs/schemas"

RUNS = {
    "db": HERE / "runs/run-l0-db-aad4382-001",
    "code": HERE / "runs/run-l0-code-aad4382-001",
}
PROBE_NAME = {"db": "probe-db.json", "code": "probe-code.json"}
RUN_ID = {"db": "run-l0-db-aad4382-001", "code": "run-l0-code-aad4382-001"}
# 이전 실행 — 있으면 그 보고서를 읽어 비교한다. 수치를 여기 적지 않는다: 손으로 옮긴 기준선은
# 원본과 어긋나도 아무도 모른다(V2 가 보고서를 프로브+이 상수들에서 다시 만들어 대조한다).
PREVIOUS = {
    "db": HERE / "runs/run-l0-db-3c27259-004",
    "code": HERE / "runs/run-l0-code-3c27259-003",
}
# 실측 세션의 시각 (RFC 3339 축소 프로파일). 보고서를 다시 만들어도 흔들리지 않도록 못박는다 —
# 사후 수정은 새 runId 로 남긴다(I3 §5.5).
TIMES = {
    # 실측이 끝난 시각과 그 실행의 소요다 — 프로브가 시각을 산출물에 넣으면 매 실행이 표류하므로
    # 여기 못박되, 지어내지 않는다.
    "db": ("2026-07-31T08:46:00Z", "2026-07-31T08:46:11Z"),
    "code": ("2026-07-31T08:41:00Z", "2026-07-31T08:41:07Z"),
}
# 이번 실행에서 **수집기의 무엇이** 달라졌는가. 트랙마다 다르므로 한 문장을 공유하지 않는다 —
# 공유하면 db 재측정에 code 트랙의 사유가 붙어 보고서가 근거를 잘못 가리킨다.
COLLECTOR_CHANGE = {
    "db": "#115 마스킹 경계 문자 처리 통합 수정(\\s·CRLF·백슬래시)",
    "code": "#112 결정성 수정",
}
# 이번 실행이 **왜 새 runId 인가**. 수집기가 아니라 gold 쪽이 움직인 재측정도 있다 —
# 사유를 트랙 문장에 섞으면 "수집기가 바뀌어서 다시 쟀다" 는 거짓 서술이 남는다(#125).
REPIN_REASON = (
    "gold 입력 축 재고정(#125) — L0 프로브의 입력 revision 을 정답 축에서 분리해 새로 고정했고, "
    "그 개정으로 goldSetId 가 바뀌어 이전 gold 로 채점된 실행은 비교 기준선에서 제외된다"
    "(I1 §7.4 · I2 §10.4)"
)
# 비교 가능성은 신원이 같을 때만 성립한다(I3 R17).
IDENTITY = ("projectId", "layer", "track", "sourceRevision", "fixtureHash")
COMPARED_METRICS = ("determinism", "provenanceCompleteness", "scopeCoverage")


def line_range(locator: str) -> tuple[int, int] | None:
    m = re.search(r"#L(\d+)(?:-L(\d+))?", locator or "")
    if not m:
        return None
    start = int(m.group(1))
    return start, int(m.group(2) or start)


def measurement(status: str, value, note: str) -> dict:
    return {"status": status, "value": value, "note": note}


def probe(track: str) -> dict:
    return json.loads((RUNS[track] / PROBE_NAME[track]).read_text())


@functools.lru_cache(maxsize=1)
def gold_manifest() -> dict:
    """gold 정본을 읽는 **단 하나의 지점**. 보고서 한 건을 만드는 동안 승인 상태가 바뀌면
    같은 보고서 안에서 경고와 기준선 자격이 갈릴 수 있으므로, 한 프로세스 안에서는 한 번만 읽는다."""
    return json.loads((GOLD / "manifest.json").read_text())


def probe_axis() -> dict:
    """gold 의 L0 **수집 입력 축**(#125). 정답 축(sourceRevision)과 승인이 따로 간다."""
    return gold_manifest()["probeAxis"]


def axis_approved() -> bool:
    """이 실행을 채점한 gold 가 **양쪽 축 모두** 승인됐는가 — gold 에서 읽는다.

    정답 축(`status`)만 보면 입력 축 재고정이 승인 없이 기준선을 만들고, 입력 축만 보면 그 반대다.

    보고서에 손으로 적으면 승인 없이 기준선이 만들어지고, 그 뒤의 모든 비교가 승인되지 않은
    입력 신원 위에 얹힌다(I1 §7). 승인이 나면 이 값이 바뀌면서 보고서가 프로브에서 다시
    만들어지지 않게 되므로(V2), 승인된 수치는 **새 runId** 로 남게 된다(I3 §5.5).
    """
    gold = gold_manifest()
    return (gold["status"]["state"] == "APPROVED"
            and gold["probeAxis"]["status"]["state"] == "APPROVED")


def _db_facts(p: dict) -> dict:
    acq = p["acquisition"]
    fixtures = p["failureFixtures"]
    # 분모는 **프로브가 독립적으로 센 것** 이다: 인벤토리가 '수집 대상이 아니다' 로 분류한 문장 수와
    # gold 가 선언한 픽스처 기대 보고 항목. 수집기 신고를 분모로 쓰면 "보고한 것을 보고했다" 는
    # 자기 인증이 된다. 그 자리가 없던 실행(v1 프로브)은 excluded+failed 로 읽는다.
    should_report = (acq.get("reportableByInventory", acq["excluded"] + acq["failed"])
                     + sum(f["expectedReported"] for f in fixtures))
    # 분자도 귀속으로 센다 — 인벤토리 문장을 덮는 항목이 사유와 함께 있는가, 픽스처 기대 항목이
    # 좌표 겹침으로 귀속되는가.
    reported = (acq.get("reportedByInventory", 0)
                + sum(f.get("actualReported", 0) for f in fixtures))
    ingest_values = sum(c["retrievableValues"] for c in p["ingestStore"]["piiShapedColumns"])
    return {
        "input": p["statementInventory"]["total"],
        "output": acq["acquired"],
        "failed": acq["failed"],
        # 실패는 집계만 남기지 않고 사례를 그대로 옮긴다(I3 R4) — 사례가 없으면 재현도 회귀도 없다.
        "failures": [
            {"id": f"fail-db-L{(line_range(x['locator']) or (0,))[0]}",
             "summary": f"{x['reasonCode']}: {x['target']} — {x['reason']}",
             "link": f"artifact://{p['input']['path']}",
             "fixture": x["locator"].split("#")[0] or p["input"]["path"]}
            for x in acq.get("failures", [])
        ],
        "excluded": acq["excluded"],
        "exclusions": acq["exclusions"],
        "determinism": p["determinism"]["rate"],
        "provenance": p["provenance"]["rate"],
        "shouldReport": should_report,
        "reported": reported,
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
    # counts 는 인벤토리에서 **항등으로** 나온다: input = parsed + (walked-parsed) + (input-walked).
    # 실패를 0 으로 박아두면 수집기가 정직하게 실패를 보고하는 순간 R2 가 깨져 보고서 생성 자체가
    # 거부된다 — 정직한 수집이 형식 위반이 되는 자리는 계약이 아니라 산식의 결함이다.
    not_collected = inv.get("notCollectedCount", inv["excludedByExtensionFilter"])
    # 실패의 분모도 프로브가 직접 센 것이다: 읽었으나 사실을 산출하지 못한 파일.
    # 건수와 사례를 같은 집합에서 만들어야 R2·R4 가 서로를 확인한다.
    failed_files = inv.get("failedFiles", [])
    reported_failures = set(inv.get("failedFilesReported", []))
    scope_root = inv.get("scopeRoot", "backend/src/main/kotlin")
    return {
        "input": inv["input"],
        # 사실을 낸 파일만 산출이다. 파싱만 되고 사실이 0건인 파일을 output 에 넣으면 실패가 성공으로
        # 위장된다 — 이 이슈가 수집기에서 없앤 위장이 보고서 층에서 되살아나는 자리다.
        "output": inv.get("producedFacts", inv["parsed"]),
        "failed": len(failed_files) if "failedFiles" in inv else inv["walked"] - inv["parsed"],
        "failures": [
            {"id": f"fail-code-{i}",
             "summary": (f"파싱 실패로 사실을 산출하지 못했다: {path}" if path in reported_failures
                         else f"사실을 산출하지 못했는데 수집기가 사유를 남기지 않았다: {path}"),
             "link": "artifact://build/l0/probe-code.json",
             "fixture": f"{scope_root}/{path}"}
            for i, path in enumerate(sorted(failed_files), start=1)
        ],
        "excluded": not_collected,
        "exclusions": inv["exclusions"],
        "determinism": p["determinismObserved"]["rate"],
        "provenance": p["provenance"]["rate"],
        # db 트랙과 같은 규칙: 분모는 프로브가 직접 센 '수집기가 읽지 않은 파일' 과 gold 픽스처의
        # 기대 보고 항목이고, 분자는 그 각각이 사유와 함께 산출물에 남았는지다(자기 인증 방지).
        "shouldReport": (not_collected + len(failed_files)
                         + sum(f["expectedReported"] for f in fixtures)),
        "reported": (inv.get("reportedNotCollected", 0) + len(reported_failures)
                     + sum(f.get("actualReported", 0) for f in fixtures)),
        "markedFullySucceeded": sum(1 for f in fixtures if f["markedAsFullySucceeded"]),
        "piiPositives": p["pii"]["positives"],
        "piiMasked": p["pii"]["masked"],
        "piiUnmasked": len(p["pii"]["unmaskedInArtifact"]),
        "piiNotCollected": len(p["pii"]["notCollected"]),
    }


def gates(track: str, p: dict, f: dict) -> list[dict]:
    """I1 §4.1 의 L0 무조건 게이트 4종 — 이 레이어에 해당하는 항목만 적는다(I3 §3.6)."""
    # 보고율 = 보고된 항목 / 보고돼야 하는 항목.
    # 분모가 0 이면 **재지 못한 것이지 통과한 것이 아니다** — 0/0 을 1.0 으로 적으면 '보고할 것이
    # 없었다' 와 '전부 보고했다' 가 같은 값이 되어 그 자리는 더 이상 지표가 아니다(I3 R20 이 
    # scopeCoverage 에 건 것과 같은 규칙). 계약의 어휘로 NOT_MEASURED 를 쓰고 경고를 함께 낸다(R10).
    err_visibility = round(f["reported"] / f["shouldReport"], 4) if f["shouldReport"] else None
    if track == "db":
        sec_observed = (
            f"코퍼스 양성 {f['piiPositives']}건 중 마스킹 {f['piiMasked']}건 "
            f"(미마스킹 {f['piiUnmasked']}건 · 미수집 {f['piiNotCollected']}건) · "
            f"샘플 적재 경로(마스킹 opt-out 기준선)에 미마스킹 PII 형태 값 {f['ingestUnmaskedValues']}건"
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
            "status": "NOT_MEASURED" if err_visibility is None
                      else ("PASS" if err_visibility >= 1.0 else "FAIL"),
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

    #88 에서 code 트랙은 산출물 해시가 갈리는 와중에도(H1) 'code 클래스를 봤다' 는 state 는 3회 모두
    같았다 — 두 값을 한 필드에 섞으면 어느 쪽도 측정할 수 없게 된다. #112 로 산출물 결정성이 회복된
    뒤에도 정의는 그대로다. 그래서 프로브가 state 를 따로 재고 여기서는 그 측정을 옮겨 적는다(하드코딩 금지).
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


def baseline_block(track: str, run: dict, schema_version: str, metrics: dict,
                   eligible: bool, gs: list[dict] | None = None) -> dict:
    """이전 기준선 대비 변화(I3 R17). 비교 대상이 없으면 '변화 없음' 이 아니라 '비교 불가' 다."""
    prev_dir = PREVIOUS.get(track)
    if prev_dir is None:
        return {
            "previous": None,
            "comparable": False,
            "reason": "L0 첫 실측이라 비교 대상이 없다. fixtureHash 는 I2(#99) 승인으로 고정됐고 적용 대상 "
                      "버전이 전부 PINNED 이므로 이 보고서는 다음 실행의 기준선이 될 수 있다(I3 R12).",
            "eligibleAsBaseline": eligible,
            "deltas": [],
        }

    prev = json.loads((prev_dir / "report.json").read_text())
    ident = {**{k: prev["run"][k] for k in IDENTITY},
             "runId": prev["run"]["runId"], "schemaVersion": prev["schemaVersion"]}
    same = all(prev["run"][k] == run[k] for k in IDENTITY) and \
        prev["schemaVersion"] == schema_version and \
        prev["run"]["reportKind"] == "BASELINE" and \
        prev["baseline"]["eligibleAsBaseline"]
    if not same:
        # 어느 필드가 갈렸는지 **계산해서** 적는다. "신원이 다르다" 만 적으면 gold 개정으로
        # 비교가 끊긴 것과 트랙을 잘못 인용한 것이 같은 문장이 된다.
        differing = [k for k in IDENTITY if prev["run"][k] != run[k]]
        axis = probe_axis()
        return {
            "previous": ident,
            "comparable": False,
            "reason": (
                f"{ident['runId']} 과 신원이 다르다(다른 필드: {', '.join(differing) or '없음'}) — "
                f"gold 입력 축 재고정(#125: probeAxis {axis['revision'][:7]}, "
                f"{axis['status']['state']})으로 이전 gold 로 채점된 실행은 비교 기준선에서 제외된다"
                "(I1 §7.4 · I2 §10.4). 이전 실행은 덮어쓰지 않고 여기서 인용만 한다(I3 §5.5)."
            ),
            "eligibleAsBaseline": eligible,
            "deltas": [],
        }

    deltas = []
    for m in COMPARED_METRICS:
        a, b = prev["metrics"].get(m, {}), metrics.get(m, {})
        if a.get("status") != "MEASURED" or b.get("status") != "MEASURED":
            continue
        deltas.append({"metric": m, "previous": a["value"], "current": b["value"],
                       "delta": round(b["value"] - a["value"], 4)})
    # 게이트 관측값도 비교한다 — 수집기 수정의 효과가 지표가 아니라 게이트에만 나타나는 실행이 있다
    # (#114 의 오류 가시성이 그렇다). 수치로 비교할 수 있는 게이트만 넣는다(보안 게이트는 문장이다).
    prev_gates = {g["id"]: g for g in prev.get("gates", [])}
    for g in gs or []:
        a = prev_gates.get(g["id"], {}).get("observed")
        b = g["observed"]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
                and not isinstance(a, bool) and not isinstance(b, bool):
            deltas.append({"metric": f"gates.{g['id']}", "previous": a, "current": b,
                           "delta": round(b - a, 4)})
    return {
        "previous": ident,
        "comparable": True,
        "reason": f"{ident['runId']} 과 project·layer·track·sourceRevision·fixtureHash·schemaVersion 이 "
                  "같다 — 같은 입력을 같은 계약으로 잰 실행이므로 수치를 직접 비교한다. 달라진 것은 "
                  f"수집기 버전이며({COLLECTOR_CHANGE[track]}), 그 변화량이 아래 deltas 다.",
        "eligibleAsBaseline": eligible,
        "deltas": deltas,
    }


GATE_FOLLOWUP = {
    "gate-determinism": "L0-fix-1",
    "gate-l0-metadata-completeness": "L0-fix-2",
    "gate-error-visibility": "L0-fix-3·4",
    "gate-security-masking": "L0-fix-5",
}


def _open_gates(gs: list[dict]) -> str:
    """아직 열려 있는 무조건 게이트를 **게이트 결과에서** 문장으로 만든다.

    판정문에 남은 게이트를 손으로 적으면, 그 게이트가 통과로 바뀐 뒤에도 보고서가 "아직 실패다" 라고
    말한다 — 근거와 서술이 어긋나는 순간 판정문은 증거가 아니라 장식이 된다(#114 재측정에서 실제로
    그렇게 될 뻔했다: 식별 필드가 5/5 가 됐는데 "5/5 라 추적 가능성 게이트가 남아 있다" 고 적혔다).
    """
    open_ = [g for g in gs if g["status"] != "PASS"]
    if not open_:
        return "무조건 게이트는 전부 통과했다 — Core 승격은 판정 승인권자의 몫이다(I1 §1.2)."
    names = " · ".join(f"{g['name'].split('(')[0].strip()}({GATE_FOLLOWUP.get(g['id'], '후속')})"
                       for g in open_)
    return f"그래도 Core 는 아니다 — 남은 무조건 게이트: {names}. 그래서 Lab 이다."


def feature_judgments(track: str, run_id: str, f: dict, gs: list[dict]) -> list[dict]:
    reported_all = f["reported"] >= f["shouldReport"]
    if track == "db":
        if reported_all:
            ddl_rationale = (
                f"고정 입력에서 CREATE TABLE 27건을 빠짐없이 수집하고 3회 실행이 동일했다"
                f"(결정성 {f['determinism']}). #114 로 제외·실패·부분수집이 반환형에 실려 보고율 "
                f"{f['reported']}/{f['shouldReport']} 이고 조용한 부분 복구는 {f['silentPartialRecovery']}건이다 "
                f"— TB_BAD_MIDDLE 은 부분 복구를 버리고 실패로 보고한다. 필수 식별 필드는 "
                f"{int(f['provenance'] * 5)}/5 다(#113). {_open_gates(gs)} 수집 능력 자체는 쓸 만하므로 "
                "Retire 도 아니다."
            )
        else:
            ddl_rationale = (
                "고정 입력에서 CREATE TABLE 27건을 빠짐없이 수집하고 3회 실행이 동일했다(결정성 1.0). "
                f"그러나 필수 식별 필드 {int(f['provenance'] * 5)}/5, 제외·실패 보고율 0.0 이며 "
                f"부분 복구를 조용히 수행한 사례 {f['silentPartialRecovery']}건(TB_BAD_MIDDLE — 컬럼 1개만 살려 추출)이 "
                "확인됐다. 추적 가능성과 정직성 게이트를 통과하지 못해 Core 로 올릴 수 없고, 수집 능력 자체는 "
                "쓸 만하므로 Retire 도 아니다."
            )
        return [
            {
                "featureId": "P-ddl-parser",
                "judgment": "Lab",
                "measured": True,
                "rationale": ddl_rationale,
                "evidenceRefs": [run_id],
            },
            {
                "featureId": "E1",
                "judgment": "Lab",
                "measured": True,
                "rationale": (
                    "샘플 적재 경로(SampleLegacyDb)는 CREATE 뿐 아니라 INSERT 까지 전 문장을 실행해 행 데이터를 "
                    "저장소에 남긴다 — 이 프로브가 잰 **마스킹 opt-out 기준선**"
                    "(IngestPolicy(maskRowData=false))에서 미마스킹 PII 형태 값 "
                    f"{f['ingestUnmaskedValues']}건이 질의로 회수됐다. 측정 조건을 빼고 읽으면 안 된다: "
                    "기본 적재 경로는 #115 이후 적재 **전에** 마스킹한다. 이 판정은 기준선 기준이며, "
                    "마스킹 적용 상태의 재판정은 gold 재고정(승인 사항) 뒤 새 runId 의 몫이다. "
                    "L0 최소저장 원칙은 그와 별개로 여전히 미충족이다(행 자체를 두지 않는 최소화는 기본값이 아니다). "
                    "벤치 입력 픽스처로서의 가치는 유지되므로 Lab."
                ),
                "evidenceRefs": [run_id],
            },
        ]
    if f["determinism"] < 1.0:
        rationale = (
            f"수집 범위 {f['input']}개 파일을 전량 파싱했고 노드·엣지·좌표는 재현됐다. 그러나 동일 입력 3회 "
            f"실행의 산출물이 서로 달라 결정성 {f['determinism']} (군집 라벨 비결정 — cluster.py 의 집합 순회 "
            "순서). H1 이 발동하는 상태이므로 Core 판정 불가, 원인이 국소적이고 수정 가능하므로 Retire 도 아니다."
        )
    elif not reported_all:
        rationale = (
            f"수집 범위 {f['input']}개 파일을 전량 파싱했고, #112 로 군집 라벨의 집합 순회 순서 의존을 없애 "
            f"결정성 {f['determinism']} 이 됐다 (PYTHONHASHSEED 무관 · H1 해소). 그래도 Core 는 아니다 — 필수 식별 "
            f"{int(f['provenance'] * 5)}/5 이고, 보고돼야 할 실패·제외 {f['shouldReport']}건 중 산출물에 남는 것이 "
            f"0건이다(픽스처 {f['markedFullySucceeded']}건은 오히려 전량 성공으로 표시된다). 추적 가능성·정직성 "
            "게이트가 남아 있으므로 Lab."
        )
    else:
        rationale = (
            f"수집 범위 {f['input']}개 파일을 전량 파싱했고 결정성 {f['determinism']}(#112 · H1 해소), "
            f"필수 식별 {int(f['provenance'] * 5)}/5(#113), #114 로 제외·실패·부분수집이 meta.issues 에 "
            f"사유·좌표와 함께 실려 보고율 {f['reported']}/{f['shouldReport']} 이다. 파싱 오류가 있는 파일은 "
            f"status 로 표시되어 완전 성공으로 위장된 실패 픽스처가 {f['markedFullySucceeded']}건이다. "
            f"{_open_gates(gs)}"
        )
    return [
        {
            "featureId": "E17",
            "judgment": "Lab",
            "measured": True,
            "rationale": rationale,
            "evidenceRefs": [run_id],
        },
    ]


def build(track: str) -> dict:
    return build_from(track, probe(track))


def build_from(track: str, p: dict) -> dict:
    f = _db_facts(p) if track == "db" else _code_facts(p)
    run_id = RUN_ID[track]
    started, completed = TIMES[track]
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
    # 재지 못한 게이트는 경고로 드러낸다 — 침묵하면 '통과' 와 구분되지 않는다(I3 R10).
    warnings += [
        {
            "code": "METRIC_UNMEASURED",
            "message": f"게이트를 재지 못했다(분모 0): {g['name']}",
            "trigger": f"gates.{g['id']}",
        }
        for g in gs if g["status"] == "NOT_MEASURED"
    ]
    # 승인 전 gold 위의 실행이라는 사실을 보고서 안에 남긴다(I3 R12 · #125). 남기지 않으면 읽는
    # 쪽이 gold 를 따로 조회해야 하고, 조회하지 않은 인용이 곧 승인 우회다.
    if not axis_approved():
        axis = probe_axis()
        warnings.append({
            "code": "GOLD_UNAPPROVED",
            "message": f"gold 입력 축({axis['revision'][:7]})이 {axis['status']['state']} 상태다 — "
                       "이 수치는 다음 실행의 비교 기준선이 될 수 없다(I1 §7 · I2 §6)",
            "trigger": "evl.conflictDetection.goldSetId",
        })

    if track == "db":
        collector_version = p["collector"]["citedVersion"]
        # 남은 실패는 **이 보고서의 게이트 상태에서 뽑는다**. 손으로 적으면 게이트가 닫힌 뒤에도
        # 문구가 남아, 같은 보고서가 "메타데이터 실패" 를 말하면서 그 게이트를 1.0 PASS 로 싣는다
        # (리뷰 LOD-109 — run-l0-db-3c27259-003 에서 실제로 그랬다).
        failed_gates = [GATE_FOLLOWUP.get(g["id"], g["id"]) for g in (gs or []) if g["status"] == "FAIL"]
        remaining = f"남은 실패는 {' · '.join(failed_gates)} 다" if failed_gates \
            else "무조건 게이트에 남은 실패는 없다"
        notes = (
            f"L0 DB 트랙 재실측({COLLECTOR_CHANGE['db']} 후). 프로브 산출물: probe-db.json "
            "(backend/src/test/kotlin/com/ontostudio/rdb/L0DbSourceProbeTest.kt 가 생성하며 표류 시 테스트가 "
            f"실패한다). counts.input 은 고정 입력의 SQL 문장 {f['input']}건이다 — 행 데이터(INSERT) 8건은 "
            "L0 최소저장 원칙상 제외이지만 분모에 남기고(I3 R20) 이제 사유·좌표와 함께 보고된다. 보고율은 "
            f"{f['reported']}/{f['shouldReport']} 이며, 실패 픽스처의 기대 보고 항목은 사유코드 일치와 좌표 "
            "겹침으로 귀속해 셌다 — 건수만 맞추거나 그럴듯한 좌표를 적어 통과하는 경로를 막는다. 조용한 부분 "
            f"복구는 {f['silentPartialRecovery']}건이다(TB_BAD_MIDDLE 은 부분 복구를 버리고 실패로 보고한다). "
            f"새 runId 인 이유는 {REPIN_REASON} 이다 — 수집기는 {PREVIOUS['db'].name} 과 같고, 입력 "
            f"파일(legacy-sample.sql)도 두 축에서 바이트가 같다(gold probeAxis.sameAsAnswerAxis=true). "
            "그래서 수치는 그대로지만 채점 신원이 달라 비교 기준선으로는 인용만 한다(I1 §7.4). "
            f"{remaining}. 보안 게이트는 수집 경로에 마스킹 단계가 생긴 뒤에도 FAIL 로 읽는다 — "
            "이 프로브가 재는 것은 샘플 적재 경로를 **마스킹 없이**(IngestPolicy(maskRowData=false)) 돌린 "
            "기준선이기 때문이다. 마스킹 적용 상태의 게이트 회복은 I2 Gold Set 재고정(승인 사항) 뒤에 "
            "새 runId 로 남긴다 — 승인 없이 판정을 올리지 않는다(I1 §3.2)."
        )
    else:
        collector_version = p["collector"]["citedVersion"]
        # db 트랙과 같은 규칙 — 남은 실패를 손으로 적지 않는다. #113(메타데이터 5/5)으로 닫힌 게이트를
        # "아직 실패" 라고 말하던 자리가 여기였다.
        failed_gates = [GATE_FOLLOWUP.get(g["id"], g["id"]) for g in (gs or []) if g["status"] == "FAIL"]
        remaining = f"남은 실패는 {' · '.join(failed_gates)} 다" if failed_gates \
            else "무조건 게이트에 남은 실패는 없다"
        axis = probe_axis()
        notes = (
            f"L0 코드 트랙 재실측 — {REPIN_REASON}. 이 실행이 처음으로 **현재 수집기**"
            f"(#112 결정성 · #114 오류 가시성 · #115 마스킹이 모두 들어간 판)를 고정 입력 위에서 잰다. "
            f"입력은 gold 입력 축 {axis['revision'][:7]}({axis['status']['state']})의 blob 에서 재구성한 "
            f"{f['input']}개 파일이며, 정답 축(3c27259)은 승인된 채로 남는다 — 두 축을 함께 옮기면 "
            "l1/code.json 의 닫힌 범위가 무너진다(I2 §6). 프로브 산출물: probe-code.json "
            "(probe_code.py --check 로 표류 검사 + 결정성 1.0·시드 무관 확인). determinism 은 기본 "
            "인터프리터 설정 3회 실행의 최대 동일 그룹/3 이며, PYTHONHASHSEED 를 바꾼 실행까지 산출물이 "
            "같다는 통제 실험이 프로브에 함께 남아 있다(determinismControl.seedIndependent). 보고율 "
            f"{f['reported']}/{f['shouldReport']} 의 분모는 확장자 제외 {f['excluded']}건과 실패 픽스처 3건의 "
            "기대 보고 항목이고, 산출물은 파일마다 status(parsed|partial|failed)를 실어 파싱 오류 구간과 겹치는 "
            f"선언을 사실로 내지 않는다(완전 성공으로 표시된 실패 픽스처 {f['markedFullySucceeded']}건). "
            f"{remaining}. 보안 게이트는 수집 경로에 마스킹 단계가 생긴 뒤에도(#115 — 프로브의 "
            "maskingCapability.exists=true) FAIL 로 읽는다: 코퍼스 양성 28건이 전부 .sql/.properties/.log 라 "
            "코드 수집기가 읽는 확장자 안에 없고(walked=0), 마스킹 동작 자체를 이 gold 로는 잴 수 없다 — "
            "미측정을 통과로 적지 않는다. precision/recall 은 L1(#89)의 몫이라 NOT_APPLICABLE 이다."
        )

    # I3 §7.3 — 통제어휘 변경·R규칙 의미 변경은 버전을 올린다. #125 가 GOLD_UNAPPROVED 와
    # R12 의 승인 항을 더했으므로 이 실행부터 v1 이다. 이전 실행(v0)과는 직접 비교하지 않는다.
    schema_version = "run-quality-report/v1"
    versions = {
        "collector": {"status": "PINNED", "value": collector_version},
        "extractor": {"status": "NOT_APPLICABLE", "value": None},
        "model": {"status": "NOT_APPLICABLE", "value": None},
        "prompt": {"status": "NOT_APPLICABLE", "value": None},
    }
    run_obj = {
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
    }
    metrics = {
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
    }
    # R12 — 재현할 수 없는 실행은 기준선이 아니다.
    # 여기에 **입력 축의 승인**이 하나 더 붙는다(#125): 재현할 수 있어도 그 입력 신원이
    # 승인되지 않았으면 기준선이 아니다(I1 §7 · I2 §6). 승인 상태는 gold 에서 읽는다.
    eligible = (run_obj["fixtureHash"] != "UNPINNED" and run_obj["reportKind"] == "BASELINE"
                and not [v for v in versions.values() if v["status"] == "UNPINNED"]
                and axis_approved())
    bl = baseline_block(track, run_obj, schema_version, metrics, eligible, gs)
    if not bl["comparable"]:
        # 경고 문구는 실제 사유에서 나와야 한다 — '비교 대상이 없다' 와 '비교 대상은 있으나 신원이
        # 다르다' 는 다른 사실이고, previous 가 채워진 보고서에 전자를 적으면 그 자체가 거짓이다.
        message = ("L0 첫 실측이라 비교 대상 실행이 없다 — 변화량을 산출하지 않았다"
                   if bl["previous"] is None else
                   f"{bl['previous']['runId']} 과 신원·기준선 자격이 달라 비교할 수 없다 — "
                   "변화량을 산출하지 않았다")
        warnings.append({
            "code": "BASELINE_NOT_COMPARABLE",
            "message": message,
            "trigger": "baseline",
        })

    report = {
        "schemaVersion": schema_version,
        "run": run_obj,
        "versions": versions,
        "counts": {
            "input": f["input"], "output": f["output"],
            "failed": f["failed"], "excluded": f["excluded"],
        },
        "exclusions": f["exclusions"],
        "failures": f.get("failures", []),
        "metrics": metrics,
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
        "baseline": bl,
        "verdict": {
            "value": "BLOCKED" if halts else "PASS",
            "haltRules": halts,
            "restrictions": [],
        },
        "featureJudgments": feature_judgments(track, run_id, f, gs),
        "warnings": warnings,
        "notes": notes,
    }
    return report


def validate(report: dict) -> list[str]:
    sys.path.insert(0, str(SCHEMAS))
    from jsonschema import Draft202012Validator  # noqa: E402
    import validate_rqr  # noqa: E402

    schema = validate_rqr.schema_for(report)
    errs = [f"[schema] {e.json_path}: {e.message}"
            for e in Draft202012Validator(schema).iter_errors(report)]
    errs += [f"[R] {e}" for e in validate_rqr.cross_field_errors(report)]
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", choices=["db", "code"])
    args = ap.parse_args()

    rc = 0
    for track in (["db", "code"] if not args.stdout else [args.stdout]):
        report = build(track)
        errs = validate(report)
        if errs:
            rc = 1
            print(f"[FAIL] {track}: 보고서가 I3 계약을 위반한다")
            for e in errs:
                print("  " + e)
            continue
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.stdout:
            print(text, end="")
        else:
            out = RUNS[track] / "report.json"
            # 보고서는 프로브의 순수 함수이므로 재생성은 멱등이다. 내용이 달라졌다면 근거가 바뀐 것이며,
            # 그때 기존 보고서를 덮어쓰면 이전 실행이 사라진다 — 새 runId 로 남긴다(I3 §5.5).
            if out.exists() and out.read_text() != text:
                rc = 1
                print(f"[FAIL] {out.relative_to(REPO)} 를 덮어쓰지 않았다 — 재생성 결과가 커밋된 "
                      f"보고서와 다르다. 근거가 바뀌었으면 RUN_ID/TIMES 에 새 runId 를 추가해 "
                      f"새 보고서로 남긴다(I3 §5.5).")
                continue
            out.write_text(text)
            print(f"[ok] {out.relative_to(REPO)} — verdict={report['verdict']['value']} "
                  f"halt={report['verdict']['haltRules']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
