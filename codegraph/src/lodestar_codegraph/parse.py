from __future__ import annotations
from dataclasses import dataclass, field
from tree_sitter import Node as TsNode, Tree
from .lang import LANGS, LangSpec
from .model import FAILED, Issue, PARSE_ERROR, UNSUPPORTED_LANGUAGE
from .walk import SourceFile


@dataclass
class ParsedFile:
    sf: SourceFile
    tree: Tree
    spec: LangSpec
    # 파싱 오류 구간의 1-base 행 범위. 이 구간과 겹치는 선언은 사실로 산출하지 않는다.
    error_spans: list[tuple[int, int]] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.error_spans)


def parse_file(sf: SourceFile) -> ParsedFile | None:
    """하위 호환 진입점 — 사유가 필요하면 [parse_with_issues] 를 쓴다."""
    return parse_with_issues(sf)[0]


def _line_count(source: bytes) -> int:
    text = source.decode("utf-8", "replace")
    n = text.count("\n")
    return n if text.endswith("\n") else n + 1


def _error_nodes(root: TsNode) -> list[TsNode]:
    """ERROR·MISSING 노드 중 **가장 바깥 것만**. 중첩까지 세면 실패 건수가 부풀어 R-F-4 를 깬다."""
    out: list[TsNode] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "ERROR" or n.is_missing:
            out.append(n)
            continue          # 하위 오류는 이 구간에 흡수된다
        if n.has_error:
            stack.extend(n.children)
    out.sort(key=lambda n: (n.start_point[0], n.end_point[0]))
    return out


def _error_target(n: TsNode, pkg: str) -> str | None:
    """오류 구간이 어떤 선언을 삼켰는지 — `class`/`object`/`fun` 다음 식별자."""
    prev_kw = False
    for c in n.children:
        if c.type in ("class", "object", "interface", "fun", "enum"):
            prev_kw = True
            continue
        if prev_kw and c.type in ("identifier", "simple_identifier", "type_identifier"):
            return f"{pkg}." + c.text.decode("utf-8", "replace") if pkg \
                else c.text.decode("utf-8", "replace")
        prev_kw = False
    return None


def _package(root: TsNode, spec: LangSpec) -> str:
    for c in root.children:
        if c.type == spec.package_decl:
            for d in c.children:
                if d.type in ("scoped_identifier", "qualified_identifier", "identifier"):
                    return d.text.decode("utf-8", "replace").replace(" ", "")
    return ""


def parse_with_issues(sf: SourceFile) -> tuple[ParsedFile | None, list[Issue]]:
    """파싱 결과와 **파싱 실패 보고**를 함께 돌려준다(#114).

    tree-sitter 는 오류 복구 파서라 깨진 입력에서도 부분 트리를 만든다. 그 부분 트리에서 심볼을
    건져 '성공' 으로 표시하면 부분 추출이 완전 추출로 위장된다(gold F.CODE.BROKEN_SYNTAX ·
    F.CODE.PARTIAL_EXTRACT). 그래서 오류 구간을 좌표로 남기고, 겹치는 선언은 산출하지 않는다.
    """
    spec = LANGS.get(sf.lang)
    if spec is None:
        return None, [Issue(
            FAILED, UNSUPPORTED_LANGUAGE,
            f"파서가 없는 언어다: {sf.lang}", f"{sf.rel}#L1", sf.rel)]

    tree = spec.parser().parse(sf.source)
    root = tree.root_node
    last_line = _line_count(sf.source)
    pkg = _package(root, spec)

    spans: list[tuple[int, int]] = []
    issues: list[Issue] = []
    for n in _error_nodes(root):
        start = n.start_point[0] + 1
        # tree-sitter 의 끝 좌표는 파일 끝 개행 뒤의 가상 행을 가리킬 수 있다 — 원본 행수로 자른다.
        end = min(max(n.end_point[0] + 1, start), last_line)
        spans.append((start, end))
        target = _error_target(n, pkg) or sf.rel
        issues.append(Issue(
            FAILED, PARSE_ERROR,
            "구문 오류로 이 구간을 사실로 산출하지 못했다 — tree-sitter 의 부분 트리에서 심볼을 "
            "건져 성공으로 표시하지 않는다",
            f"{sf.rel}#L{start}" if start == end else f"{sf.rel}#L{start}-L{end}",
            target))

    if root.child_count == 0 and root.has_error:
        # 트리가 아예 서지 않은 경우 — 파일 단위 실패다.
        return None, issues or [Issue(
            FAILED, PARSE_ERROR, "파일에서 어떤 구문도 파싱되지 않았다", f"{sf.rel}#L1", sf.rel)]

    return ParsedFile(sf=sf, tree=tree, spec=spec, error_spans=spans), issues
