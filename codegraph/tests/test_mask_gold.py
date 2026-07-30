"""#115 마스킹 게이트 — #99 gold PII 코퍼스 전수 검증 (Python 엔진).

게이트: 양성 28건 **미마스킹 0건**. 오탐(음성이 가려짐)은 게이트가 아니라 기록 대상이며
GIT_SHA·CONTENT_HASH 오탐은 revision·fixture 추적을 끊으므로 여기서 따로 붉어진다(gold gate 선언).
"""
from __future__ import annotations

import json
import pathlib

from lodestar_codegraph.mask import mask_text

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
