from __future__ import annotations
from dataclasses import dataclass
from tree_sitter import Tree
from .lang import LANGS, LangSpec
from .walk import SourceFile


@dataclass
class ParsedFile:
    sf: SourceFile
    tree: Tree
    spec: LangSpec


def parse_file(sf: SourceFile) -> ParsedFile | None:
    spec = LANGS.get(sf.lang)
    if spec is None:
        return None
    tree = spec.parser().parse(sf.source)
    if tree.root_node.has_error and tree.root_node.child_count == 0:
        return None
    return ParsedFile(sf=sf, tree=tree, spec=spec)
