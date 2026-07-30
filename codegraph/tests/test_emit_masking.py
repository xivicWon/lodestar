"""#115 — 코드 수집 경로의 마스킹 단계.

codegraph 산출물에 실리는 텍스트 필드(label · qualified_name · path · source_root · 외부 호출명)는
쓰기 **전에** 마스킹을 통과한다. 마스킹은 산출물에 남는 마지막 관문이므로 emit 에 둔다 — 상위 단계가
새 텍스트 채널(#114 의 제외·실패 사유 등)을 추가해도 같은 관문을 지난다.

노드 `id` 는 그대로 둔다: 엣지가 참조하는 키이며 원문이 아니라 해시·정규화 이름이다. id 를 바꾸면
엣지가 끊긴다 — 마스킹이 그래프를 망가뜨리는 것은 마스킹의 실패다.
"""
from __future__ import annotations

import json

from lodestar_codegraph.emit import build_and_write
from lodestar_codegraph.model import EXTRACTED, Edge, Node


def _node(nid: str, label: str, qn: str, path: str) -> Node:
    return Node(nid, "type", label, qn, path, "kotlin")


def _hashes(nodes: list[Node]) -> dict[str, str]:
    """#113 의 노드 단위 신원을 채운다 — 해시 조회 키는 **마스킹 전 원문 경로**다.

    마스킹된 경로로 조회하면 PII 가 섞인 경로의 노드만 content_hash 가 비어 신원 계약이 깨진다.
    """
    return {n.path: "sha256:" + "0" * 64 for n in nodes}


def _written(out) -> tuple[dict, str]:
    """**기록된 파일**을 다시 읽는다 — 반환값만 보면 직렬화·쓰기 경로의 회귀를 놓친다(리뷰 LOD-079)."""
    text = out.read_text(encoding="utf-8")
    return json.loads(text), text


def test_emitted_text_fields_are_masked(tmp_path):
    nodes = [_node("type:A", "hong@example.com", "com.acme.hong@example.com", "src/hong@example.com.kt")]
    out = tmp_path / "cg.json"
    doc = build_and_write(nodes, [], {"source_root": "/tmp/ghp_" + "A" * 36}, str(out),
                          file_hashes=_hashes(nodes))
    disk, blob = _written(out)
    assert disk == doc, "기록된 파일과 반환값이 다르다"
    assert "hong@example.com" not in blob
    assert "ghp_" + "A" * 36 not in blob
    assert disk["nodes"][0]["label"] == "[MASKED:EMAIL]"
    assert disk["nodes"][0]["id"] == "type:A"  # 엣지 참조 키는 유지


def test_masking_summary_is_recorded_without_plaintext(tmp_path):
    nodes = [_node("type:A", "hong@example.com", "A", "p")]
    out = tmp_path / "cg.json"
    build_and_write(nodes, [], {}, str(out), file_hashes=_hashes(nodes))
    disk, _ = _written(out)
    m = disk["meta"]["masking"]
    assert m["masked_total"] >= 1
    assert m["by_class"]["EMAIL"] >= 1
    assert "PII.EMAIL" in m["by_rule"]
    assert "hong@example.com" not in json.dumps(m, ensure_ascii=False)
    assert m["spec_version"] == "masking-rules/v0"


def test_masked_paths_are_counted_separately(tmp_path):
    """`path` 는 #88 이 코드 트랙의 좌표·식별자 대용으로 쓰는 필드다 — 가려졌다면 조용히 넘어가면 안 된다."""
    nodes = [_node("type:A", "A", "A", "src/hong@example.com.kt"),
             _node("type:B", "B", "B", "src/PriceCalc.kt")]
    doc = build_and_write(nodes, [], {}, str(tmp_path / "cg.json"), file_hashes=_hashes(nodes))
    assert doc["meta"]["masking"]["masked_path_fields"] == 1


def test_clean_input_is_untouched_and_summary_is_zero(tmp_path):
    nodes = [_node("type:A", "PriceCalc", "com.ontostudio.PriceCalc", "src/PriceCalc.kt")]
    edges = [Edge(1, "type:A", "type:A", "calls", EXTRACTED, 1.0)]
    doc = build_and_write(nodes, edges, {"source_root": "backend/src/main/kotlin"},
                          str(tmp_path / "cg.json"), file_hashes=_hashes(nodes))
    assert doc["nodes"][0]["qualified_name"] == "com.ontostudio.PriceCalc"
    assert doc["meta"]["masking"]["masked_total"] == 0
    assert doc["meta"]["masking"]["masked_path_fields"] == 0
    assert doc["meta"]["source_root"] == "backend/src/main/kotlin"


def test_edges_still_resolve_after_masking(tmp_path):
    nodes = [_node("type:A", "a@b.co", "A", "p"), _node("type:B", "B", "B", "p")]
    edges = [Edge(1, "type:A", "type:B", "calls", EXTRACTED, 1.0)]
    doc = build_and_write(nodes, edges, {}, str(tmp_path / "cg.json"), prune_dangling=True,
                          file_hashes=_hashes(nodes))
    assert doc["meta"]["edge_count"] == 1


def test_external_call_names_are_masked(tmp_path):
    out = tmp_path / "cg.json"
    build_and_write([], [], {"external_calls": ["send(hong@example.com)", "log(x)"]}, str(out))
    disk, blob = _written(out)
    assert "hong@example.com" not in blob
    assert disk["meta"]["external_calls"] == ["send([MASKED:EMAIL])", "log(x)"]


def test_meta_keys_and_tuples_are_masked(tmp_path):
    """키에 원문을 넣거나 tuple 로 감싸면 관문을 우회한다 — 둘 다 막는다(리뷰 LOD-073)."""
    out = tmp_path / "cg.json"
    build_and_write([], [], {
        "by_owner": {"hong@example.com": 1},
        "tags": ("ghp_" + "B" * 36, "ok"),
    }, str(out))
    disk, blob = _written(out)
    assert "hong@example.com" not in blob
    assert "ghp_" + "B" * 36 not in blob
    assert list(disk["meta"]["by_owner"]) == ["[MASKED:EMAIL]"]
    assert disk["meta"]["tags"] == ["[MASKED:GITHUB_TOKEN]", "ok"]
