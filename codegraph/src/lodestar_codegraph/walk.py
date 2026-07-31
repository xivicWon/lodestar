from __future__ import annotations
import fnmatch
import os
from dataclasses import dataclass
from .lang import lang_for_path
from .model import IGNORED_BY_CONFIG, Issue, SKIPPED, UNSUPPORTED_LANGUAGE


@dataclass
class SourceFile:
    path: str       # 절대경로
    rel: str        # source_root 기준 상대경로
    lang: str
    source: bytes


def _ignored(rel: str, ignore_globs: list[str]) -> bool:
    parts = rel.split(os.sep)
    for g in ignore_globs:
        pat = g.rstrip("/")
        if fnmatch.fnmatch(rel, pat) or any(fnmatch.fnmatch(p, pat) for p in parts):
            return True
    return False


def walk_sources(root: str, ignore_globs: list[str]) -> list[SourceFile]:
    """수집 대상 파일만. 제외 사유까지 필요하면 [walk_with_exclusions] 를 쓴다."""
    return walk_with_exclusions(root, ignore_globs)[0]


def walk_with_exclusions(
    root: str, ignore_globs: list[str]
) -> tuple[list[SourceFile], list[Issue]]:
    """수집 대상 파일과 **제외된 파일의 사유**를 함께 돌려준다(#114).

    확장자 필터로 조용히 거르면 '수집 범위 밖' 과 '수집했는데 없음' 이 구분되지 않는다
    (EVL 계약 §2.5 의 `not_collected` 대 `absent`). 제외가 정당해도 사유·좌표는 남긴다(I3 R20).
    """
    out: list[SourceFile] = []
    excluded: list[Issue] = []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        # 디렉토리 프루닝
        dirnames[:] = [
            d for d in dirnames
            if not _ignored(os.path.join(rel_dir, d) if rel_dir != "." else d, ignore_globs)
        ]
        for fn in filenames:
            abspath = os.path.join(dirpath, fn)
            rel = os.path.relpath(abspath, root)
            if _ignored(rel, ignore_globs):
                excluded.append(Issue(
                    SKIPPED, IGNORED_BY_CONFIG,
                    "무시 규칙(.codegraphignore·기본 프루닝)에 걸린 경로다",
                    f"{rel}#L1", rel))
                continue
            lang = lang_for_path(fn)
            if lang is None:
                excluded.append(Issue(
                    SKIPPED, UNSUPPORTED_LANGUAGE,
                    "수집기가 지원하는 언어가 아니다 — .java/.kt/.kts 만 파싱한다(lang.lang_for_path)",
                    f"{rel}#L1", rel))
                continue
            with open(abspath, "rb") as f:
                out.append(SourceFile(path=abspath, rel=rel, lang=lang, source=f.read()))
    out.sort(key=lambda s: s.rel)
    excluded.sort(key=lambda i: (i.locator, i.reason_code))
    return out, excluded


def load_ignore(root: str, override: str | None) -> list[str]:
    path = override or os.path.join(root, ".codegraphignore")
    globs: list[str] = ["build", ".gradle", ".git", "node_modules"]
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    globs.append(line)
    return globs
