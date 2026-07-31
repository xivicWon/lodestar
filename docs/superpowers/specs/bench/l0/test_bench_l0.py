"""L0 벤치 **계측기**의 단위 테스트 (#114).

이 리포의 원칙은 "재는 것을 검사한다" 인데, 정작 **재는 도구**(프로브의 귀속 계산 · 보고서의 게이트
산식 · 확인기의 규칙)에는 검사가 없었다. 실제로 이번 작업의 결함은 대부분 제품이 아니라 계측기에서
나왔고, 그중 몇은 고정 입력에 해당 케이스가 없어(분모 0) 실측으로는 드러나지 않았다.

여기서 재는 것은 수집 결과가 아니라 **계측기가 거짓을 거짓이라고 말하는가** 다. 그래서 입력은 실측이
아니라 합성이며, 각 테스트는 "이렇게 어긋난 증거를 주면 그 자리가 반드시 붉어져야 한다" 를 고정한다.

    python3 -m pytest docs/superpowers/specs/bench/l0/test_bench_l0.py -q

**이 테스트들은 되돌려서 확인했다.** "고친 코드에서 통과한다" 는 검증이 아니다 — 수정 전 로직을
그대로 되살렸을 때 붉어지는지를 봐야 그 테스트가 무언가를 지키고 있다고 말할 수 있다. 각 수정에
대해 이전 로직을 복원해 확인한 결과(2026-07-31):

| 되돌린 수정 | 붉어진 테스트 |
|---|---|
| 분류: `failed = 전체 − 노드있음 − 미수집` (실패가 항상 0건) | 분류 3건 |
| `output = parsed` (사실 0건 파일도 산출로 셈) | counts 항등·산출·계약·사례 5건 |
| 실패를 보고 분모에서 제외 | 분모 1건 |
| `counts.failed = 0` 고정 | R2·R4 5건 |
| 분모 0 게이트를 `PASS` 로 | NOT_MEASURED 2건 |
| 보고율 분모를 수집기 신고에서 가져오기 | 자기 인증 2건 |
| 결함 주입 무력화 감지 제거 + 절대값 주입 | 주입 무력화 1건 |
| V5 파일 단위 좌표 예외 제거 | V5 1건 |

한 번은 되돌리기를 **부정확하게** 해서 전부 통과했다 — 그때 통과는 "테스트가 약하다" 가 아니라
"되돌리기가 틀렸다" 였고, 실제 이전 로직으로 다시 되돌리자 3건이 붉어졌다. 되돌리기 자체도
원본과 대조해야 한다는 뜻이다.
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


# ---- 프로브: 범위 분류 (수집기 신고가 아니라 프로브 규칙으로) ------------------------------

def _doc(*file_nodes) -> dict:
    return {"nodes": [{"kind": "file", "path": p, "status": st} for p, st in file_nodes]}


def test_분류_사실을_낸_파일만_산출이다():
    """파싱만 되고 사실이 0건인 파일을 산출로 세면 실패가 성공으로 위장된다 — 수집기에서 없앤 위장이
    보고서 층에서 되살아나는 자리다."""
    rels = ["scope/Ok.kt", "scope/Broken.kt", "scope/notes.txt"]
    cls = probe_code.classify_scope(rels, _doc(("Ok.kt", "parsed"), ("Broken.kt", "failed")), "scope")
    assert cls["factFiles"] == ["Ok.kt"]
    assert cls["failedFiles"] == ["Broken.kt"], "status=failed 는 산출이 아니라 실패다"
    assert cls["notCollected"] == ["scope/notes.txt"]


def test_분류_노드조차_없는_파일도_실패로_잡힌다():
    """트리가 아예 서지 않으면 파일 노드가 없다 — 그 파일이 어느 집계에도 안 남으면 조용히 사라진다."""
    cls = probe_code.classify_scope(["scope/Gone.kt"], _doc(), "scope")
    assert cls["failedFiles"] == ["Gone.kt"] and cls["notCollected"] == []


def test_분류_부분_추출은_산출이다():
    """부분 추출은 사실을 냈다 — 실패로 세면 이번엔 반대 방향으로 거짓이 된다(상한은 status 가 맡는다)."""
    cls = probe_code.classify_scope(["scope/Partial.kt"], _doc(("Partial.kt", "partial")), "scope")
    assert cls["factFiles"] == ["Partial.kt"] and cls["failedFiles"] == []


def test_분류는_수집기_신고와_무관하게_분모를_정한다():
    """수집기가 파일 노드를 아예 안 만들어도 '읽을 수 있었던 파일' 은 프로브의 확장자 규칙이 정한다."""
    cls = probe_code.classify_scope(["scope/A.kt", "scope/B.java", "scope/c.md"], _doc(), "scope")
    assert cls["failedFiles"] == ["A.kt", "B.java"]
    assert cls["notCollected"] == ["scope/c.md"]


# ---- 보고서: 게이트 산식 ---------------------------------------------------------------

def _facts(reported, should, **over):
    f = {"input": 36, "output": 27, "failed": 0, "excluded": 9, "exclusions": [],
         "determinism": 1.0, "provenance": 0.0,
         "shouldReport": should, "reported": reported, "silentPartialRecovery": 0,
         "piiPositives": 14, "piiMasked": 0, "piiUnmasked": 0, "piiNotCollected": 14,
         "ingestUnmaskedValues": 14}
    f.update(over)
    return f


def _gate(f, gid="gate-error-visibility", track="db"):
    return {g["id"]: g for g in build_report.gates(track, {}, f)}[gid]


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


def _run_collector(source_root, out) -> dict:
    """수집기를 실제로 돌린다 — 프로브가 읽는 산출물과 같은 것을 본다."""
    import os
    import subprocess
    cg = REPO / "codegraph"
    env = dict(os.environ, PYTHONPATH=str(cg / "src"))
    proc = subprocess.run([sys.executable, "-m", "lodestar_codegraph", str(source_root),
                           "-o", str(out)], cwd=cg, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(pathlib.Path(out).read_text())


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


@pytest.mark.parametrize("patch,expected", [
    ({"parsed": 59, "producedFacts": 58, "failedFiles": ["a/Broken.kt"]},
     {"output": 58, "failed": 1, "excluded": 0}),
    ({"parsed": 57, "producedFacts": 57, "notCollectedCount": 2, "reportedNotCollected": 2},
     {"output": 57, "failed": 0, "excluded": 2}),
    ({"parsed": 55, "producedFacts": 54, "failedFiles": ["a/Broken.kt"],
      "notCollectedCount": 4, "reportedNotCollected": 4},
     {"output": 54, "failed": 1, "excluded": 4}),
])
def test_counts_는_인벤토리에서_항등으로_나온다(patch, expected):
    """input = output + failed + excluded (I3 R2).

    실패를 0 으로 박아두면 수집기가 **정직하게** 실패를 보고하는 순간 R2 가 깨져 보고서 생성이
    거부된다 — 정직한 수집이 형식 위반이 되는 자리는 계약이 아니라 산식의 결함이다.
    """
    p = copy.deepcopy(_probe("code"))
    p["inventory"].update(patch)
    f = build_report._code_facts(p)
    assert {k: f[k] for k in expected} == expected
    assert f["input"] == f["output"] + f["failed"] + f["excluded"]


def test_사실을_못_낸_파일은_산출로_세지_않는다():
    p = copy.deepcopy(_probe("code"))
    p["inventory"].update({"parsed": 59, "producedFacts": 58, "failedFiles": ["a/Broken.kt"],
                           "failedFilesReported": ["a/Broken.kt"]})
    f = build_report._code_facts(p)
    assert f["output"] == 58 and f["failed"] == 1
    assert f["input"] == f["output"] + f["failed"] + f["excluded"]


def test_실패도_보고돼야_하는_대상이라_분모에_들어간다():
    """읽었는데 사실을 못 낸 파일은 사유와 함께 보고돼야 한다 — 분모에서 빠지면 침묵이 통과가 된다."""
    p = copy.deepcopy(_probe("code"))
    base = build_report._code_facts(p)["shouldReport"]
    p["inventory"].update({"parsed": 59, "producedFacts": 58,
                           "failedFiles": ["a/Silent.kt"], "failedFilesReported": []})
    f = build_report._code_facts(p)
    assert f["shouldReport"] == base + 1
    assert f["reported"] == base, "사유 없는 실패는 보고로 세지 않는다"
    assert _gate(f, track="code")["status"] == "FAIL"


def test_파싱_실패가_있어도_보고서가_계약을_통과한다():
    """건수와 사례를 같은 집합에서 만들어야 R2·R4 가 서로를 확인한다."""
    p = copy.deepcopy(_probe("code"))
    p["inventory"].update({"parsed": 59, "producedFacts": 58, "failedFiles": ["a/Broken.kt"],
                           "failedFilesReported": ["a/Broken.kt"]})
    rep = build_report.build_from("code", p)
    assert rep["counts"] == {"input": 59, "output": 58, "failed": 1, "excluded": 0}
    assert len(rep["failures"]) == 1 and rep["failures"][0]["fixture"].endswith("a/Broken.kt")
    assert validate_rqr.cross_field_errors(rep) == []


def test_사유_없는_실패는_사례에_그_사실로_적힌다():
    p = copy.deepcopy(_probe("code"))
    p["inventory"].update({"parsed": 59, "producedFacts": 58, "failedFiles": ["a/Silent.kt"],
                           "failedFilesReported": []})
    rep = build_report.build_from("code", p)
    assert "사유를 남기지 않았다" in rep["failures"][0]["summary"]
    assert validate_rqr.cross_field_errors(rep) == []


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


def test_판정문의_남은_게이트는_게이트_결과에서_나온다():
    """손으로 적으면 게이트가 통과로 바뀐 뒤에도 보고서가 '아직 실패다' 라고 말한다.

    #114 재측정에서 실제로 그럴 뻔했다: #113 으로 식별 필드가 5/5 가 됐는데 판정문은 여전히
    "5/5 라 추적 가능성 게이트가 남아 있다" 였다 — 근거와 서술이 어긋나면 판정문은 장식이 된다.
    """
    passing = [{"id": "gate-security-masking", "name": "L0 보안 (PII)", "status": "PASS"}]
    failing = [{"id": "gate-l0-metadata-completeness", "name": "L0 메타데이터 완전성 (5필드)",
                "status": "FAIL"}]
    assert "전부 통과" in build_report._open_gates(passing)
    text = build_report._open_gates(failing)
    assert "L0 메타데이터 완전성" in text and "L0-fix-2" in text


def test_판정_근거는_이_실행을_가리킨다():
    p = copy.deepcopy(_probe("db"))
    rep = build_report.build_from("db", p)
    for j in rep["featureJudgments"]:
        assert rep["run"]["runId"] in j["evidenceRefs"]
        # 게이트가 하나라도 실패면 Core 로 올릴 수 없다(I1 G4).
        assert j["judgment"] != "Core" or all(g["status"] == "PASS" for g in rep["gates"])


def test_사유_없는_미수집은_제외_목록에_그_사실로_남는다(tmp_path):
    """수집기가 말한 것만 모으면 삼킨 파일이 목록에서도 사라진다 — 제외 합계가 counts 를 확인해주지 못한다.

    프로브는 분모와 같은 집합(수집기가 읽지 않은 파일)에서 목록을 만들고, 사유가 없으면 'UNREPORTED' 로
    남긴다. 그래야 R3(합계 일치)와 오류 가시성 게이트가 같은 사실을 가리킨다.
    """
    scope = tmp_path / "scope"
    (scope / "sub").mkdir(parents=True)
    (scope / "Ok.kt").write_text("package p\nclass Ok { fun a(): Int = 1 }\n")
    (scope / "notes.txt").write_text("수집 대상이 아닌 파일\n")
    doc = _run_collector(scope, tmp_path / "out.json")
    issues = doc["meta"]["issues"]
    assert [i["reason_code"] for i in issues] == ["UNSUPPORTED_LANGUAGE"], issues
    assert issues[0]["locator"] == "notes.txt#L1" and issues[0]["reason"]


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


def test_모든_결함_주입이_증거를_실제로_바꾼다(ctx):
    """주입이 no-op 이면 규칙은 멀쩡히 통과하고 케이스 수도 그대로라 아무도 알아채지 못한다.

    이번 M0 작업에서 세 번 일어났다: 실패하던 게이트·지표가 통과로 바뀌자, 그 값을 통과로 덮던
    주입이 아무것도 바꾸지 않게 됐다. 확인기 러너가 이제 이걸 실패로 세고, 여기서 그 성질을 고정한다.
    """
    stale = []
    for case in verify_l0.injections():
        bad = copy.deepcopy(ctx)
        case[2](bad)
        if bad == ctx:
            stale.append(f"{case[0]}: {case[1]}")
    assert stale == [], f"증거를 바꾸지 않는 결함 주입: {stale}"


def test_확인기_규칙과_케이스_총계가_manifest_와_같다():
    """규칙·케이스가 늘었는데 매니페스트가 그대로면 그 자체로 실패다 — 계측기의 계측기."""
    manifest = json.loads((HERE / "manifest.json").read_text())
    assert manifest["ruleRange"] == f"V1-V{verify_l0.MAX_RULE}"
    assert manifest["caseCount"] == len(verify_l0.injections())
    assert {c[0] for c in verify_l0.injections()} == set(verify_l0.RULES), \
        "결함 주입 케이스가 없는 규칙은 '적기만 하고 검사하지 않는' 규칙이다"
