import os
from itertools import count
from lodestar_codegraph.walk import walk_sources, load_ignore
from lodestar_codegraph.parse import parse_file
from lodestar_codegraph.extract import extract_file
from lodestar_codegraph.resolve import resolve_calls

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample")


def _pipeline():
    files = walk_sources(FIX, load_ignore(FIX, None))
    seq = count(1)
    parsed, nodes = [], []
    for f in files:
        pf = parse_file(f)
        parsed.append(pf)
        nodes += extract_file(pf, seq).nodes
    calls, external = resolve_calls(parsed, nodes, seq)
    return nodes, calls, external


def test_same_type_call_is_extracted():
    _, calls, _ = _pipeline()
    # Bar.go -> Bar.helper : 같은 타입 유일 → EXTRACTED
    hit = [e for e in calls
           if e.src.startswith("function:com.x.Bar.go/")
           and e.dst.startswith("function:com.x.Bar.helper/")]
    assert hit and hit[0].provenance == "EXTRACTED" and hit[0].confidence == 1.0


def test_same_type_call_prefers_extracted():
    _, calls, _ = _pipeline()
    # Svc.handle -> save : Svc.save(같은 타입) 유일 → EXTRACTED
    hit = [e for e in calls if e.src.startswith("function:com.x.Svc.handle/")
           and e.dst.startswith("function:com.x.Svc.save/")]
    assert hit and hit[0].provenance == "EXTRACTED"


def test_ambiguous_call_has_alternatives():
    _, calls, _ = _pipeline()
    # Client.use -> save : Client엔 save 없음, 후보 3개(Repo/Store/Svc) → AMBIGUOUS
    hit = [e for e in calls if e.src.startswith("function:com.x.Client.use/")
           and e.dst.split(".")[-1].startswith("save")]
    assert hit
    assert hit[0].provenance == "AMBIGUOUS"
    assert len(hit[0].alternatives) >= 1          # 나머지 후보가 alternatives에
    assert hit[0].confidence <= 0.4               # min(0.4, 0.8/3)


def test_external_call_counted_no_edge():
    nodes, calls, external = _pipeline()
    # Foo.run -> println : 미정의 → external 카운트, 엣지 없음
    assert external >= 1
    dsts = {e.dst for e in calls}
    assert not any("println" in d for d in dsts)
    # Repo.save 는 내부라 매칭됨(대조군)
    assert any(d.startswith("function:com.x.Repo.save/") for d in dsts)


def test_calls_edges_reference_only_real_node_ids():
    """DRY 회귀 가드: resolve._collect_functions는 더 이상 id 생성 알고리즘을 독자
    재구현하지 않고 extract.collect_functions 하나만 사용한다. 만약 이 단일화가 깨지고
    resolve 쪽이 다시 자체적으로 함수 id를 재구성하다가 extract의 id 스킴과 어긋나면,
    calls 엣지의 src/dst가 실제 Node.id 집합에 없는 dangling id를 가리키게 된다 —
    이 테스트는 그 실패 양상을 직접 가드한다: 모든 calls 엣지의 src/dst가 실제로
    존재하는 노드 id 집합 안에 있어야 한다."""
    nodes, calls, _ = _pipeline()
    node_ids = {n.id for n in nodes}
    calls_edges = [e for e in calls if e.kind == "calls"]
    assert calls_edges  # 가드가 의미 있으려면 최소 하나는 있어야 함
    for e in calls_edges:
        assert e.src in node_ids, f"dangling calls src: {e.src}"
        assert e.dst in node_ids, f"dangling calls dst: {e.dst}"
