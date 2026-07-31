"""#115 마스킹 게이트 — #99 gold PII 코퍼스 전수 검증 (Python 엔진).

게이트: 양성 28건 **미마스킹 0건**. 오탐(음성이 가려짐)은 게이트가 아니라 기록 대상이며
GIT_SHA·CONTENT_HASH 오탐은 revision·fixture 추적을 끊으므로 여기서 따로 붉어진다(gold gate 선언).
"""
from __future__ import annotations

import json
import pathlib

from lodestar_codegraph.mask import detect, mask_text

REPO = pathlib.Path(__file__).resolve().parents[2]
GOLD = REPO / "docs/superpowers/specs/gold/pii.json"


def _gold():
    return json.loads(GOLD.read_text(encoding="utf-8"))


def _masked_corpus() -> dict[str, str]:
    out = {}
    for f in _gold()["scope"]["files"]:
        raw = (REPO / f["path"]).read_text(encoding="utf-8")
        out[f["sourceId"]] = mask_text(raw).text
    return out


def test_gold_corpus_hashes_match_pinned():
    import hashlib

    for f in _gold()["scope"]["files"]:
        got = "sha256:" + hashlib.sha256((REPO / f["path"]).read_bytes()).hexdigest()
        assert got == f["contentHash"], f["path"]


def test_no_positive_survives_unmasked():
    masked = _masked_corpus()
    survivors = [
        i["id"]
        for i in _gold()["items"]
        if i["expect"] == "MASKED" and i["value"]["text"] in masked[i["ref"]["sourceId"]]
    ]
    assert survivors == [], f"미마스킹 양성: {survivors}"


def test_positive_count_matches_gold_declaration():
    g = _gold()
    assert sum(1 for i in g["items"] if i["expect"] == "MASKED") == g["counts"]["MASKED"]


def test_negatives_are_not_masked():
    masked = _masked_corpus()
    lost = [
        i["id"]
        for i in _gold()["items"]
        if i["expect"] == "NOT_MASKED" and i["value"]["text"] not in masked[i["ref"]["sourceId"]]
    ]
    assert lost == [], f"오탐(음성이 가려짐): {lost}"


def test_masking_is_idempotent_and_deterministic():
    once = _masked_corpus()
    twice = {k: mask_text(v).text for k, v in once.items()}
    assert once == twice
    assert once == _masked_corpus()


def _lines(source_id: str) -> list[str]:
    path = next(f["path"] for f in _gold()["scope"]["files"] if f["sourceId"] == source_id)
    return (REPO / path).read_text(encoding="utf-8").split("\n")


def _raw(source_id: str) -> str:
    path = next(f["path"] for f in _gold()["scope"]["files"] if f["sourceId"] == source_id)
    return (REPO / path).read_text(encoding="utf-8")


def test_every_declared_occurrence_is_fully_covered_by_a_span():
    """'원문이 사라졌다' 는 부분 마스킹으로도 성립한다 — 선언된 모든 구간이 스팬에 완전히 덮여야 한다.

    덧붙여 클래스도 대조한다: 엉뚱한 규칙이 우연히 덮은 경우와 구별한다(리뷰 LOD-065).
    """
    for item in _gold()["items"]:
        if item["expect"] != "MASKED":
            continue
        src = item["ref"]["sourceId"]
        raw, text = _raw(src), item["value"]["text"]
        spans = detect(raw)
        idx, occurrences = raw.find(text), []
        while idx >= 0:
            occurrences.append((idx, idx + len(text)))
            idx = raw.find(text, idx + 1)
        assert occurrences, f"{item['id']}: 원본에서 값을 찾지 못했다"
        for a, b in occurrences:
            covering = [s for s in spans if s.start <= a and s.end >= b]
            assert covering, f"{item['id']}: ({a},{b}) 구간을 완전히 덮는 스팬이 없다"
            assert any(s.cls == item["value"]["class"] for s in covering), (
                f"{item['id']}: 덮은 스팬의 클래스가 gold 선언({item['value']['class']})과 다르다: "
                f"{[s.cls for s in covering]}")


def test_negatives_survive_at_their_declared_locator():
    """파일 어딘가에 같은 문자열이 남은 것으로는 부족하다 — **선언된 줄**에서 살아있어야 한다."""
    for item in _gold()["items"]:
        if item["expect"] != "NOT_MASKED":
            continue
        src = item["ref"]["sourceId"]
        line_no = int(item["ref"]["locator"].rsplit("#L", 1)[1])
        masked_line = mask_text(_raw(src)).text.split("\n")[line_no - 1]
        assert item["value"]["text"] in masked_line, f"{item['id']}: 선언된 줄에서 사라졌다"
        assert item["value"]["text"] in _lines(src)[line_no - 1], f"{item['id']}: 좌표가 원본과 다르다"
