from __future__ import annotations
import json
import os
from .model import Node, Edge


def build_and_write(nodes: list[Node], edges: list[Edge], meta_extra: dict,
                    out_path: str, prune_dangling: bool = True,
                    file_hashes: dict[str, str] | None = None) -> dict:
    """[file_hashes] 는 상대경로 → `sha256:...`.

    노드마다 `source_id`·`content_hash` 를 붙여 **소스 단위로** 수집 신원이 닫히게 한다(#113).
    실행 단위 필드(project_id·revision·collector_version)는 `meta_extra` 로 들어온다.
    """
    ids = {n.id for n in nodes}
    kept = [e for e in edges if not prune_dangling or (e.src in ids and e.dst in ids)]

    hashes = file_hashes or {}
    node_docs = sorted(
        ({"id": n.id, "kind": n.kind, "label": n.label,
          "qualified_name": n.qualified_name, "path": n.path, "lang": n.lang,
          "source_id": n.path, "content_hash": hashes.get(n.path),
          "community": n.community, "degree": n.degree, "god_node": n.god_node}
         for n in nodes),
        key=lambda d: d["id"],
    )
    edge_docs = sorted(
        ({"id": e.id, "from": e.src, "to": e.dst, "kind": e.kind,
          "provenance": e.provenance, "confidence": round(e.confidence, 4),
          "alternatives": e.alternatives}
         for e in kept),
        key=lambda d: (d["from"], d["to"], d["kind"]),
    )
    communities = {n.community for n in nodes if n.community is not None}
    meta = {**meta_extra,
            "generated_by": "lodestar-codegraph v1",
            "node_count": len(node_docs),
            "edge_count": len(edge_docs),
            "community_count": len(communities)}
    doc = {"meta": meta, "nodes": node_docs, "edges": edge_docs}

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=False)
    return doc
