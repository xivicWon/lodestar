from __future__ import annotations
from typing import Iterator
from tree_sitter import Node as TsNode
from .model import Node, Edge, EXTRACTED, INFERRED, AMBIGUOUS
from .parse import ParsedFile
from .extract import function_index, _child_field_ident, _package_name, _descend, _params_arity


def _called_name(call: TsNode) -> str | None:
    """method_invocation(java) / call_expression(kotlin)에서 호출 메서드 단순명을 뽑는다.

    - java `method_invocation`: 'name' 필드가 항상 호출 메서드명이다. `foo()`, `obj.foo()`,
      `new X().foo()`, `System.out.println(...)`(name="println") 전부 이 필드 하나로 처리된다
      (실제 파스트리로 확인함: object_creation_expression/field_access 리시버가 앞에 붙어도
      'name' 필드는 항상 마지막 식별자를 가리킨다).
    - kotlin `call_expression`은 'name' 필드가 없다 (확인됨). 두 형태뿐이다:
        1) 단순 호출 `helper()` → call_expression의 직접 자식이 identifier/simple_identifier.
        2) 멤버 호출 `repo.save(1)` → call_expression → navigation_expression.
           navigation_expression의 **마지막** identifier/simple_identifier 직계 자식이
           메서드명이다(`repo.save`의 자식은 [identifier 'repo', '.', identifier 'save']
           → 마지막인 'save'가 메서드명). 체인 호출 `a.b.c.save()`도 최상위
           navigation_expression의 직계 자식은 [navigation_expression('a.b.c'), '.',
           identifier 'save']이므로 마지막 identifier 직계자식이 여전히 'save'다 — 앞쪽
           navigation_expression은 리시버 체인이라 내려가지 않는다(내려가면 리시버 쪽 이름을
           메서드명으로 오인할 수 있어 여기서는 직계자식만 본다).
      (참고: 원래 참고코드는 `_descend(...)[0]`로 이를 근사했는데, `_descend`가 스택
      pop()으로 자식을 역순 처리하는 부수효과 덕에 이 두 fixture 케이스에선 우연히 같은
      결과가 나왔다. 하지만 그 동작은 스택 순회의 우연한 부작용이라 신뢰할 근거가 없어,
      "navigation_expression의 마지막 identifier 직계자식"이라는 명시적 규칙으로 대체했다.)
    """
    name_field = call.child_by_field_name("name")
    if name_field is not None:
        return name_field.text.decode()
    for c in call.children:
        if c.type in ("identifier", "simple_identifier"):
            return c.text.decode()
        if c.type == "navigation_expression":
            name = None
            for nc in c.children:
                if nc.type in ("identifier", "simple_identifier"):
                    name = nc.text.decode()
            return name
    return None


def _collect_functions(pf: ParsedFile) -> list[tuple[int, int, str, str, str]]:
    """이 파일의 모든 function 선언을 (start_byte, end_byte, function_id, owner_fqn, package)로 수집.

    extract.extract_file과 *동일한* owner_fqn/arity 알고리즘 및 문서 순서 순회를 재현해서
    함수 id(오버로드 시 #seq 접미사 포함)를 정확히 재구성한다. 참고코드처럼 '파일 내 같은
    이름의 func_decl을 찾아 매칭'하는 방식은, 한 파일에 서로 다른 타입 소속의 동명 메서드가
    여러 개 있으면(예: 이 fixture의 Svc.save/Store.save) 잘못된 함수에 스팬을 배정할 수
    있어 정확한 owner_fqn 기반 재구성으로 대체했다.
    """
    spec = pf.spec
    root = pf.tree.root_node
    pkg = _package_name(root, spec)
    out: list[tuple[int, int, str, str, str]] = []
    arity_seen: dict[str, int] = {}

    def visit_type(tnode: TsNode, owner_fqn: str | None = None) -> None:
        name = _child_field_ident(tnode)
        if not name:
            return
        fqn = f"{owner_fqn}.{name}" if owner_fqn else (f"{pkg}.{name}" if pkg else name)
        for body in tnode.children:
            if body.type in ("class_body", "enum_body", "interface_body"):
                for m in body.children:
                    if m.type in spec.func_decls:
                        visit_func(m, fqn)
                    elif m.type in spec.type_decls:
                        visit_type(m, fqn)

    def visit_func(fnode: TsNode, owner_fqn: str) -> None:
        name = _child_field_ident(fnode)
        if not name:
            return
        arity = _params_arity(fnode)
        base = f"{owner_fqn}.{name}/{arity}"
        seen = arity_seen.get(base, 0)
        arity_seen[base] = seen + 1
        fid = f"function:{base}" + (f"#{seen}" if seen else "")
        out.append((fnode.start_byte, fnode.end_byte, fid, owner_fqn, pkg))

    for c in root.children:
        if c.type in spec.type_decls:
            visit_type(c)
    return out


