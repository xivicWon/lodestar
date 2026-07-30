from __future__ import annotations
import json
import os
from .mask import MaskLedger, MaskPolicy, mask_field
from .model import Node, Edge


def _mask_meta(value, ledger: MaskLedger, policy: MaskPolicy | None):
    """meta 의 문자열 값을 재귀적으로 마스킹한다. 수·불리언은 그대로 둔다."""
    if isinstance(value, str):
        return mask_field(value, ledger, policy)
    if isinstance(value, list):
        return [_mask_meta(v, ledger, policy) for v in value]
    if isinstance(value, dict):
        return {k: _mask_meta(v, ledger, policy) for k, v in value.items()}
    return value


def build_and_write(nodes: list[Node], edges: list[Edge], meta_extra: dict,
                    out_path: str, prune_dangling: bool = True,
                    mask_policy: MaskPolicy | None = None) -> dict:
    ids = {n.id for n in nodes}
    kept = [e for e in edges if not prune_dangling or (e.src in ids and e.dst in ids)]

    # #115 마스킹 단계 — 산출물에 실리는 텍스트는 쓰기 전에 여기를 통과한다. `id` 는 엣지 참조 키이므로
    # 손대지 않는다(원문이 아니라 정규화 이름이며, 바꾸면 그래프가 끊긴다).
    ledger = MaskLedger()

    node_docs = sorted(
        ({"id": n.id, "kind": n.kind,
          "label": mask_field(n.label, ledger, mask_policy),
          "qualified_name": mask_field(n.qualified_name, ledger, mask_policy),
          "path": mask_field(n.path, ledger, mask_policy), "lang": n.lang,
          "community": n.community, "degree": n.degree, "god_node": n.god_node}
         for n in nodes),
        key=lambda d: d["id"],
    )
    edge_docs = sorted(
        ({"id": e.id, "from": e.src, "to": e.dst, "kind": e.kind,
          "provenance": e.provenance, "confidence": round(e.confidence, 4),
          "alternatives": [mask_field(a, ledger, mask_policy) for a in e.alternatives]}
         for e in kept),
        key=lambda d: (d["from"], d["to"], d["kind"]),
    )
    communities = {n.community for n in nodes if n.community is not None}
    meta = {**_mask_meta(meta_extra, ledger, mask_policy),
            "masking": ledger.summary(),
            "generated_by": "lodestar-codegraph v1",
            "node_count": len(node_docs),
            "edge_count": len(edge_docs),
            "community_count": len(communities)}
    doc = {"meta": meta, "nodes": node_docs, "edges": edge_docs}

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=False)
    return doc
