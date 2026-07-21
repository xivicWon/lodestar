# E17 코드 소스 수집기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 소스코드(Java+Kotlin)를 tree-sitter로 파싱해 노드/엣지로 추출·분석하고, 정적 `codegraph.json`을 산출하는 독립 Python 도구를 만든다.

**Architecture:** 리포 루트 `codegraph/`에 독립 Python 프로젝트. 파이프라인 = walk(트리 순회) → parse(tree-sitter) → extract(노드+구조엣지) → resolve(호출해석+provenance) → cluster(Louvain/degree) → emit(JSON). 언어별 노드타입 차이는 `lang.py` 매핑 테이블 하나로 격리. Graphify를 호출하지 않고 그 노드화 방식을 직접 구현.

**Tech Stack:** Python 3.13, tree-sitter 0.23.2, tree-sitter-java 0.23.5, tree-sitter-kotlin 1.1.0, networkx(Louvain), pytest.

## Global Constraints

- 대상 언어 v1 = **Java + Kotlin만** (D8/D9). Python 자기분석 제외.
- 산출물 `codegraph.json`은 **git 커밋 안 함**; `codegraph/out/`를 `.gitignore` (D10). 코드+테스트+소형 픽스처만 커밋.
- provenance 어휘 = **EXTRACTED / INFERRED / AMBIGUOUS** (E16-0 재사용, D6).
- confidence 공식 (D13): EXTRACTED=1.0; INFERRED=0.8(+같은 패키지 0.1, 상한 0.9); AMBIGUOUS=`min(0.4, 0.8/N)`.
- 노드 id = `file:<상대경로>` | `type:<FQN>` | `function:<FQN>.<name>/<arity>` (D12). 충돌 시 선언순 순번.
- 통합 단일 그래프에서 Java↔Kotlin 경계 넘어 FQN 기준 해석 (D11).
- 결정적 재현성: `random`/시각 미사용, 출력은 id 정렬. 동일 입력→바이트 동일 출력.
- tree-sitter 코어/문법 버전은 `pyproject.toml`에 **핀 고정** (ABI 리스크).
- 파싱 실패 파일은 스킵 + `meta.skipped` 기록 (무시 금지).
- 품질 게이트: `pytest` 그린.

## File Structure

```
codegraph/
  pyproject.toml                     # 의존성 핀 고정, 패키지 메타
  .gitignore                         # out/
  README.md                          # 실행법
  src/lodestar_codegraph/
    __init__.py
    __main__.py                      # CLI: python -m lodestar_codegraph <root> [-o] [...]
    model.py                         # Node/Edge dataclass, provenance 상수
    lang.py                          # 언어별 tree-sitter 노드타입 매핑 테이블 + 로더
    walk.py                          # 소스 트리 walk + .codegraphignore + 언어판별
    parse.py                         # tree-sitter 파싱 → ParsedFile
    extract.py                       # ParsedFile → 노드 + 구조엣지(contains/imports/extends/implements)
    resolve.py                       # calls 엣지 해석 + provenance/confidence/alternatives
    cluster.py                       # networkx Louvain + degree + god-node 태깅
    emit.py                          # codegraph.json 직렬화
  tests/
    fixtures/sample/                 # 소형 Java+Kotlin 트리
    test_walk.py test_parse.py test_extract.py test_resolve.py test_cluster.py test_emit.py
  out/                               # 산출물(gitignore)
```

각 파일 하나의 책임: walk=발견, parse=구문트리, extract=구조, resolve=호출해석, cluster=군집, emit=직렬화. lang.py가 언어차이를 흡수해 나머지는 언어무관.

---

### Task 1: 스캐폴드 + walk + parse (E17-1)

**Files:**
- Create: `codegraph/pyproject.toml`, `codegraph/.gitignore`, `codegraph/src/lodestar_codegraph/__init__.py`
- Create: `codegraph/src/lodestar_codegraph/model.py`, `lang.py`, `walk.py`, `parse.py`, `__main__.py`
- Test: `codegraph/tests/test_walk.py`, `codegraph/tests/test_parse.py`
- Create fixtures: `codegraph/tests/fixtures/sample/com/x/Foo.java`, `.../Foo.kt`, `codegraph/tests/fixtures/sample/build/Ignored.java`

**Interfaces:**
- Produces:
  - `model.Node(id:str, kind:str, label:str, qualified_name:str, path:str, lang:str, community:int|None=None, degree:int=0, god_node:bool=False)`
  - `model.Edge(id:int, src:str, dst:str, kind:str, provenance:str, confidence:float, alternatives:list[str])` — serialized as `from`/`to` in emit (Python `from` 예약어 회피).
  - `model.EXTRACTED="EXTRACTED"`, `INFERRED="INFERRED"`, `AMBIGUOUS="AMBIGUOUS"`
  - `lang.LANGS: dict[str, LangSpec]` where key ∈ {"java","kotlin"}; `LangSpec` has `.parser()` (tree_sitter.Parser) and node-type field names below.
  - `lang.lang_for_path(path:str) -> str|None` (".java"→"java", ".kt"/".kts"→"kotlin", else None)
  - `walk.SourceFile(path:str, rel:str, lang:str, source:bytes)`
  - `walk.walk_sources(root:str, ignore_globs:list[str]) -> list[SourceFile]`
  - `parse.ParsedFile(sf:walk.SourceFile, tree:tree_sitter.Tree, spec:lang.LangSpec)`
  - `parse.parse_file(sf:walk.SourceFile) -> ParsedFile|None` (파싱 실패 시 None)

