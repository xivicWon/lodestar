#!/usr/bin/env python3
"""#113 L0-fix — `gate-l0-metadata-completeness` 재측정.

#88 프로브와 **같은 산식**으로 다시 잰다: 필수 5필드가 산출물에서 **소스 단위로** 조회되는가.
코드 트랙은 여기서 실제 수집기를 돌려 재고, DB 트랙은 Kotlin 수집기이므로 백엔드 테스트가 재서
`metadata/completeness-db.json` 에 남긴 것을 읽는다(#88 이 프로브를 나눈 것과 같은 이유다).

    python3 docs/superpowers/specs/bench/l0/metadata_completeness.py            # 측정 + 표류 검사
    python3 docs/superpowers/specs/bench/l0/metadata_completeness.py --bootstrap  # 최초 생성

#88 의 baseline 산출물(`runs/run-l0-*-3c27259-001`)은 손대지 않는다 — revision 3c27259 시점의
증거이고, 고친 코드로 덮어쓰면 그 시점의 사실이 사라진다(I3 §5.5).

계약: ../../2026-07-30-m0-l0-collection-metadata-contract.md
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
OUT_DIR = HERE / "metadata"
CODE_COMMITTED = OUT_DIR / "completeness-code.json"
DB_COMMITTED = OUT_DIR / "completeness-db.json"
CG_ROOT = REPO / "codegraph"
SCOPE_ROOT = "backend/src/main/kotlin"

REQUIRED = ["projectId", "sourceId", "revision", "contentHash", "collectorVersion"]
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REV_RE = re.compile(r"^(?:[0-9a-f]{7,40}|(?:inline|bundle|live|dirty|nogit):[0-9a-f]{12})$")
VER_RE = re.compile(r"^[a-z0-9][a-z0-9-]*@\d+\.\d+\.\d+(?:\+[0-9a-f]{7,40})?$")

#: 키가 있는 것만 세면 빈 값·플레이스홀더도 5/5 가 된다 — 게이트가 통과를 뜻하지 않게 된다.
PLACEHOLDERS = {"unknown", "n/a", "na", "null", "none", "todo", "tbd", "-", "?"}


def usable(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() not in PLACEHOLDERS

#: 값이 입력·수집기 버전에 따라 달라지는 블록 — 표류 검사에서 제외한다(#88 의 determinismObserved 와 같은 처리).
VOLATILE = "volatile"


def run_collector(source_root: pathlib.Path, out_path: pathlib.Path) -> dict:
    env = dict(os.environ, PYTHONPATH=str(CG_ROOT / "src"))
    env.pop("PYTHONHASHSEED", None)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "lodestar_codegraph", str(source_root), "-o", str(out_path)],
        cwd=CG_ROOT, env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"수집기 실행 실패: {proc.stderr[-2000:]}")
    return json.loads(out_path.read_text())


def measure_code() -> dict:
    with tempfile.TemporaryDirectory(prefix="l0-metadata-") as tmp:
        doc = run_collector(REPO / SCOPE_ROOT, pathlib.Path(tmp) / "codegraph.json")

    meta, nodes = doc["meta"], doc["nodes"]
    meta_keys = sorted(meta)
    node_keys = sorted(nodes[0]) if nodes else []

    # #88 M-CODE-3 와 같은 산식 — 별칭이 아니라 **직접 키**로만 센다.
    # 다만 키의 존재로 끝내지 않는다: 빈 값·플레이스홀더가 담긴 자리는 신원이 아니다.
    sample_node = nodes[0] if nodes else {}
    present = []
    for field in REQUIRED:
        flat = field.lower()
        for scope, keys, values in (("meta", meta_keys, meta), ("nodes[]", node_keys, sample_node)):
            hit = next((k for k in keys if k.replace("_", "").lower() == flat), None)
            if hit and usable(values.get(hit)):
                present.append({"field": field, "via": f"{scope}.{hit}", "basis": "직접 키 + 값 확인"})
                break

    missing_source_id = [n["id"] for n in nodes if not usable(n.get("source_id"))]
    missing_hash = [n["id"] for n in nodes if not HASH_RE.match(n.get("content_hash") or "")]

    return {
        "measurementVersion": "l0-metadata-completeness/v1",
        "issue": 113,
        "gate": "gate-l0-metadata-completeness",
        "track": "code",
        "contract": "docs/superpowers/specs/2026-07-30-m0-l0-collection-metadata-contract.md",
        "baseline": "docs/superpowers/specs/bench/l0/runs/run-l0-code-3c27259-001 (0/5, 손대지 않는다)",
        "required": REQUIRED,
        "artifact": {
            "probe": "실제 수집기(lodestar_codegraph)를 돌려 산출물의 meta·nodes 키를 센다",
            "scopeRoot": SCOPE_ROOT,
            "metaKeys": meta_keys,
            "nodeKeys": node_keys,
            "present": present,
            "absent": [f for f in REQUIRED if f not in {p["field"] for p in present}],
        },
        "perSource": {
            "probe": "노드 하나에서 5필드가 닫히는가 — 소스를 지목하지 못하는 신원은 추적성이 아니다",
            "nodesMissingSourceId": missing_source_id,
            "nodesMissingContentHash": missing_hash,
            "formats": {
                "metaProjectId": usable(meta.get("project_id")),
                "metaSourceId": usable(meta.get("source_id")),
                "metaContentHash": bool(HASH_RE.match(meta.get("content_hash", ""))),
                "metaRevision": bool(REV_RE.match(meta.get("revision", ""))),
                "collectorVersion": bool(VER_RE.match(meta.get("collector_version", ""))),
            },
        },
        "completeness": {
            "present": len(present),
            "required": len(REQUIRED),
            "rate": round(len(present) / len(REQUIRED), 4),
        },
        VOLATILE: {
            "note": "값은 수집 범위의 내용·리비전에 따라 달라진다 — 표류 검사 대상이 아니다",
            "projectId": meta.get("project_id"),
            "revision": meta.get("revision"),
            "contentHash": meta.get("content_hash"),
            "collectorVersion": meta.get("collector_version"),
            "nodeCount": len(nodes),
            "walked": meta.get("walked"),
        },
    }


def check_code(m: dict) -> list[str]:
    errs = []
    if m["completeness"]["rate"] != 1.0:
        errs.append(f"code: 완전성 {m['completeness']['rate']} — 누락: {m['artifact']['absent']}")
    if m["perSource"]["nodesMissingSourceId"]:
        errs.append(f"code: sourceId 없는 노드 {len(m['perSource']['nodesMissingSourceId'])}건")
    if m["perSource"]["nodesMissingContentHash"]:
        errs.append(f"code: contentHash 없는 노드 {len(m['perSource']['nodesMissingContentHash'])}건")
    for name, ok in m["perSource"]["formats"].items():
        if not ok:
            errs.append(f"code: {name} 가 계약 형식이 아니다")
    return errs


def check_db(m: dict) -> list[str]:
    errs = []
    if m["completeness"]["rate"] != 1.0:
        errs.append(f"db: 완전성 {m['completeness']['rate']} — 누락: {m['typeGraph']['absent']}")
    paths = m["collectionPaths"]["paths"]
    if not paths:
        errs.append("db: 측정된 수집 경로가 0건이다")
    for p in paths:
        if p["rate"] != 1.0:
            errs.append(f"db: {p['path']} 경로 완전성 {p['rate']} — 누락: {p['absent']}")
    return errs


def stable(m: dict) -> dict:
    return {k: v for k, v in m.items() if k != VOLATILE}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", action="store_true", help="커밋된 측정 결과를 최초 생성한다")
    args = ap.parse_args()

    code = measure_code()
    text = json.dumps(code, ensure_ascii=False, indent=2) + "\n"
    build = REPO / "build/l0/completeness-code.json"
    build.parent.mkdir(parents=True, exist_ok=True)
    build.write_text(text)

    errs = check_code(code)

    if not DB_COMMITTED.exists():
        errs.append(f"db: 측정 결과가 없다: {DB_COMMITTED.relative_to(REPO)} — "
                    "`cd backend && ./gradlew test --tests '*L0DbMetadataCompletenessTest'` 로 만든다")
    else:
        errs += check_db(json.loads(DB_COMMITTED.read_text()))

    if args.bootstrap:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        CODE_COMMITTED.write_text(text)
    elif not CODE_COMMITTED.exists():
        errs.append(f"code: 커밋된 측정 결과가 없다: {CODE_COMMITTED.relative_to(REPO)} "
                    "— 최초 생성이면 --bootstrap")
    elif stable(json.loads(CODE_COMMITTED.read_text())) != stable(code):
        errs.append(f"code: 커밋된 측정 결과와 이번 실행이 다르다 — 생성물: {build}")

    for line in errs:
        print(f"[FAIL] {line}")
    if errs:
        return 1
    print(f"[ok] gate-l0-metadata-completeness — db 5/5 · code {code['completeness']['present']}/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
