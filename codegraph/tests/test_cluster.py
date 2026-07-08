from lodestar_codegraph.model import Node, Edge, EXTRACTED
from lodestar_codegraph.cluster import annotate


def _n(i):
    return Node(id=i, kind="type", label=i, qualified_name=i, path="p", lang="java")


def test_degree_and_community_and_godnode():
    nodes = [_n("A"), _n("B"), _n("C"), _n("D")]
    edges = [
        Edge(1, "A", "B", "calls", EXTRACTED, 1.0),
        Edge(2, "A", "C", "calls", EXTRACTED, 1.0),
        Edge(3, "A", "D", "calls", EXTRACTED, 1.0),
        Edge(4, "B", "C", "calls", EXTRACTED, 1.0),
    ]
    annotate(nodes, edges, god_percentile=75.0)
    by = {n.id: n for n in nodes}
    assert by["A"].degree == 3
    assert by["B"].degree == 2
    # A가 최고 degree → god_node
    assert by["A"].god_node is True
    # community 할당됨(정수)
    assert all(n.community is not None for n in nodes)