- [ ] **Step 1: pyproject.toml + .gitignore + 패키지 init 작성**

`codegraph/pyproject.toml`:
```toml
[project]
name = "lodestar-codegraph"
version = "0.1.0"
description = "Lodestar code source collector — source → codegraph.json (tree-sitter)"
requires-python = ">=3.11"
dependencies = [
  "tree-sitter==0.23.2",
  "tree-sitter-java==0.23.5",
  "tree-sitter-kotlin==1.1.0",
  "networkx>=3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`codegraph/.gitignore`:
```
out/
__pycache__/
*.egg-info/
.pytest_cache/
```

`codegraph/src/lodestar_codegraph/__init__.py`:
```python
__all__ = ["model", "lang", "walk", "parse"]
```

- [ ] **Step 2: model.py 작성**

`codegraph/src/lodestar_codegraph/model.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field

EXTRACTED = "EXTRACTED"
INFERRED = "INFERRED"
AMBIGUOUS = "AMBIGUOUS"


@dataclass
class Node:
    id: str
    kind: str            # "file" | "type" | "function"
    label: str
    qualified_name: str
    path: str
    lang: str            # "java" | "kotlin" | ""
    community: int | None = None
    degree: int = 0
    god_node: bool = False


@dataclass
class Edge:
    id: int
    src: str             # serialized as "from"
    dst: str             # serialized as "to"
    kind: str            # contains|imports|extends|implements|calls
    provenance: str      # EXTRACTED|INFERRED|AMBIGUOUS
    confidence: float
    alternatives: list[str] = field(default_factory=list)
```

- [ ] **Step 3: lang.py 작성 (언어별 노드타입 매핑 — 검증된 실제 타입)**

`codegraph/src/lodestar_codegraph/lang.py`:
```python
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
```

- [ ] **Step 4: walk.py 작성**

`codegraph/src/lodestar_codegraph/walk.py`:
```python
from __future__ import annotations
import fnmatch
import os
from dataclasses import dataclass
from .lang import lang_for_path


@dataclass
class SourceFile:
    path: str       # 절대경로
    rel: str        # source_root 기준 상대경로
    lang: str
    source: bytes


def _ignored(rel: str, ignore_globs: list[str]) -> bool:
    parts = rel.split(os.sep)
    for g in ignore_globs:
        pat = g.rstrip("/")
        if fnmatch.fnmatch(rel, pat) or any(fnmatch.fnmatch(p, pat) for p in parts):
            return True
    return False


def walk_sources(root: str, ignore_globs: list[str]) -> list[SourceFile]:
    out: list[SourceFile] = []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        # 디렉토리 프루닝
        dirnames[:] = [
            d for d in dirnames
            if not _ignored(os.path.join(rel_dir, d) if rel_dir != "." else d, ignore_globs)
        ]
        for fn in filenames:
            lang = lang_for_path(fn)
            if lang is None:
                continue
            abspath = os.path.join(dirpath, fn)
            rel = os.path.relpath(abspath, root)
            if _ignored(rel, ignore_globs):
                continue
            with open(abspath, "rb") as f:
                out.append(SourceFile(path=abspath, rel=rel, lang=lang, source=f.read()))
    out.sort(key=lambda s: s.rel)
    return out


def load_ignore(root: str, override: str | None) -> list[str]:
    path = override or os.path.join(root, ".codegraphignore")
    globs: list[str] = ["build", ".gradle", ".git", "node_modules"]
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    globs.append(line)
    return globs
```

- [ ] **Step 5: 픽스처 작성**

`codegraph/tests/fixtures/sample/com/x/Foo.java`:
```java
package com.x;
import com.x.Repo;
public class Foo extends Base {
    void run() { new Repo().save(1); }
}
```

`codegraph/tests/fixtures/sample/com/x/Repo.java`:
```java
package com.x;
public class Repo {
    void save(int n) {}
}
```

`codegraph/tests/fixtures/sample/com/x/Bar.kt`:
```kotlin
package com.x
class Bar {
    fun go() { helper() }
    fun helper() {}
}
```

`codegraph/tests/fixtures/sample/build/Ignored.java`:
```java
package build;
public class Ignored {}
```

- [ ] **Step 6: test_walk.py 작성 (실패 확인용)**

`codegraph/tests/test_walk.py`:
```python
import os
from lodestar_codegraph.walk import walk_sources, load_ignore

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample")


