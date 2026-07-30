"""#112 회귀 — 군집 라벨이 해시 시드에 좌우되면 안 된다.

같은 프로세스 안에서는 집합 순회 순서가 고정이라 비결정이 드러나지 않는다. 그래서 이 테스트는
**PYTHONHASHSEED 를 바꾼 별도 프로세스**로 재기만 한다 — 실측 프로브(#88 `probe_code.py`)가
BLOCKED(H1) 판정의 근거로 쓴 것과 같은 방식이다.

입력은 군집 경계가 애매한 모양이어야 한다. 정답이 하나뿐인 작은 그래프는 순서를 바꿔도 같은
답이 나와서, 회귀가 살아 있어도 테스트가 통과한다.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

SRC = str(pathlib.Path(__file__).resolve().parents[1] / "src")
SEEDS = ["0", "1", "12345", "random"]

CLUSTER_SCRIPT = """
import json, sys
from lodestar_codegraph.model import Node, Edge, EXTRACTED
from lodestar_codegraph.cluster import annotate

N = 40
names = [f"type:N{i:02d}" for i in range(N)]
nodes = [Node(id=x, kind="type", label=x, qualified_name=x, path="p", lang="kotlin")
         for x in names]
edges, eid = [], 0
for i in range(N):
    for step in (1, 2, 7, 13):
        j = (i * 3 + step) % N
        if i != j:
            eid += 1
            edges.append(Edge(eid, names[i], names[j], "calls", EXTRACTED, 1.0))

annotate(nodes, edges, god_percentile=99.0)
json.dump({x.id: [x.community, x.degree, x.god_node] for x in nodes}, sys.stdout, sort_keys=True)
"""


def _write_kotlin_fixture(root: pathlib.Path, n: int = 24, per_file: int = 6) -> None:
    """서로를 얽어 부르는 클래스 n개 — 군집 경계가 애매한 호출 그래프를 만든다."""
    root.mkdir(parents=True, exist_ok=True)
    for f in range(n // per_file):
        lines = [f"package demo.p{f}", ""]
        for k in range(per_file):
            i = f * per_file + k
            targets = [t for t in ((i * 3 + s) % n for s in (1, 2, 7, 13)) if t != i]
            calls = " + ".join(f"N{t:02d}().f{t:02d}()" for t in targets)
            lines += [f"class N{i:02d} {{", f"    fun f{i:02d}(): Int = {calls}", "}", ""]
        (root / f"F{f}.kt").write_text("\n".join(lines))


def _env(seed: str) -> dict:
    env = dict(os.environ, PYTHONPATH=SRC)
    if seed == "random":
        env.pop("PYTHONHASHSEED", None)  # 기본 설정 = 해시 랜덤화 on
    else:
        env["PYTHONHASHSEED"] = seed
    return env


def test_cluster_labels_are_hash_seed_independent():
    outs = []
    for seed in SEEDS:
        p = subprocess.run([sys.executable, "-c", CLUSTER_SCRIPT],
                           env=_env(seed), capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        outs.append(p.stdout)
    assert len(set(outs)) == 1, (
        "군집 라벨이 PYTHONHASHSEED 에 따라 달라진다 — 집합 순회 순서 의존이 남아 있다:\n"
        + "\n".join(f"  seed={s}: {o[:200]}" for s, o in zip(SEEDS, outs))
    )
    # 라벨은 0..k-1 로 정규화돼 있어야 한다 — 구멍이 있으면 라벨이 순서의 흔적을 남긴 것이다.
    comm = {v[0] for v in json.loads(outs[0]).values()}
    assert comm == set(range(len(comm)))


def test_cluster_labels_ignore_input_order():
    """같은 그래프라면 노드·엣지를 어떤 순서로 넘겨도 같은 라벨이 나온다."""
    from lodestar_codegraph.cluster import annotate
    from lodestar_codegraph.model import Node, Edge, EXTRACTED

    n = 30
    names = [f"type:N{i:02d}" for i in range(n)]
    edges = []
    eid = 0
    for i in range(n):
        for step in (1, 2, 7):
            j = (i * 3 + step) % n
            if i != j:
                eid += 1
                edges.append(Edge(eid, names[i], names[j], "calls", EXTRACTED, 1.0))

    def run(order_names, order_edges):
        nodes = [Node(id=x, kind="type", label=x, qualified_name=x, path="p", lang="kotlin")
                 for x in order_names]
        annotate(nodes, order_edges, god_percentile=99.0)
        return {x.id: (x.community, x.degree, x.god_node) for x in nodes}

    assert run(names, edges) == run(list(reversed(names)), list(reversed(edges)))


def test_codegraph_json_is_byte_identical_across_hash_seeds(tmp_path):
    src = tmp_path / "src"
    _write_kotlin_fixture(src)

    blobs = []
    for i, seed in enumerate(SEEDS):
        out = tmp_path / f"cg{i}.json"
        p = subprocess.run(
            [sys.executable, "-m", "lodestar_codegraph", str(src), "-o", str(out)],
            env=_env(seed), capture_output=True, text=True,
        )
        assert p.returncode == 0, p.stderr
        blobs.append(out.read_bytes())

    assert len(set(blobs)) == 1, (
        "동일 입력의 codegraph.json 이 PYTHONHASHSEED 에 따라 달라진다 (결정성 게이트 위반)"
    )
    doc = json.loads(blobs[0])
    assert doc["meta"]["node_count"] > 0 and doc["meta"]["community_count"] > 1
