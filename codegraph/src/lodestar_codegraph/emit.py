from __future__ import annotations
import json
import os
from .mask import MaskLedger, MaskPolicy, mask_field
from .model import Node, Edge


def _mask_meta(value, ledger: MaskLedger, policy: MaskPolicy | None):
    """meta 의 문자열을 재귀적으로 마스킹한다. 수·불리언은 그대로 둔다.

    **키도 마스킹한다** — 키에 원문을 넣으면 값만 가리는 관문을 우회한다(리뷰 LOD-073).
    tuple·set 도 JSON 으로 직렬화되므로 함께 처리한다.
    """
    if isinstance(value, str):
        return mask_field(value, ledger, policy)
    if isinstance(value, (list, tuple, set)):
        return [_mask_meta(v, ledger, policy) for v in value]
    if isinstance(value, dict):
        return {_mask_meta(k, ledger, policy) if isinstance(k, str) else k:
                _mask_meta(v, ledger, policy) for k, v in value.items()}
    return value


def build_and_write(nodes: list[Node], edges: list[Edge], meta_extra: dict,
                    out_path: str, prune_dangling: bool = True,
                    mask_policy: MaskPolicy | None = None,
                    file_hashes: dict[str, str] | None = None) -> dict:
    """[file_hashes] 는 상대경로 → `sha256:...`.

    노드마다 `source_id`·`content_hash` 를 붙여 **소스 단위로** 수집 신원이 닫히게 한다(#113).
    실행 단위 필드(project_id·revision·collector_version)는 `meta_extra` 로 들어온다.
    """
    ids = {n.id for n in nodes}
    kept = [e for e in edges if not prune_dangling or (e.src in ids and e.dst in ids)]

    # #115 마스킹 단계 — 산출물에 실리는 텍스트는 쓰기 전에 여기를 통과한다. `id` 는 엣지 참조 키이므로
    # 손대지 않는다(원문이 아니라 정규화 이름이며, 바꾸면 그래프가 끊긴다).
    ledger = MaskLedger()

    # `path` 는 #88 문서가 코드 트랙의 sourceId 대용으로 지목한 필드다. 마스킹하면 좌표가 원본에서
    # 조회되지 않을 수 있으므로(경로에 이메일·해시 형태가 들어간 드문 경우) **가려진 경로 수를 따로
    # 센다** — 조용히 바뀌지 않게 하려는 것이다.
    masked_paths = sum(1 for n in nodes if mask_field(n.path, None, mask_policy) != n.path)

    hashes = file_hashes or {}

    def _node_doc(n: Node) -> dict:
        # path 는 **한 번만** 마스킹한다 — 두 번 부르면 같은 원문이 원장에 두 번 계수된다.
        # `source_id` 는 그 결과를 그대로 쓴다: 산출물에 실리는 같은 문자열이므로 path 와 다른
        # 노출 정책을 가질 이유가 없다. 해시 조회 키는 **원문 경로**여야 file_hashes 와 맞는다.
        masked_path = mask_field(n.path, ledger, mask_policy)
        return {"id": n.id, "kind": n.kind,
                "label": mask_field(n.label, ledger, mask_policy),
                "qualified_name": mask_field(n.qualified_name, ledger, mask_policy),
                "path": masked_path, "lang": n.lang,
                "source_id": masked_path, "content_hash": hashes.get(n.path),
                "community": n.community, "degree": n.degree, "god_node": n.god_node}

    node_docs = sorted((_node_doc(n) for n in nodes), key=lambda d: d["id"])
    edge_docs = sorted(
        ({"id": e.id, "from": e.src, "to": e.dst, "kind": e.kind,
          "provenance": e.provenance, "confidence": round(e.confidence, 4),
          "alternatives": [mask_field(a, ledger, mask_policy) for a in e.alternatives]}
         for e in kept),
        key=lambda d: (d["from"], d["to"], d["kind"]),
    )
    communities = {n.community for n in nodes if n.community is not None}
    meta = {**_mask_meta(meta_extra, ledger, mask_policy),
            "masking": {**ledger.summary(), "masked_path_fields": masked_paths},
            "generated_by": "lodestar-codegraph v1",
            "node_count": len(node_docs),
            "edge_count": len(edge_docs),
            "community_count": len(communities)}
    # 계약 위반 산출물을 파일로 내보내지 않는다. 현재 호출 경로에서는 도달하지 않지만(노드의 path 는
    # file_hashes 의 키와 같은 SourceFile.rel 이다), 도달하면 신원 없는 노드가 조용히 하류로 흘러간다.
    orphans = sorted({d["id"] for d in node_docs if not d["content_hash"]})
    if orphans:
        raise ValueError(
            f"소스 해시가 없는 노드 {len(orphans)}건 — 노드 단위 신원이 닫히지 않았다(#113 계약 §5.2): "
            f"{orphans[:5]}")

    doc = {"meta": meta, "nodes": node_docs, "edges": edge_docs}

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=False)
    return doc
