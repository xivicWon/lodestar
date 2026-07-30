"""#115 — 코드 수집 경로의 마스킹 단계.

codegraph 산출물에 실리는 텍스트 필드(label · qualified_name · path · source_root · 외부 호출명)는
쓰기 **전에** 마스킹을 통과한다. 마스킹은 산출물에 남는 마지막 관문이므로 emit 에 둔다 — 상위 단계가
새 텍스트 채널(#114 의 제외·실패 사유 등)을 추가해도 같은 관문을 지난다.

노드 `id` 는 그대로 둔다: 엣지가 참조하는 키이며 원문이 아니라 해시·정규화 이름이다. id 를 바꾸면
엣지가 끊긴다 — 마스킹이 그래프를 망가뜨리는 것은 마스킹의 실패다.
"""
from __future__ import annotations

import json

from lodestar_codegraph.emit import build_and_write
from lodestar_codegraph.model import EXTRACTED, Edge, Node


def _node(nid: str, label: str, qn: str, path: str) -> Node:
    return Node(nid, "type", label, qn, path, "kotlin")


def test_emitted_text_fields_are_masked(tmp_path):
    nodes = [_node("type:A", "hong@example.com", "com.acme.hong@example.com", "src/hong@example.com.kt")]
    doc = build_and_write(nodes, [], {"source_root": "/tmp/ghp_" + "A" * 36},
                          str(tmp_path / "cg.json"))
    blob = json.dumps(doc, ensure_ascii=False)
    assert "hong@example.com" not in blob
    assert "ghp_" + "A" * 36 not in blob
    assert doc["nodes"][0]["label"] == "[MASKED:EMAIL]"
    assert doc["nodes"][0]["id"] == "type:A"  # 엣지 참조 키는 유지


def test_masking_summary_is_recorded_without_plaintext(tmp_path):
    nodes = [_node("type:A", "hong@example.com", "A", "p")]
    doc = build_and_write(nodes, [], {}, str(tmp_path / "cg.json"))
    m = doc["meta"]["masking"]
    assert m["masked_total"] >= 1
    assert m["by_class"]["EMAIL"] >= 1
    assert "PII.EMAIL" in m["by_rule"]
    assert "hong@example.com" not in json.dumps(m, ensure_ascii=False)
    assert m["spec_version"] == "masking-rules/v0"


def test_clean_input_is_untouched_and_summary_is_zero(tmp_path):
    nodes = [_node("type:A", "PriceCalc", "com.ontostudio.PriceCalc", "src/PriceCalc.kt")]
    edges = [Edge(1, "type:A", "type:A", "calls", EXTRACTED, 1.0)]
    doc = build_and_write(nodes, edges, {"source_root": "backend/src/main/kotlin"},
                          str(tmp_path / "cg.json"))
    assert doc["nodes"][0]["qualified_name"] == "com.ontostudio.PriceCalc"
    assert doc["meta"]["masking"]["masked_total"] == 0
    assert doc["meta"]["source_root"] == "backend/src/main/kotlin"


def test_edges_still_resolve_after_masking(tmp_path):
    nodes = [_node("type:A", "a@b.co", "A", "p"), _node("type:B", "B", "B", "p")]
    edges = [Edge(1, "type:A", "type:B", "calls", EXTRACTED, 1.0)]
    doc = build_and_write(nodes, edges, {}, str(tmp_path / "cg.json"), prune_dangling=True)
    assert doc["meta"]["edge_count"] == 1


def test_external_call_names_are_masked(tmp_path):
    doc = build_and_write([], [], {"external_calls": ["send(hong@example.com)", "log(x)"]},
                          str(tmp_path / "cg.json"))
    assert "hong@example.com" not in json.dumps(doc, ensure_ascii=False)
    assert doc["meta"]["external_calls"] == ["send([MASKED:EMAIL])", "log(x)"]
