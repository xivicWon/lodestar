import os
from itertools import count
from lodestar_codegraph.walk import walk_sources, load_ignore, SourceFile
from lodestar_codegraph.parse import parse_file
from lodestar_codegraph.extract import extract_file, ExtractResult

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


def _extract_source(rel: str, lang: str, source: bytes) -> ExtractResult:
    """소스 문자열 하나를 직접 파싱·추출 (fixtures 디렉터리를 건드리지 않는 격리 테스트용)."""
    sf = SourceFile(path=rel, rel=rel, lang=lang, source=source)
    pf = parse_file(sf)
    assert pf is not None
    return extract_file(pf, count(1))


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


def test_nested_type_fqn_and_contains_edge():
    """Bug 1 회귀: 중첩 타입 FQN은 Outer.Inner여야 하고, contains 엣지는 파일이 아니라
    소유 타입(Outer)에서 나와야 한다. (구 코드는 fqn을 매 재귀마다 패키지에서 다시 계산해
    Outer가 사라지고 type:com.x.Inner + file→Inner contains 엣지를 만들었다.)"""
    src = (
        b"package com.x;\n"
        b"public class Outer {\n"
        b"    static class Inner {\n"
        b"        void m() {}\n"
        b"    }\n"
        b"}\n"
    )
    r = _extract_source("com/x/Outer.java", "java", src)
    ids = {n.id for n in r.nodes}
    assert "type:com.x.Outer" in ids
    assert "type:com.x.Outer.Inner" in ids
    assert "type:com.x.Inner" not in ids  # 구 버그의 (틀린) 결과
    assert r.type_index["com.x.Outer.Inner"] == "type:com.x.Outer.Inner"
    kinds = {(e.src, e.kind, e.dst) for e in r.edges}
    assert ("type:com.x.Outer", "contains", "type:com.x.Outer.Inner") in kinds
    assert ("file:com/x/Outer.java", "contains", "type:com.x.Outer.Inner") not in kinds


def test_generic_supertype_no_self_loop_and_implements_edge():
    """Bug 2 회귀: `implements Comparable<Foo>`에서 제네릭 타입 인자(Foo)를 상위타입으로
    잘못 읽으면 Foo -> Foo self-loop가 생긴다. 직접 상위타입명(Comparable)만 취해야 한다."""
    src = b"package com.x;\npublic class GenFoo implements Comparable<GenFoo> {}\n"
    r = _extract_source("com/x/GenFoo.java", "java", src)
    assert not any(e.src == e.dst for e in r.edges)  # self-loop 없음
    kinds = {(e.src, e.kind, e.dst) for e in r.edges}
    # dangling 대상(Comparable은 내부에 없음)이라도 엣지 자체는 생성됨 — 정상(EXPECTED)
    assert ("type:com.x.GenFoo", "implements", "type:com.x.Comparable") in kinds


def test_extends_and_implements_distinct_kinds():
    """Bug 3 회귀: extends와 implements가 서로 다른 kind로 구분돼야 한다
    (구 코드는 둘 다 kind="extends"로 뭉뚱그렸고, implements는 아예 생성되지 않았다)."""
    src = b"package com.x;\npublic class Combo extends Base implements Iface {}\n"
    r = _extract_source("com/x/Combo.java", "java", src)
    kinds = {(e.src, e.kind, e.dst) for e in r.edges}
    assert ("type:com.x.Combo", "extends", "type:com.x.Base") in kinds
    assert ("type:com.x.Combo", "implements", "type:com.x.Iface") in kinds


def test_java_interface_extends_edge():
    """Bug 4 회귀: Java `interface I extends Other`는 superclass/super_interfaces가
    아니라 extends_interfaces 노드를 쓰므로, 이를 처리하지 않으면 엣지가 아예 안 생긴다."""
    src = b"package com.x;\npublic interface IFace extends Other {}\n"
    r = _extract_source("com/x/IFace.java", "java", src)
    kinds = {(e.src, e.kind, e.dst) for e in r.edges}
    assert ("type:com.x.IFace", "extends", "type:com.x.Other") in kinds
