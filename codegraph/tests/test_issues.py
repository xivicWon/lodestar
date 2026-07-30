"""#114 — 수집 제외·실패·부분추출이 산출물에 사유·좌표와 함께 남는가.

기준은 gold(#99) `failures.json` 의 코드 트랙 3건이다. 재는 것은 정확도가 아니라 정직성이다:
확장자 필터로 조용히 거르지 않는가, 깨진 파일을 성공으로 표시하지 않는가, 부분 추출을 부분으로 적는가.
"""
from __future__ import annotations
import json
import os
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
CG = REPO / "codegraph"
FAILURE_FIXTURES = REPO / "docs/superpowers/specs/gold/fixtures/failure"


def _run(source_root: pathlib.Path, out: pathlib.Path) -> dict:
    env = dict(os.environ, PYTHONPATH=str(CG / "src"))
    proc = subprocess.run([sys.executable, "-m", "lodestar_codegraph", str(source_root),
                           "-o", str(out)], cwd=CG, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text())


def _scope(tmp_path, *names: str) -> pathlib.Path:
    d = tmp_path / "scope"
    d.mkdir(exist_ok=True)
    for n in names:
        shutil.copy(FAILURE_FIXTURES / n, d / n)
    return d


def test_미지원_언어는_사유와_좌표로_보고된다(tmp_path):
    """F.CODE.UNSUPPORTED_LANG — 확장자 필터의 조용한 제외를 없앤다."""
    doc = _run(_scope(tmp_path, "code-unsupported-lang.scala"), tmp_path / "o.json")
    m = doc["meta"]
    assert m["walked"] == 0 and m["excluded"] == 1, m
    i = m["issues"][0]
    assert i["kind"] == "skipped"
    assert i["reason_code"] == "UNSUPPORTED_LANGUAGE"
    assert i["locator"] == "code-unsupported-lang.scala#L1"
    assert i["reason"], "사유 없는 보고는 미보고다(R-F-2)"
    assert doc["nodes"] == [], "제외된 파일이 노드로 나타나면 안 된다"


def test_파싱_실패_파일은_성공으로_표시되지_않는다(tmp_path):
    """F.CODE.BROKEN_SYNTAX — 부분 트리에서 심볼을 건져 성공으로 표시하면 실패다."""
    doc = _run(_scope(tmp_path, "code-broken-syntax.kt"), tmp_path / "o.json")
    m = doc["meta"]
    assert m["failed"] == 1 and m["partial"] == 0, m
    assert m["failed_files"] == ["code-broken-syntax.kt"]

    i = m["issues"][0]
    assert i["kind"] == "failed"
    assert i["reason_code"] == "PARSE_ERROR"
    assert i["locator"] == "code-broken-syntax.kt#L6-L11", i["locator"]

    kinds = {n["kind"] for n in doc["nodes"]}
    assert kinds == {"file"}, f"깨진 구간에서 사실을 건지면 안 된다: {doc['nodes']}"
    assert [n["status"] for n in doc["nodes"]] == ["failed"]


def test_부분_추출은_partial_로_명시된다(tmp_path):
    """F.CODE.PARTIAL_EXTRACT — 앞부분은 추출하되 파일을 '성공' 으로 표시하지 않는다."""
    doc = _run(_scope(tmp_path, "code-partial-extract.kt"), tmp_path / "o.json")
    m = doc["meta"]
    assert m["partial"] == 1 and m["failed"] == 0, m
    assert m["partial_files"] == ["code-partial-extract.kt"]

    i = m["issues"][0]
    assert i["kind"] == "partial"
    assert i["reason_code"] == "PARSE_ERROR"
    assert i["locator"] == "code-partial-extract.kt#L12-L14", i["locator"]
    assert i["target"] == "fixture.failure.TailBroken", i["target"]

    names = sorted(n["qualified_name"] for n in doc["nodes"])
    assert names == ["code-partial-extract.kt", "fixture.failure.GoodOne",
                     "fixture.failure.GoodOne.ok"], names
    assert {n["status"] for n in doc["nodes"]} == {"partial"}, \
        "부분 추출 파일에서 나온 사실은 partial 로 표시돼야 한다(I1 §3.3)"


def test_온전한_입력은_보고할_것이_없다(tmp_path):
    doc = _run(pathlib.Path(__file__).parent / "fixtures/sample", tmp_path / "o.json")
    m = doc["meta"]
    assert m["failed"] == 0 and m["partial"] == 0
    assert all(i["reason_code"] != "PARSE_ERROR" for i in m["issues"]), m["issues"]
    assert all(n["status"] == "parsed" for n in doc["nodes"])