def test_walk_finds_java_and_kotlin_skips_build():
    ignore = load_ignore(FIX, None)
    files = walk_sources(FIX, ignore)
    rels = sorted(f.rel for f in files)
    assert any(r.endswith("Foo.java") for r in rels)
    assert any(r.endswith("Bar.kt") for r in rels)
    assert not any("build" in r for r in rels)  # build/ 프루닝
    langs = {f.rel: f.lang for f in files}
    assert langs[[r for r in rels if r.endswith("Foo.java")][0]] == "java"
    assert langs[[r for r in rels if r.endswith("Bar.kt")][0]] == "kotlin"
```

- [ ] **Step 7: walk 테스트 실행 (통과 확인)**

Run: `cd codegraph && python -m pytest tests/test_walk.py -v`
Expected: PASS (walk.py 이미 구현됨 — 이 태스크는 인프라 + 검증 동시)

- [ ] **Step 8: parse.py 작성**

`codegraph/src/lodestar_codegraph/parse.py`:
```python
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
```

- [ ] **Step 9: test_parse.py 작성**

`codegraph/tests/test_parse.py`:
```python
import os
from lodestar_codegraph.walk import walk_sources, load_ignore
from lodestar_codegraph.parse import parse_file

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample")


def _parsed():
    files = walk_sources(FIX, load_ignore(FIX, None))
    return {f.rel: parse_file(f) for f in files}


def test_parse_java_and_kotlin_roots():
    parsed = _parsed()
    foo = [p for r, p in parsed.items() if r.endswith("Foo.java")][0]
    bar = [p for r, p in parsed.items() if r.endswith("Bar.kt")][0]
    assert foo is not None and foo.tree.root_node.type == "program"
    assert bar is not None and bar.tree.root_node.type == "source_file"
