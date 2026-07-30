#!/usr/bin/env python3
"""#88 L0 Source — 코드 트랙 프로브.

기능이 아니라 **계측기**다. 고정 revision(3c27259)의 `backend/src/main/kotlin` 을 입력으로 실제
수집기(`lodestar_codegraph`)를 돌려 I1 §4.1 의 L0 무조건 게이트 4종을 측정하고, 결과를 결정적
JSON 프로브 산출물로 남긴다. 보고서(Run Quality Report v0)는 이 산출물에서만 만든다.

    python3 docs/superpowers/specs/bench/l0/probe_code.py            # 측정 + build/l0/probe-code.json
    python3 docs/superpowers/specs/bench/l0/probe_code.py --check    # 커밋된 산출물과 대조

측정 규칙과 판정: docs/superpowers/specs/2026-07-30-m0-l0-source-validation.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
GOLD = REPO / "docs/superpowers/specs/gold"
RUN_DIR = HERE / "runs/run-l0-code-3c27259-001"
COMMITTED = RUN_DIR / "probe-code.json"
OUT = REPO / "build/l0/probe-code.json"

SCOPE_ROOT = "backend/src/main/kotlin"
CG_ROOT = REPO / "codegraph"

# 측정 규칙 (선언)
# M-CODE-1  입력 단위는 파일이다. 수집 범위 루트 아래의 모든 정규 파일이 분모이며,
#           확장자 필터로 걸러진 파일은 '사유와 함께 보고되어야 하는 제외' 다.
# M-CODE-2  결정성 = 3회 실행의 산출물 해시 중 최대 동일 그룹 크기 / 3.
# M-CODE-3  provenance 는 필수 5필드가 **소스 단위로** 산출물에서 조회 가능한지로 센다.
#           동등 식별자는 아래 별칭표로만 인정하고, 인정 근거를 함께 남긴다.
REQUIRED_PROVENANCE = ["projectId", "sourceId", "revision", "contentHash", "collectorVersion"]
PROVENANCE_ALIASES = {
    # 필수 필드 -> (산출물 키, 인정 사유, 고정된 값인가)
    "sourceId": ("nodes[].path", "노드마다 수집 범위 기준 상대경로가 있어 소스를 지목할 수 있다", False),
    "collectorVersion": ("meta.generated_by", "'lodestar-codegraph v1' — 수집기 이름과 세대만 있고 커밋·semver 가 없다", False),
}
# 마스킹 구현 탐지 패턴 (선언) — 하나라도 걸리면 '마스킹 단계 존재' 로 본다.
MASKING_PATTERNS = r"mask|redact|anonymi|pseudonymi|scrub|obfuscat"
MASKING_SEARCH_DIRS = ["backend/src/main", "codegraph/src", "frontend/src"]


def sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def sha256_file(p: pathlib.Path) -> str:
    return sha256_bytes(p.read_bytes())


def gold(name: str) -> dict:
    return json.loads((GOLD / name).read_text())


def run_collector(source_root: pathlib.Path, out_path: pathlib.Path, seed: str | None = None) -> dict:
    """실제 수집기를 서브프로세스로 돌린다 — 재구현하지 않고 산출물만 읽는다."""
    env = dict(os.environ, PYTHONPATH=str(CG_ROOT / "src"))
    if seed is not None:
        env["PYTHONHASHSEED"] = seed
    else:
        env.pop("PYTHONHASHSEED", None)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "lodestar_codegraph", str(source_root), "-o", str(out_path)],
        cwd=CG_ROOT, env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"수집기 실행 실패: {proc.stderr[-2000:]}")
    doc = json.loads(out_path.read_text())
    return doc


def canonical(doc: dict) -> bytes:
    """산출물의 정규화 표현 — meta.source_root(절대·상대 경로)만 제외한다. 실행 위치는 수집 결과가 아니다."""
    d = json.loads(json.dumps(doc))
    d["meta"].pop("source_root", None)
    return json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def strip_communities(doc: dict) -> bytes:
    d = json.loads(json.dumps(doc))
    d["meta"].pop("source_root", None)
    d["meta"].pop("community_count", None)
    for n in d["nodes"]:
        n.pop("community", None)
        n.pop("god_node", None)
    return json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def nondeterministic_paths(a: dict, b: dict) -> list[str]:
    """두 산출물이 어디서 갈라지는지 — 키 경로로만 남긴다."""
    paths = set()
    if a["meta"] != b["meta"]:
        for k in sorted(set(a["meta"]) | set(b["meta"])):
            if a["meta"].get(k) != b["meta"].get(k):
                paths.add(f"meta.{k}")
    if a["edges"] != b["edges"]:
        paths.add("edges[]")
    an = {n["id"]: n for n in a["nodes"]}
    bn = {n["id"]: n for n in b["nodes"]}
    if set(an) != set(bn):
        paths.add("nodes[].id")
    for i in set(an) & set(bn):
        for k in an[i]:
            if an[i][k] != bn[i].get(k):
                paths.add(f"nodes[].{k}")
    return sorted(paths)


def walk_all_files(root: pathlib.Path, ignore: list[str]) -> list[pathlib.Path]:
    """M-CODE-1 의 분모 — 수집기의 디렉토리 프루닝만 따르고 확장자 필터는 적용하지 않는다."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for fn in filenames:
            out.append(pathlib.Path(dirpath) / fn)
    return sorted(out)


