from __future__ import annotations
import math
import networkx as nx
from .model import Node, Edge


def annotate(nodes: list[Node], edges: list[Edge], god_percentile: float) -> None:
    ids = {n.id for n in nodes}
    g = nx.Graph()
    # 그래프에 넣는 순서를 못박는다(#112). 집합·입력 순서를 그대로 흘리면 Louvain 이 노드 순서에
    # 의존하므로 seed 를 고정해도 군집 배정이 프로세스마다 갈린다 — 문자열 해시 랜덤화 때문에
    # 집합 순회 순서가 PYTHONHASHSEED 에 좌우되기 때문이다.
    g.add_nodes_from(sorted(ids))
    # 엣지도 정렬해서 누적한다. weight 는 부동소수 합이라 더하는 순서가 값을 바꿀 수 있다.
    for e in sorted(edges, key=lambda x: (x.src, x.dst, x.kind, x.id)):
        if e.src in ids and e.dst in ids and e.src != e.dst:
            a, b = (e.src, e.dst) if e.src <= e.dst else (e.dst, e.src)
            w = g.get_edge_data(a, b, {}).get("weight", 0.0)
            g.add_edge(a, b, weight=w + e.confidence)

    # degree
    deg = dict(g.degree())
    # community (Louvain, 결정적 seed) — 라벨은 멤버 정렬로 정규화한다. 같은 분할이면
    # 어떤 순서로 나오든 같은 라벨이 되도록 정렬된 멤버 튜플을 tie-break 로 쓴다.
    communities = nx.community.louvain_communities(g, weight="weight", seed=42)
    ordered = sorted((sorted(m) for m in communities))
    comm_of: dict[str, int] = {}
    for cid, members in enumerate(ordered):
        for m in members:
            comm_of[m] = cid

    degrees = sorted(deg.values())
    if degrees:
        idx = min(len(degrees) - 1, int(math.ceil(god_percentile / 100.0 * len(degrees))) - 1)
        threshold = degrees[max(0, idx)]
    else:
        threshold = 0

    for n in nodes:
        n.degree = deg.get(n.id, 0)
        n.community = comm_of.get(n.id)
        n.god_node = n.degree >= threshold and n.degree > 0
