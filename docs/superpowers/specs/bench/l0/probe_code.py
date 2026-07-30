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
import tomllib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
GOLD = REPO / "docs/superpowers/specs/gold"
RUN_DIR = HERE / "runs/run-l0-code-3c27259-002"
COMMITTED = RUN_DIR / "probe-code.json"
OUT = REPO / "build/l0/probe-code.json"

SCOPE_ROOT = "backend/src/main/kotlin"
CG_ROOT = REPO / "codegraph"


def collector_version() -> str:
    """수집기 버전은 손으로 적지 않는다 — pyproject 에서 읽는다. 손으로 옮긴 버전은 올려도 티가 나지 않는다."""
    return tomllib.loads((CG_ROOT / "pyproject.toml").read_text())["project"]["version"]


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


def blob_tree(revision: str, prefix: str) -> dict[str, str]:
    """고정 revision 의 `prefix` 아래 파일 전부의 blob 해시. 작업 트리가 아니라 revision 이 정본이다."""
    listing = subprocess.run(["git", "ls-tree", "-r", "--format=%(path)", revision, prefix],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout
    out = {}
    for path in filter(None, (l.strip() for l in listing.split("\n"))):
        content = subprocess.run(["git", "show", f"{revision}:{path}"],
                                 cwd=REPO, capture_output=True, check=True).stdout
        out[path] = sha256_bytes(content)
    return out


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
            "declaredVersion": f"lodestar-codegraph v1 (meta.generated_by) · pyproject {collector_version()}",
            "citedVersion": f"lodestar-codegraph@{collector_version()}",
            "note": "산출물이 선언하는 것은 이름과 세대뿐이다 — 커밋·semver 가 없어 산출물만으로는 재현 대상을 특정할 수 없다. "
                    "입력 revision(3c27259)과 달리 수집기는 #112 의 결정성 수정이 들어간 0.1.1 이다 — 입력 신원과 수집기 버전은 다른 축이다.",
        },
    }

    # 1) 입력 신원 — gold 고정 해시 대조 + **고정 revision blob 전수 대조**
    #    gold 가 고정한 것은 범위 59파일 중 7건뿐이다. 나머지 52건이 무검증으로 남으면
    #    "고정 revision 을 쟀다" 는 주장이 성립하지 않으므로, 전 파일을 blob 과 직접 대조한다.
    ignore = ["build", ".gradle", ".git", "node_modules"]
    all_files = walk_all_files(scope, ignore)
    hashes = {str(p.relative_to(REPO)): sha256_file(p) for p in all_files}
    pinned = {s["path"]: s for s in manifest["pinnedSources"]
              if s.get("origin") == "repo" and s["path"].startswith(SCOPE_ROOT)}
    mismatched = sorted(p for p, s in pinned.items()
                        if hashes.get(p) != s["contentHash"])
    rev = manifest["sourceRevision"]
    rev_files = {p: h for p, h in blob_tree(rev, SCOPE_ROOT).items()}
    rev_mismatched = sorted(p for p in set(hashes) | set(rev_files)
                            if hashes.get(p) != rev_files.get(p))
    probe["input"] = {
        "scopeRoot": SCOPE_ROOT,
        "fileCount": len(all_files),
        "pinnedComparedCount": len(pinned),
        "pinnedMismatched": mismatched,
        "allPinnedMatch": not mismatched,
        "revisionFileCount": len(rev_files),
        "revisionMismatched": rev_mismatched,
        "allFilesMatchRevision": not rev_mismatched,
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
    # 커버리지 state 의 결정성(EVL §7.1)은 **산출물 결정성과 다른 것**이다 — 3회 실행에서 code 클래스의
    # state 가 같았는가만 본다. 하드코딩하지 않고 여기서 재서 보고서에 넘긴다.
    code_states = ["present" if d["meta"]["walked"] > 0 else "not_collected" for d in runs]
    probe["coverageState"] = {
        "note": "산출물 해시 결정성이 아니라 '봤는가/있었는가' state 의 3회 안정성이다(EVL §7.1)",
        "codeStateRuns": code_states,
        "codeState": code_states[0],
        "codeStateStable": len(set(code_states)) == 1,
    }

    probe["determinismObserved"] = {
        "note": "기본 설정(해시 랜덤화 on) 3회 실행. #112 수정 이후 이 블록은 프로세스마다 같아야 하며 "
                "표류 검사 대상이다 — 값이 흔들리면 그 자체가 회귀다.",
        "runs": 3,
        "distinctHashes": len(set(run_hashes)),
        "largestIdenticalGroup": largest,
        "rate": round(largest / 3, 4),
        "divergingPaths": diverge,
    }

    # 4) 시드 독립성 통제 실험 — 같은 시드 2회와 다른 시드 1회가 **모두** 같아야 한다.
    #    (#88 에서는 같은 시드끼리만 같고 시드를 바꾸면 갈렸다 — 그 갈림이 H1 의 근거였다.)
    seed0 = [sha256_bytes(canonical(run_collector(scope, work / f"s0_{i}.json", seed="0")))
             for i in range(2)]
    seed1 = sha256_bytes(canonical(run_collector(scope, work / "s1.json", seed="1")))
    probe["determinismControl"] = {
        "experiment": "PYTHONHASHSEED 를 고정한 실행 2회와 다른 시드 1회를 비교한다",
        "seed0Hashes": seed0,
        "seed0Identical": seed0[0] == seed0[1],
        "seed1Hash": seed1,
        "seedChangesArtifact": seed0[0] != seed1,
        "seedIndependent": seed0[0] == seed0[1] == seed1,
        "structuralHashStable": len(struct_hashes) == 1,
        "structuralHash": sorted(struct_hashes)[0],
        "fix": "cluster.annotate 가 노드·엣지를 정렬해서 그래프에 넣고(`g.add_nodes_from(sorted(ids))`) "
               "군집 라벨을 멤버 정렬로 정규화한다(#112). 이전에는 집합을 그대로 넘겨 문자열 해시 랜덤화가 "
               "노드 순서를, 노드 순서가 Louvain 의 군집 배정을 바꿨다.",
        "scope": "산출물 전체(canonical)가 시드에 무관하게 동일하다. 군집 라벨을 뺀 구조 해시도 "
                 "여전히 안정적이다(structuralHashStable) — 사실과 라벨이 함께 재현된다.",
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
        "goldGap": "gold v0 의 양성 28건(전체 항목 44건 = 양성 28 + 음성 16)은 전부 "
                   ".sql/.properties/.log 에 있다 — 코드 수집기가 "
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


# #88 에서는 `determinismObserved` 가 프로세스마다 달라져 표류 검사에서 뺐다. #112 로 그 원인이
# 사라졌으므로 예외를 없앤다 — 결정성이 다시 흔들리면 표류로 걸려야 한다.
VOLATILE: tuple[str, ...] = ()


def stable(probe: dict) -> dict:
    return {k: v for k, v in probe.items() if k not in VOLATILE}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="커밋된 프로브 산출물의 표류 검사(변동 블록 제외)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    out = pathlib.Path(args.out).resolve()
    if args.check:
        # 기준 증거를 **먼저** 읽는다. 쓰고 나서 비교하면 --out 을 기준 파일로 지정해
        # 표류한 결과로 기준을 갱신한 뒤 자기 자신과 비교하는 거짓 통과가 가능하다.
        if out == COMMITTED.resolve():
            print(f"[FAIL] --check 는 기준 파일에 쓸 수 없다: {out}")
            return 1
        if not COMMITTED.exists():
            print(f"[FAIL] 커밋된 산출물이 없다: {COMMITTED}")
            return 1
        baseline = stable(json.loads(COMMITTED.read_text()))

    probe = measure()
    text = json.dumps(probe, ensure_ascii=False, indent=2) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"[probe] {out}")

    obs = probe["determinismObserved"]
    print(f"[probe] determinism(observed) rate={obs['rate']} distinct={obs['distinctHashes']} "
          f"diverging={obs['divergingPaths']}")

    if args.check:
        want, got = baseline, stable(probe)
        if want != got:
            diff = [k for k in sorted(set(want) | set(got)) if want.get(k) != got.get(k)]
            print(f"[FAIL] 프로브 산출물 표류 — 블록: {diff}")
            return 1
        obs_rate = probe["determinismObserved"]["rate"]
        if obs_rate < 1.0:
            print(f"[FAIL] 결정성 {obs_rate} — 동일 입력 3회 실행이 갈렸다: "
                  f"{probe['determinismObserved']['divergingPaths']}")
            return 1
        ctrl = probe["determinismControl"]
        if not ctrl["seedIndependent"]:
            print("[FAIL] PYTHONHASHSEED 를 바꾸면 산출물이 달라진다 — 재현 보장이 없다")
            return 1
        print("[ok] 프로브 산출물 일치 + 결정성 1.0 (시드 무관)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
