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
