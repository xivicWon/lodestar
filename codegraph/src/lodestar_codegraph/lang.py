from __future__ import annotations
from dataclasses import dataclass
import tree_sitter_java
import tree_sitter_kotlin
from tree_sitter import Language, Parser


@dataclass(frozen=True)
class LangSpec:
    name: str
    language: Language
    # 선언 노드 타입
    type_decls: tuple[str, ...]     # class/interface/object/enum
    func_decls: tuple[str, ...]     # method/function/constructor
    package_decl: str               # 패키지 선언 노드
    import_decl: str                # import 노드
    call_expr: str                  # 호출 표현식 노드

    def parser(self) -> Parser:
        return Parser(self.language)


JAVA = LangSpec(
    name="java",
    language=Language(tree_sitter_java.language()),
    type_decls=("class_declaration", "interface_declaration", "enum_declaration"),
    func_decls=("method_declaration", "constructor_declaration"),
    package_decl="package_declaration",
    import_decl="import_declaration",
    call_expr="method_invocation",
)

KOTLIN = LangSpec(
    name="kotlin",
    language=Language(tree_sitter_kotlin.language()),
    type_decls=("class_declaration", "object_declaration", "interface_declaration"),
    func_decls=("function_declaration",),
    package_decl="package_header",
    import_decl="import",
    call_expr="call_expression",
)

LANGS: dict[str, LangSpec] = {"java": JAVA, "kotlin": KOTLIN}


def lang_for_path(path: str) -> str | None:
    if path.endswith(".java"):
        return "java"
    if path.endswith((".kt", ".kts")):
        return "kotlin"
    return None