def resolve_calls(parsed: list[ParsedFile], nodes: list[Node],
                   edge_seq: Iterator[int]) -> tuple[list[Edge], int]:
    fidx = function_index(nodes)

    # function id -> (owner type fqn, package). 호출 지점(src)과 후보(dst) 양쪽에 다 쓴다.
    func_meta: dict[str, tuple[str, str]] = {}
    # 파일 상대경로 -> [(start_byte, end_byte, function_id), ...] (그 파일 내 함수 스팬)
    file_spans: dict[str, list[tuple[int, int, str]]] = {}

    for pf in parsed:
        if pf is None:
            continue
        collected = _collect_functions(pf)
        file_spans[pf.sf.rel] = [(s, e, fid) for s, e, fid, _owner, _pkg in collected]
        for _s, _e, fid, owner_fqn, pkg in collected:
            func_meta[fid] = (owner_fqn, pkg)

    edges: list[Edge] = []
    external = 0

    for pf in parsed:
        if pf is None:
            continue
        spec = pf.spec
        root = pf.tree.root_node
        spans = file_spans.get(pf.sf.rel, [])

        for call in _descend(root, (spec.call_expr,)):
            pos = call.start_byte
            # 호출을 포함하는 가장 좁은(최내곽) function 스팬 하나를 고른다.
            src = None
            best_width = None
            for s, e, fid in spans:
                if s <= pos < e and (best_width is None or (e - s) < best_width):
                    src, best_width = fid, e - s
            if src is None:
                continue  # 함수 밖(필드 초기화 등)의 호출 — 스킵

            name = _called_name(call)
            if not name:
                continue

            cands = fidx.get(name, [])
            if not cands:
                external += 1
                continue

            src_owner, src_pkg = func_meta.get(src, ("", ""))

            same_type = [c for c in cands if func_meta.get(c, ("", ""))[0] == src_owner]
            if len(same_type) == 1:
                edges.append(Edge(next(edge_seq), src, same_type[0], "calls", EXTRACTED, 1.0))
                continue

            if len(cands) == 1:
                conf = 0.8
                if func_meta.get(cands[0], ("", ""))[1] == src_pkg:
                    conf = min(0.9, conf + 0.1)
                edges.append(Edge(next(edge_seq), src, cands[0], "calls", INFERRED, conf))
                continue

            # N>1 → AMBIGUOUS: 같은 패키지 후보를 우선하고, 그중(또는 전체 중) 첫 후보를 dst로.
            same_pkg = [c for c in cands if func_meta.get(c, ("", ""))[1] == src_pkg]
            rest = [c for c in cands if c not in same_pkg]
            ordered = same_pkg + rest
            dst = ordered[0]
            conf = min(0.4, 0.8 / len(cands))
            edges.append(Edge(next(edge_seq), src, dst, "calls", AMBIGUOUS, conf,
                               alternatives=ordered[1:]))

    return edges, external
