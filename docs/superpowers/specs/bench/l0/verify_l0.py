#!/usr/bin/env python3
"""#88 L0 Source — 커밋된 실측 증거의 적합성 확인기 (V1~V14).

보고서 하나가 스키마를 통과하는 것으로는 부족하다. 확인해야 하는 것은 **보고서의 수치가 프로브
산출물에서 나왔고, 프로브의 입력이 고정 revision·gold 해시와 같고, 보고서가 가리키는 좌표가 실제로
조회되는가** 다. 그 연결이 끊기면 형식만 맞는 보고서가 baseline 으로 흘러든다.

    pip install jsonschema
    python3 docs/superpowers/specs/bench/l0/verify_l0.py
    # 31 cases, 0 mismatches   (= manifest.json 의 caseCount)

각 규칙은 **결함 주입 케이스**를 가진다 — 규칙만 적고 검사가 없는 상태를 막는 장치다(I2 §5 · I3 §4.1
과 같은 원칙). 규칙이 예외를 던지면 그 규칙의 실패로 기록하고 나머지 규칙을 계속 실행한다.

계약: ../../2026-07-30-m0-l0-source-validation.md
"""
from __future__ import annotations

import copy
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
GOLD = REPO / "docs/superpowers/specs/gold"
SCHEMAS = REPO / "docs/superpowers/specs/schemas"
MANIFEST = json.loads((HERE / "manifest.json").read_text())

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SCHEMAS))
import build_report  # noqa: E402
import probe_code  # noqa: E402
import validate_rqr  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

TRACKS = ("db", "code")
MAX_RULE = 14
L0_COLLECTOR_FEATURES = {"db": {"P-ddl-parser", "E1"}, "code": {"E17"}}


