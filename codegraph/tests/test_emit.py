import json
import os
from lodestar_codegraph.model import Node, Edge, EXTRACTED
from lodestar_codegraph.emit import build_and_write


def test_emit_prunes_dangling_and_serializes(tmp_path):
    nodes = [
        Node("type:A", "type", "A", "A", "p", "java"),
        Node("type:B", "type", "B", "B", "p", "java"),
    ]
    edges = [
        Edge(1, "type:A", "type:B", "calls", EXTRACTED, 1.0),
        Edge(2, "type:A", "type:MISSING", "calls", EXTRACTED, 1.0),  # dangling
    ]
    out = tmp_path / "cg.json"
    hashes = {"p": "sha256:" + "0" * 64}  # 노드마다 소스 해시가 있어야 한다(#113 계약 §5.2)
    doc = build_and_write(nodes, edges, {"source_root": "p"}, str(out), prune_dangling=True,
                          file_hashes=hashes)
    assert doc["meta"]["node_count"] == 2
    assert doc["meta"]["edge_count"] == 1  # dangling 제거
    e = doc["edges"][0]
    assert e["from"] == "type:A" and e["to"] == "type:B"
    # 파일로도 쓰였는지
    with open(out) as f:
        disk = json.load(f)
    assert disk == doc


def test_emit_deterministic(tmp_path):
    nodes = [Node("type:B", "type", "B", "B", "p", "java"),
             Node("type:A", "type", "A", "A", "p", "java")]
    edges = []
    o1 = tmp_path / "a.json"; o2 = tmp_path / "b.json"
    hashes = {"p": "sha256:" + "0" * 64}
    build_and_write(nodes, edges, {}, str(o1), file_hashes=hashes)
    build_and_write(nodes, edges, {}, str(o2), file_hashes=hashes)
    assert open(o1).read() == open(o2).read()
    # 정렬: A가 B보다 먼저
    doc = json.load(open(o1))
    assert [n["id"] for n in doc["nodes"]] == ["type:A", "type:B"]


def test_emit_refuses_nodes_without_a_source_hash(tmp_path):
    """신원 없는 노드를 파일로 내보내지 않는다 — 조용히 통과하면 하류가 그것을 사실로 받는다."""
    import pytest
    nodes = [Node("type:A", "type", "A", "A", "p", "java")]
    with pytest.raises(ValueError, match="소스 해시가 없는 노드"):
        build_and_write(nodes, [], {}, str(tmp_path / "cg.json"), file_hashes={})
    with pytest.raises(ValueError, match="소스 해시가 없는 노드"):
        build_and_write(nodes, [], {}, str(tmp_path / "cg2.json"), file_hashes={"other": "sha256:" + "0" * 64})