```

- [ ] **Step 10: parse 테스트 실행**

Run: `cd codegraph && python -m pytest tests/test_parse.py -v`
Expected: PASS

- [ ] **Step 11: __main__.py 스텁 작성 (CLI 뼈대, 다음 태스크에서 파이프라인 연결)**

`codegraph/src/lodestar_codegraph/__main__.py`:
```python
from __future__ import annotations
import argparse
import os
import sys
from .walk import walk_sources, load_ignore
from .parse import parse_file


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lodestar_codegraph")
    ap.add_argument("source_root")
    ap.add_argument("-o", "--out", default="out/codegraph.json")
    ap.add_argument("--ignore", default=None)
    ap.add_argument("--god-node-percentile", type=float, default=99.0)
    args = ap.parse_args(argv)

    ignore = load_ignore(args.source_root, args.ignore)
    files = walk_sources(args.source_root, ignore)
    parsed = [p for p in (parse_file(f) for f in files) if p is not None]
    skipped = len(files) - len(parsed)
    print(f"walked={len(files)} parsed={len(parsed)} skipped={skipped}", file=sys.stderr)
    # 파이프라인(extract→resolve→cluster→emit)은 Task 2-4에서 연결
    print("TODO: extract/resolve/cluster/emit — 후속 태스크", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 12: CLI 스모크 실행 (ABI 로드 확인)**

Run: `cd codegraph && python -m lodestar_codegraph tests/fixtures/sample`
Expected(stderr): `walked=3 parsed=3 skipped=0` (build/Ignored.java는 프루닝되어 walked에서 제외)

- [ ] **Step 13: 커밋**

```bash
cd /Users/wonjaeho/Workspace/onto-studio
git add codegraph/pyproject.toml codegraph/.gitignore codegraph/src codegraph/tests
git commit -m "feat(e17-1): codegraph 스캐폴드 + walk + tree-sitter parse

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 노드 + 구조 엣지 추출 (E17-2)

**Files:**
- Create: `codegraph/src/lodestar_codegraph/extract.py`
- Test: `codegraph/tests/test_extract.py`

**Interfaces:**
- Consumes: `parse.ParsedFile`, `model.Node/Edge/EXTRACTED`, `lang.LangSpec`.
- Produces:
  - `extract.ExtractResult(nodes:list[Node], edges:list[Edge], type_index:dict[str,str])` — `type_index` maps FQN→node id for types (resolve/import 용).
  - `extract.extract_file(pf:ParsedFile, edge_seq:Iterator[int]) -> ExtractResult` — 파일 하나의 노드/구조엣지. `edge_seq`는 전역 엣지 id 카운터(itertools.count).
  - `extract.function_index(nodes:list[Node]) -> dict[str, list[str]]` — 메서드명(짧은)→function node id 목록 (resolve 용).
  - node id 규칙: file=`file:<rel>`, type=`type:<FQN>`, function=`function:<typeFQN>.<name>/<arity>`(중복 arity는 `#순번` 접미사).

- [ ] **Step 1: test_extract.py 작성 (실패 확인)**

`codegraph/tests/test_extract.py`:
```python
import os
from itertools import count
from lodestar_codegraph.walk import walk_sources, load_ignore
from lodestar_codegraph.parse import parse_file
from lodestar_codegraph.extract import extract_file

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
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd codegraph && python -m pytest tests/test_extract.py -v`
Expected: FAIL (`ModuleNotFoundError: extract`)

- [ ] **Step 3: extract.py 작성**

`codegraph/src/lodestar_codegraph/extract.py`:
```python
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
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

Run: `cd codegraph && python -m pytest tests/test_extract.py -v`
Expected: PASS (2 passed). imports 엣지가 `type:com.x.Repo`를 가리키는지, contains/extends 확인.

> 주: 구조엣지는 dangling 대상(예: `type:com.x.Base`, 내부에 없는 import)을 가리킬 수 있다. emit 단계에서 "존재하는 노드로의 엣지만 유지"할지 여부는 Task 4에서 결정(기본: 내부 노드로의 엣지만 최종 그래프에 유지, 외부참조는 카운트).

- [ ] **Step 5: 커밋**

```bash
cd /Users/wonjaeho/Workspace/onto-studio
git add codegraph/src/lodestar_codegraph/extract.py codegraph/tests/test_extract.py
git commit -m "feat(e17-2): 노드(file/type/function) + 구조엣지(contains/imports/extends)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: calls 해석 + provenance (E17-3)

**Files:**
- Create: `codegraph/src/lodestar_codegraph/resolve.py`
- Test: `codegraph/tests/test_resolve.py`

**Interfaces:**
- Consumes: `parse.ParsedFile`, `extract.function_index`, `model.Edge/Node/EXTRACTED/INFERRED/AMBIGUOUS`.
- Produces:
  - `resolve.resolve_calls(parsed:list[ParsedFile], nodes:list[Node], edge_seq:Iterator[int]) -> tuple[list[Edge], int]` — calls 엣지 목록 + `external_calls`(매칭 0개) 카운트.
  - 규칙: 호출부가 속한 function 노드를 `src`로. 대상은 메서드명으로 function_index 조회.
    - 후보 1개 → provenance=INFERRED, confidence=0.8(+같은 패키지 0.1, ≤0.9).
    - 후보 N>1 → provenance=AMBIGUOUS, dst=같은 패키지 우선/그다음 첫 후보, alternatives=나머지, confidence=`min(0.4, 0.8/N)`.
    - 후보 0 → 엣지 없음, external_calls += 1.
  - 같은 파일/같은 타입 내 유일 정의로 해석되면 provenance=EXTRACTED, confidence=1.0.

- [ ] **Step 1: 픽스처 확장 (애매 호출 케이스 추가)**

`codegraph/tests/fixtures/sample/com/x/Svc.kt` 생성:
```kotlin
package com.x
class Svc {
    fun handle() { save(1) }   // 자기 자신 save 존재 → 같은 타입 유일 → EXTRACTED
    fun save(n: Int) {}
}
class Store {
    fun save(n: Int) {}
}
class Client {
    fun use() { save(1) }      // Client엔 save 없음; Repo.save+Store.save+Svc.save 3후보, 같은타입 0 → AMBIGUOUS
}
```

또한 `codegraph/tests/fixtures/sample/com/x/Foo.java`의 `run()`에 외부 호출 1건 추가(println은 function 노드 아님 → external):
```java
package com.x;
import com.x.Repo;
public class Foo extends Base {
    void run() {
        new Repo().save(1);
        System.out.println("hi");   // println 미정의 → external_calls 카운트, 엣지 없음
    }
}
```

- [ ] **Step 2: test_resolve.py 작성 (실패 확인)**

`codegraph/tests/test_resolve.py`:
```python
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
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

Run: `cd codegraph && python -m pytest tests/test_resolve.py -v`
Expected: FAIL (`ModuleNotFoundError: resolve`)

- [ ] **Step 4: resolve.py 작성**

`codegraph/src/lodestar_codegraph/resolve.py`:
```python
from __future__ import annotations
from typing import Iterator
from tree_sitter import Node as TsNode
from .model import Node, Edge, EXTRACTED, INFERRED, AMBIGUOUS
from .parse import ParsedFile
from .extract import function_index, _child_field_ident, _package_name, _descend


def _enclosing_function_id(call: TsNode, func_spans: list[tuple[int, int, str]]) -> str | None:
    """call 노드의 시작 바이트를 포함하는 최내곽 function 노드 id."""
    pos = call.start_byte
    best = None
    best_span = None
    for s, e, fid in func_spans:
        if s <= pos < e and (best_span is None or (e - s) < best_span):
            best, best_span = fid, e - s
    return best


def _called_name(call: TsNode) -> str | None:
    """method_invocation(java) / call_expression(kotlin)에서 호출 메서드 단순명."""
    # java: method_invocation -> ... 'name' field 또는 마지막 identifier 이전 identifier
    # kotlin: call_expression -> navigation_expression -> 마지막 identifier / 또는 직접 identifier
    idents = _descend(call, ("identifier", "simple_identifier"))
    # 호출명은 value_arguments 직전의 identifier — 근사로 첫 자식 체인의 마지막 이름 사용
    # java method_invocation: name 필드
    name_field = call.child_by_field_name("name")
    if name_field is not None:
        return name_field.text.decode()
    # kotlin: navigation_expression의 마지막 identifier, 없으면 첫 identifier
    for c in call.children:
        if c.type == "navigation_expression":
            ids = _descend(c, ("identifier", "simple_identifier"))
            if ids:
                return ids[0].text.decode()
        if c.type in ("identifier", "simple_identifier"):
            return c.text.decode()
    return idents[0].text.decode() if idents else None


def resolve_calls(parsed: list[ParsedFile], nodes: list[Node],
                  edge_seq: Iterator[int]) -> tuple[list[Edge], int]:
    fidx = function_index(nodes)
    # function id -> (owner type fqn, package)
    owner_of: dict[str, str] = {}
    pkg_of_type: dict[str, str] = {}
    for n in nodes:
        if n.kind == "function":
            owner = n.qualified_name.rsplit(".", 1)[0]
            owner_of[n.id] = owner
            pkg_of_type[owner] = owner.rsplit(".", 1)[0] if "." in owner else ""

    edges: list[Edge] = []
    external = 0

    for pf in parsed:
        spec = pf.spec
        root = pf.tree.root_node
        pkg = _package_name(root, spec)
        # 이 파일의 function 스팬 목록
        func_spans: list[tuple[int, int, str]] = []
        for n in nodes:
            if n.kind == "function" and n.path == pf.sf.rel:
                # 스팬은 트리에서 다시 찾기: 이름/owner로 매칭이 어려우므로 위치기반 재수집
                pass
        # 위치기반: 트리에서 func_decls 노드 수집 + id 재구성
        fdecls = _descend(root, spec.func_decls)
        # id 재구성을 위해 owner 추적이 필요 → 간단히: 각 func_decl의 이름+arity로 이 파일 노드와 매칭
        file_funcs = [n for n in nodes if n.kind == "function" and n.path == pf.sf.rel]
        for fd in fdecls:
            nm = _child_field_ident(fd)
            if not nm:
                continue
            cand = [n for n in file_funcs if n.qualified_name.split(".")[-1] == nm]
            if cand:
                func_spans.append((fd.start_byte, fd.end_byte, cand[0].id))

        for call in _descend(root, (spec.call_expr,)):
            src = _enclosing_function_id(call, func_spans)
            if src is None:
                continue
            name = _called_name(call)
            if not name:
                continue
            cands = fidx.get(name, [])
            if not cands:
                external += 1
                continue
            src_owner = owner_of.get(src, "")
            # 같은 타입 내 후보 우선 → EXTRACTED
            same_type = [c for c in cands if owner_of.get(c) == src_owner]
            if len(same_type) == 1:
                edges.append(Edge(next(edge_seq), src, same_type[0], "calls", EXTRACTED, 1.0))
                continue
            if len(cands) == 1:
                conf = 0.8
                if pkg_of_type.get(owner_of.get(cands[0], ""), "") == pkg:
                    conf = min(0.9, conf + 0.1)
                edges.append(Edge(next(edge_seq), src, cands[0], "calls", INFERRED, conf))
                continue
            # N>1 → AMBIGUOUS, 같은 패키지 우선
            same_pkg = [c for c in cands if pkg_of_type.get(owner_of.get(c, ""), "") == pkg]
            ordered = same_pkg + [c for c in cands if c not in same_pkg]
            dst = ordered[0]
            conf = min(0.4, 0.8 / len(cands))
            edges.append(Edge(next(edge_seq), src, dst, "calls", AMBIGUOUS, conf,
                              alternatives=ordered[1:]))

    return edges, external
```

- [ ] **Step 5: 테스트 실행 (통과 확인)**

Run: `cd codegraph && python -m pytest tests/test_resolve.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: 커밋**

```bash
cd /Users/wonjaeho/Workspace/onto-studio
git add codegraph/src/lodestar_codegraph/resolve.py codegraph/tests/test_resolve.py codegraph/tests/fixtures
git commit -m "feat(e17-3): calls 해석 + provenance(EXTRACTED/INFERRED/AMBIGUOUS)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 군집 + emit + CLI 연결 (E17-4)

**Files:**
- Create: `codegraph/src/lodestar_codegraph/cluster.py`, `codegraph/src/lodestar_codegraph/emit.py`
- Modify: `codegraph/src/lodestar_codegraph/__main__.py` (파이프라인 연결)
- Create: `codegraph/README.md`
- Test: `codegraph/tests/test_cluster.py`, `codegraph/tests/test_emit.py`

**Interfaces:**
- Consumes: `model.Node/Edge`, networkx.
- Produces:
  - `cluster.annotate(nodes:list[Node], edges:list[Edge], god_percentile:float) -> None` — in-place로 각 노드 community/degree/god_node 설정. 최종 그래프에 존재하는 노드로의 엣지만 degree에 반영.
  - `emit.build_and_write(nodes, edges, meta_extra:dict, out_path:str, prune_dangling:bool=True) -> dict` — 존재하지 않는 대상으로의 엣지 제거(prune_dangling), meta 계산, JSON 직렬화 후 dict 반환.
  - JSON: edge의 `src`→`"from"`, `dst`→`"to"`. 노드/엣지 id 정렬(결정적).

- [ ] **Step 1: test_cluster.py 작성 (실패 확인)**

`codegraph/tests/test_cluster.py`:
```python
from lodestar_codegraph.model import Node, Edge, EXTRACTED
from lodestar_codegraph.cluster import annotate


def _n(i):
    return Node(id=i, kind="type", label=i, qualified_name=i, path="p", lang="java")


def test_degree_and_community_and_godnode():
    nodes = [_n("A"), _n("B"), _n("C"), _n("D")]
    edges = [
        Edge(1, "A", "B", "calls", EXTRACTED, 1.0),
        Edge(2, "A", "C", "calls", EXTRACTED, 1.0),
        Edge(3, "A", "D", "calls", EXTRACTED, 1.0),
        Edge(4, "B", "C", "calls", EXTRACTED, 1.0),
    ]
    annotate(nodes, edges, god_percentile=75.0)
    by = {n.id: n for n in nodes}
    assert by["A"].degree == 3
    assert by["B"].degree == 2
    # A가 최고 degree → god_node
    assert by["A"].god_node is True
    # community 할당됨(정수)
    assert all(n.community is not None for n in nodes)
```

- [ ] **Step 2: 실행 (실패 확인)**

Run: `cd codegraph && python -m pytest tests/test_cluster.py -v`
Expected: FAIL (`ModuleNotFoundError: cluster`)

- [ ] **Step 3: cluster.py 작성**

`codegraph/src/lodestar_codegraph/cluster.py`:
```python
from __future__ import annotations
import networkx as nx
from .model import Node, Edge


def annotate(nodes: list[Node], edges: list[Edge], god_percentile: float) -> None:
    ids = {n.id for n in nodes}
    g = nx.Graph()
    g.add_nodes_from(ids)
    for e in edges:
        if e.src in ids and e.dst in ids:
            w = g.get_edge_data(e.src, e.dst, {}).get("weight", 0.0)
            g.add_edge(e.src, e.dst, weight=w + e.confidence)

    # degree
    deg = dict(g.degree())
    # community (Louvain, 결정적 seed)
    communities = nx.community.louvain_communities(g, weight="weight", seed=42)
    comm_of: dict[str, int] = {}
    for cid, members in enumerate(sorted(communities, key=lambda m: min(m) if m else "")):
        for m in members:
            comm_of[m] = cid

    degrees = sorted(deg.values())
    if degrees:
        import math
        idx = min(len(degrees) - 1, int(math.ceil(god_percentile / 100.0 * len(degrees))) - 1)
        threshold = degrees[max(0, idx)]
    else:
        threshold = 0

    for n in nodes:
        n.degree = deg.get(n.id, 0)
        n.community = comm_of.get(n.id)
        n.god_node = n.degree >= threshold and n.degree > 0
```

- [ ] **Step 4: 실행 (통과 확인)**

Run: `cd codegraph && python -m pytest tests/test_cluster.py -v`
Expected: PASS

- [ ] **Step 5: test_emit.py 작성 (실패 확인)**

`codegraph/tests/test_emit.py`:
```python
import json
import os
from lodestar_codegraph.model import Node, Edge, EXTRACTED
from lodestar_codegraph.emit import build_and_write


def test_emit_prunes_dangling_and_serializes(tmp_path):
    nodes = [
        Node("type:A", "type", "A", "A", "p", "java"),
        Node("type:B", "type", "B", "B", "p", "java"),
    ]
    edges = [
        Edge(1, "type:A", "type:B", "calls", EXTRACTED, 1.0),
        Edge(2, "type:A", "type:MISSING", "calls", EXTRACTED, 1.0),  # dangling
    ]
    out = tmp_path / "cg.json"
    doc = build_and_write(nodes, edges, {"source_root": "p"}, str(out), prune_dangling=True)
    assert doc["meta"]["node_count"] == 2
    assert doc["meta"]["edge_count"] == 1  # dangling 제거
    e = doc["edges"][0]
    assert e["from"] == "type:A" and e["to"] == "type:B"
    # 파일로도 쓰였는지
    with open(out) as f:
        disk = json.load(f)
    assert disk == doc


def test_emit_deterministic(tmp_path):
    nodes = [Node("type:B", "type", "B", "B", "p", "java"),
             Node("type:A", "type", "A", "A", "p", "java")]
    edges = []
    o1 = tmp_path / "a.json"; o2 = tmp_path / "b.json"
    build_and_write(nodes, edges, {}, str(o1))
    build_and_write(nodes, edges, {}, str(o2))
    assert open(o1).read() == open(o2).read()
    # 정렬: A가 B보다 먼저
    doc = json.load(open(o1))
    assert [n["id"] for n in doc["nodes"]] == ["type:A", "type:B"]
```

- [ ] **Step 6: 실행 (실패 확인)**

Run: `cd codegraph && python -m pytest tests/test_emit.py -v`
Expected: FAIL (`ModuleNotFoundError: emit`)

- [ ] **Step 7: emit.py 작성**

`codegraph/src/lodestar_codegraph/emit.py`:
```python
from __future__ import annotations
import json
import os
from .model import Node, Edge


def build_and_write(nodes: list[Node], edges: list[Edge], meta_extra: dict,
                    out_path: str, prune_dangling: bool = True) -> dict:
    ids = {n.id for n in nodes}
    kept = [e for e in edges if not prune_dangling or (e.src in ids and e.dst in ids)]

    node_docs = sorted(
        ({"id": n.id, "kind": n.kind, "label": n.label,
          "qualified_name": n.qualified_name, "path": n.path, "lang": n.lang,
          "community": n.community, "degree": n.degree, "god_node": n.god_node}
         for n in nodes),
        key=lambda d: d["id"],
    )
    edge_docs = sorted(
        ({"id": e.id, "from": e.src, "to": e.dst, "kind": e.kind,
          "provenance": e.provenance, "confidence": round(e.confidence, 4),
          "alternatives": e.alternatives}
         for e in kept),
        key=lambda d: (d["from"], d["to"], d["kind"]),
    )
    communities = {n.community for n in nodes if n.community is not None}
    meta = {**meta_extra,
            "generated_by": "lodestar-codegraph v1",
            "node_count": len(node_docs),
            "edge_count": len(edge_docs),
            "community_count": len(communities)}
    doc = {"meta": meta, "nodes": node_docs, "edges": edge_docs}

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=False)
    return doc