def blob(revision: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{revision}:{path}"], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout


def load_ctx() -> dict:
    ctx = {"gold": json.loads((GOLD / "manifest.json").read_text()),
           "reports": {}, "probes": {}}
    for t in TRACKS:
        run = build_report.RUNS[t]
        ctx["reports"][t] = json.loads((run / "report.json").read_text())
        ctx["probes"][t] = json.loads((run / build_report.PROBE_NAME[t]).read_text())
    return ctx


# ---- 규칙 -------------------------------------------------------------------------------

def v1_schema_and_i3_rules(ctx):
    """V1 두 보고서가 스키마와 I3 R1~R20 을 통과한다."""
    schema = json.loads((SCHEMAS / "run-quality-report.v0.schema.json").read_text())
    errs, seen = [], 0
    for t, rep in ctx["reports"].items():
        seen += 1
        for e in Draft202012Validator(schema).iter_errors(rep):
            errs.append(f"{t}: [schema] {e.json_path}: {e.message}")
        for e in validate_rqr.cross_field_errors(rep):
            errs.append(f"{t}: [I3] {e}")
    return errs, seen


def v2_report_derives_from_probe(ctx):
    """V2 보고서는 프로브 산출물의 순수 함수다 — 손으로 고친 수치를 막는다."""
    errs, seen = [], 0
    for t, rep in ctx["reports"].items():
        seen += 1
        rebuilt = build_report.build_from(t, ctx["probes"][t])
        if rebuilt != rep:
            diff = [k for k in sorted(set(rebuilt) | set(rep)) if rebuilt.get(k) != rep.get(k)]
            errs.append(f"{t}: 보고서가 프로브에서 재생성되지 않는다 — 블록: {diff}")
    return errs, seen


def v3_input_identity(ctx):
    """V3 프로브 입력이 고정 revision 의 해시와 같다 — 아니면 baseline 이 아니다."""
    errs, seen = [], 0
    p = ctx["probes"]["db"]
    seen += 1
    if not p["input"]["hashMatchesPinned"]:
        errs.append("db: 입력 해시가 gold 고정값과 다르다")
    if p["input"]["contentHash"] != p["input"]["pinnedContentHash"]:
        errs.append("db: contentHash/pinnedContentHash 불일치")
    c = ctx["probes"]["code"]
    seen += 1
    if not c["input"]["allPinnedMatch"] or c["input"]["pinnedMismatched"]:
        errs.append(f"code: gold 고정 원본과 다른 파일: {c['input']['pinnedMismatched']}")
    if c["input"]["pinnedComparedCount"] < 1:
        errs.append("code: gold 고정 원본과 대조한 파일이 0건이다 — 입력 신원이 확인되지 않았다")
    # gold 는 범위의 일부만 고정한다(59파일 중 7건). 나머지는 고정 revision blob 과 **전수** 대조해야
    # '고정 revision 을 쟀다' 가 성립한다 — 경로 집합까지 같은지 프로브가 양방향으로 본다.
    seen += 1
    if not c["input"]["allFilesMatchRevision"] or c["input"]["revisionMismatched"]:
        errs.append(f"code: 고정 revision 과 다른 파일: {c['input']['revisionMismatched']}")
    if c["input"]["revisionFileCount"] != c["input"]["fileCount"]:
        errs.append(f"code: 범위 파일 수({c['input']['fileCount']})와 고정 revision 의 파일 수"
                    f"({c['input']['revisionFileCount']})가 다르다")
    for t in TRACKS:
        seen += 1
        if not ctx["probes"][t]["readOnly"]["unchanged"]:
            errs.append(f"{t}: 수집이 원본을 변경했다 (read-only 위반)")
    return errs, seen


def v4_gold_pinning(ctx):
    """V4 fixtureHash·goldSetId 가 gold manifest 의 파생값과 같다(I2 §6.1)."""
    errs, seen = [], 0
    g = ctx["gold"]
    for t in TRACKS:
        rep, p = ctx["reports"][t], ctx["probes"][t]
        seen += 1
        if rep["run"]["fixtureHash"] != g["fixtureHash"]:
            errs.append(f"{t}: run.fixtureHash 가 gold 고정값과 다르다")
        if rep["evl"]["conflictDetection"]["goldSetId"] != g["goldSetId"]:
            errs.append(f"{t}: goldSetId 가 gold 신원과 다르다")
        if not g["sourceRevision"].startswith(rep["run"]["sourceRevision"]):
            errs.append(f"{t}: sourceRevision 이 gold 고정 revision 과 다르다")
        if p["fixtureHash"] != g["fixtureHash"]:
            errs.append(f"{t}: 프로브의 fixtureHash 가 gold 고정값과 다르다")
        if g["status"]["state"] != "APPROVED":
            errs.append(f"{t}: gold 가 승인 상태가 아니다 — 이 수치는 baseline 이 될 수 없다(I1 G2)")
    return errs, seen


def v5_exclusion_locators_resolve(ctx):
    """V5 제외 좌표가 고정 revision 의 원본에서 실제로 조회된다 — 그럴듯한 경로 문자열을 막는다."""
    errs, seen = [], 0
    rev = ctx["gold"]["sourceRevision"]
    cache: dict[str, list[str]] = {}
    for t, rep in ctx["reports"].items():
        for ex in rep["exclusions"]:
            for loc in ex["examples"]:
                seen += 1
                m = re.match(r"^([^#]+)#L(\d+)", loc)
                if not m:
                    errs.append(f"{t}: 좌표 형식이 아니다: {loc}")
                    continue
                path, line = m.group(1), int(m.group(2))
                if path not in cache:
                    try:
                        cache[path] = blob(rev, path).split("\n")
                    except subprocess.CalledProcessError:
                        cache[path] = []
                lines = cache[path]
                if not lines:
                    errs.append(f"{t}: 고정 revision 에 없는 경로: {path}")
                elif not 1 <= line <= len(lines):
                    errs.append(f"{t}: 좌표가 파일 범위를 벗어난다: {loc} (행수 {len(lines)})")
                else:
                    target = re.search(r"\(([^)]+)\)\s*$", loc)
                    # 파일 단위 제외(미지원 언어 등)의 대상은 그 파일 자신이다 — 파일 안의 어떤 행에도
                    # 자기 경로가 적혀 있지 않으므로 행 내용 대조를 요구하면 정상 증거가 실패한다.
                    file_level = target and (path.endswith(target.group(1))
                                             or target.group(1).endswith(path))
                    if target and not file_level and target.group(1) not in lines[line - 1]:
                        errs.append(f"{t}: 좌표가 가리키는 행에 대상이 없다: {loc} → {lines[line - 1]!r}")
    return errs, seen


def v6_failure_fixtures_registered(ctx):
    """V6 실패 재현 픽스처가 gold manifest 에 등록돼 있고 해시가 일치한다(I3 §3.3 의 L0 대응)."""
    errs, seen = [], 0
    pinned = {s["path"]: s.get("contentHash") for s in ctx["gold"]["pinnedSources"]}
    gold_failures = {f["id"]: f for f in json.loads((GOLD / "failures.json").read_text())["fixtures"]}
    for t in TRACKS:
        for fx in ctx["probes"][t]["failureFixtures"]:
            seen += 1
            if fx["path"] not in pinned:
                errs.append(f"{t}: 픽스처가 gold manifest 에 등록되지 않았다: {fx['path']}")
            elif pinned[fx["path"]] != fx["contentHash"]:
                errs.append(f"{t}: 픽스처 해시가 gold 고정값과 다르다: {fx['path']}")
            if not fx["hashMatchesPinned"]:
                errs.append(f"{t}: 프로브가 해시 불일치를 기록했다: {fx['path']}")
            if fx["id"] not in gold_failures:
                errs.append(f"{t}: gold failures.json 에 없는 픽스처 id: {fx['id']}")
            else:
                # id 의 존재만 보면 다른 픽스처의 id 를 바꿔 붙여도 통과한다 — **귀속**을 본다.
                g = gold_failures[fx["id"]]
                if g["path"] != fx["path"]:
                    errs.append(f"{t}: 픽스처 id 와 경로의 귀속이 다르다: {fx['id']} → "
                                f"gold={g['path']} / 프로브={fx['path']}")
                if g["contentHash"] != fx["contentHash"]:
                    errs.append(f"{t}: {fx['id']} 의 해시가 gold 선언과 다르다")
                if g["reported"] and fx["expectedReported"] != len(g["reported"]):
                    errs.append(f"{t}: {fx['id']} 의 기대 보고 건수가 gold 와 다르다")
    if seen != 6:
        errs.append(f"실패 픽스처 6건을 모두 돌려야 한다 — 실행된 것 {seen}건")
    return errs, seen


def v7_gates_match_verdict(ctx):
    """V7 게이트 실패가 판정·중단 규칙과 정합한다(I1 G4 · §3.2 · I3 R6·R8·R9)."""
    errs, seen = [], 0
    for t, rep in ctx["reports"].items():
        seen += 1
        gs = {g["id"]: g for g in rep["gates"]}
        missing = {"gate-determinism", "gate-l0-metadata-completeness",
                   "gate-error-visibility", "gate-security-masking"} - set(gs)
        if missing:
            errs.append(f"{t}: L0 무조건 게이트가 빠졌다: {sorted(missing)}")
        failed = [g for g in rep["gates"] if g["status"] == "FAIL"]
        halts = rep["verdict"]["haltRules"]
        if failed and rep["verdict"]["value"] == "PASS":
            errs.append(f"{t}: 게이트 FAIL 이 있는데 판정이 PASS 다")
        if gs.get("gate-determinism", {}).get("status") == "FAIL" and "H1" not in halts:
            errs.append(f"{t}: 결정성 실패인데 H1 이 없다")
        if gs.get("gate-security-masking", {}).get("status") == "FAIL" and "H2" not in halts:
            errs.append(f"{t}: L0 보안 미통과인데 H2 가 없다")
        if failed and not halts and not rep["verdict"]["restrictions"]:
            errs.append(f"{t}: 게이트가 실패했는데 중단·제한 근거가 비어 있다")
    return errs, seen


def v8_collector_judgments(ctx):
    """V8 이 실행이 측정한 수집기 전부에 판정이 있고, 근거가 이 실행을 가리킨다(#88 완료 기준 · I1 G5)."""
    errs, seen = [], 0
    for t, rep in ctx["reports"].items():
        seen += 1
        judged = {j["featureId"]: j for j in rep["featureJudgments"]}
        missing = L0_COLLECTOR_FEATURES[t] - set(judged)
        if missing:
            errs.append(f"{t}: 판정이 없는 수집기: {sorted(missing)}")
        for fid, j in judged.items():
            if j["judgment"] == "Core" and not j["measured"]:
                errs.append(f"{t}: 측정하지 않은 {fid} 를 Core 로 판정했다(I1 §5.3)")
            if rep["run"]["runId"] not in j["evidenceRefs"] and \
                    f"report:{rep['run']['runId']}" not in j["evidenceRefs"]:
                errs.append(f"{t}: {fid} 판정 근거가 이 실행을 가리키지 않는다")
            if j["judgment"] == "Core" and any(g["status"] == "FAIL" for g in rep["gates"]):
                errs.append(f"{t}: 무조건 게이트가 실패한 실행으로 {fid} 를 Core 로 판정했다(I1 G4)")
    return errs, seen


def v9_tracks_separated(ctx):
    """V9 트랙별로 분리 산출한다 — 합산은 실패를 가린다(I1 §4.2 · I3 §1)."""
    errs = []
    ids = [r["run"]["runId"] for r in ctx["reports"].values()]
    tracks = [r["run"]["track"] for r in ctx["reports"].values()]
    if len(set(ids)) != len(ids):
        errs.append(f"보고서가 같은 runId 를 쓴다: {ids}")
    if sorted(tracks) != sorted(TRACKS):
        errs.append(f"트랙이 분리되지 않았다: {tracks}")
    for t, rep in ctx["reports"].items():
        if rep["run"]["track"] != t:
            errs.append(f"{t}: 보고서의 track 이 디렉토리와 다르다({rep['run']['track']})")
        if rep["run"]["layer"] != "L0":
            errs.append(f"{t}: layer 가 L0 이 아니다")
    return errs, len(ids)


def v10_baseline_eligibility(ctx):
    """V10 BASELINE 로 남기는 조건(I3 R12) — 고정 fixture + 실측 + 적용 버전 PINNED."""
    errs, seen = [], 0
    for t, rep in ctx["reports"].items():
        seen += 1
        pinned_fix = rep["run"]["fixtureHash"] != "UNPINNED"
        is_baseline = rep["run"]["reportKind"] == "BASELINE"
        versions_ok = all(v["status"] == "PINNED"
                          for v in rep["versions"].values() if v["status"] != "NOT_APPLICABLE")
        expect = pinned_fix and is_baseline and versions_ok
        if rep["baseline"]["eligibleAsBaseline"] != expect:
            errs.append(f"{t}: eligibleAsBaseline={rep['baseline']['eligibleAsBaseline']} "
                        f"이지만 조건 계산은 {expect} 다")
        if is_baseline and not pinned_fix:
            errs.append(f"{t}: 미고정 fixture 로 BASELINE 을 주장한다")
        if rep["versions"]["collector"]["status"] != "PINNED":
            errs.append(f"{t}: 수집기 버전이 고정되지 않았다 — 재현할 수 없는 실행은 기준선이 아니다")
    return errs, seen


def v11_declared_paths_measured(ctx):
    """V11 선언한 수집 경로가 **전부** 계측됐다 — 재지 않은 경로를 실측 주장에 넣는 것을 막는다."""
    errs, seen = [], 0
    db = ctx["probes"]["db"]
    seen += 1
    # db 는 두 경로다: DDL 텍스트(DdlParser) + JDBC 메타데이터(SampleLegacyDb→MetadataService).
    if "acquisition" not in db or not db["acquisition"]["acquired"]:
        errs.append("db: DDL 텍스트 경로의 수집 결과가 없다")
    md = db.get("ingestStore", {}).get("metadataService")
    if not md:
        errs.append("db: 선언한 MetadataService 경로가 계측되지 않았다 — 저장소 질의만으로는 "
                    "그 수집기의 산출물·게이트 특성을 잰 것이 아니다")
    else:
        for key in ("acquiredTables", "determinismRate", "provenanceRate", "runs"):
            if key not in md:
                errs.append(f"db: MetadataService 계측에 {key} 가 없다")
        if md.get("runs", 0) < 3:
            errs.append("db: MetadataService 결정성을 3회 실행으로 재지 않았다")
    code = ctx["probes"]["code"]
    seen += 1
    if not code.get("inventory", {}).get("walked"):
        errs.append("code: 수집기 실행 결과가 없다")
    if "coverageState" not in code:
        errs.append("code: 커버리지 state 를 재지 않았다 — 보고서의 deterministic 이 근거를 잃는다")
    return errs, seen


def v12_determinism_contract(ctx):
    """V12 결정성 PASS 를 적은 실행은 프로브에서 실제로 1.0 이고, 시드에 무관하다(#112).

    게이트 상태는 보고서의 문장이고, 결정성은 프로브가 잰 사실이다. 둘을 따로 보지 않으면
    '수치는 1.0 인데 시드를 바꾸면 갈리는' 실행이 PASS 로 남을 수 있다 — #88 이 정확히 그 상태였다.
    """
    errs, seen = [], 0
    for t, rep in ctx["reports"].items():
        seen += 1
        gate = {g["id"]: g for g in rep["gates"]}.get("gate-determinism", {})
        p = ctx["probes"][t]
        rate = (p["determinismObserved"]["rate"] if t == "code"
                else p["determinism"]["rate"])
        if gate.get("status") == "PASS" and rate != 1.0:
            errs.append(f"{t}: gate-determinism 이 PASS 인데 프로브 결정성은 {rate} 다")
        if gate.get("observed") != rate:
            errs.append(f"{t}: 게이트에 적힌 결정성({gate.get('observed')})이 프로브({rate})와 다르다")
    seen += 1
    # code 트랙만 시드 통제 실험을 남긴다(db 수집기는 Kotlin 이라 해시 랜덤화 대상이 아니다).
    for e in probe_code.determinism_errors(ctx["probes"]["code"]):
        errs.append(f"code: {e}")
    return errs, seen


def v13_cited_baseline_resolves(ctx):
    """V13 인용한 이전 실행이 실제로 조회되고, 그 증거 자체가 계약을 통과한다(#112).

    `baseline.previous` 는 다른 실행을 근거로 끌어오는 포인터다. 그 실행이 사라지거나 손상돼도
    현재 보고서는 형식상 멀쩡하다 — V5 가 제외 좌표에 하는 일을 실행 인용에도 한다.
    현재 실행만 검사하는 V1 은 인용된 실행을 보지 않는다.
    """
    errs, seen = [], 0
    schema = json.loads((SCHEMAS / "run-quality-report.v0.schema.json").read_text())
    for t, rep in ctx["reports"].items():
        prev = rep["baseline"]["previous"]
        if prev is None:
            continue
        seen += 1
        cited = None
        for d in sorted((HERE / "runs").iterdir()):
            f = d / "report.json"
            if f.is_file():
                r = json.loads(f.read_text())
                if r["run"]["runId"] == prev["runId"]:
                    cited = r
                    break
        if cited is None:
            errs.append(f"{t}: 인용한 이전 실행의 보고서가 없다: {prev['runId']}")
            continue
        for k in ("projectId", "layer", "track", "sourceRevision", "fixtureHash"):
            if cited["run"][k] != prev[k]:
                errs.append(f"{t}: baseline.previous.{k} 가 인용한 실행의 실제 값과 다르다 "
                            f"({prev[k]!r} / 실제 {cited['run'][k]!r})")
        if cited["schemaVersion"] != prev["schemaVersion"]:
            errs.append(f"{t}: baseline.previous.schemaVersion 이 인용한 실행과 다르다")
        # 인용된 증거가 그 자체로 계약을 통과하지 못하면 비교의 기준이 될 수 없다.
        for e in Draft202012Validator(schema).iter_errors(cited):
            errs.append(f"{t}: 인용한 {prev['runId']} 가 스키마를 어긴다 — {e.json_path}: {e.message}")
        for e in validate_rqr.cross_field_errors(cited):
            errs.append(f"{t}: 인용한 {prev['runId']} 가 I3 규칙을 어긴다 — {e}")
        # deltas 의 previous 값은 인용한 보고서의 지표(또는 게이트 관측값)와 같아야 한다.
        cited_gates = {f"gates.{g['id']}": g.get("observed") for g in cited.get("gates", [])}
        for d in rep["baseline"]["deltas"]:
            if d["metric"].startswith("gates."):
                got = cited_gates.get(d["metric"])
            else:
                got = cited["metrics"].get(d["metric"], {}).get("value")
            if got != d["previous"]:
                errs.append(f"{t}: deltas[{d['metric']}].previous={d['previous']} 인데 "
                            f"{prev['runId']} 의 값은 {got} 다")
    return errs, seen


def _range(locator: str):
    m = re.search(r"#L(\d+)(?:-L(\d+))?", locator or "")
    if not m:
        return None
    start = int(m.group(1))
    return start, int(m.group(2) or start)


def v14_report_attribution(ctx):
    """V14 보고율은 **귀속**으로 센다 — 건수만 맞추거나 그럴듯한 좌표를 적어 통과하는 경로를 막는다(#114).

    확인기는 프로브의 `reported: true` 를 믿지 않고, 그 항목이 인용한 관측 좌표가 gold 기대 좌표와
    실제로 겹치는지·사유가 있는지를 다시 본다. 겹침을 다시 계산하지 않으면 '보고했다' 는 주장 자체가
    검증되지 않은 채 오류 가시성 게이트를 통과한다.
    """
    errs, seen = [], 0
    gold_failures = {f["id"]: f for f in json.loads((GOLD / "failures.json").read_text())["fixtures"]}
    for t in TRACKS:
        for fx in ctx["probes"][t]["failureFixtures"]:
            att = fx.get("reportAttribution")
            if att is None:
                # 보고 채널이 없던 실행 — '보고 0건' 이라는 주장 자체를 검사한다.
                seen += 1
                if fx.get("actualReported", 0) != 0:
                    errs.append(f"{t}: {fx['id']} 는 귀속 근거 없이 보고 건수를 주장한다")
                continue
            expected = gold_failures[fx["id"]]["reported"]
            if len(att["expected"]) != len(expected):
                errs.append(f"{t}: {fx['id']} 의 기대 항목 수가 gold 와 다르다")
            for e, g in zip(att["expected"], expected):
                seen += 1
                if e["kind"] != g["kind"] or e["locator"] != g["locator"]:
                    errs.append(f"{t}: {fx['id']} 의 기대 항목이 gold 선언과 다르다 "
                                f"({e['kind']} {e['locator']} ≠ {g['kind']} {g['locator']})")
                    continue
                if not e["reported"]:
                    continue
                if not e.get("reasonPresent"):
                    errs.append(f"{t}: {fx['id']} {g['kind']} 를 사유 없이 보고로 셌다(R-F-2)")
                want, got = _range(g["locator"]), _range(e.get("observedLocator", ""))
                if got is None:
                    errs.append(f"{t}: {fx['id']} {g['kind']} 의 관측 좌표가 없다 — 보고로 셀 수 없다")
                elif not (got[0] <= want[1] and want[0] <= got[1]):
                    errs.append(f"{t}: {fx['id']} {g['kind']} 의 관측 좌표 {e['observedLocator']} 가 "
                                f"gold 좌표 {g['locator']} 와 겹치지 않는다")
            recomputed = sum(1 for e in att["expected"] if e["reported"])
            if att["actualReported"] != recomputed or fx["actualReported"] != recomputed:
                errs.append(f"{t}: {fx['id']} 의 보고 건수가 항목별 귀속과 맞지 않는다 "
                            f"(주장 {fx['actualReported']} / 귀속 {recomputed})")
            if att.get("unattributedReports"):
                # 과대 집계는 R-F-4 위반 신호다 — 픽스처에서는 실패로 본다.
                errs.append(f"{t}: {fx['id']} 에 gold 기대에 귀속되지 않은 보고가 있다: "
                            f"{att['unattributedReports']}")
    return errs, seen


RULES = {
    "V1": v1_schema_and_i3_rules,
    "V2": v2_report_derives_from_probe,
    "V3": v3_input_identity,
    "V4": v4_gold_pinning,
    "V5": v5_exclusion_locators_resolve,
    "V6": v6_failure_fixtures_registered,
    "V7": v7_gates_match_verdict,
    "V8": v8_collector_judgments,
    "V9": v9_tracks_separated,
    "V10": v10_baseline_eligibility,
    "V11": v11_declared_paths_measured,
    "V12": v12_determinism_contract,
    "V13": v13_cited_baseline_resolves,
    "V14": v14_report_attribution,
}


# ---- 결함 주입 케이스 -------------------------------------------------------------------
# 규칙마다 '이 규칙이 실제로 무는가' 를 확인한다. 케이스 총계는 manifest.json 이 못박는다.

def _inj(ctx, fn):
    c = copy.deepcopy(ctx)
    fn(c)
    return c


def injections() -> list[tuple[str, str, callable]]:
    def bad_schema(c):
        c["reports"]["db"]["verdict"]["value"] = "MOSTLY_PASS"

    def bad_i3(c):
        c["reports"]["db"]["counts"]["excluded"] += 1

    def handmade_metric(c):
        # 실패한 게이트의 수치를 손으로 통과시킨 모양. (#112 이후 determinism 은 실제로 1.0 이라
        # 그 값을 1.0 으로 바꾸는 주입은 아무것도 바꾸지 않는다 — 아직 실패인 지표를 고른다.)
        c["reports"]["code"]["metrics"]["provenanceCompleteness"]["value"] = 1.0

    def handmade_gate(c):
        # 실제로 실패한 게이트를 손으로 통과시킨다. 이미 통과한 게이트에 PASS 를 덮으면 주입이
        # 아무것도 바꾸지 않아, 규칙이 무는지 확인하지 못한 채 케이스만 남는다.
        for g in c["reports"]["db"]["gates"]:
            if g["id"] == "gate-l0-metadata-completeness":
                g["status"] = "PASS"
                g["observed"] = 1.0

    def input_drift(c):
        c["probes"]["db"]["input"]["hashMatchesPinned"] = False

    def wrote_source(c):
        c["probes"]["code"]["readOnly"]["unchanged"] = False

    def fixture_hash_drift(c):
        c["reports"]["db"]["run"]["fixtureHash"] = "sha256:" + "0" * 64

    def gold_not_approved(c):
        c["gold"]["status"]["state"] = "DRAFT"

    def phantom_locator(c):
        c["reports"]["db"]["exclusions"][0]["examples"][0] = \
            "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql#L9999 (VW_ORD_SUMMARY)"

    def wrong_line(c):
        c["reports"]["db"]["exclusions"][0]["examples"][0] = \
            "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql#L1 (VW_ORD_SUMMARY)"

    def unregistered_fixture(c):
        c["probes"]["db"]["failureFixtures"][0]["path"] = \
            "docs/superpowers/specs/gold/fixtures/failure/db-not-real.sql"

    def dropped_fixture(c):
        c["probes"]["code"]["failureFixtures"].pop()

    def missing_gate(c):
        c["reports"]["code"]["gates"] = [g for g in c["reports"]["code"]["gates"]
                                         if g["id"] != "gate-security-masking"]

    def halt_dropped(c):
        # 결정성이 다시 깨진 실행인데 H1 을 달지 않은 보고서.
        for g in c["reports"]["code"]["gates"]:
            if g["id"] == "gate-determinism":
                g["status"] = "FAIL"
                g["observed"] = 0.6667
        c["reports"]["code"]["verdict"]["haltRules"] = ["H2"]

    def pass_with_failed_gate(c):
        c["reports"]["db"]["verdict"]["value"] = "PASS"

    def missing_judgment(c):
        c["reports"]["db"]["featureJudgments"] = [
            j for j in c["reports"]["db"]["featureJudgments"] if j["featureId"] != "E1"]

    def core_on_failed_run(c):
        c["reports"]["code"]["featureJudgments"][0]["judgment"] = "Core"

    def judgment_without_evidence(c):
        c["reports"]["db"]["featureJudgments"][0]["evidenceRefs"] = ["run-someone-else-0001"]

    def merged_tracks(c):
        c["reports"]["code"]["run"]["track"] = "db"

    def unpinned_collector_baseline(c):
        c["reports"]["db"]["versions"]["collector"] = {"status": "UNPINNED", "value": None}

    def revision_drift(c):
        c["probes"]["code"]["input"]["revisionMismatched"] = [
            "backend/src/main/kotlin/com/ontostudio/rdb/DdlParser.kt"]
        c["probes"]["code"]["input"]["allFilesMatchRevision"] = False

    def swapped_fixture_id(c):
        fx = c["probes"]["db"]["failureFixtures"]
        fx[0]["id"], fx[1]["id"] = fx[1]["id"], fx[0]["id"]

    def metadata_path_unmeasured(c):
        c["probes"]["db"]["ingestStore"].pop("metadataService")

    def coverage_state_unmeasured(c):
        c["probes"]["code"].pop("coverageState")

    def determinism_regressed(c):
        # 게이트는 PASS 인 채로 프로브만 갈린 실행 — #88 상태로의 회귀.
        c["probes"]["code"]["determinismObserved"].update(
            {"rate": 0.6667, "distinctHashes": 2, "divergingPaths": ["nodes[].community"]})

    def fake_report_claim(c):
        """관측 좌표 없이 '보고했다' 고 주장 — 귀속 근거 없는 보고율."""
        att = c["probes"]["db"]["failureFixtures"][0]["reportAttribution"]
        att["expected"][0].pop("observedLocator", None)

    def wrong_report_locator(c):
        """그럴듯하지만 gold 기대 구간과 겹치지 않는 관측 좌표."""
        att = c["probes"]["code"]["failureFixtures"][0]["reportAttribution"]
        att["expected"][0]["observedLocator"] = "code-broken-syntax.kt#L999"

    def phantom_baseline(c):
        c["reports"]["code"]["baseline"]["previous"]["runId"] = "run-l0-code-3c27259-999"

    def forged_delta_baseline(c):
        for d in c["reports"]["code"]["baseline"]["deltas"]:
            if d["metric"] == "determinism":
                d["previous"] = 0.9  # 개선폭을 작게 보이도록 기준선을 손봄

    def baseline_identity_lie(c):
        c["reports"]["code"]["baseline"]["previous"]["sourceRevision"] = "deadbee"

    def seed_dependent(c):
        # 3회는 우연히 같았지만 시드를 바꾸면 갈리는 실행 — 재현 보장이 없다.
        c["probes"]["code"]["determinismControl"]["seedIndependent"] = False

    return [
        ("V1", "판정 어휘 위반", bad_schema),
        ("V1", "counts 합 불일치(I3 R2)", bad_i3),
        ("V2", "지표를 손으로 고침", handmade_metric),
        ("V2", "게이트 결과를 손으로 통과시킴", handmade_gate),
        ("V3", "입력이 고정 해시와 다름", input_drift),
        ("V3", "수집이 원본을 변경", wrote_source),
        ("V4", "fixtureHash 가 gold 와 다름", fixture_hash_drift),
        ("V4", "미승인 gold 로 baseline 주장", gold_not_approved),
        ("V5", "좌표가 파일 범위를 벗어남", phantom_locator),
        ("V5", "좌표가 다른 행을 가리킴", wrong_line),
        ("V6", "미등록 픽스처", unregistered_fixture),
        ("V6", "픽스처 일부만 실행", dropped_fixture),
        ("V7", "무조건 게이트 누락", missing_gate),
        ("V7", "결정성 실패인데 H1 없음", halt_dropped),
        ("V7", "게이트 FAIL 인데 PASS 판정", pass_with_failed_gate),
        ("V8", "측정한 수집기 판정 누락", missing_judgment),
        ("V8", "게이트 실패 실행으로 Core 판정", core_on_failed_run),
        ("V8", "근거가 이 실행을 가리키지 않음", judgment_without_evidence),
        ("V9", "두 트랙을 한 트랙으로 표기", merged_tracks),
        ("V10", "버전 미고정인데 baseline 자격 주장", unpinned_collector_baseline),
        ("V3", "고정 revision 과 다른 파일이 범위에 있음", revision_drift),
        ("V6", "픽스처 id 를 바꿔 붙임(귀속 위조)", swapped_fixture_id),
        ("V11", "선언한 MetadataService 경로를 재지 않음", metadata_path_unmeasured),
        ("V11", "커버리지 state 를 재지 않음", coverage_state_unmeasured),
        ("V12", "결정성이 다시 갈렸는데 게이트는 PASS", determinism_regressed),
        ("V12", "시드를 바꾸면 산출물이 달라짐", seed_dependent),
        ("V13", "인용한 이전 실행이 실재하지 않음", phantom_baseline),
        ("V14", "귀속 근거 없이 보고 주장", fake_report_claim),
        ("V14", "관측 좌표가 gold 구간과 겹치지 않음", wrong_report_locator),
        ("V13", "deltas 의 기준선 값을 손으로 고침", forged_delta_baseline),
        ("V13", "인용한 실행의 신원을 다르게 적음", baseline_identity_lie),
    ]


def main() -> int:
    ctx = load_ctx()
    failures = []

    print("== 규칙 실행 (커밋된 증거)")
    for rid, fn in RULES.items():
        try:
            errs, seen = fn(ctx)
        except Exception as e:  # 손상된 증거일수록 예외가 잘 난다 — 침묵하지 않는다
            failures.append(f"[{rid}] 예외: {type(e).__name__}: {e}")
            print(f"  {rid}: 예외 — {type(e).__name__}: {e}")
            continue
        if seen == 0:
            failures.append(f"[{rid}] 검사 대상이 0건이다 — 규칙이 아무것도 들여다보지 않았다")
        for e in errs:
            failures.append(f"[{rid}] {e}")
        print(f"  {rid}: 대상 {seen}건, 오류 {len(errs)}건")

    print("== 결함 주입 (규칙이 실제로 무는가)")
    cases = injections()
    mismatches = 0
    for rid, name, fn in cases:
        bad = _inj(ctx, fn)
        try:
            errs, _ = RULES[rid](bad)
            caught = bool(errs)
        except Exception:
            caught = True  # 예외도 '걸렸다' 로 본다 — 통과만 아니면 된다
        if not caught:
            mismatches += 1
            print(f"  [{rid}] {name}: 걸리지 않았다")
    covered = {rid for rid, _, _ in cases}
    for rid in RULES:
        if rid not in covered:
            mismatches += 1
            print(f"  [{rid}] 결함 주입 케이스가 없다")

    if len(cases) != MANIFEST["caseCount"]:
        mismatches += 1
        print(f"  케이스 수가 manifest 와 다르다: {len(cases)} != {MANIFEST['caseCount']}")
    if MANIFEST["ruleRange"] != f"V1-V{MAX_RULE}" or len(RULES) != MAX_RULE:
        mismatches += 1
        print(f"  규칙 범위가 manifest 와 다르다: {MANIFEST['ruleRange']} / 규칙 {len(RULES)}개")

    print(f"\n{len(cases)} cases, {mismatches} mismatches")
    for f in failures:
        print("FAIL " + f)
    if failures or mismatches:
        return 1
    print("[ok] L0 실측 증거가 계약과 일치한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
