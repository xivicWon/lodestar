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


def _supertypes(type_node: TsNode) -> list[str]:
    """extends/implements 대상 단순명 목록 (근사)."""
    out = []
    for c in type_node.children:
        if c.type in ("superclass", "super_interfaces"):
            for ti in _descend(c, ("type_identifier",)):
                out.append(_text(ti))
        if c.type == "delegation_specifiers":  # kotlin
            for ut in _descend(c, ("user_type",)):
                nm = _child_field_ident(ut)
                if nm:
                    out.append(nm)
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

    def visit_type(tnode: TsNode):
        name = _child_field_ident(tnode)
        if not name:
            return
        fqn = f"{pkg}.{name}" if pkg else name
        tid = f"type:{fqn}"
        r.nodes.append(Node(id=tid, kind="type", label=name,
                            qualified_name=fqn, path=rel, lang=pf.sf.lang))
        r.type_index[fqn] = tid
        r.edges.append(Edge(next(edge_seq), file_id, tid, "contains", EXTRACTED, 1.0))
        # supertypes → extends (내부 여부는 resolve/emit 단계에서 필터하지 않고 단순명으로;
        #   여기선 FQN 확정 불가하므로 같은 패키지로 가정한 FQN 후보로 엣지 생성)
        for sup in _supertypes(tnode):
            sup_fqn = f"{pkg}.{sup}" if pkg else sup
            r.edges.append(Edge(next(edge_seq), tid, f"type:{sup_fqn}",
                                "extends", EXTRACTED, 1.0))
        # 멤버 함수
        for body in tnode.children:
            if body.type in ("class_body", "enum_body", "interface_body"):
                for m in body.children:
                    if m.type in spec.func_decls:
                        visit_func(m, fqn)
                    elif m.type in spec.type_decls:  # 중첩 타입
                        visit_type(m)

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
