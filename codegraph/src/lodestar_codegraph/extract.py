from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterator
from tree_sitter import Node as TsNode
from .model import Node, Edge, EXTRACTED
from .parse import ParsedFile
from .lang import LangSpec


@dataclass
class ExtractResult:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    type_index: dict[str, str] = field(default_factory=dict)  # FQN -> type node id


def _text(n: TsNode) -> str:
    return n.text.decode("utf-8", "replace")


def _child_field_ident(n: TsNode) -> str | None:
    """선언 노드에서 이름 identifier 찾기 (첫 identifier/type_identifier 자식)."""
    for c in n.children:
        if c.type in ("identifier", "type_identifier", "simple_identifier"):
            return _text(c)
    return None


def _package_name(root: TsNode, spec: LangSpec) -> str:
    for c in root.children:
        if c.type == spec.package_decl:
            # 마지막 qualified/scoped identifier 텍스트
            for d in c.children:
                if d.type in ("scoped_identifier", "qualified_identifier", "identifier"):
                    return _text(d).replace(" ", "")
    return ""


def _imports(root: TsNode, spec: LangSpec) -> list[str]:
    out = []
    for c in root.children:
        if c.type == spec.import_decl:
            for d in c.children:
                if d.type in ("scoped_identifier", "qualified_identifier"):
                    out.append(_text(d).replace(" ", ""))
    return out


def _direct_type_name(n: TsNode) -> str | None:
    """type_identifier/generic_type(java)·user_type(kotlin) 노드의 '자기 자신' 이름만 추출.

    type_arguments/type_projection(제네릭 타입 인자) 서브트리는 절대 내려가지 않는다.
    예: `Comparable<Foo>` → "Comparable"만 반환하고 인자로 들어간 "Foo"는 무시한다
    (내려가면 self-loop 등 오탐 엣지가 생김 — Bug 2).
    """
    if n.type == "type_identifier":
        return _text(n)
    if n.type == "generic_type":
        for c in n.children:
            if c.type == "type_identifier":
                return _text(c)
        return None
    if n.type == "user_type":
        for c in n.children:
            if c.type in ("identifier", "simple_identifier"):
                return _text(c)
        return None
    return None


def _supertypes(type_node: TsNode) -> list[tuple[str, str]]:
    """extends/implements 대상 (직접 상위타입 단순명, edge kind) 목록 (근사).

    - Java `superclass` → kind="extends"
    - Java `super_interfaces` → kind="implements"
    - Java `extends_interfaces` (interface의 extends) → kind="extends"  (Bug 4)
    - Kotlin `delegation_specifiers`는 문법상 상속/구현을 구분하지 않으므로,
      생성자 호출 형태(`constructor_invocation`, 예: `Base()`)는 상위 클래스로 보고
      kind="extends", 순수 타입 참조(`user_type`, 예: `Comparable<Bar>`)는
      인터페이스 구현으로 보고 kind="implements" (휴리스틱).
    - 단, Kotlin `interface`는 인터페이스만 상속할 수 있고 구현은 불가능하므로
      (`interface Vehicle : Movable`), 소유 타입 선언(`type_node`)이 인터페이스이면
      delegation_specifiers의 모든 대상을 kind="extends"로 강제한다 (Bug 5).
      tree-sitter-kotlin은 interface를 별도 노드 타입(`interface_declaration`)이
      아니라 `class_declaration` + `interface` 키워드 자식으로 표현하므로,
      그 키워드 자식의 존재로 인터페이스 여부를 판별한다.
    """
    kt_interface = any(c.type == "interface" for c in type_node.children)
    out: list[tuple[str, str]] = []
    for c in type_node.children:
        if c.type == "superclass":
            for e in c.children:
                nm = _direct_type_name(e)
                if nm:
                    out.append((nm, "extends"))
        elif c.type in ("super_interfaces", "extends_interfaces"):
            kind = "extends" if c.type == "extends_interfaces" else "implements"
            for tl in c.children:
                if tl.type != "type_list":
                    continue
                for e in tl.children:
                    nm = _direct_type_name(e)
                    if nm:
                        out.append((nm, kind))
        elif c.type == "delegation_specifiers":  # kotlin
            for ds in c.children:
                if ds.type != "delegation_specifier":
                    continue
                for e in ds.children:
                    if e.type == "constructor_invocation":
                        for f in e.children:
                            nm = _direct_type_name(f)
                            if nm:
                                out.append((nm, "extends"))
                    elif e.type == "user_type":
                        nm = _direct_type_name(e)
                        if nm:
                            out.append((nm, "extends" if kt_interface else "implements"))
    return out


