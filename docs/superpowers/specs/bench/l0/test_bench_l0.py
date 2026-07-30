"""L0 벤치 **계측기**의 단위 테스트 (#114).

이 리포의 원칙은 "재는 것을 검사한다" 인데, 정작 **재는 도구**(프로브의 귀속 계산 · 보고서의 게이트
산식 · 확인기의 규칙)에는 검사가 없었다. 실제로 이번 작업의 결함은 대부분 제품이 아니라 계측기에서
나왔고, 그중 몇은 고정 입력에 해당 케이스가 없어(분모 0) 실측으로는 드러나지 않았다.

여기서 재는 것은 수집 결과가 아니라 **계측기가 거짓을 거짓이라고 말하는가** 다. 그래서 입력은 실측이
아니라 합성이며, 각 테스트는 "이렇게 어긋난 증거를 주면 그 자리가 반드시 붉어져야 한다" 를 고정한다.

    python3 -m pytest docs/superpowers/specs/bench/l0/test_bench_l0.py -q
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
SCHEMAS = REPO / "docs/superpowers/specs/schemas"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SCHEMAS))

import build_report  # noqa: E402
import probe_code  # noqa: E402
import validate_rqr  # noqa: E402
import verify_l0  # noqa: E402


# ---- 프로브: 좌표 · 귀속 ---------------------------------------------------------------

@pytest.mark.parametrize("locator,expected", [
    ("fixtures/a.kt#L16", (16, 16)),
    ("fixtures/a.kt#L12-L14", (12, 14)),
    ("#L3-L7", (3, 7)),
    ("jdbc://cat/schema/TB", None),
    ("", None),
])
def test_좌표_행범위_파싱(locator, expected):
    assert probe_code.line_range(locator) == expected


def _issue(reason_code="PARSE_ERROR", locator="a.kt#L12-L14", reason="구문 오류", target="a.T"):
    return {"kind": "failed", "reason_code": reason_code, "reason": reason,
            "locator": locator, "target": target}


GOLD_ONE = [{"kind": "PARSE_ERROR", "target": "fixture.failure.TailBroken", "locator": "#L12-L14"}]


def test_귀속_사유코드와_좌표가_맞으면_보고로_센다():
    att = probe_code.attribute(GOLD_ONE, [_issue()])
    assert att["actualReported"] == 1
    e = att["expected"][0]
    assert e["reported"] and e["reasonPresent"]
    assert e["observedLocator"] == "a.kt#L12-L14"
    assert att["unattributedReports"] == []


def test_귀속_사유코드가_다르면_보고가_아니다():
    att = probe_code.attribute(GOLD_ONE, [_issue(reason_code="UNSUPPORTED_LANGUAGE")])
    assert att["actualReported"] == 0
    assert att["expected"][0]["reported"] is False
    # 귀속되지 않은 보고는 숨기지 않고 드러낸다 — 과대 집계 신호다(gold R-F-4).
    assert att["unattributedReports"] == ["UNSUPPORTED_LANGUAGE a.kt#L12-L14"]


def test_귀속_좌표가_겹치지_않으면_보고가_아니다():
    att = probe_code.attribute(GOLD_ONE, [_issue(locator="a.kt#L40-L42")])
    assert att["actualReported"] == 0


def test_귀속_사유가_비어_있으면_보고가_아니다():
    """사유 없이 건수만 세거나 로그에만 남기면 미보고로 집계한다(gold R-F-2)."""
    att = probe_code.attribute(GOLD_ONE, [_issue(reason="")])
    assert att["actualReported"] == 0


def test_귀속_한_항목이_두_기대를_동시에_채우지_않는다():
    gold = GOLD_ONE + [{"kind": "PARSE_ERROR", "target": "x", "locator": "#L13"}]
    att = probe_code.attribute(gold, [_issue()])
    assert att["actualReported"] == 1, "한 보고를 두 번 세면 보고율이 부풀어 오른다"


# ---- 보고서: 게이트 산식 ---------------------------------------------------------------

def _facts(reported, should, **over):
    f = {"input": 36, "output": 27, "failed": 0, "excluded": 9, "exclusions": [],
         "determinism": 1.0, "provenance": 0.0,
         "shouldReport": should, "reported": reported, "silentPartialRecovery": 0,
         "piiPositives": 14, "piiMasked": 0, "piiUnmasked": 0, "piiNotCollected": 14,
         "ingestUnmaskedValues": 14}
    f.update(over)
    return f


def _gate(f, gid="gate-error-visibility"):
    return {g["id"]: g for g in build_report.gates("db", {}, f)}[gid]


def test_보고율_전량_보고는_PASS():
    assert _gate(_facts(14, 14))["status"] == "PASS"


def test_보고율_일부만_보고하면_FAIL():
    g = _gate(_facts(7, 14))
    assert (g["observed"], g["status"]) == (0.5, "FAIL")


def test_분모가_0이면_통과가_아니라_NOT_MEASURED():
    """0/0 을 1.0 으로 적으면 '보고할 것이 없었다' 와 '전부 보고했다' 가 같은 값이 된다(I3 R20 과 같은 규칙)."""
    g = _gate(_facts(0, 0))
    assert g["status"] == "NOT_MEASURED"
    assert g["observed"] is None


# ---- 보고서: 프로브 모양이 달라도 그 실행의 사실을 읽는다 --------------------------------

def _probe(track):
    return build_report.probe(track)


def test_보고_채널이_없던_실행은_보고_0으로_읽힌다():
    """v1 프로브(반환형에 채널 없음)에는 귀속 자리가 없다 — 없으면 0 이며, 그것이 그 실행의 측정이다."""
    p = copy.deepcopy(_probe("db"))
    p["acquisition"].pop("reportableByInventory")
    p["acquisition"].pop("reportedByInventory")
    p["acquisition"].pop("reported")
    for fx in p["failureFixtures"]:
        fx["actualReported"] = 0
    f = build_report._db_facts(p)
    assert f["reported"] == 0
    assert f["shouldReport"] == p["acquisition"]["excluded"] + p["acquisition"]["failed"] + 5
    assert _gate(f)["status"] == "FAIL"


def test_분모는_수집기_신고가_아니라_프로브가_센_것이다():
    """수집기가 문장을 통째로 언급하지 않아도 분모는 줄지 않는다 — 자기 인증 방지."""
    p = copy.deepcopy(_probe("db"))
    p["acquisition"]["excluded"] = 0          # 수집기가 "제외한 것 없다" 고 말해도
    p["acquisition"]["reportedByInventory"] = 0
    f = build_report._db_facts(p)
    assert f["shouldReport"] >= p["acquisition"]["reportableByInventory"]
    assert _gate(f)["status"] == "FAIL"


def test_코드_트랙_분모는_수집기가_읽지_않은_파일이다():
    p = copy.deepcopy(_probe("code"))
    p["inventory"]["notCollectedCount"] = 3
    p["inventory"]["reportedNotCollected"] = 1
    f = build_report._code_facts(p)
    assert f["shouldReport"] == 3 + sum(fx["expectedReported"] for fx in p["failureFixtures"])
    assert f["reported"] == 1 + sum(fx["actualReported"] for fx in p["failureFixtures"])


def test_재지_못한_게이트는_경고와_함께_보고서에_실린다():
    """NOT_MEASURED 를 경고 없이 실으면 계약 검증(R10)이 문다 — 침묵은 통과와 구분되지 않는다."""
    p = copy.deepcopy(_probe("db"))
    p["acquisition"]["reportableByInventory"] = 0
    p["acquisition"]["reportedByInventory"] = 0
    for fx in p["failureFixtures"]:
        fx["expectedReported"] = 0
        fx["actualReported"] = 0
        fx["reportAttribution"] = {"expected": [], "expectedReported": 0, "actualReported": 0,
                                   "unattributedReports": []}
    rep = build_report.build_from("db", p)
    gate = {g["id"]: g for g in rep["gates"]}["gate-error-visibility"]
    assert gate["status"] == "NOT_MEASURED"
    assert {"code": "METRIC_UNMEASURED", "trigger": "gates.gate-error-visibility"} \
        in [{"code": w["code"], "trigger": w["trigger"]} for w in rep["warnings"]]
    assert validate_rqr.cross_field_errors(rep) == [], "계약 위반 없이 실려야 한다"


# ---- 확인기: 규칙이 실제로 무는가 --------------------------------------------------------

@pytest.fixture(scope="module")
def ctx():
    return verify_l0.load_ctx()


def _first_attribution(c, track="db"):
    for fx in c["probes"][track]["failureFixtures"]:
        if fx.get("reportAttribution", {}).get("expected"):
            return fx["reportAttribution"]
    raise AssertionError("귀속 근거가 있는 픽스처가 없다")


def test_V14_커밋된_증거는_통과한다(ctx):
    errs, seen = verify_l0.v14_report_attribution(ctx)
    assert errs == []
    assert seen > 0, "0건을 본 규칙은 아무것도 검사하지 않은 것이다"


@pytest.mark.parametrize("break_it,expect", [
    (lambda att: att["expected"][0].pop("observedLocator"), "관측 좌표가 없다"),
    (lambda att: att["expected"][0].update({"observedLocator": "x#L999"}), "겹치지 않는다"),
    (lambda att: att["expected"][0].update({"reasonPresent": False}), "사유 없이"),
    (lambda att: att.update({"actualReported": 99}), "귀속과 맞지 않는다"),
    (lambda att: att.update({"unattributedReports": ["PARSE_ERROR a#L1"]}), "귀속되지 않은 보고"),
])
def test_V14_어긋난_귀속을_문다(ctx, break_it, expect):
    c = copy.deepcopy(ctx)
    break_it(_first_attribution(c))
    errs, _ = verify_l0.v14_report_attribution(c)
    assert any(expect in e for e in errs), errs


def test_V14_기대_항목을_gold_와_다르게_적으면_문다(ctx):
    c = copy.deepcopy(ctx)
    _first_attribution(c)["expected"][0]["locator"] = "#L1"
    errs, _ = verify_l0.v14_report_attribution(c)
    assert any("gold 선언과 다르다" in e for e in errs), errs


def _ctx_with_exclusion(ctx, example):
    c = copy.deepcopy(ctx)
    c["reports"]["db"]["exclusions"] = [{"reason": "r", "count": 1, "examples": [example]}]
    c["reports"]["code"]["exclusions"] = []
    return c


SQL = "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql"


def test_V5_파일_단위_제외_좌표를_오탐하지_않는다(ctx):
    """미지원 언어 같은 파일 단위 제외의 대상은 그 파일 자신이다 — 어떤 행에도 자기 경로는 없다."""
    errs, seen = verify_l0.v5_exclusion_locators_resolve(_ctx_with_exclusion(ctx, f"{SQL}#L1 ({SQL})"))
    assert (errs, seen) == ([], 1)


def test_V5_그럴듯하지만_없는_대상은_문다(ctx):
    errs, _ = verify_l0.v5_exclusion_locators_resolve(
        _ctx_with_exclusion(ctx, f"{SQL}#L1 (TB_NOT_THERE)"))
    assert any("대상이 없다" in e for e in errs), errs


def test_V5_파일_범위를_벗어난_좌표를_문다(ctx):
    errs, _ = verify_l0.v5_exclusion_locators_resolve(
        _ctx_with_exclusion(ctx, f"{SQL}#L99999 (TB_CUST_MST)"))
    assert any("범위를 벗어난다" in e for e in errs), errs


def test_확인기_규칙과_케이스_총계가_manifest_와_같다():
    """규칙·케이스가 늘었는데 매니페스트가 그대로면 그 자체로 실패다 — 계측기의 계측기."""
    manifest = json.loads((HERE / "manifest.json").read_text())
    assert manifest["ruleRange"] == f"V1-V{verify_l0.MAX_RULE}"
    assert manifest["caseCount"] == len(verify_l0.injections())
    assert {c[0] for c in verify_l0.injections()} == set(verify_l0.RULES), \
        "결함 주입 케이스가 없는 규칙은 '적기만 하고 검사하지 않는' 규칙이다"
