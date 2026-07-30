"""L0 수집 식별 메타데이터 — DB·CODE 공통 계약 v0 의 CODE 트랙 구현 (#113).

계약: docs/superpowers/specs/2026-07-30-m0-l0-collection-metadata-contract.md

다섯 필드(projectId·sourceId·revision·contentHash·collectorVersion)를 산출물에 남긴다.
모르는 신원은 지어내지 않는다 — git 이 정본이 아니면 `nogit:`/`dirty:` 접두어로 그 사실을 드러낸다.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess

COLLECTOR_NAME = "lodestar-codegraph"
DEFAULT_PROJECT_ID = "lodestar"

REQUIRED_FIELDS = ("project_id", "source_id", "revision", "content_hash", "collector_version")

#: VCS 가 정본이 아닌 소스가 쓰는 revision 접두어.
REVISION_SCHEMES = ("inline", "bundle", "live", "dirty", "nogit")

_REVISION = re.compile(r"^(?:[0-9a-f]{7,40}|(?:%s):[0-9a-f]{12})$" % "|".join(REVISION_SCHEMES))
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
_PLACEHOLDERS = {"unknown", "n/a", "na", "null", "none", "todo", "tbd", "-", "?"}


def _version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("lodestar-codegraph")
        except PackageNotFoundError:
            pass
    except ImportError:  # pragma: no cover
        pass
    # 설치되지 않은 채(PYTHONPATH) 실행되는 경우 — pyproject 의 버전과 같이 움직인다.
    return "0.1.0"


def collector_version() -> str:
    """`<이름>@<semver>[+<commit>]`. 빌드가 커밋을 알면 붙인다(env `LODESTAR_BUILD_REVISION`)."""
    base = f"{COLLECTOR_NAME}@{_version()}"
    commit = (os.environ.get("LODESTAR_BUILD_REVISION") or "").strip().lower()
    return f"{base}+{commit}" if _COMMIT.match(commit) else base


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_hash(path: str) -> str:
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def hash_of_scope(file_hashes: dict[str, str]) -> str:
    """수집 범위의 신원 — 상대경로와 파일 해시를 **둘 다** 잇는다.

    내용만 이으면 파일이 추가·이동돼도 해시가 같을 수 있다. 범위가 바뀌면 반드시 바뀌어야 한다.
    """
    lines = sorted(f"{rel} {h}" for rel, h in file_hashes.items())
    return sha256_bytes("".join(line + "\n" for line in lines).encode())


def scope_hash(source_root: str, paths: list[str]) -> str:
    """[hash_of_scope] 를 파일 경로 목록에서 바로 구한다."""
    root = os.path.abspath(source_root)
    return hash_of_scope({os.path.relpath(os.path.abspath(p), root): file_hash(p) for p in paths})


def _git(root: str, *args: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    except OSError:  # git 자체가 없다
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def detect_revision(source_root: str, scope_content_hash: str,
                    collected: list[str] | None = None) -> str:
    """수집 범위의 스냅샷 식별자.

    커밋 sha 를 쓰려면 **수집한 것이 그 커밋에서 그대로 나와야** 한다. 그래서 두 가지를 본다 —
    범위 안에 수정된 파일이 없는가, 그리고 수집한 파일이 전부 HEAD 에 추적되는가([collected],
    수집 범위 루트 기준 상대경로). 후자를 빼면 gitignore 된 소스를 수집해도 워킹트리는 clean 이라
    "HEAD 로 재현된다" 는 거짓 주장이 된다.

    재현되지 않으면 `dirty:`/`nogit:` + 범위 해시 앞 12자. 시각은 쓰지 않는다 —
    같은 입력의 두 실행이 달라지면 결정성 측정(I1 H1)이 오염된다.
    """
    root = os.path.abspath(source_root)
    short = scope_content_hash.removeprefix("sha256:")[:12]
    head = _git(root, "rev-parse", "HEAD")
    if head is None or not _COMMIT.match(head):
        return f"nogit:{short}"
    status = _git(root, "status", "--porcelain", "--", root)
    if status is None or status:
        return f"dirty:{short}"
    if collected:
        listing = _git(root, "ls-files", "--full-name", "--", root)
        if listing is None:
            return f"dirty:{short}"
        prefix = _git(root, "rev-parse", "--show-prefix") or ""
        tracked = {p[len(prefix):] for p in listing.split("\n") if p.startswith(prefix)}
        if any(rel.replace(os.sep, "/") not in tracked for rel in collected):
            # 추적되지 않는 소스를 수집했다 — HEAD 에서 같은 범위가 나오지 않는다.
            return f"dirty:{short}"
    return head


def scope_id(source_root: str) -> str:
    """수집 범위의 이름 — **실행 위치가 아니라** 범위 자체를 가리킨다.

    절대경로를 그대로 실으면 같은 스냅샷을 다른 기계에서 수집했을 때 산출물이 달라진다.
    실행 위치는 수집 결과가 아니다(`meta.source_root` 를 정규화에서 빼는 것과 같은 이유).
    """
    root = os.path.abspath(source_root)
    repo = _git(root, "rev-parse", "--show-toplevel")
    if repo and os.path.isdir(repo):
        return os.path.relpath(root, repo).replace(os.sep, "/")
    return os.path.basename(root.rstrip(os.sep))


def _require_identity(field: str, value: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field} 는 비어있을 수 없다")
    if value.strip().lower() in _PLACEHOLDERS:
        raise ValueError(f"{field} 에 플레이스홀더를 쓸 수 없다: {value!r} — 모르는 신원은 지어내지 않는다")
    return value


def build_metadata(project_id: str, source_root: str, file_hashes: dict[str, str],
                   revision: str | None = None) -> dict:
    """실행 단위 메타데이터. 한 실행은 한 스냅샷이므로 revision·collectorVersion 은 실행에 하나다."""
    _require_identity("project_id", project_id)
    root = os.path.abspath(source_root)
    content_hash = hash_of_scope(file_hashes)
    if revision is None:
        revision = detect_revision(root, content_hash, sorted(file_hashes))
    elif not _REVISION.match(revision):
        raise ValueError(
            f"revision 은 커밋 sha(7~40 hex) 또는 선언된 비-VCS 스킴이어야 한다: {revision!r}")
    return {
        "project_id": project_id,
        "source_id": f"code:{scope_id(root)}",
        "revision": revision,
        "content_hash": content_hash,
        "collector_version": collector_version(),
    }