def _descend(n: TsNode, types: tuple[str, ...]) -> list[TsNode]:
    out = []
    stack = list(n.children)
    while stack:
        x = stack.pop()
        if x.type in types:
            out.append(x)
        stack.extend(x.children)
    return out


def _params_arity(func_node: TsNode) -> int:
    for c in func_node.children:
        if c.type in ("formal_parameters", "function_value_parameters"):
            return sum(1 for p in c.children
                       if p.type in ("formal_parameter", "parameter", "spread_parameter"))
    return 0


def extract_file(pf: ParsedFile, edge_seq: Iterator[int]) -> ExtractResult:
    spec = pf.spec
    root = pf.tree.root_node
    rel = pf.sf.rel
    pkg = _package_name(root, spec)
    r = ExtractResult()

    file_id = f"file:{rel}"
    r.nodes.append(Node(id=file_id, kind="file", label=rel.split("/")[-1],
                        qualified_name=rel, path=rel, lang=pf.sf.lang))

    arity_seen: dict[str, int] = {}

    def visit_type(tnode: TsNode, owner_fqn: str | None = None):
        name = _child_field_ident(tnode)
        if not name:
            return
        # 중첩 타입은 owner_fqn을 이어붙인다 (Outer.Inner). owner_fqn이 없으면(최상위)
        # 패키지에서 새로 계산한다 — 재귀 호출마다 패키지에서 다시 계산하면 중첩 타입의
        # outer가 사라지는 버그가 생김 (Bug 1).
        fqn = f"{owner_fqn}.{name}" if owner_fqn else (f"{pkg}.{name}" if pkg else name)
        tid = f"type:{fqn}"
        r.nodes.append(Node(id=tid, kind="type", label=name,
                            qualified_name=fqn, path=rel, lang=pf.sf.lang))
        r.type_index[fqn] = tid
        # 중첩 타입의 contains 엣지는 파일이 아니라 소유 타입에서 나온다.
        contains_src = f"type:{owner_fqn}" if owner_fqn else file_id
        r.edges.append(Edge(next(edge_seq), contains_src, tid, "contains", EXTRACTED, 1.0))
        # supertypes → extends/implements (내부 여부는 resolve/emit 단계에서 필터하지 않고
        #   단순명으로; 여기선 FQN 확정 불가하므로 같은 패키지로 가정한 FQN 후보로 엣지 생성)
        for sup_name, sup_kind in _supertypes(tnode):
            sup_fqn = f"{pkg}.{sup_name}" if pkg else sup_name
            r.edges.append(Edge(next(edge_seq), tid, f"type:{sup_fqn}",
                                sup_kind, EXTRACTED, 1.0))
        # 멤버 함수
        for body in tnode.children:
            if body.type in ("class_body", "enum_body", "interface_body"):
                for m in body.children:
                    if m.type in spec.func_decls:
                        visit_func(m, fqn)
                    elif m.type in spec.type_decls:  # 중첩 타입
                        visit_type(m, fqn)

    def visit_func(fnode: TsNode, owner_fqn: str):
        name = _child_field_ident(fnode)
        if not name:
            return
        arity = _params_arity(fnode)
        base = f"{owner_fqn}.{name}/{arity}"
        seen = arity_seen.get(base, 0)
        arity_seen[base] = seen + 1
        fid = f"function:{base}" + (f"#{seen}" if seen else "")
        r.nodes.append(Node(id=fid, kind="function", label=name,
                            qualified_name=f"{owner_fqn}.{name}", path=rel, lang=pf.sf.lang))
        r.edges.append(Edge(next(edge_seq), f"type:{owner_fqn}", fid,
                            "contains", EXTRACTED, 1.0))

    # 최상위 타입 + imports
    for c in root.children:
        if c.type in spec.type_decls:
            visit_type(c)
    for imp in _imports(root, spec):
        r.edges.append(Edge(next(edge_seq), file_id, f"type:{imp}", "imports", EXTRACTED, 1.0))

    return r


def function_index(nodes: list[Node]) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for n in nodes:
        if n.kind == "function":
            short = n.qualified_name.split(".")[-1]
            idx.setdefault(short, []).append(n.id)
    return idx