def measure() -> dict:
    manifest = gold("manifest.json")
    work = pathlib.Path(tempfile.mkdtemp(prefix="l0-code-probe-"))
    try:
        return _measure(manifest, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _measure(manifest: dict, work: pathlib.Path) -> dict:
    scope = REPO / SCOPE_ROOT
    probe: dict = {
        "probeVersion": "l0-code-probe/v1",
        "layer": "L0",
        "track": "code",
        "projectId": "lodestar",
        "sourceRevision": manifest["sourceRevision"],
        "goldSetId": manifest["goldSetId"],
        "fixtureHash": manifest["fixtureHash"],
        "collector": {
            "impl": "lodestar_codegraph (walk → tree-sitter parse → extract → resolve → cluster → emit)",
            "declaredVersion": "lodestar-codegraph v1 (meta.generated_by) · pyproject 0.1.0",
            "citedVersion": "lodestar-codegraph@0.1.0+3c27259",
            "note": "산출물이 선언하는 것은 이름과 세대뿐이다 — 커밋·semver 가 없어 산출물만으로는 재현 대상을 특정할 수 없다",
        },
    }

    # 1) 입력 신원 — 고정 원본 해시 대조
    ignore = ["build", ".gradle", ".git", "node_modules"]
    all_files = walk_all_files(scope, ignore)
    hashes = {str(p.relative_to(REPO)): sha256_file(p) for p in all_files}
    pinned = {s["path"]: s for s in manifest["pinnedSources"]
              if s.get("origin") == "repo" and s["path"].startswith(SCOPE_ROOT)}
    mismatched = sorted(p for p, s in pinned.items()
                        if hashes.get(p) != s["contentHash"])
    probe["input"] = {
        "scopeRoot": SCOPE_ROOT,
        "fileCount": len(all_files),
        "pinnedComparedCount": len(pinned),
        "pinnedMismatched": mismatched,
        "allPinnedMatch": not mismatched,
        "scopeHash": sha256_bytes(
            "\n".join(f"{p} {h}" for p, h in sorted(hashes.items())).encode() + b"\n"),
    }

    # 2) 범위 인벤토리 — 수집기가 실제로 본 파일 대 범위 안의 전체 파일
    doc = run_collector(scope, work / "scope.json")
    walked, parsed = doc["meta"]["walked"], doc["meta"]["parsed"]
    collected_ext = {".kt", ".kts", ".java"}
    excluded = [str(p.relative_to(REPO)) for p in all_files if p.suffix not in collected_ext]
    probe["inventory"] = {
        "rule": "M-CODE-1",
        "input": len(all_files),
        "walked": walked,
        "parsed": parsed,
        "skippedByCollector": doc["meta"]["skipped"],
        "excludedByExtensionFilter": len(excluded),
        "exclusions": ([{
            "reason": "UNSUPPORTED_LANGUAGE: 확장자 필터가 .kt/.kts/.java 외 파일을 조용히 제외한다 (lang.py#lang_for_path)",
            "count": len(excluded),
            "examples": excluded,
        }] if excluded else []),
        "nodeCount": doc["meta"]["node_count"],
        "edgeCount": doc["meta"]["edge_count"],
        "externalCalls": doc["meta"]["external_calls"],
    }

    # 3) 결정성 — 기본 인터프리터 설정 3회 (M-CODE-2)
    runs = [run_collector(scope, work / f"det{i}.json") for i in range(3)]
    run_hashes = [sha256_bytes(canonical(d)) for d in runs]
    largest = max(run_hashes.count(h) for h in run_hashes)
    struct_hashes = {sha256_bytes(strip_communities(d)) for d in runs}
    diverge = sorted({p for i in range(1, 3) for p in nondeterministic_paths(runs[0], runs[i])})
    probe["determinismObserved"] = {
        "note": "기본 설정(해시 랜덤화 on) 3회 실행. 이 블록은 프로세스마다 값이 달라지므로 표류 검사 대상이 아니다.",
        "runs": 3,
        "distinctHashes": len(set(run_hashes)),
        "largestIdenticalGroup": largest,
        "rate": round(largest / 3, 4),
        "divergingPaths": diverge,
    }

    # 4) 결정성 근본 원인 — 시드 통제 실험 (표류 검사 대상: 시드를 고정하면 재현된다)
    seed0 = [sha256_bytes(canonical(run_collector(scope, work / f"s0_{i}.json", seed="0")))
             for i in range(2)]
    seed1 = sha256_bytes(canonical(run_collector(scope, work / "s1.json", seed="1")))
    probe["determinismRootCause"] = {
        "experiment": "PYTHONHASHSEED 를 고정한 실행 2회와 다른 시드 1회를 비교한다",
        "seed0Hashes": seed0,
        "seed0Identical": seed0[0] == seed0[1],
        "seed1Hash": seed1,
        "seedChangesArtifact": seed0[0] != seed1,
        "structuralHashStable": len(struct_hashes) == 1,
        "structuralHash": sorted(struct_hashes)[0],
        "cause": "cluster.annotate 가 `ids = {n.id for n in nodes}`(집합)을 그대로 "
                 "`g.add_nodes_from(ids)` 에 넘긴다(cluster.py#L8-L10). 문자열 해시 랜덤화로 집합 순회 순서가 "
                 "프로세스마다 달라지고, Louvain 은 노드 순서에 의존하므로 seed=42 를 고정해도 군집 배정이 갈린다.",
        "blastRadius": "노드의 community·god_node 가 흔들린다. 노드·엣지·좌표는 동일하다("
                       "structuralHashStable) — 즉 사실 자체가 아니라 사실에 붙는 군집 라벨이 재현되지 않는다.",
    }

    # 5) provenance — 필수 5필드가 산출물에서 소스 단위로 조회되는가 (M-CODE-3)
    meta_keys = sorted(doc["meta"].keys())
    node_keys = sorted(doc["nodes"][0].keys()) if doc["nodes"] else []
    present = []
    for f in REQUIRED_PROVENANCE:
        direct = [k for k in meta_keys + node_keys
                  if k.replace("_", "").lower() == f.lower()]
        if direct:
            present.append({"field": f, "via": direct[0], "basis": "직접 키", "pinned": True})
        elif f in PROVENANCE_ALIASES:
            key, basis, pinned = PROVENANCE_ALIASES[f]
            present.append({"field": f, "via": key, "basis": basis, "pinned": pinned})
    probe["provenance"] = {
        "probe": "산출물(codegraph.json)의 meta·nodes 키 집합",
        "metaKeys": meta_keys,
        "nodeKeys": node_keys,
        "required": REQUIRED_PROVENANCE,
        "present": present,
        "absent": [f for f in REQUIRED_PROVENANCE if f not in {p["field"] for p in present}],
        "rate": round(len(present) / len(REQUIRED_PROVENANCE), 4),
    }

    # 6) 실패·제외 보고 채널
    probe["reporting"] = {
        "probe": "산출물에 실패·제외를 사유와 함께 실을 자리가 있는가",
        "aggregateKeys": [k for k in meta_keys if k in ("skipped", "external_calls")],
        "perItemReasons": False,
        "note": "meta.skipped 는 건수만 있고 대상·사유가 없다. 확장자 필터로 제외된 파일은 walked 에도 "
                "들어가지 않아 산출물에서 흔적이 사라진다 — 'not_collected' 와 'absent' 가 L0 에서 이미 뭉개진다.",
    }

    # 7) 실패 재현 픽스처 (I2 gold failures.json 의 코드 3건)
    fixtures = []
    for f in gold("failures.json")["fixtures"]:
        path = f["path"]
        if path.endswith(".sql"):
            continue
        src = REPO / path
        d = work / ("fx-" + pathlib.Path(path).stem)
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, d / pathlib.Path(path).name)
        out = run_collector(d, work / f"{d.name}.json")
        # FILE 노드와 심볼 노드를 나눠 적는다 — FILE 노드의 존재가 곧 '이 파일을 성공으로 표시했다' 다.
        labels = sorted({f"{n['kind']}:{n['qualified_name']}" for n in out["nodes"]})
        expected = sorted({e.get("fqn") or f"{e.get('owner','')}.{e.get('name','')}"
                           for e in f["extracted"]})
        fixtures.append({
            "id": f["id"],
            "kind": f["kind"],
            "path": path,
            "contentHash": sha256_file(src),
            "hashMatchesPinned": sha256_file(src) == f["contentHash"],
            "walked": out["meta"]["walked"],
            "parsed": out["meta"]["parsed"],
            "skipped": out["meta"]["skipped"],
            "expectedExtracted": expected,
            "actualExtracted": labels,
            "expectedReported": len(f["reported"]),
            "actualReported": 0,
            "markedAsFullySucceeded": out["meta"]["parsed"] == out["meta"]["walked"] and out["meta"]["walked"] > 0,
            "silentSkipIsFailure": f["silentSkipIsFailure"],
            "verdict": "UNREPORTED" if f["reported"] else "OK",
        })
    probe["failureFixtures"] = fixtures

    # 8) PII·시크릿 — 코퍼스를 수집 범위에 두면 산출물 표면에 원문이 남는가
    pii = gold("pii.json")
    pdir = work / "pii"
    pdir.mkdir(parents=True, exist_ok=True)
    for f in pii["scope"]["files"]:
        shutil.copy(REPO / f["path"], pdir / pathlib.Path(f["path"]).name)
    pout = run_collector(pdir, work / "pii.json")
    artifact_text = json.dumps(pout, ensure_ascii=False)
    positives = [i for i in pii["items"] if i["expect"] == "MASKED"]
    unmasked = [i["id"] for i in positives if i["value"]["text"] in artifact_text]
    probe["pii"] = {
        "corpusFiles": [f["sourceId"] for f in pii["scope"]["files"]],
        "positives": len(positives),
        "masked": 0,
        "unmaskedInArtifact": unmasked,
        "notCollected": [i["id"] for i in positives if i["id"] not in unmasked],
        "walked": pout["meta"]["walked"],
        "goldGap": "gold v0 의 양성 44건은 전부 .sql/.properties/.log 에 있다 — 코드 수집기가 "
                   "실제로 읽는 확장자(.kt/.java) 안에 양성이 없어, 수집된 표면에서의 마스킹 동작은 "
                   "이 gold 로 측정할 수 없다. 픽스처를 여기서 만들지 않고 I2 개정 안건으로 남긴다.",
    }

    # 9) 마스킹 구현 존재 여부
    hits = []
    for d in MASKING_SEARCH_DIRS:
        base = REPO / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in {".kt", ".py", ".ts", ".vue", ".java"}:
                for m in re.finditer(MASKING_PATTERNS, p.read_text(errors="ignore"), re.I):
                    hits.append(f"{p.relative_to(REPO)}:{m.group(0)}")
    probe["maskingCapability"] = {
        "searchDirs": MASKING_SEARCH_DIRS,
        "pattern": MASKING_PATTERNS,
        "hits": sorted(set(hits)),
        "exists": bool(hits),
    }

    # 10) read-only 확인
    after = {str(p.relative_to(REPO)): sha256_file(p) for p in walk_all_files(scope, ignore)}
    probe["readOnly"] = {
        "filesCompared": len(after),
        "unchanged": after == hashes,
        "changed": sorted(p for p in set(hashes) | set(after) if hashes.get(p) != after.get(p)),
    }
    return probe


