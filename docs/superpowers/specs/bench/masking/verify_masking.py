#!/usr/bin/env python3
"""#115 마스킹 증거 적합성 확인기 (M1~M10).

"게이트가 PASS 라고 적혀 있다" 는 것으로는 부족하다. 확인할 것은 **수치가 증거에서 나왔고, 증거의
입력이 승인된 gold 와 같고, 두 엔진이 같은 결과를 냈고, 어디에도 원문이 남지 않았는가** 다.

모든 규칙은 결함 주입 케이스를 갖는다 — 규칙만 적고 검사가 없는 상태를 막는 장치다(I2 §5 · L0 벤치와
같은 원칙). 규칙은 자기가 들여다본 대상 수를 보고하며 0건이면 실패로 처리한다.

    python3 docs/superpowers/specs/bench/masking/verify_masking.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
GOLD = REPO / "docs/superpowers/specs/gold"
MANIFEST = HERE / "manifest.json"

sys.path.insert(0, str(REPO / "codegraph/src"))
from lodestar_codegraph.mask import detect, load_rules, mask_text  # noqa: E402

_spec = importlib.util.spec_from_file_location("build_masking_report", HERE / "build_masking_report.py")
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)

CONTRACTED_ALLOW = [
    "ALLOW.MASK_TOKEN", "ALLOW.GIT_SHA", "ALLOW.CONTENT_HASH", "ALLOW.UUID",
    "ALLOW.JDBC_URL", "ALLOW.TIMESTAMP", "ALLOW.INTERNAL_ID",
]
CONTRACTED_DETECT = [
    "SECRET.AWS_ACCESS_KEY_ID", "SECRET.GITHUB_TOKEN", "SECRET.SLACK_TOKEN", "SECRET.JWT",
    "SECRET.PRIVATE_KEY_BLOCK", "SECRET.URL_CREDENTIAL", "SECRET.KEYED_VALUE",
    "PII.KR_RRN", "PII.EMAIL", "PII.KR_PHONE", "PII.CARD_NO_DELIMITED", "PII.CARD_NO_PLAIN",
    "PII.KR_BANK_ACCOUNT", "PII.KR_BIZ_NO", "PII.IP_ADDRESS", "PII.KR_ADDRESS", "PII.KR_NAME",
]

RULE_COPIES = [
    REPO / "backend/src/main/resources/com/ontostudio/security/masking-rules.v0.json",
    REPO / "codegraph/src/lodestar_codegraph/masking-rules.v0.json",
]


def sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def load_ctx() -> dict:
    ctx = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in builder.EVIDENCE.items()}
    ctx["report"] = json.loads((HERE / "report.json").read_text(encoding="utf-8"))
    ctx["pii"] = json.loads((GOLD / "pii.json").read_text(encoding="utf-8"))
    ctx["goldManifest"] = json.loads((GOLD / "manifest.json").read_text(encoding="utf-8"))
    ctx["parityFixture"] = json.loads(builder.EVIDENCE["parityFixture"].read_text(encoding="utf-8"))
    ctx["corpus"] = {
        f["sourceId"]: (REPO / f["path"]).read_text(encoding="utf-8")
        for f in ctx["pii"]["scope"]["files"]
    }
    return ctx


# ---- 규칙 -----------------------------------------------------------------------------------
# 각 규칙: (ok, inspected, detail)

def derive_fixture_hash(entries) -> str:
    """gold `validate_gold.py#derive_fixture_hash` 와 같은 산식 — 경로 사전순 `"<경로> <sha256>"` 집계."""
    lines = sorted(f"{path} {digest}" for path, digest in entries)
    return sha256_bytes(("\n".join(lines) + "\n").encode())


def m1_gold_identity(ctx):
    pii, man = ctx["pii"], ctx["goldManifest"]
    n = 0
    for f in pii["scope"]["files"]:
        n += 1
        if sha256_bytes(ctx["corpus"][f["sourceId"]].encode("utf-8")) != f["contentHash"]:
            return False, n, f"코퍼스 해시 불일치: {f['sourceId']}"
    # 승인된 fixtureHash 를 **디스크의 실제 픽스처**에서 다시 계산해 대조한다 — manifest 의 선언값만
    # 비교하면 승인되지 않은 픽스처 변경을 잡지 못한다(리뷰 질문 8).
    entries = []
    for e in man["fixtures"]:
        n += 1
        path = GOLD / e["path"]   # manifest 의 픽스처 경로는 gold 디렉토리 기준이다
        if not path.exists():
            return False, n, f"픽스처가 없다: {e['path']}"
        entries.append((e["path"], sha256_bytes(path.read_bytes())))
    if derive_fixture_hash(entries) != man["fixtureHash"]:
        return False, n, "실제 픽스처에서 재계산한 fixtureHash 가 승인값과 다르다"
    if man["status"]["state"] != "APPROVED":
        return False, n, "gold 가 승인 상태가 아니다"
    if man["expectedCounts"]["pii.json"] != len(pii["items"]):
        return False, n, "gold 항목 수가 고정값과 다르다"
    if ctx["report"]["fixtureHash"] != man["fixtureHash"]:
        return False, n, "보고서 fixtureHash 가 gold 파생값과 다르다"
    if ctx["report"]["goldSetState"] != man["status"]["state"]:
        return False, n, "보고서의 gold 상태 표기가 다르다"
    return True, n, f"코퍼스 {n}파일 · gold {len(pii['items'])}항목"


def m2_engine_parity(ctx):
    k, p = builder.span_view(ctx["engineKotlin"]), builder.span_view(ctx["enginePython"])
    spans = sum(len(f["spans"]) for f in k)
    if not spans:
        return False, 0, "비교할 스팬이 없다"
    if k != p:
        diff = [a["sourceId"] for a, b in zip(k, p) if a != b]
        return False, spans, f"엔진 결과 불일치(gold): {diff or 'file set'}"
    if ctx["report"]["engines"]["parity"] is not True:
        return False, spans, "보고서가 불일치를 일치로 적었다"

    # gold 는 새 분기를 지나가지 않는다 — 패리티 픽스처에서도 두 엔진이 같아야 한다.
    pk, pp = ctx["parityKotlin"], ctx["parityPython"]
    cases = len(pk["cases"])
    if not cases:
        return False, spans, "패리티 케이스가 없다"
    vk, vp = builder.parity_view(pk), builder.parity_view(pp)
    if vk != vp:
        diff = [a.get("id") for a, b in zip(vk, vp) if a != b]
        return False, spans + cases, f"엔진 결과 불일치(패리티): {diff or 'case set'}"
    fixture_hash = sha256_bytes(builder.EVIDENCE["parityFixture"].read_bytes())
    if not (pk["fixtureHash"] == pp["fixtureHash"] == fixture_hash):
        return False, spans + cases, "두 증거가 가리키는 패리티 픽스처가 서로 다르거나 변조됐다"
    if ctx["report"]["engines"]["branchParity"]["identical"] is not True:
        return False, spans + cases, "보고서가 분기 불일치를 일치로 적었다"
    return True, spans + cases, f"gold 스팬 {spans}건 + 패리티 {cases}케이스×정책 {len(pk['policies'])}종 동일"


def m3_report_is_pure_function(ctx):
    rebuilt = builder.build()
    keys = sorted(set(rebuilt) | set(ctx["report"]))
    for key in keys:
        if rebuilt.get(key) != ctx["report"].get(key):
            return False, len(keys), f"보고서가 증거에서 파생되지 않았다: {key}"
    return True, len(keys), f"최상위 {len(keys)}블록 재생성 일치"


def m4_positive_locators_resolve(ctx):
    pii = ctx["pii"]
    spans = {f["sourceId"]: f["spans"] for f in ctx["enginePython"]["files"]}
    n = 0
    for item in pii["items"]:
        if item["expect"] != "MASKED":
            continue
        n += 1
        src = item["ref"]["sourceId"]
        line_no = int(item["ref"]["locator"].rsplit("#L", 1)[1])
        line = ctx["corpus"][src].split("\n")[line_no - 1]
        if item["value"]["text"] not in line:
            return False, n, f"{item['id']}: 좌표가 원본에서 조회되지 않는다"
        if not any(s["line"] == line_no for s in spans[src]):
            return False, n, f"{item['id']}: 그 줄에 마스킹 스팬이 없다"
    if not n:
        return False, 0, "양성이 없다"
    return True, n, f"양성 {n}건의 좌표·스팬 귀속 확인"


def m5_gate_arithmetic(ctx):
    rep = ctx["report"]
    ids = [g["id"] for g in rep["gates"]]
    required = ["gate-security-masking", "gate-engine-parity", "gate-engine-parity-branches",
                "gate-db-ingest-masking", "gate-code-emit-masking", "gate-no-plaintext-in-records"]
    if sorted(ids) != sorted(required):
        return False, len(ids), f"게이트 목록이 다르다: {ids}"
    by_id = {g["id"]: g for g in rep["gates"]}
    broken = rep["gold"]["unmasked"] + rep["gold"]["partiallyCovered"]
    if bool(broken) == (by_id["gate-security-masking"]["status"] == "PASS"):
        return False, len(ids), "미마스킹·부분마스킹 건수와 게이트 상태가 어긋난다"
    if by_id["gate-security-masking"]["observed"] != len(broken):
        return False, len(ids), "게이트 관측값이 판정 목록과 다르다"
    db = ctx["ingestDb"]["retrievableUnmaskedPiiValues"]
    if (by_id["gate-db-ingest-masking"]["status"] == "PASS") != (db == 0):
        return False, len(ids), "적재 경로 게이트가 관측과 어긋난다"
    branch = by_id["gate-engine-parity-branches"]
    if (branch["status"] == "PASS") != (branch["observed"] is True):
        return False, len(ids), "분기 패리티 게이트가 관측과 어긋난다"
    return True, len(ids), f"게이트 {len(ids)}종 산식 일치"


def m6_false_positives_are_accounted(ctx):
    rep, verdicts = ctx["report"], ctx["goldVerdicts"]
    negs = [i for i in verdicts["items"] if i["expect"] == "NOT_MASKED"]
    if not negs:
        return False, 0, "음성이 없다"
    if rep["gold"]["preserved"] + len(rep["gold"]["falsePositives"]) != len(negs):
        return False, len(negs), "음성 판정 합이 음성 수와 다르다"
    if abs(rep["gold"]["falsePositiveRate"] - len(rep["gold"]["falsePositives"]) / len(negs)) > 1e-9:
        return False, len(negs), "오탐률이 판정과 어긋난다"
    for cls in builder.CRITICAL_FP_CLASSES:
        if cls not in rep["gold"]["criticalClassFalsePositives"]:
            return False, len(negs), f"{cls} 오탐 표기가 없다"
        actual = sum(1 for i in negs if i["class"] == cls and i["verdict"] == "FALSE_POSITIVE")
        if rep["gold"]["criticalClassFalsePositives"][cls] != actual:
            return False, len(negs), f"{cls} 오탐 표기가 관측과 다르다"
    return True, len(negs), f"음성 {len(negs)}건 · 오탐 {len(rep['gold']['falsePositives'])}건"


def m7_rule_spec_single_source(ctx):
    canonical = REPO / "docs/superpowers/specs/security/masking-rules.v0.json"
    want = sha256_bytes(canonical.read_bytes())
    n = 1
    for c in RULE_COPIES:
        n += 1
        if sha256_bytes(c.read_bytes()) != want:
            return False, n, f"규칙 사본 표류: {c.relative_to(REPO)}"
    if ctx["report"]["engines"]["ruleSpecHash"] != want:
        return False, n, "보고서가 다른 규칙 스펙을 가리킨다"
    spec = ctx["ruleSpec"]
    for r in spec["allow"] + spec["detect"]:
        n += 1
        if "\\d" in r["regex"] or "\\w" in r["regex"] or "(?P<" in r["regex"]:
            return False, n, f"{r['id']}: 이식성 제약 위반"
        # Java 형식 이름있는 그룹은 Python 에서 컴파일되지 않는다(리뷰 LOD-053). lookbehind 는 허용한다.
        if re.search(r"\(\?<[A-Za-z]", r["regex"]):
            return False, n, f"{r['id']}: Java 형식 이름있는 그룹"
        re.compile(r["regex"])
    # 사본 3종을 똑같이 잘못 바꾸면 해시는 일치한다 — 규칙 구성 자체를 못박는다(리뷰 LOD-054).
    if [r["id"] for r in spec["allow"]] != CONTRACTED_ALLOW:
        return False, n, "allow 규칙 구성이 계약과 다르다"
    if [r["id"] for r in spec["detect"]] != CONTRACTED_DETECT:
        return False, n, "detect 규칙 구성이 계약과 다르다"
    return True, n, f"사본 {len(RULE_COPIES)}종 + 규칙 {len(spec['allow']) + len(spec['detect'])}개(구성 일치)"


def m8_deterministic_and_idempotent(ctx):
    n = 0
    for f in ctx["enginePython"]["files"]:
        n += 1
        raw = ctx["corpus"][f["sourceId"]]
        once = mask_text(raw).text
        if sha256_bytes(once.encode("utf-8")) != f["maskedTextHash"]:
            return False, n, f"{f['sourceId']}: 증거의 마스킹 결과 해시가 재현되지 않는다"
        if mask_text(raw).text != once or mask_text(once).text != once:
            return False, n, f"{f['sourceId']}: 결정성·멱등성 위반"
        if len(detect(raw)) != f["maskedSpans"]:
            return False, n, f"{f['sourceId']}: 스팬 수가 재현되지 않는다"
    if not n:
        return False, 0, "대조할 파일이 없다"
    return True, n, f"{n}파일 재현·멱등 확인"


def m9_no_plaintext_in_records(ctx):
    """증거·보고서 어디에도 gold 양성 원문이 없어야 한다(#85). 음성은 추적에 필요하므로 대상이 아니다."""
    texts = {k: json.dumps(ctx[k], ensure_ascii=False) for k in list(builder.EVIDENCE) + ["report"]}
    positives = [i["value"]["text"] for i in ctx["pii"]["items"] if i["expect"] == "MASKED"]
    n = 0
    for name, blob in texts.items():
        if name == "ruleSpec":
            continue  # 규칙 스펙은 정규식이며 값이 아니다
        for text in positives:
            n += 1
            if text in blob:
                return False, n, f"{name} 에 원문이 남았다"
    if not n:
        return False, 0, "검사 대상이 없다"
    gate = next((g for g in ctx["report"]["gates"] if g["id"] == "gate-no-plaintext-in-records"), None)
    if gate is None:
        return False, n, "원문 미기록 게이트가 보고서에 없다"
    if gate["observed"] != 0 or gate["status"] != "PASS" or gate.get("hits") != []:
        return False, n, "게이트가 원문 기록을 보고하는데 확인기는 찾지 못했다 — 둘 중 하나가 틀렸다"
    return True, n, f"{len(texts) - 1}개 문서 × 양성 {len(positives)}건 대조 + 게이트 관측 대조"


def m10_declared_paths_are_measured(ctx):
    """선언한 두 수집 경로가 전부 계측됐는가 — 재지 않은 경로를 주장에 넣지 않는다(L0 벤치 V11 과 같은 규칙)."""
    db, code, rep = ctx["ingestDb"], ctx["emitCode"], ctx["report"]
    n = 0
    for name, cond, why in (
        ("db:ingest", db["maskedTotal"] > 0, "적재 경로에서 마스킹이 0건이면 계측되지 않은 것이다"),
        ("db:ddlText", db["ddlTextPath"]["maskedTotal"] > 0, "DDL 텍스트 경로가 계측되지 않았다"),
        ("db:minimize", db["minimizePolicy"]["retrievableValues"] == 0, "최소화 정책이 동작하지 않는다"),
        ("db:schema", db["collectedTables"] == db["minimizePolicy"]["collectedTables"],
         "정책에 따라 수집 구조가 달라졌다 — 마스킹·최소화는 구조를 바꾸지 않아야 한다"),
        ("code:emit", code["variants"][code["gateVariant"]]["maskingSummary"]["masked_total"] > 0,
         "코드 산출 경로가 계측되지 않았다"),
        ("code:ids", all(v["idsPreserved"] for v in code["variants"].values()),
         "마스킹이 노드 id 를 바꿨다 — 엣지 참조가 끊긴다"),
        ("report:paths", set(rep["collectionPaths"]) == {"db", "code"}, "보고서가 두 경로를 분리 기록하지 않았다"),
    ):
        n += 1
        if not cond:
            return False, n, f"{name}: {why}"
    return True, n, f"경로 관측 {n}종"


def m11_parity_fixture_covers_new_branches(ctx):
    """픽스처가 새 분기를 실제로 지나가는가 — 지나가지 않으면 이 증거는 아무것도 막지 못한다.

    또한 길이 보존 모드가 케이스마다 문자 수·행 수를 유지하는지 증거에서 확인한다(개행 보존 계약).
    """
    pk = ctx["parityKotlin"]
    fixture = ctx["parityFixture"]
    rules = {s["ruleId"] for c in pk["cases"] for name in pk["policies"] for s in c[name]["spans"]}
    required = {"SECRET.KEYED_VALUE", "SECRET.URL_CREDENTIAL", "SECRET.PRIVATE_KEY_BLOCK"}
    missing = required - rules
    n = len(pk["cases"])
    if missing:
        return False, n, f"픽스처가 지나가지 않는 분기: {sorted(missing)}"
    if not any(any(ord(ch) > 0xFFFF for ch in c["text"]) for c in fixture["cases"]):
        return False, n, "BMP 밖 문자가 없어 좌표 단위 계약이 검증되지 않는다"
    if not any("\n" in c["text"] for c in fixture["cases"]):
        return False, n, "여러 줄 입력이 없어 개행 보존 계약이 검증되지 않는다"
    for c in pk["cases"]:
        lp = c["lengthPreserving"]
        if lp["maskedChars"] != c["inputChars"] or lp["maskedLines"] != c["inputLines"]:
            return False, n, f"{c['id']}: 길이 보존 모드가 문자 수·행 수를 바꿨다"
    if len({c["id"] for c in pk["cases"]}) != n:
        return False, n, "패리티 케이스 id 가 중복된다"
    return True, n, f"패리티 {n}케이스가 분기 {len(required)}종·BMP 밖·여러 줄을 지나간다"


RULES = {
    "M1": ("gold 신원 — 코퍼스 해시·승인 상태·항목 수·fixtureHash", m1_gold_identity),
    "M2": ("두 엔진의 결과가 같다 (Kotlin ↔ Python)", m2_engine_parity),
    "M3": ("보고서는 증거의 순수 함수다", m3_report_is_pure_function),
    "M4": ("양성 좌표가 원본에서 조회되고 그 줄에 스팬이 있다", m4_positive_locators_resolve),
    "M5": ("게이트 산식 — 미마스킹 1건이라도 있으면 PASS 불가", m5_gate_arithmetic),
    "M6": ("오탐이 전부 회계된다 + 임계 클래스 별도 표기", m6_false_positives_are_accounted),
    "M7": ("규칙 스펙 단일 원본 + 이식성 제약", m7_rule_spec_single_source),
    "M8": ("결정성·멱등성이 재현된다", m8_deterministic_and_idempotent),
    "M9": ("증거·보고서에 원문이 없다", m9_no_plaintext_in_records),
    "M10": ("선언한 수집 경로가 전부 계측됐다", m10_declared_paths_are_measured),
    "M11": ("패리티 픽스처가 새 분기를 지나가고 길이·행을 보존한다", m11_parity_fixture_covers_new_branches),
}


# ---- 결함 주입 -------------------------------------------------------------------------------

def _first_positive(ctx):
    return next(i for i in ctx["pii"]["items"] if i["expect"] == "MASKED")


CASES = [
    ("C01", "M1", lambda c: c["corpus"].__setitem__("pii:corpus.sql", c["corpus"]["pii:corpus.sql"] + "\n")),
    ("C02", "M1", lambda c: c["goldManifest"]["status"].__setitem__("state", "DRAFT")),
    ("C03", "M1", lambda c: c["report"].__setitem__("fixtureHash", "sha256:" + "0" * 64)),
    ("C04", "M1", lambda c: c["goldManifest"]["expectedCounts"].__setitem__("pii.json", 43)),
    ("C05", "M2", lambda c: c["engineKotlin"]["files"][0]["spans"].pop()),
    ("C06", "M2", lambda c: c["engineKotlin"]["files"][1].__setitem__("maskedTextHash", "sha256:" + "1" * 64)),
    ("C07", "M2", lambda c: c["engineKotlin"]["files"][0]["byClass"].__setitem__("EMAIL", 99)),
    ("C08", "M3", lambda c: c["report"]["gold"].__setitem__("masked", 27)),
    ("C09", "M3", lambda c: c["report"].__setitem__("specVersion", "masking-rules/v1")),
    ("C10", "M4", lambda c: _first_positive(c)["ref"].__setitem__("locator", "docs/superpowers/specs/gold/fixtures/pii/corpus.sql#L5")),
    ("C11", "M4", lambda c: c["enginePython"]["files"][0]["spans"].clear()),
    ("C12", "M5", lambda c: c["report"]["gold"]["unmasked"].append("PII.POS.SQL.L18.1")),
    ("C13", "M5", lambda c: c["report"]["gates"].pop()),
    ("C14", "M5", lambda c: c["ingestDb"].__setitem__("retrievableUnmaskedPiiValues", 3)),
    ("C15", "M6", lambda c: c["report"]["gold"].__setitem__("preserved", 15)),
    ("C16", "M6", lambda c: c["report"]["gold"]["criticalClassFalsePositives"].pop("GIT_SHA")),
    ("C17", "M7", lambda c: c["report"]["engines"].__setitem__("ruleSpecHash", "sha256:" + "2" * 64)),
    ("C18", "M7", lambda c: c["ruleSpec"]["detect"][0].__setitem__("regex", "\\d{16}")),
    ("C19", "M8", lambda c: c["enginePython"]["files"][2].__setitem__("maskedTextHash", "sha256:" + "3" * 64)),
    ("C20", "M8", lambda c: c["enginePython"]["files"][0].__setitem__("maskedSpans", 13)),
    ("C21", "M9", lambda c: c["ingestDb"].__setitem__("leak", _first_positive(c)["value"]["text"])),
    ("C22", "M9", lambda c: c["report"].__setitem__("notes", "예: " + _first_positive(c)["value"]["text"])),
    ("C23", "M10", lambda c: c["ingestDb"].__setitem__("maskedTotal", 0)),
    ("C24", "M10", lambda c: c["ingestDb"]["minimizePolicy"].__setitem__("retrievableValues", 5)),
    ("C25", "M10", lambda c: c["emitCode"]["variants"]["bareValue"].__setitem__("idsPreserved", False)),
    ("C26", "M10", lambda c: c["report"]["collectionPaths"].pop("code")),
    ("C27", "M1", lambda c: c["goldManifest"]["fixtures"].__setitem__(
        0, {**c["goldManifest"]["fixtures"][0], "path": "docs/superpowers/specs/gold/pii.json"})),
    ("C28", "M5", lambda c: c["report"]["gold"]["partiallyCovered"].append("PII.POS.SQL.L18.6")),
    ("C29", "M7", lambda c: c["ruleSpec"]["detect"].pop()),
    ("C30", "M7", lambda c: c["ruleSpec"]["allow"][1].__setitem__("regex", "(?<name>[0-9a-f]{40})")),
    ("C31", "M9", lambda c: next(
        g for g in c["report"]["gates"] if g["id"] == "gate-no-plaintext-in-records"
    ).__setitem__("observed", 2)),
    ("C32", "M2", lambda c: c["parityKotlin"]["cases"][0]["default"]["spans"].pop()),
    ("C33", "M2", lambda c: c["parityKotlin"]["cases"][7]["lengthPreserving"].__setitem__(
        "maskedTextHash", "sha256:" + "4" * 64)),
    ("C34", "M2", lambda c: c["parityPython"].__setitem__("fixtureHash", "sha256:" + "5" * 64)),
    ("C35", "M2", lambda c: c["report"]["engines"]["branchParity"].__setitem__("identical", True)
     if c["parityKotlin"]["cases"][1].__setitem__("inputChars", 999) else None),
    ("C36", "M11", lambda c: c["parityFixture"].__setitem__(
        "cases", [x for x in c["parityFixture"]["cases"] if "ASTRAL" not in x["id"]])),
    ("C37", "M11", lambda c: [
        cc[name].__setitem__("spans", [s for s in cc[name]["spans"]
                                       if s["ruleId"] != "SECRET.PRIVATE_KEY_BLOCK"])
        for cc in c["parityKotlin"]["cases"] for name in c["parityKotlin"]["policies"]]),
    ("C38", "M11", lambda c: c["parityKotlin"]["cases"][7]["lengthPreserving"].__setitem__(
        "maskedLines", 1)),
    ("C39", "M11", lambda c: c["parityKotlin"]["cases"].append(c["parityKotlin"]["cases"][0])),
]


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ctx = load_ctx()

    failures = []
    print("== 규칙 (실제 증거) ==")
    for rid, (title, fn) in RULES.items():
        try:
            ok, inspected, detail = fn(copy.deepcopy(ctx))
        except Exception as e:  # 규칙이 터지면 그 규칙의 실패로 기록하고 나머지를 계속 본다
            ok, inspected, detail = False, 0, f"예외: {type(e).__name__}: {e}"
        if inspected == 0:
            ok, detail = False, f"들여다본 대상이 0건이다 ({detail})"
        print(f"  [{'ok' if ok else 'FAIL'}] {rid} {title} — {detail} (대상 {inspected})")
        if not ok:
            failures.append(f"{rid}: {detail}")

    print("== 결함 주입 ==")
    for case_id, rid, mutate in CASES:
        broken = copy.deepcopy(ctx)
        mutate(broken)
        title, fn = RULES[rid]
        try:
            ok, _, detail = fn(broken)
        except Exception as e:
            ok, detail = False, f"예외: {type(e).__name__}"
        if ok:
            print(f"  [FAIL] {case_id} → {rid} 가 결함을 잡지 못했다")
            failures.append(f"{case_id}: {rid} 미검출")
        else:
            print(f"  [ok] {case_id} → {rid} 검출 ({detail})")

    if len(CASES) != manifest["caseCount"]:
        failures.append(f"케이스 수 {len(CASES)} ≠ manifest {manifest['caseCount']}")
    if manifest["ruleRange"] != f"M1-M{len(RULES)}":
        failures.append(f"규칙 범위 표기 불일치: {manifest['ruleRange']}")
    if load_rules().spec_version != ctx["ruleSpec"]["specVersion"]:
        failures.append("엔진이 읽는 스펙 버전과 원본이 다르다")

    print(f"\n{len(RULES)} rules, {len(CASES)} cases, {len(failures)} mismatches")
    for f in failures:
        print(f"  - {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
