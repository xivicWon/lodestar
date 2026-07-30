from __future__ import annotations
import argparse
import sys
from dataclasses import replace
from itertools import count
from .model import FAILED, PARTIAL, SKIPPED
from .walk import walk_with_exclusions, load_ignore
from .parse import parse_with_issues
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
    files, issues = walk_with_exclusions(args.source_root, ignore)

    seq = count(1)
    parsed, nodes, edges = [], [], []
    for f in files:
        pf, file_issues = parse_with_issues(f)
        issues += file_issues
        if pf is None:
            continue
        parsed.append(pf)
        r = extract_file(pf, seq)
        nodes += r.nodes
        edges += r.edges
        # 사실을 일부라도 건진 파일의 오류는 실패가 아니라 **부분 수집**이다 — 어느 쪽인지
        # 산출물에 명시해야 부분 성공이 완전 성공으로 위장되지 않는다(#114).
        if any(n.kind == "file" and n.status == "partial" for n in r.nodes):
            issues = [replace(i, kind=PARTIAL) if i in file_issues else i for i in issues]

    calls, external = resolve_calls(parsed, nodes, seq)
    edges += calls

    annotate(nodes, edges, args.god_node_percentile)

    langs = sorted({f.lang for f in files})
    issues.sort(key=lambda i: (i.locator, i.reason_code, i.kind))
    partial_files = sorted({n.qualified_name for n in nodes
                            if n.kind == "file" and n.status == "partial"})
    failed_files = sorted({n.qualified_name for n in nodes
                           if n.kind == "file" and n.status == "failed"})
    meta_extra = {
        "source_root": args.source_root,
        "languages": langs,
        "walked": len(files),
        "parsed": len(parsed),
        "skipped": len(files) - len(parsed),
        "external_calls": external,
        # #114 — 제외·실패·부분수집을 사유·좌표와 함께 산출물에 싣는다. 건수만 세는 자리는
        # 남기되(하위 호환), 판정 근거는 issues 다.
        "excluded": sum(1 for i in issues if i.kind == SKIPPED),
        "failed": sum(1 for i in issues if i.kind == FAILED),
        "partial": sum(1 for i in issues if i.kind == PARTIAL),
        "partial_files": partial_files,
        "failed_files": failed_files,
        "issues": [i.doc() for i in issues],
    }
    doc = build_and_write(nodes, edges, meta_extra, args.out, prune_dangling=True)
    m = doc["meta"]
    print(f"nodes={m['node_count']} edges={m['edge_count']} "
          f"communities={m['community_count']} skipped={m['skipped']} "
          f"excluded={m['excluded']} failed={m['failed']} partial={m['partial']} "
          f"external_calls={m['external_calls']} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