```

- [ ] **Step 8: 실행 (통과 확인)**

Run: `cd codegraph && python -m pytest tests/test_emit.py -v`
Expected: PASS (2 passed)

- [ ] **Step 9: __main__.py 파이프라인 연결**

`codegraph/src/lodestar_codegraph/__main__.py` 를 아래로 교체:
```python
from __future__ import annotations
import argparse
import sys
from itertools import count
from .walk import walk_sources, load_ignore
from .parse import parse_file
from .extract import extract_file
from .resolve import resolve_calls
from .cluster import annotate
from .emit import build_and_write


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lodestar_codegraph")
    ap.add_argument("source_root")
    ap.add_argument("-o", "--out", default="out/codegraph.json")
    ap.add_argument("--ignore", default=None)
    ap.add_argument("--god-node-percentile", type=float, default=99.0)
    args = ap.parse_args(argv)

    ignore = load_ignore(args.source_root, args.ignore)
    files = walk_sources(args.source_root, ignore)

    seq = count(1)
    parsed, nodes, edges = [], [], []
    for f in files:
        pf = parse_file(f)
        if pf is None:
            continue
        parsed.append(pf)
        r = extract_file(pf, seq)
        nodes += r.nodes
        edges += r.edges

    calls, external = resolve_calls(parsed, nodes, seq)
    edges += calls

    annotate(nodes, edges, args.god_node_percentile)

    langs = sorted({f.lang for f in files})
    meta_extra = {
        "source_root": args.source_root,
        "languages": langs,
        "walked": len(files),
        "parsed": len(parsed),
        "skipped": len(files) - len(parsed),
        "external_calls": external,
    }
    doc = build_and_write(nodes, edges, meta_extra, args.out, prune_dangling=True)
    m = doc["meta"]
    print(f"nodes={m['node_count']} edges={m['edge_count']} "
          f"communities={m['community_count']} skipped={m['skipped']} "
          f"external_calls={m['external_calls']} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 10: README.md 작성**

`codegraph/README.md`:
```markdown
# lodestar-codegraph

소스코드(Java+Kotlin) → 정적 `codegraph.json` (노드/엣지/군집). Graphify 방식의 네이티브 구현.

## 설치
    pip install -e .[dev]

## 실행
    python -m lodestar_codegraph <source_root> -o out/codegraph.json

## 테스트
    pytest

산출물은 `out/`(gitignore). 스키마·설계: `docs/superpowers/specs/2026-07-07-e17-code-source-collector-design.md`.
```

- [ ] **Step 11: 전체 테스트 + fixture E2E 실행**

Run: `cd codegraph && python -m pytest -v`
Expected: 모든 테스트 PASS.

Run: `cd codegraph && python -m lodestar_codegraph tests/fixtures/sample -o out/sample.json`
Expected(stderr): `nodes=... edges=... communities=... skipped=0 external_calls=... -> out/sample.json`
Run: `python -c "import json; d=json.load(open('codegraph/out/sample.json')); print(d['meta'])"` — meta에 languages=["java","kotlin"] 확인.

- [ ] **Step 12: 커밋**

```bash
cd /Users/wonjaeho/Workspace/onto-studio
git add codegraph/src/lodestar_codegraph/cluster.py codegraph/src/lodestar_codegraph/emit.py \
        codegraph/src/lodestar_codegraph/__main__.py codegraph/README.md \
        codegraph/tests/test_cluster.py codegraph/tests/test_emit.py
git commit -m "feat(e17-4): Louvain 군집 + degree/god-node + codegraph.json emit + CLI 연결

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: vtm/api 실측 수집 (검증)

**Files:** 없음 (실행·검증만). 산출물은 gitignore.

- [ ] **Step 1: vtm/api 전체 수집 실행**

Run:
```bash
cd /Users/wonjaeho/Workspace/onto-studio/codegraph
python -m lodestar_codegraph \
  /Users/wonjaeho/Workspace/withnetworks/withVTM2.0/api \
  -o out/vtm-api.codegraph.json
```
Expected(stderr): `nodes=<큰수> edges=<큰수> communities=<N> skipped=<소수> external_calls=<큰수> -> out/vtm-api.codegraph.json`

- [ ] **Step 2: 산출물 sanity 체크**

Run:
```bash
python - <<'PY'
import json
d = json.load(open("out/vtm-api.codegraph.json"))
m = d["meta"]
print("meta:", {k: m[k] for k in ("languages","node_count","edge_count","community_count","skipped","external_calls")})
kinds = {}
for n in d["nodes"]: kinds[n["kind"]] = kinds.get(n["kind"],0)+1
print("node kinds:", kinds)
prov = {}
for e in d["edges"]: prov[e["provenance"]] = prov.get(e["provenance"],0)+1
print("edge provenance:", prov)
gods = [n["label"] for n in d["nodes"] if n["god_node"]][:10]
print("sample god-nodes:", gods)
PY
```
Expected: node kinds에 file/type/function 모두 존재, edge provenance에 EXTRACTED/INFERRED/AMBIGUOUS 분포, god-node 목록 출력. skipped가 전체의 소수(대부분 파싱 성공)인지 확인 — 과다하면 Kotlin 문법 매핑 재점검.

- [ ] **Step 3: 결과 요약 보고 (커밋 없음)**

사용자에게 meta·분포·god-node 요약 보고. (SQLite 적재는 후속 스코프 밖 — 여기서 멈춤.)

---

## Self-Review

**1. Spec coverage:**
- §2 D1(Python+tree-sitter)→전체, D2(codegraph/)→구조, D3(codegraph.json/-o)→emit+CLI, D4(E16정렬)→스키마, D5(3단계 노드)→extract, D6(provenance)→resolve, D7(Louvain/god)→cluster, D8(Java+Kotlin)→lang, D9(자기분석제외)→Global Constraints, D10(커밋안함)→.gitignore, D11(통합그래프)→resolve, D12(오버로드 id)→extract arity, D13(confidence공식)→resolve, D14(상한없음+meta)→__main__ meta. ✅
- §3 스키마 → emit build_and_write. §4 파이프라인 6단계 → Task 1-4 각 파일. §5 CLI → __main__. §6 테스트전략 → 각 test_*. §7 E16정렬 → 스코프밖(구현안함, 매핑표만). ✅
- §9 이슈분해 E17-1~4 → Task 1~4 매핑. Task 5는 스펙의 "vtm/api 테스트" 실측(§5 예시). ✅

**2. Placeholder scan:** 코드 스텝 모두 실제 코드 포함. `__main__.py` Task1은 의도적 스텁("TODO: 후속 태스크")이나 Task4 Step9에서 전체 교체로 해소 — 명시됨. 그 외 TBD/TODO 없음. ✅

**3. Type consistency:**
- `Edge(id, src, dst, kind, provenance, confidence, alternatives)` — 전 태스크 일관. emit에서 src→"from"/dst→"to" 직렬화 명시. ✅
- `extract_file(pf, edge_seq)` 반환 `ExtractResult(nodes, edges, type_index)` — Task2 정의, Task3/4에서 `.nodes/.edges` 사용 일관. ✅
- `function_index`, `_child_field_ident`, `_package_name`, `_descend` — extract.py 정의, resolve.py에서 import. Task3 Step4에서 import 명시. ✅
- `resolve_calls(parsed, nodes, edge_seq) -> (edges, external)`, `annotate(nodes, edges, god_percentile)`, `build_and_write(nodes, edges, meta_extra, out_path, prune_dangling)` — __main__ 연결부와 시그니처 일치. ✅

주의사항(구현자 참고): `_called_name`/`_enclosing_function_id`는 tree-sitter 노드구조 근사 해석이라, Task3 Step5에서 실패 시 실제 파싱트리를 출력해 노드타입을 재확인할 것(브레인스토밍에서 검증한 타입: java=method_invocation+name필드, kotlin=call_expression>navigation_expression). resolve.py의 func_spans 재수집은 O(functions×funcs_in_file)이라 대형파일서 느리면 dict 인덱스로 최적화(후속).
