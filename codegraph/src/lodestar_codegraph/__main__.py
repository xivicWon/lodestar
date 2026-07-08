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
