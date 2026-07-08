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
