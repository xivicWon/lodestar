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
