#!/usr/bin/env python3
"""#125 L0 Source — 코드 트랙 프로브 **v3** (gold 입력 축 재고정 후 재측정).

기능이 아니라 **계측기**다. gold 가 고정한 **입력 축**(`probeAxis.revision`)의 `backend/src/main/kotlin` 을 입력으로 실제
수집기(`lodestar_codegraph`)를 돌려 I1 §4.1 의 L0 무조건 게이트 4종을 측정하고, 결과를 결정적
JSON 프로브 산출물로 남긴다. 보고서(Run Quality Report v0)는 이 산출물에서만 만든다.

    python3 docs/superpowers/specs/bench/l0/probe_code.py            # 측정 + build/l0/probe-code.json
    python3 docs/superpowers/specs/bench/l0/probe_code.py --check    # 커밋된 산출물과 대조

**이전 실행과의 차이**: run-003(#114)까지는 입력을 gold 의 **정답 축**(3c27259)에서 재구성했다. 그런데
L0-fix(#113·#114·#115)가 그 입력 디렉토리 자체를 고치므로, 정답 축에 머무는 한 이 프로브는 **현재
수집기의 측정을 남길 자리가 없었다**(`--check` 가 상시 실패). #125 로 gold 에 L0 수집 입력 축이 생겨
입력을 aad4382 로 다시 고정했고, 이 실행은 그 축의 첫 측정이다. 정답 축은 3c27259 에 승인된 채로
남는다 — 두 축을 함께 옮기면 `l1/code.json` 의 닫힌 범위가 무너진다(I2 §6).

입력 축은 아직 **승인되지 않았다**(PROPOSED). 그래서 이 실행의 보고서는 `eligibleAsBaseline=false`
로 남고, 지난 실행은 덮어쓰지 않고 `baseline.previous` 로 인용만 한다(I3 §5.5).

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
RUN_DIR = HERE / "runs/run-l0-code-aad4382-001"
COMMITTED = RUN_DIR / "probe-code.json"
OUT = REPO / "build/l0/probe-code.json"

CG_ROOT = REPO / "codegraph"


def collector_version() -> str:
    """수집기 버전은 손으로 적지 않는다 — pyproject 에서 읽는다. 손으로 옮긴 버전은 올려도 티가 나지 않는다."""
    return tomllib.loads((CG_ROOT / "pyproject.toml").read_text())["project"]["version"]


def collector_dependencies() -> dict:
    """런타임 의존성의 **고정 선언**을 수집기 자신에게서 읽는다(#123).

    여기서 다시 파싱하지 않고 수집기 모듈(`lodestar_codegraph.deps`)을 **수집 실행과 같은
    인터프리터**로 돌려 읽는다. 프로브가 따로 파싱하면 수집기가 보는 선언과 프로브가 적는 선언이
    갈릴 수 있고, 그때 이 블록은 산출물과 무관한 사실을 증거처럼 싣는다.

    블록의 값은 선언에서만 나오므로 환경이 선언과 같은 한 실행마다 동일하다 — `--check` 의 바이트
    대조와 충돌하지 않는다. 어긋난 환경에서는 `installedMatchesDeclared` 가 뒤집혀 표류로 걸린다.
    """
    env = dict(os.environ, PYTHONPATH=str(CG_ROOT / "src"))
    proc = subprocess.run([sys.executable, "-m", "lodestar_codegraph.deps"],
                          cwd=CG_ROOT, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"런타임 의존성 선언을 읽지 못했다: {proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


# 측정 규칙 (선언)
# M-CODE-1  입력 단위는 파일이다. 수집 범위 루트 아래의 모든 정규 파일이 분모이며,
#           확장자 필터로 걸러진 파일은 '사유와 함께 보고되어야 하는 제외' 다.
# M-CODE-2  결정성 = 3회 실행의 산출물 해시 중 최대 동일 그룹 크기 / 3.
# M-CODE-3  provenance 는 필수 5필드가 **소스 단위로** 산출물에서 조회 가능한지로 센다.
#           동등 식별자는 아래 별칭표로만 인정하고, 인정 근거를 함께 남긴다.
# M-CODE-4  보고(REPORTED) = 산출물에 사유(빈 문자열 아님)·좌표·대상이 함께 실린 것.
#           gold 기대 항목과의 대조는 (사유코드 일치 ∧ 좌표 행범위 겹침) 으로 귀속한다 —
#           건수만 맞추거나 그럴듯한 좌표를 적어 통과하는 경로를 막는다.
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


def scope_root(manifest: dict | None = None, track: str = "code") -> str:
    """수집 범위 루트는 **gold 가 정한다**(`probeAxis.scopeRoots`).

    여기 상수로 두면 gold 의 범위 선언과 프로브가 실제로 읽는 범위가 갈릴 수 있고, 그때 G5.10 은
    gold 안에서만 정합해 통과한다 — 두 곳이 같은 값을 우연히 들고 있는 동안에는 아무도 모른다.
    범위는 입력 신원의 일부이므로 고정된 쪽에서 읽어 오는 것이 맞다.
    """
    m = manifest if manifest is not None else gold("manifest.json")
    for r in m["probeAxis"]["scopeRoots"]:
        if r["track"] == track:
            return r["root"]
    raise KeyError(f"gold probeAxis.scopeRoots 에 track={track} 이 없다")


SCOPE_ROOT = scope_root()


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


def materialize(revision: str, prefix: str, dest: pathlib.Path) -> dict[str, str]:
    """고정 revision 의 `prefix` 아래 파일 전부를 `dest` 에 풀어놓고 {repo상대경로: 해시} 를 돌려준다.

    작업 트리를 입력으로 삼으면 수집기를 고치는 순간 '고정 revision 을 쟀다' 가 거짓이 된다.
    입력 신원을 revision 에 두면 수정 전후 실행이 같은 입력으로 비교된다.
    """
    listing = subprocess.run(["git", "ls-tree", "-r", "--format=%(path)", revision, prefix],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout
    out = {}
    for path in sorted(filter(None, (l.strip() for l in listing.split("\n")))):
        content = subprocess.run(["git", "show", f"{revision}:{path}"],
                                 cwd=REPO, capture_output=True, check=True).stdout
        target = dest / pathlib.Path(path).relative_to(prefix)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        out[path] = sha256_bytes(content)
    return out


COLLECTED_EXT = {".kt", ".kts", ".java"}


def classify_scope(rels: list[str], doc: dict, scope_root: str = SCOPE_ROOT) -> dict:
    """수집 범위의 파일을 **프로브의 규칙으로** 나눈다 — 수집기 신고로 나누면 자기 인증이다.

    - `factFiles`  사실을 낸 파일(파일 노드 status 가 parsed·partial)
    - `readable`   확장자상 수집기가 읽을 수 있었던 파일(M-CODE-1)
    - `notCollected` 읽을 수 없어 수집되지 않은 파일 → 제외 보고의 분모
    - `failedFiles`  읽을 수 있었는데 사실을 못 낸 파일 → 실패 사례의 분모
      (status=failed 도, 트리가 아예 서지 않아 노드조차 없는 파일도 여기 들어온다)

    status 는 수집기가 스스로 붙인 표시라 '사실을 냈는가' 판정에만 쓰고, 분모는 프로브가 정한다.
    """
    fact_files = {n["path"] for n in doc["nodes"]
                  if n["kind"] == "file" and n.get("status") in ("parsed", "partial")}
    readable = [r for r in rels if pathlib.PurePosixPath(r).suffix in COLLECTED_EXT]
    under = lambda r: str(pathlib.PurePosixPath(r).relative_to(scope_root))  # noqa: E731
    return {
        "factFiles": sorted(fact_files),
        "readable": sorted(readable),
        "notCollected": sorted(r for r in rels if r not in readable),
        "failedFiles": sorted(under(r) for r in readable if under(r) not in fact_files),
    }


def line_range(locator: str) -> tuple[int, int] | None:
    m = re.search(r"#L(\d+)(?:-L(\d+))?", locator)
    if not m:
        return None
    start = int(m.group(1))
    return start, int(m.group(2) or start)


def attribute(gold_reported: list[dict], issues: list[dict]) -> dict:
    """gold 기대 보고 항목 ↔ 산출물이 실제로 낸 항목의 귀속(M-CODE-4)."""
    used: set[int] = set()
    expected = []
    for g in gold_reported:
        want = line_range(g["locator"]) or (0, 0)
        hit = None
        for idx, i in enumerate(issues):
            if idx in used or i["reason_code"] != g["kind"] or not i["reason"]:
                continue
            got = line_range(i["locator"])
            if got and got[0] <= want[1] and want[0] <= got[1]:
                hit = idx
                break
        e = {"kind": g["kind"], "target": g["target"], "locator": g["locator"]}
        if hit is None:
            e["reported"] = False
        else:
            used.add(hit)
            i = issues[hit]
            last = re.split(r"[\s./]+", g["target"])[-1]
            e.update({"reported": True, "observedKind": i["kind"],
                      "observedLocator": i["locator"], "observedTarget": i["target"],
                      "reasonPresent": bool(i["reason"]),
                      "targetMatches": last in i["target"]})
        expected.append(e)
    return {
        "expected": expected,
        "expectedReported": len(gold_reported),
        "actualReported": sum(1 for e in expected if e["reported"]),
        "unattributedReports": [f"{i['reason_code']} {i['locator']}"
                                for idx, i in enumerate(issues) if idx not in used],
    }


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
    # 입력 축이다 — 정답 축(sourceRevision)이 아니다(#125 · I2 §6).
    axis = manifest["probeAxis"]
    rev = axis["revision"]
    scope = work / "scope"
    rev_files = materialize(rev, SCOPE_ROOT, scope)
    probe: dict = {
        "probeVersion": "l0-code-probe/v3",
        "layer": "L0",
        "track": "code",
        "projectId": "lodestar",
        "sourceRevision": rev,
        "inputAxis": {
            "axis": "probeAxis",
            "revision": rev,
            "pinnedSourceCount": sum(1 for s in axis["sources"] if s["track"] == "code"),
            "note": "L0 수집 입력 축(#125). gold 정답 축은 3c27259 에 그대로 있고, 이 실행이 잰 것은 "
                    "이 축의 입력이다. 축의 승인 상태는 gold 에 있으며 여기 복사하지 않는다 — 복사하면 "
                    "승인이 바뀔 때 프로브 산출물이 표류하고, 승인은 측정이 아니다.",
        },
        "goldSetId": manifest["goldSetId"],
        "fixtureHash": manifest["fixtureHash"],
        "collector": {
            "impl": "lodestar_codegraph (walk → tree-sitter parse → extract → resolve → cluster → emit)",
            "declaredVersion": f"lodestar-codegraph v1 (meta.generated_by) · pyproject {collector_version()}",
            "citedVersion": f"lodestar-codegraph@{collector_version()}",
            # 재현 대상은 수집기 semver 하나로 지목되지 않는다 — 산출물의 바이트는 런타임 의존성에도
            # 달려 있다(군집 라벨은 networkx 의 louvain 이 만든다). 그 선언을 여기 함께 남긴다(#123).
            "dependencies": collector_dependencies(),
            "note": "산출물이 선언하는 것은 이름과 세대뿐이다 — 커밋·semver 가 없어 산출물만으로는 재현 대상을 "
                    f"특정할 수 없다(L0-fix-2). 입력 revision({rev[:7]})과 수집기 버전은 다른 축이며, 이 "
                    "실행의 수집기는 #112 의 결정성 수정 · #114 의 제외·실패 채널 · #115 의 마스킹 단계가 "
                    "모두 들어간 판이다.",
        },
    }

    # 환경이 선언과 어긋나면 **수집기를 돌리기 전에** 멈춘다. 계속 가면 두 가지로 나빠진다:
    # 운이 좋으면 표류가 `collector` 블록 하나로만 보고돼 원인이 코드인지 환경인지 구분되지 않고,
    # 운이 나쁘면 수집기가 그 버전에서 아예 죽어 무관해 보이는 트레이스백만 남는다(실측: networkx
    # 3.1 은 엣지가 없는 입력에서 `modularity` 의 `1/deg_sum**2` 로 ZeroDivisionError 를 낸다).
    env_errs = environment_errors(probe)
    if env_errs:
        raise EnvironmentMismatch("; ".join(env_errs))

    # 1) 입력 신원 — 고정 revision blob 에서 재구성한 범위를 gold 고정 해시와 대조한다.
    #    gold 입력 축이 고정한 것은 범위 파일 중 7건뿐이므로 나머지도 blob 해시와 전수 대조한다
    #    (재구성 자체가 blob 이라 항등이지만, 경로 집합·건수의 어긋남은 여전히 잡힌다).
    ignore = ["build", ".gradle", ".git", "node_modules"]
    all_files = walk_all_files(scope, ignore)
    rel_of = {str(p): str(pathlib.PurePosixPath(SCOPE_ROOT) / p.relative_to(scope))
              for p in all_files}
    hashes = {rel_of[str(p)]: sha256_file(p) for p in all_files}
    # 대조 대상은 **입력 축의 고정값**이다. 정답 축의 해시로 대조하면 입력을 재고정한 뒤에도
    # 옛 정답 축의 내용을 요구하게 되어, 정상 실행이 영원히 불일치로 읽힌다.
    pinned = {s["path"]: s for s in axis["sources"]
              if s["track"] == "code" and s["path"].startswith(SCOPE_ROOT)}
    mismatched = sorted(p for p, s in pinned.items()
                        if hashes.get(p) != s["contentHash"])
    rev_mismatched = sorted(p for p in set(hashes) | set(rev_files)
                            if hashes.get(p) != rev_files.get(p))
    probe["input"] = {
        "scopeRoot": SCOPE_ROOT,
        "materializedFrom": f"git blob @{rev[:7]}",
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
    excluded = [rel_of[str(p)] for p in all_files if p.suffix not in collected_ext]
    # 제외·실패는 프로브가 다시 분류하지 않고 **산출물이 스스로 말한 것** 을 읽는다.
    issues = doc["meta"]["issues"]
    reported = [i for i in issues if i["reason"] and line_range(i["locator"]) and i["target"]]
    # 보고율의 분모는 **프로브가 독립적으로 센 것** 이어야 한다. 분자·분모를 모두 수집기 신고에서
    # 가져오면 "보고한 것을 보고했다" 는 자기 인증이 되어 아무것도 재지 못한다. 그래서 범위 안에서
    # 수집기가 읽지 않은 파일(walked 에 없는 파일)을 프로브가 직접 세고, 그 각각에 대해 사유가 달린
    # 항목이 산출물에 있는지 본다.
    # 분류는 **프로브의 규칙(M-CODE-1)** 으로 한다 — 수집기 신고로 나누면 "성공했다고 말한 것이
    # 성공" 이 되어 자기 인증이다. 파일 노드의 status 는 수집기가 스스로 붙인 표시이므로
    # '사실을 냈는가' 판정에만 쓰고, 분모(읽을 수 있었던 파일)는 확장자 규칙으로 프로브가 정한다.
    cls = classify_scope(sorted(rel_of.values()), doc)
    fact_files, not_collected = set(cls["factFiles"]), cls["notCollected"]
    failed_files = cls["failedFiles"]
    reported_paths = {f"{SCOPE_ROOT}/{i['locator'].split('#')[0]}"
                      for i in reported if i["reason"]}
    reported_not_collected = [r for r in not_collected if r in reported_paths]
    # 제외 목록은 **분모와 같은 집합**(수집기가 읽지 않은 파일)에서 만든다. 수집기가 말한 것만 모으면
    # 보고하지 않고 삼킨 파일이 목록에서도 사라져, 보고서의 제외 합계와 counts.excluded 가 서로를
    # 확인해주지 못한다(I3 R2·R3). 사유가 없는 파일은 **그 사실 자체를 사유로** 남긴다.
    by_path = {}
    for i in issues:
        if i["kind"] == "skipped":
            by_path.setdefault(f"{SCOPE_ROOT}/{i['locator'].split('#')[0]}", i)
    grouped: dict[str, list[str]] = {}
    for rel in not_collected:
        i = by_path.get(rel)
        if i is None:
            key = "UNREPORTED: 수집기가 읽지 않았는데 사유를 남기지 않았다 (조용한 제외)"
            grouped.setdefault(key, []).append(f"{rel}#L1 ({rel})")
        else:
            key = f"{i['reason_code']}: {i['reason']}"
            grouped.setdefault(key, []).append(
                f"{rel}#L{line_range(i['locator'])[0]} ({i['target']})")
    probe["inventory"] = {
        "rule": "M-CODE-1",
        "input": len(all_files),
        "walked": walked,
        "parsed": parsed,
        "skippedByCollector": doc["meta"]["skipped"],
        "excludedByExtensionFilter": len(excluded),
        "excludedReportedByCollector": doc["meta"]["excluded"],
        "failedReportedByCollector": doc["meta"]["failed"],
        "partialReportedByCollector": doc["meta"]["partial"],
        "scopeRoot": SCOPE_ROOT,
        # 사실을 낸 파일만 산출로 센다 — 파싱은 됐지만 사실이 0건인 파일을 output 에 넣으면
        # 실패가 성공으로 위장된다(#114 가 수집기에서 없앤 것과 같은 위장이 보고서 층에서 재현된다).
        "producedFacts": len(fact_files),
        "failedFiles": failed_files,
        "failedFilesReported": sorted(
            f for f in failed_files
            if any(i["locator"].split("#")[0] == f and i["reason"] for i in issues)),
        "notCollected": not_collected,
        "notCollectedCount": len(not_collected),
        "reportedNotCollected": len(reported_not_collected),
        "unreportedNotCollected": [r for r in not_collected if r not in reported_paths],
        "reported": len(reported),
        "exclusions": [{"reason": r, "count": len(v), "examples": v} for r, v in grouped.items()],
        "issues": issues,
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
    # 비율은 **#113 의 전용 측정을 인용한다**. 키가 있는지만 다시 재면 값이 비어 있거나
    # 플레이스홀더여도 통과하는, 더 느슨한 근거로 같은 게이트를 판정하게 된다. 키 집합은
    # 인용이 실재와 어긋나지 않는지 보는 보조 증거로만 남긴다.
    cited = json.loads((HERE / "metadata/completeness-code.json").read_text())
    probe["provenance"] = {
        "probe": "#113 전용 측정(metadata/completeness-code.json)의 completeness 를 인용한다 — "
                 "산출물 키 존재가 아니라 소스 단위로 값이 채워졌는지까지 본 결과다",
        "citedEvidence": "docs/superpowers/specs/bench/l0/metadata/completeness-code.json",
        "citedMeasurementVersion": cited["measurementVersion"],
        "metaKeys": meta_keys,
        "nodeKeys": node_keys,
        "required": REQUIRED_PROVENANCE,
        "present": present,
        "absent": [f for f in REQUIRED_PROVENANCE if f not in {p["field"] for p in present}],
        "rate": cited["completeness"]["rate"],
    }

    # 6) 실패·제외 보고 채널
    probe["reporting"] = {
        "probe": "산출물에 실패·제외를 사유·좌표와 함께 실을 자리가 있는가",
        "aggregateKeys": [k for k in meta_keys
                          if k in ("skipped", "excluded", "failed", "partial", "external_calls")],
        "channelKeys": [k for k in meta_keys if k in ("issues", "partial_files", "failed_files")],
        "channelExists": "issues" in meta_keys,
        "note": "#114 로 meta.issues 가 생겼다 — 제외·실패·부분수집이 사유·좌표·대상과 함께 실린다. "
                "노드에는 status(parsed|partial|failed) 가 붙어 부분 추출이 완전 추출로 위장되지 않는다.",
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
        # FILE 노드와 심볼 노드를 나눠 적는다 — FILE 노드의 status 가 곧 '이 파일을 어떻게 표시했나' 다.
        labels = sorted({f"{n['kind']}:{n['qualified_name']}" for n in out["nodes"]})
        expected = sorted({e.get("fqn") or f"{e.get('owner','')}.{e.get('name','')}"
                           for e in f["extracted"]})
        symbols = sorted({n["qualified_name"] for n in out["nodes"] if n["kind"] != "file"})
        file_status = sorted({n["status"] for n in out["nodes"] if n["kind"] == "file"})
        attribution = attribute(f["reported"], out["meta"]["issues"])
        marked_ok = file_status == ["parsed"]
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
            "extractedSymbols": symbols,
            "unexpectedExtracted": sorted(set(symbols) - set(expected)),
            "missingExtracted": sorted(set(expected) - set(symbols)),
            "fileStatus": file_status,
            "expectedReported": attribution["expectedReported"],
            "actualReported": attribution["actualReported"],
            "reportAttribution": attribution,
            "markedAsFullySucceeded": marked_ok,
            "silentSkipIsFailure": f["silentSkipIsFailure"],
            "verdict": (
                "EXTRACTION_MISMATCH" if sorted(symbols) != expected else
                "UNREPORTED" if attribution["actualReported"] < attribution["expectedReported"] else
                "SILENT_SUCCESS" if f["reported"] and marked_ok else
                "OVER_REPORTED" if attribution["unattributedReports"] else "OK"),
        })
    probe["failureFixtures"] = fixtures
    # 보고 채널의 모양은 항목이 있는 실행에서만 확인된다 — 범위 실행에 제외·실패가 0건이면
    # 픽스처 실행의 항목으로 판정한다(0건을 근거로 'reason 없음' 이라고 적으면 거짓이 된다).
    seen_items = list(issues) + [e for fx in fixtures
                                 for e in fx["reportAttribution"]["expected"] if e["reported"]]
    probe["reporting"]["perItemReasons"] = bool(seen_items) and all(
        i.get("reason") or i.get("reasonPresent") for i in seen_items)
    probe["reporting"]["itemFields"] = sorted(issues[0].keys()) if issues else \
        ["kind", "locator", "reason", "reason_code", "target"]
    probe["reporting"]["itemsObserved"] = len(seen_items)

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
        # #114 이후 '수집하지 않았다' 는 사실 자체가 사유와 함께 남는다 — 미수집과 부재의 구분(EVL §2.5).
        "exclusionsReported": pout["meta"]["excluded"],
        "exclusionReasons": sorted({i["reason_code"] for i in pout["meta"]["issues"]}),
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

    # 10) read-only 확인 — 재구성한 범위가 수집 실행 전후로 같은가
    after = {rel_of[str(p)]: sha256_file(p) for p in walk_all_files(scope, ignore)}
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


class EnvironmentMismatch(RuntimeError):
    """측정 환경이 선언한 재현 대상과 다르다 — 이 환경의 측정은 그 대상의 측정이 아니다(#123)."""


def environment_errors(probe: dict) -> list[str]:
    """측정 환경이 **선언한 재현 대상**과 같은가(#123).

    `--check` 는 산출물 표류를 블록명으로만 보고한다. 이번 계약으로 `collector` 블록은 환경에
    민감해졌으므로(선언과 다른 networkx 가 설치돼 있으면 `installedMatchesDeclared` 가 뒤집힌다),
    표류의 원인이 코드인지 환경인지 구분해주지 않으면 읽는 쪽은 산출물을 직접 열어봐야 안다.

    `determinism_errors` 와 같은 이유로 순수 함수다 — `main(--check)` 안에만 두면 그 판정 자체는
    아무도 검사하지 않는다. 확인기(`verify_l0.py` V15)가 커밋된 증거에 같은 규칙을 건다.
    """
    dep = probe.get("collector", {}).get("dependencies")
    if dep is None:
        return ["런타임 의존성 선언이 산출물에 없다 — 재현 대상이 닫히지 않는다(#123)"]
    errs = []
    if dep["unpinnedDependencies"]:
        errs.append(f"고정되지 않은 런타임 의존성: {dep['unpinnedDependencies']} — "
                    "그 버전이 바뀌면 산출물이 바뀔 수 있고, 그 변화는 어디에도 잡히지 않는다")
    if not dep["dependencyPins"]:
        errs.append("고정 선언이 비어 있다 — 재현 대상을 지목하지 못한다")
    # 마커가 붙어 이 환경에서 설치 여부를 판정하지 않은 선언. 판정하지 않은 것을 '검사했다' 에
    # 넣지 않는다 — 재현 대상이 환경에 따라 갈리는 자리다.
    if dep.get("conditionalDependencies"):
        errs.append(f"이 환경에서 판정하지 않은 조건부 의존성: {dep['conditionalDependencies']} — "
                    "재현 대상이 환경에 따라 갈린다")
    if not dep["installedMatchesDeclared"] or dep["installedMismatches"]:
        errs.append(f"측정 환경이 선언한 고정과 다르다: {dep['installedMismatches']} — "
                    "표류의 원인이 코드가 아니라 환경이다. `pip install -e codegraph` 로 맞춘다")
    return errs


def determinism_errors(probe: dict) -> list[str]:
    """결정성 계약(#112) — 3회 실행이 하나로 모이고, 시드를 바꿔도 같아야 한다.

    `main(--check)` 안에만 두면 그 판정 자체는 아무도 검사하지 않는다. 순수 함수로 빼서
    확인기(`verify_l0.py` V12)가 커밋된 산출물에 같은 규칙을 걸고 결함 주입으로 문다.
    """
    errs = []
    obs = probe.get("determinismObserved", {})
    if obs.get("rate") != 1.0:
        errs.append(f"결정성 {obs.get('rate')} — 동일 입력 {obs.get('runs')}회 실행이 갈렸다: "
                    f"{obs.get('divergingPaths')}")
    if obs.get("distinctHashes") != 1:
        errs.append(f"산출물 해시가 {obs.get('distinctHashes')}종이다 — 하나여야 한다")
    ctrl = probe.get("determinismControl", {})
    if not ctrl.get("seedIndependent"):
        errs.append("PYTHONHASHSEED 를 바꾸면 산출물이 달라진다 — 재현 보장이 없다")
    return errs


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

    try:
        probe = measure()
    except EnvironmentMismatch as e:
        # 트레이스백이 아니라 문장으로 끝낸다 — 이 실패는 버그가 아니라 '환경을 맞추라' 는 지시다.
        print(f"[FAIL] {e}")
        return 1
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
            # 표류의 원인이 환경이면 그 자리에서 말한다 — 블록명만으로는 코드가 바뀐 것인지
            # 내 venv 의 networkx 가 다른 것인지 구분되지 않는다(#123).
            for e in environment_errors(probe):
                print(f"[FAIL] {e}")
            return 1
        # 표류가 없어도 계약을 어긴 채 **일관되게** 어긴 실행이 있을 수 있다 — 커밋된 산출물이 이미
        # 미고정 선언을 담고 있으면 대조는 통과한다. 그래서 규칙을 따로 건다.
        det = determinism_errors(probe) + environment_errors(probe)
        if det:
            for e in det:
                print(f"[FAIL] {e}")
            return 1
        print("[ok] 프로브 산출물 일치 + 결정성 1.0 (시드 무관) + 런타임 의존성 고정 일치")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
