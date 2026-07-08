from __future__ import annotations
import math
import networkx as nx
from .model import Node, Edge


def annotate(nodes: list[Node], edges: list[Edge], god_percentile: float) -> None:
    ids = {n.id for n in nodes}
    g = nx.Graph()
    g.add_nodes_from(ids)
    for e in edges:
        if e.src in ids and e.dst in ids:
            w = g.get_edge_data(e.src, e.dst, {}).get("weight", 0.0)
            g.add_edge(e.src, e.dst, weight=w + e.confidence)

    # degree
    deg = dict(g.degree())
    # community (Louvain, 결정적 seed)
    communities = nx.community.louvain_communities(g, weight="weight", seed=42)
    comm_of: dict[str, int] = {}
    for cid, members in enumerate(sorted(communities, key=lambda m: min(m) if m else "")):
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
