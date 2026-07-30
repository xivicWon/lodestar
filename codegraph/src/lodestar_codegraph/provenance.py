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
    """수집기 버전은 손으로 적지 않는다 — 설치 메타데이터, 없으면 pyproject 에서 읽는다.

    손으로 옮긴 버전은 올려도 티가 나지 않고, 그러면 `collectorVersion` 이 재현 대상을 잘못 가리킨다.
    """
    # 소스 트리에서 돌고 있으면 **그 트리의 pyproject** 가 정본이다. 설치 메타데이터를 먼저 보면
    # 낡은 editable 설치(0.1.0)가 실제 실행 중인 코드(0.1.1)를 가리는 일이 생긴다.
    pyproject = os.path.join(os.path.dirname(__file__), "..", "..", "pyproject.toml")
    if os.path.isfile(pyproject):
        import tomllib
        with open(pyproject, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("lodestar-codegraph")
        except PackageNotFoundError:
            pass
    except ImportError:  # pragma: no cover
        pass
    raise RuntimeError(
        "수집기 버전을 확정할 수 없다 — 모르는 버전을 지어내지 않는다(#113 계약 §2.1)")


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

    경로는 **길이 접두어**로 싣는다. 구분자만 쓰면 직렬화가 단사가 아니다 — 공백·개행은 POSIX
    파일명에 합법이므로, 이름에 구분자를 심은 파일 하나가 여러 파일로 이뤄진 다른 범위와 같은
    바이트를 만든다. 길이를 먼저 적으면 경로 안에 무엇이 들어 있든 경계가 밀리지 않는다.
    """
    out = bytearray()
    for rel in sorted(file_hashes):
        raw = rel.encode()
        out += str(len(raw)).encode() + b":" + raw + b"\0" + file_hashes[rel].encode() + b"\0"
    return sha256_bytes(bytes(out))


def scope_hash(source_root: str, paths: list[str]) -> str:
    """[hash_of_scope] 를 파일 경로 목록에서 바로 구한다."""
    root = os.path.abspath(source_root)
    return hash_of_scope({os.path.relpath(os.path.abspath(p), root): file_hash(p) for p in paths})


def _git(root: str, *args: str) -> str | None:
    try:
        # surrogateescape 로 읽는다. POSIX 파일명은 UTF-8 이 아닐 수 있고, 엄격 디코딩이면
        # 그런 파일이 하나만 있어도 수집이 예외로 멈춘다(os.listdir 이 쓰는 것과 같은 방식이다).
        proc = subprocess.run(["git", "-C", root, *args], capture_output=True,
                              encoding="utf-8", errors="surrogateescape")
    except OSError:  # git 자체가 없다
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _blob_sha(path: str) -> str:
    """git blob 오브젝트 id — `git hash-object` 와 같은 값을 파일을 읽어 직접 계산한다."""
    with open(path, "rb") as f:
        data = f.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _head_blobs(root: str, prefix: str) -> dict[str, str] | None:
    """HEAD 가 담고 있는 `root` 아래 파일의 blob id — 경로는 root 기준 상대경로.

    `-z` 의 **기본 출력 형식**으로 읽는다(`<mode> <type> <sha>\\t<path>`). 그래야 경로가 그대로
    나온다 — `--format=%(path)` 는 `-z` 를 줘도 비ASCII·공백·개행이 든 경로를 따옴표로 감싸고
    8진 이스케이프해서 내보내므로, 문자열 비교가 어긋나 **깨끗한 파일이 dirty 로 오판**된다.
    `--full-name` 이 없으면 경로가 CWD 기준으로 나와 prefix 제거와 어긋난다.
    """
    listing = _git(root, "ls-tree", "-r", "-z", "--full-name", "HEAD", "--", root)
    if listing is None:
        return None
    out = {}
    for record in listing.split("\0"):
        if not record.strip():
            continue
        meta, _, path = record.partition("\t")
        parts = meta.split()
        if len(parts) < 3:
            continue
        if path.startswith(prefix):
            out[path[len(prefix):]] = parts[2]
    return out


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
        # 심볼릭 링크는 수집기가 **대상의 바이트**를 읽지만 git 은 링크 자체(대상 경로 문자열)만
        # 추적한다. 대상이 범위 밖에 있으면 그 내용이 바뀌어도 `status -- <범위>` 는 clean 이라
        # HEAD 로 재현된다고 주장하게 된다. 수집한 바이트를 HEAD 가 담고 있지 않으므로 dirty 다.
        if any(os.path.islink(os.path.join(root, rel)) for rel in collected):
            return f"dirty:{short}"
        prefix = _git(root, "rev-parse", "--show-prefix") or ""
        head_blobs = _head_blobs(root, prefix)
        if head_blobs is None:
            return f"dirty:{short}"
        for rel in collected:
            key = rel.replace(os.sep, "/")
            if key not in head_blobs:
                # 추적되지 않는 소스를 수집했다 — HEAD 에서 같은 범위가 나오지 않는다.
                return f"dirty:{short}"
            # 내용까지 HEAD 와 대조한다. `status` 는 assume-unchanged·skip-worktree 로 표시된
            # 변경을 보여주지 않으므로, status 만 믿으면 실제로 읽은 바이트와 다른 커밋을 적게 된다.
            if _blob_sha(os.path.join(root, rel)) != head_blobs[key]:
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
    elif ":" in revision:
        # 비-VCS revision 은 **이 산출물의 내용**에서 나온 것이어야 한다(Kotlin 쪽 CollectionMetadata 와
        # 같은 불변식). 형식만 보면 아무 12자리나 붙여 신원을 가리키지 않는 revision 을 만들 수 있다.
        scheme = revision.split(":", 1)[0]
        expected = f"{scheme}:{content_hash.removeprefix('sha256:')[:12]}"
        if revision != expected:
            raise ValueError(
                f"revision 이 contentHash 에서 파생되지 않았다: {revision!r} (기대: {expected!r})")
    return {
        "project_id": project_id,
        "source_id": f"code:{scope_id(root)}",
        "revision": revision,
        "content_hash": content_hash,
        "collector_version": collector_version(),
    }
