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
from . import provenance


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lodestar_codegraph")
    ap.add_argument("source_root")
    ap.add_argument("-o", "--out", default="out/codegraph.json")
    ap.add_argument("--ignore", default=None)
    ap.add_argument("--god-node-percentile", type=float, default=99.0)
    ap.add_argument("--project-id", default=provenance.DEFAULT_PROJECT_ID,
                    help="수집 대상 프로젝트 식별자 (#113 계약 v0)")
    ap.add_argument("--revision", default=None,
                    help="소스 스냅샷 식별자. 생략하면 수집 범위의 git 상태에서 판정한다")
    args = ap.parse_args(argv)

    ignore = load_ignore(args.source_root, args.ignore)
    files, issues = walk_with_exclusions(args.source_root, ignore)

    seq = count(1)
    parsed, nodes, edges = [], [], []
    for f in files:
        pf, file_issues = parse_with_issues(f)
        if pf is None:
            issues += file_issues
            continue
        parsed.append(pf)
        r = extract_file(pf, seq)
        nodes += r.nodes
        edges += r.edges
        # 사실을 일부라도 건진 파일의 오류는 실패가 아니라 **부분 수집**이다 — 어느 쪽인지
        # 산출물에 명시해야 부분 성공이 완전 성공으로 위장되지 않는다(#114). 판정은 그 파일의
        # 결과로만 하고 누적 목록은 건드리지 않는다 — 값 동일성으로 되짚으면 다른 파일의 항목까지
        # 함께 바뀔 수 있다.
        partial = any(n.kind == "file" and n.status == "partial" for n in r.nodes)
        issues += [replace(i, kind=PARTIAL) if partial else i for i in file_issues]

    calls, external = resolve_calls(parsed, nodes, seq)
    edges += calls

    annotate(nodes, edges, args.god_node_percentile)

    langs = sorted({f.lang for f in files})
    issues.sort(key=lambda i: (i.locator, i.reason_code, i.kind))
    partial_files = sorted({n.qualified_name for n in nodes
                            if n.kind == "file" and n.status == "partial"})
    failed_files = sorted({n.qualified_name for n in nodes
                           if n.kind == "file" and n.status == "failed"})
    # 수집 신원 — 수집기가 **실제로 읽은 바이트**에서 나온다(#113 계약 v0).
    file_hashes = {f.rel: provenance.sha256_bytes(f.source) for f in files}
    meta_extra = {
        "source_root": args.source_root,
        **provenance.build_metadata(args.project_id, args.source_root, file_hashes, args.revision),
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
    doc = build_and_write(nodes, edges, meta_extra, args.out, prune_dangling=True,
                          file_hashes=file_hashes)
    m = doc["meta"]
    print(f"nodes={m['node_count']} edges={m['edge_count']} "
          f"communities={m['community_count']} skipped={m['skipped']} "
          f"excluded={m['excluded']} failed={m['failed']} partial={m['partial']} "
          f"external_calls={m['external_calls']} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
