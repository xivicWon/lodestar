import os
from itertools import count
from lodestar_codegraph.walk import walk_sources, load_ignore
from lodestar_codegraph.parse import parse_file
from lodestar_codegraph.extract import extract_file

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample")


def _extract_all():
    files = walk_sources(FIX, load_ignore(FIX, None))
    seq = count(1)
    nodes, edges = [], []
    for f in files:
        pf = parse_file(f)
        r = extract_file(pf, seq)
        nodes += r.nodes
        edges += r.edges
    return nodes, edges


def test_nodes_cover_types_and_functions():
    nodes, _ = _extract_all()
    ids = {n.id for n in nodes}
    assert "type:com.x.Foo" in ids
    assert "type:com.x.Repo" in ids
    assert "type:com.x.Bar" in ids
    assert any(i.startswith("function:com.x.Repo.save/") for i in ids)
    assert any(i.startswith("function:com.x.Bar.go/") for i in ids)
    assert any(n.kind == "file" for n in nodes)


def test_structural_edges():
    nodes, edges = _extract_all()
    kinds = {(e.src, e.kind, e.dst) for e in edges}
    # file contains type
    assert any(k[1] == "contains" and k[2] == "type:com.x.Foo" for k in kinds)
    # type contains function
    assert any(k[0] == "type:com.x.Repo" and k[1] == "contains"
               and k[2].startswith("function:com.x.Repo.save/") for k in kinds)
    # extends (Foo -> Base 는 Base가 내부에 없으므로 엣지 없음; imports Repo는 내부)
    assert any(k[0].startswith("file:") and k[1] == "imports" and k[2] == "type:com.x.Repo"
               for k in kinds)
    # 모든 구조 엣지는 EXTRACTED
    assert all(e.provenance == "EXTRACTED" for e in edges)