VOLATILE = ("determinismObserved",)


def stable(probe: dict) -> dict:
    return {k: v for k, v in probe.items() if k not in VOLATILE}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="커밋된 프로브 산출물의 표류 검사(변동 블록 제외)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    probe = measure()
    text = json.dumps(probe, ensure_ascii=False, indent=2) + "\n"
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"[probe] {out}")

    obs = probe["determinismObserved"]
    print(f"[probe] determinism(observed) rate={obs['rate']} distinct={obs['distinctHashes']} "
          f"diverging={obs['divergingPaths']}")

    if args.check:
        if not COMMITTED.exists():
            print(f"[FAIL] 커밋된 산출물이 없다: {COMMITTED}")
            return 1
        want = stable(json.loads(COMMITTED.read_text()))
        got = stable(probe)
        if want != got:
            diff = [k for k in sorted(set(want) | set(got)) if want.get(k) != got.get(k)]
            print(f"[FAIL] 프로브 산출물 표류 — 블록: {diff}")
            return 1
        rc = probe["determinismRootCause"]
        if not (rc["seed0Identical"] and rc["seedChangesArtifact"]):
            print("[FAIL] 결정성 근본 원인 실험이 재현되지 않았다 — 수집기가 바뀌었으면 새 runId 로 재측정한다")
            return 1
        print("[ok] 프로브 산출물 일치 + 근본 원인 재현")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
