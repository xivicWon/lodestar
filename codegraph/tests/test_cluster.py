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

    # degrees sorted = [1(D), 2(B), 2(C), 3(A)]; nearest-rank idx = ceil(75/100*4)-1 = 2
    # threshold = degrees[2] = 2 -> god_node = degree >= 2: A, B, C True; D False.
    assert by["A"].god_node is True
    assert by["B"].god_node is True
    assert by["C"].god_node is True
    assert by["D"].god_node is False


def test_self_loop_does_not_double_count_degree():
    # A calls itself recursively (self-loop `calls` edge) in addition to a real
    # edge A->B. networkx counts a self-loop as +2 degree; that must NOT leak
    # into the degree computed here, or recursive functions get spuriously
    # flagged as god nodes.
    #
    # A third node C (linked only to B) makes B the genuinely best-connected
    # node (degree 2) while A only has one real neighbor (B). If the
    # self-loop were still double-counted, A's inflated degree (1 real + 2
    # from the self-loop = 3) would wrongly outrank B and make A the god
    # node instead.
    nodes = [_n("A"), _n("B"), _n("C")]
    edges = [
        Edge(1, "A", "B", "contains", EXTRACTED, 1.0),
        Edge(2, "B", "C", "contains", EXTRACTED, 1.0),
        Edge(3, "A", "A", "calls", EXTRACTED, 1.0),
    ]
    annotate(nodes, edges, god_percentile=75.0)
    by = {n.id: n for n in nodes}
    # Only real neighbor is B -> degree 1, NOT 3 (1 real + 2 from self-loop).
    assert by["A"].degree == 1
    assert by["B"].degree == 2
    assert by["C"].degree == 1

    # degrees sorted = [1(A), 1(C), 2(B)]; nearest-rank idx = ceil(75/100*3)-1 = 2
    # threshold = degrees[2] = 2 -> god_node = degree >= 2: only B.
    assert by["A"].god_node is False
    assert by["B"].god_node is True
    assert by["C"].god_node is False
