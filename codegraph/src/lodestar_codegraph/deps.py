"""런타임 의존성의 고정 선언 — 재현 대상을 이름으로 지목한다 (#123).

`codegraph.json` 의 바이트는 수집기 코드만으로 정해지지 않는다. 군집 배정은
`networkx.community.louvain_communities` 가 만들고, 그 구현이 바뀌면 `nodes[].community` 와
`meta.community_count` 가 바뀐다. #112 가 없앤 것은 **같은 환경 안에서** 프로세스마다 갈리는
비결정(PYTHONHASHSEED)이고, **환경이 달라질 때의 재현성**은 코드가 아니라 선언으로 막는다.

그래서 정책은 하나다: **런타임 의존성은 전부 `==` 로 고정한다**(`pyproject.toml`). 상한 있는 범위를
쓰면 상한 안에서 구현이 바뀔 자리가 남고, 그 변화는 `versions.collector: PINNED` 에도
`probe_code.py --check` 의 바이트 대조에도 잡히지 않는다 — 그 사각지대가 이 이슈다.

이 모듈은 선언을 읽고(`declared_pins`), 지금 설치된 것과 대조하고(`pin_mismatches`), 프로브가
산출물에 실을 블록을 만든다(`report`). `report()` 의 값은 **선언에서만** 나온다 — 설치된 버전
문자열을 그대로 실으면 환경마다 바이트가 달라져 표류 검사와 충돌한다. 환경이 선언과 어긋난 사실은
불리언과 불일치 목록으로 남고, 그때는 표류로 걸리는 것이 맞다.

    python3 -m lodestar_codegraph.deps    # 프로브가 읽는 JSON 블록
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import tomllib

#: `name==version` — 고정 선언의 유일한 모양. extras·마커를 뗀 뒤에 맞춘다.
_PINNED = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+!-]*)$")
#: 패키지 이름으로 시작하는가 — `networkx`·`networkx>=3.0`·`pkg @ url` 은 모두 **이름을 읽을 수
#: 있는** 선언이다. 고정이 아니면 목록으로 보고하면 되고, 이름조차 읽히지 않을 때만 예외다.
_NAMED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:\s|$|[<>!~=@\[])")
#: `Requires-Dist` 의 optional extra 표시. 런타임 의존성이 아니다.
_EXTRA_MARKER = re.compile(r"\bextra\s*==")

PIN_POLICY = "exact"
DIST_NAME = "lodestar-codegraph"

_DEFAULT_PYPROJECT = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"


def _requirements(pyproject: os.PathLike | str | None = None) -> list[str]:
    """런타임 의존성 선언 원문.

    소스 트리에서 돌고 있으면 **그 트리의 pyproject** 가 정본이다(`provenance._version()` 과 같은
    순서 — 낡은 설치 메타데이터가 실제로 돌고 있는 선언을 가리지 않게 한다). 소스 트리 밖(휠 설치)
    에서는 설치 메타데이터의 `Requires-Dist` 를 읽는다. 두 경로 중 어느 것도 없으면 지어내지 않고
    예외다. dev extra 는 런타임이 아니므로 제외한다 — 넣으면 개발 의존성이 런타임 미고정으로 잡혀
    고칠 수 없는 실패가 상시로 남는다.
    """
    path = pathlib.Path(pyproject) if pyproject is not None else _DEFAULT_PYPROJECT
    if path.is_file():
        return [r.strip() for r in tomllib.loads(path.read_text())["project"]["dependencies"]]
    if pyproject is None:
        declared = _dist_requires()
        if declared is not None:
            return [r.strip() for r in declared if not _EXTRA_MARKER.search(r)]
    raise RuntimeError(
        f"런타임 의존성 선언을 찾을 수 없다: {path} (이 모듈을 담은 설치본의 메타데이터에도 없다) — "
        "재현 대상을 지어내지 않는다(#123)")


def _dist_requires() -> list[str] | None:
    """**이 모듈을 담고 있는 설치본**의 `Requires-Dist`. 다른 설치본의 선언은 쓰지 않는다.

    같은 이름의 낡은 설치가 남아 있으면 `importlib.metadata` 는 그쪽 선언을 돌려준다 — 실제로 이
    작업 중에 site-packages 의 0.1.0(`networkx>=3.0`)이 잡혀 테스트가 **엉뚱한 이유로** 통과했다.
    남의 선언을 재현 대상으로 적으면 이 파일이 지목하는 것은 이 산출물을 만든 코드가 아니다.
    """
    from importlib.metadata import PackageNotFoundError, distribution
    try:
        dist = distribution(DIST_NAME)
        located = pathlib.Path(dist.locate_file("lodestar_codegraph/deps.py")).resolve()
    except (PackageNotFoundError, OSError, ValueError):
        return None
    if located != pathlib.Path(__file__).resolve():
        return None
    return dist.requires


def _split_marker(req: str) -> tuple[str, str]:
    """`name==1.0 ; python_version>="3.11"` → (`name==1.0`, `python_version>="3.11"`)."""
    spec, _, marker = req.partition(";")
    return spec.strip(), marker.strip()


def _spec(req: str) -> str:
    """고정 여부를 판정할 형태 — extras 와 마커를 뗀다. `uvicorn[standard]==0.30.0` → `uvicorn==0.30.0`.

    떼지 않으면 고정된 선언이 미고정으로 읽힌다. 실패 방향이 loud 쪽이라 사각지대를 만들지는
    않지만, 조건부 의존성을 하나 추가하는 순간 거짓 경보가 상시로 남는다.
    """
    return re.sub(r"\[[^\]]*\]", "", _split_marker(req)[0]).strip()


def is_conditional(req: str) -> bool:
    """환경 마커가 붙은 선언 — 이 환경에서 설치돼 있어야 하는지를 여기서 판정하지 않는다."""
    return bool(_split_marker(req)[1])


def declared_pins(pyproject: os.PathLike | str | None = None) -> dict[str, str]:
    """고정 선언 `{패키지: 버전}`. **패키지 이름조차 읽히지 않는** 선언은 예외다.

    고정되지 않은 선언(맨 이름·범위·직접 참조)은 예외가 아니라 `unpinned_dependencies` 로 보고한다 —
    예외로 죽으면 "무엇이 고정되지 않았다" 를 말하지 못한 채 알 수 없는 오류만 남는다. 반대로
    이름조차 못 읽는 선언을 조용히 건너뛰면 고정되지 않은 의존성이 목록에서 아예 사라진다.
    """
    pins = {}
    for req in _requirements(pyproject):
        spec = _spec(req)
        if not _NAMED.match(spec):
            raise ValueError(
                f"의존성 선언에서 패키지 이름을 읽을 수 없다: {req!r} — 무엇이 고정되지 않았는지 "
                "지목할 수 없는 선언은 고정으로 볼 수 없다(#123)")
        m = _PINNED.match(spec)
        if m:
            name, version = m.group(1), m.group(2)
            # 같은 이름을 **다른 버전**으로 두 번 고정하면 뒤가 앞을 덮어써 앞 선언이 흔적 없이
            # 사라진다 — 목록에도 불일치에도 남지 않아 아무 데도 걸리지 않는다(LOD-181). 이 PR 이
            # 없애려던 것과 같은 부류의 조용한 손실이므로 판정하지 않고 막는다.
            if pins.get(name, version) != version:
                raise ValueError(
                    f"같은 의존성이 서로 다른 버전으로 고정돼 있다: {name}=={pins[name]} / "
                    f"{name}=={version} — 어느 쪽이 재현 대상인지 정해지지 않는다(#123)")
            pins[name] = version
    return pins


def unpinned_dependencies(pyproject: os.PathLike | str | None = None) -> list[str]:
    """`==` 로 고정되지 않은 런타임 의존성 — 판정은 extras·마커를 떼고, 보고는 **선언 원문**으로.

    `declared_pins` 를 먼저 부른다 — 이름조차 읽히지 않는 선언은 여기서도 침묵하면 안 된다.
    """
    declared_pins(pyproject)
    return sorted(r for r in _requirements(pyproject) if not _PINNED.match(_spec(r)))


def conditional_dependencies(pyproject: os.PathLike | str | None = None) -> list[str]:
    """마커가 붙어 이 환경에서 설치 여부를 판정하지 않은 선언. 조용히 빠지지 않게 목록으로 남긴다."""
    return sorted(r for r in _requirements(pyproject) if is_conditional(r))


def installed_version(name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def pin_mismatches(pyproject: os.PathLike | str | None = None) -> list[str]:
    """선언한 고정과 **지금 설치된 것**이 다른 항목. 설치되지 않은 것도 불일치다.

    마커가 붙은 선언은 여기서 판정하지 않는다 — 마커를 평가하지 않은 채 '설치 없음' 으로 세면
    정상 환경이 불일치로 뒤집힌다. 대신 `conditional_dependencies` 로 남아 보이게 한다.
    """
    conditional = {_spec(r) for r in conditional_dependencies(pyproject)}
    out = []
    for name, want in sorted(declared_pins(pyproject).items()):
        if f"{name}=={want}" in conditional:
            continue
        got = installed_version(name)
        if got != want:
            out.append(f"{name}: 선언 {want} / 설치 {got or '없음'}")
    return out


def report(pyproject: os.PathLike | str | None = None) -> dict:
    """프로브의 `collector` 블록에 실리는 선언. 값은 선언에서만 나온다(위 주석 참조)."""
    pins = declared_pins(pyproject)
    unpinned = unpinned_dependencies(pyproject)
    mismatches = pin_mismatches(pyproject)
    return {
        "pinPolicy": PIN_POLICY,
        "dependencyPins": sorted(f"{n}=={v}" for n, v in pins.items()),
        "unpinnedDependencies": unpinned,
        # 마커가 붙어 이 환경에서 설치 여부를 판정하지 않은 선언. 비어 있는 것이 정상이며, 값이
        # 생기면 그 자체가 표류로 걸려 검토 대상이 된다 — 판정하지 않은 것을 조용히 두지 않는다.
        "conditionalDependencies": conditional_dependencies(pyproject),
        "installedMatchesDeclared": not mismatches,
        "installedMismatches": mismatches,
        "note": "런타임 의존성은 전부 `==` 로 고정한다(#123). 여기 실리는 것은 **선언**이며, 설치된 "
                "버전 문자열은 싣지 않는다 — 그것을 실으면 환경마다 산출물 바이트가 달라져 표류 "
                "검사와 충돌한다. 환경이 선언과 어긋나면 installedMatchesDeclared 가 false 로 "
                "뒤집히고, 그때는 표류로 걸리는 것이 맞다.",
    }


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=False, sort_keys=True))
