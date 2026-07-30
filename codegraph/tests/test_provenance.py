"""#113 L0-fix — 수집 식별 메타데이터 계약 v0 (CODE 트랙).

계약: docs/superpowers/specs/2026-07-30-m0-l0-collection-metadata-contract.md

#88 프로브가 센 것과 같은 방식으로 단언한다 — `codegraph.json` 의 `meta`·`nodes` 키에서
다섯 필드가 **소스 단위로** 조회되는가(M-CODE-3).
"""
import json
import re
import subprocess

import pytest

from lodestar_codegraph import provenance as prov
from lodestar_codegraph.__main__ import main

REQUIRED = ["projectId", "sourceId", "revision", "contentHash", "collectorVersion"]
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REV_RE = re.compile(r"^(?:[0-9a-f]{7,40}|(?:inline|bundle|live|dirty|nogit):[0-9a-f]{12})$")
VER_RE = re.compile(r"^[a-z0-9][a-z0-9-]*@\d+\.\d+\.\d+(?:\+[0-9a-f]{7,40})?$")


def write_scope(tmp_path, **files):
    root = tmp_path / "src"
    root.mkdir()
    for name, body in files.items():
        (root / name).write_text(body, encoding="utf-8")
    return root


def run(root, out):
    assert main([str(root), "-o", str(out)]) == 0
    return json.loads(out.read_text())


def test_collector_version_carries_name_and_semver():
    assert VER_RE.match(prov.collector_version()), prov.collector_version()
    assert prov.collector_version().startswith("lodestar-codegraph@")


def test_scope_hash_follows_content(tmp_path):
    root = write_scope(tmp_path, **{"A.kt": "class A\n"})
    before = prov.scope_hash(str(root), [str(root / "A.kt")])
    assert HASH_RE.match(before)
    (root / "A.kt").write_text("class A { }\n", encoding="utf-8")
    assert prov.scope_hash(str(root), [str(root / "A.kt")]) != before
    # 경로가 늘어도 바뀐다 — 내용만 이으면 파일 추가/이동이 묻힌다.
    (root / "B.kt").write_text("class A { }\n", encoding="utf-8")
    assert prov.scope_hash(str(root), [str(root / "A.kt"), str(root / "B.kt")]) != before


def test_revision_outside_git_is_marked_not_a_commit(tmp_path):
    root = write_scope(tmp_path, **{"A.kt": "class A\n"})
    rev = prov.detect_revision(str(root), prov.scope_hash(str(root), [str(root / "A.kt")]))
    assert rev.startswith("nogit:"), rev
    assert REV_RE.match(rev)


def test_revision_in_clean_git_repo_is_the_commit(tmp_path):
    root = write_scope(tmp_path, **{"A.kt": "class A\n"})
    git = ["git", "-C", str(tmp_path)]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["config", "user.email", "t@t"], check=True)
    subprocess.run(git + ["config", "user.name", "t"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-qm", "x"], check=True)
    head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()

    scope = prov.scope_hash(str(root), [str(root / "A.kt")])
    assert prov.detect_revision(str(root), scope) == head

    # 워킹트리가 더러우면 HEAD 로 재현되지 않는다 — 커밋인 척하지 않는다.
    (root / "A.kt").write_text("class A { }\n", encoding="utf-8")
    dirty = prov.detect_revision(str(root), prov.scope_hash(str(root), [str(root / "A.kt")]))
    assert dirty.startswith("dirty:"), dirty


@pytest.mark.parametrize("bad", ["", " ", "unknown", "N/A", "null", "none", "todo", "-"])
def test_placeholder_project_id_is_rejected(bad):
    with pytest.raises(ValueError):
        prov.build_metadata(project_id=bad, source_root=".", file_hashes={})


def test_artifact_carries_all_five_fields_per_source(tmp_path):
    root = write_scope(tmp_path, **{
        "A.kt": "package p\nclass A { fun f() {} }\n",
        "B.kt": "package p\nclass B { fun g() { A().f() } }\n",
    })
    doc = run(root, tmp_path / "cg.json")

    meta = doc["meta"]
    assert meta["project_id"] == "lodestar"
    assert meta["source_id"] == f"code:{root}"
    assert HASH_RE.match(meta["content_hash"])
    assert REV_RE.match(meta["revision"])
    assert VER_RE.match(meta["collector_version"])

    # 소스 단위 — 노드마다 어느 파일에서 왔고 그 파일이 무엇이었는지가 닫혀야 한다.
    assert doc["nodes"], "노드가 없으면 소스 단위 조회를 측정할 수 없다"
    per_file = {}
    for n in doc["nodes"]:
        assert n["source_id"] in {"A.kt", "B.kt"}, n
        assert HASH_RE.match(n["content_hash"]), n
        per_file.setdefault(n["source_id"], set()).add(n["content_hash"])
    assert {"A.kt", "B.kt"} == set(per_file)
    assert all(len(v) == 1 for v in per_file.values()), f"같은 파일의 노드가 다른 해시를 갖는다: {per_file}"
    assert per_file["A.kt"] != per_file["B.kt"]

    # #88 프로브의 완전성 산식과 같은 계산 — 직접 키로만 5/5 여야 한다.
    keys = {k.replace("_", "").lower() for k in list(meta) + list(doc["nodes"][0])}
    assert all(f.lower() in keys for f in REQUIRED), sorted(keys)


def test_metadata_does_not_break_determinism(tmp_path):
    root = write_scope(tmp_path, **{"A.kt": "package p\nclass A { fun f() {} }\n"})
    a = run(root, tmp_path / "a.json")
    b = run(root, tmp_path / "b.json")
    for d in (a, b):
        d["meta"].pop("source_root")
        d["meta"].pop("source_id")  # 절대경로를 담는다 — 실행 위치는 수집 결과가 아니다
    assert a == b


def test_content_hash_changes_when_a_source_changes(tmp_path):
    root = write_scope(tmp_path, **{"A.kt": "package p\nclass A\n"})
    first = run(root, tmp_path / "a.json")["meta"]["content_hash"]
    (root / "A.kt").write_text("package p\nclass A { fun f() {} }\n", encoding="utf-8")
    assert run(root, tmp_path / "b.json")["meta"]["content_hash"] != first


def test_project_id_and_revision_are_overridable(tmp_path):
    root = write_scope(tmp_path, **{"A.kt": "package p\nclass A\n"})
    out = tmp_path / "cg.json"
    assert main([str(root), "-o", str(out), "--project-id", "acme",
                 "--revision", "a" * 40]) == 0
    meta = json.loads(out.read_text())["meta"]
    assert meta["project_id"] == "acme"
    assert meta["revision"] == "a" * 40


def test_bogus_revision_override_is_rejected(tmp_path):
    root = write_scope(tmp_path, **{"A.kt": "class A\n"})
    with pytest.raises(ValueError):
        main([str(root), "-o", str(tmp_path / "cg.json"), "--revision", "HEAD"])
