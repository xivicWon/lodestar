from __future__ import annotations
import fnmatch
import os
from dataclasses import dataclass
from .lang import lang_for_path


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
    out: list[SourceFile] = []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        # 디렉토리 프루닝
        dirnames[:] = [
            d for d in dirnames
            if not _ignored(os.path.join(rel_dir, d) if rel_dir != "." else d, ignore_globs)
        ]
        for fn in filenames:
            lang = lang_for_path(fn)
            if lang is None:
                continue
            abspath = os.path.join(dirpath, fn)
            rel = os.path.relpath(abspath, root)
            if _ignored(rel, ignore_globs):
                continue
            with open(abspath, "rb") as f:
                out.append(SourceFile(path=abspath, rel=rel, lang=lang, source=f.read()))
    out.sort(key=lambda s: s.rel)
    return out


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
