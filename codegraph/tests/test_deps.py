"""#123 — 런타임 의존성의 버전 고정이 **선언**돼 있는가.

군집 배정은 `networkx.community.louvain_communities` 가 만들고, 그 구현이 바뀌면
`nodes[].community`·`meta.community_count` 가 바뀐다 — 즉 `codegraph.json` 의 바이트가 달라진다.
#112 가 없앤 것은 같은 환경 안의 비결정(PYTHONHASHSEED)이고, **환경이 달라질 때의 재현성**은
선언으로만 막을 수 있다. 그래서 여기서 재는 것은 산출물이 아니라 `pyproject.toml` 의 선언이다.

`run-l0-code-*` 보고서는 `versions.collector: PINNED` 를 주장하고 `probe_code.py --check` 는
커밋된 산출물과의 바이트 대조로 표류를 판정한다 — 고정되지 않은 의존성은 그 두 주장의 사각지대다.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

from lodestar_codegraph import deps

SRC = str(pathlib.Path(__file__).resolve().parents[1] / "src")


def test_every_runtime_dependency_is_exactly_pinned():
    """런타임 의존성은 전부 `==` 다 — 하나라도 범위면 재현 대상이 열려 있다."""
    assert deps.unpinned_dependencies() == [], (
        "범위로 선언된 런타임 의존성이 있다 — 그 버전이 바뀌면 산출물이 바뀔 수 있고, "
        "그 변화는 versions.collector 에도 --check 에도 잡히지 않는다: "
        f"{deps.unpinned_dependencies()}"
    )
    assert deps.declared_pins(), "런타임 의존성 선언이 비어 있다"


def test_networkx_is_pinned():
    """군집 라벨의 실제 생산자다 — 이 이슈(#123)가 지목한 의존성이 실제로 고정돼 있는지 본다."""
    assert "networkx" in deps.declared_pins()


def test_installed_environment_matches_the_declared_pins():
    """선언한 고정이 **이 실행 환경**과 같은가 — 다르면 지금 재는 것이 재현 대상이 아니다."""
    assert deps.pin_mismatches() == [], (
        "설치된 버전이 선언한 고정과 다르다 — 이 환경의 측정은 선언된 재현 대상의 측정이 아니다: "
        f"{deps.pin_mismatches()}"
    )


def test_cluster_runs_on_the_pinned_networkx():
    """군집을 만드는 모듈이 실제로 임포트한 networkx 가 고정 버전이다."""
    import networkx as nx

    assert nx.__version__ == deps.declared_pins()["networkx"]


def test_report_is_json_serializable_and_deterministic():
    """프로브가 산출물에 싣는 블록이다 — 실행마다 흔들리면 `--check` 가 상시 실패한다."""
    a, b = deps.report(), deps.report()
    assert a == b
    assert a["pinPolicy"] == "exact"
    assert a["dependencyPins"] == sorted(a["dependencyPins"])
    assert a["installedMatchesDeclared"] is True
    assert a["unpinnedDependencies"] == [] and a["installedMismatches"] == []


def test_report_is_readable_from_a_subprocess():
    """프로브는 수집기를 서브프로세스로 돌린다 — 같은 인터프리터에서 이 블록을 읽어올 수 있어야 한다."""
    p = subprocess.run([sys.executable, "-m", "lodestar_codegraph.deps"],
                       env={"PYTHONPATH": SRC, "PATH": "/usr/bin:/bin"},
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    import json
    assert json.loads(p.stdout) == deps.report()


def test_unpinned_declaration_is_detected(tmp_path):
    """규칙이 실제로 무는가 — 범위 선언을 넣으면 잡아야 한다."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "x"\ndependencies = ["networkx>=3.0", "tree-sitter==0.23.2"]\n')
    assert deps.unpinned_dependencies(pyproject) == ["networkx>=3.0"]
    assert deps.declared_pins(pyproject) == {"tree-sitter": "0.23.2"}


def test_missing_dependency_is_not_silently_matched(tmp_path):
    """설치되지 않은 고정 의존성은 '일치' 가 아니다 — 없는 것을 같다고 적으면 재현 주장이 거짓이 된다."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\ndependencies = ["no-such-pkg==1.0.0"]\n')
    assert deps.pin_mismatches(pyproject) == ["no-such-pkg: 선언 1.0.0 / 설치 없음"]


def test_declared_pins_rejects_a_dependency_it_cannot_read(tmp_path):
    """읽을 수 없는 선언을 조용히 건너뛰지 않는다 — 건너뛰면 고정되지 않은 의존성이 목록에서 사라진다."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\ndependencies = ["networkx ; python_version<\'3.9\'"]\n')
    with pytest.raises(ValueError):
        deps.declared_pins(pyproject)
