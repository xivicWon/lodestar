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
    doc = build_and_write(nodes, edges, {"source_root": "p"}, str(out), prune_dangling=True)
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
    build_and_write(nodes, edges, {}, str(o1))
    build_and_write(nodes, edges, {}, str(o2))
    assert open(o1).read() == open(o2).read()
    # 정렬: A가 B보다 먼저
    doc = json.load(open(o1))
    assert [n["id"] for n in doc["nodes"]] == ["type:A", "type:B"]
