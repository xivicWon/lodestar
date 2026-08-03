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

#: `name==version` — 고정 선언의 유일한 모양.
_PINNED = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+!-]*)$")
#: `name>=3.0` 처럼 **비교 연산자는 있으나 고정이 아닌** 선언. 잡아서 목록으로 남긴다.
_RANGE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?:[<>!~=]=|[<>])")

PIN_POLICY = "exact"

_DEFAULT_PYPROJECT = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"


def _requirements(pyproject: os.PathLike | str | None = None) -> list[str]:
    path = pathlib.Path(pyproject) if pyproject is not None else _DEFAULT_PYPROJECT
    if not path.is_file():
        raise RuntimeError(
            f"런타임 의존성 선언을 찾을 수 없다: {path} — 재현 대상을 지어내지 않는다(#123)")
    return [r.strip() for r in tomllib.loads(path.read_text())["project"]["dependencies"]]


def declared_pins(pyproject: os.PathLike | str | None = None) -> dict[str, str]:
    """고정 선언 `{패키지: 버전}`. 고정도 범위도 아닌 선언은 **예외**다.

    읽을 수 없는 선언을 조용히 건너뛰면 고정되지 않은 의존성이 목록에서 사라진다 — 없는 것으로
    보이는 것과 고정된 것은 다르다.
    """
    pins = {}
    for req in _requirements(pyproject):
        m = _PINNED.match(req)
        if m:
            pins[m.group(1)] = m.group(2)
        elif not _RANGE.match(req):
            raise ValueError(
                f"의존성 선언을 해석할 수 없다: {req!r} — 고정 여부를 판정할 수 없는 선언은 "
                "고정으로 볼 수 없다(#123)")
    return pins


def unpinned_dependencies(pyproject: os.PathLike | str | None = None) -> list[str]:
    """`==` 로 고정되지 않은 런타임 의존성 선언 그대로."""
    return sorted(r for r in _requirements(pyproject) if not _PINNED.match(r))


def installed_version(name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def pin_mismatches(pyproject: os.PathLike | str | None = None) -> list[str]:
    """선언한 고정과 **지금 설치된 것**이 다른 항목. 설치되지 않은 것도 불일치다."""
    out = []
    for name, want in sorted(declared_pins(pyproject).items()):
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
        "installedMatchesDeclared": not mismatches,
        "installedMismatches": mismatches,
        "note": "런타임 의존성은 전부 `==` 로 고정한다(#123). 여기 실리는 것은 **선언**이며, 설치된 "
                "버전 문자열은 싣지 않는다 — 그것을 실으면 환경마다 산출물 바이트가 달라져 표류 "
                "검사와 충돌한다. 환경이 선언과 어긋나면 installedMatchesDeclared 가 false 로 "
                "뒤집히고, 그때는 표류로 걸리는 것이 맞다.",
    }


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=False, sort_keys=True))
