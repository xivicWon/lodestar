"""#123 — 런타임 의존성의 버전 고정이 **선언**돼 있는가.

군집 배정은 `networkx.community.louvain_communities` 가 만들고, 그 구현이 바뀌면
`nodes[].community`·`meta.community_count` 가 바뀐다 — 즉 `codegraph.json` 의 바이트가 달라진다.
#112 가 없앤 것은 같은 환경 안의 비결정(PYTHONHASHSEED)이고, **환경이 달라질 때의 재현성**은
선언으로만 막을 수 있다. 그래서 여기서 재는 것은 산출물이 아니라 `pyproject.toml` 의 선언이다.

`run-l0-code-*` 보고서는 `versions.collector: PINNED` 를 주장하고 `probe_code.py --check` 는
커밋된 산출물과의 바이트 대조로 표류를 판정한다 — 고정되지 않은 의존성은 그 두 주장의 사각지대다.
"""
from __future__ import annotations

import os
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
    # 부모 환경을 **상속**한 뒤 PYTHONPATH 만 덮어쓴다(`probe_code.run_collector()` 와 같은 방식).
    # 환경을 통째로 갈아끼우면 HOME·LANG 이 사라져 이 테스트만 플랫폼별로 갈린다. 타임아웃도 건다 —
    # 서브프로세스가 멈추면 테스트가 아니라 CI 가 멈춘다(LOD-180).
    p = subprocess.run([sys.executable, "-m", "lodestar_codegraph.deps"],
                       env=dict(os.environ, PYTHONPATH=SRC),
                       capture_output=True, text=True, timeout=60)
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
    """설치되지 않은 고정 의존성은 '일치' 가 아니다 — 없는 것을 같다고 적으면 재현 주장이 거짓이 된다.

    메시지 **문구**가 아니라 그 안에 있어야 할 사실(무엇이·무엇으로 선언됐고·설치가 없다)로 잰다 —
    문구에 완전 결합하면 무해한 표현 수정이 테스트를 깬다(LOD-154).
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\ndependencies = ["no-such-pkg==1.0.0"]\n')
    (msg,) = deps.pin_mismatches(pyproject)
    assert "no-such-pkg" in msg and "1.0.0" in msg and "없음" in msg


def test_extras_and_markers_do_not_hide_a_pin(tmp_path):
    """F2 — extras·마커가 붙어도 `==` 는 고정이다. 고정을 미고정으로 읽으면 거짓 경보가 된다."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "x"\ndependencies = ['
        "'uvicorn[standard]==0.30.0', "
        "'networkx==3.6.1 ; python_version>=\"3.11\"', "
        "'ranged[extra]>=1.0 ; sys_platform==\"darwin\"']\n")
    assert deps.declared_pins(pyproject) == {"uvicorn": "0.30.0", "networkx": "3.6.1"}
    # 미고정 판정은 extras·마커를 떼고 내리되, **선언 원문**으로 보고한다 — 원문이 있어야 고친다.
    assert deps.unpinned_dependencies(pyproject) == ['ranged[extra]>=1.0 ; sys_platform=="darwin"']


def test_conditional_dependency_is_not_silently_skipped(tmp_path):
    """마커가 붙은 의존성은 이 환경에서 설치 여부를 판정하지 않는다 — 대신 **목록으로 남긴다**.

    마커를 평가하지 않은 채 '설치 없음' 으로 세면 정상 환경이 불일치로 뒤집히고, 조용히 건너뛰면
    고정되지 않은 의존성이 검사 밖으로 사라진다. 판정하지 않았다는 사실 자체를 남긴다.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "x"\ndependencies = ['
        "'no-such-pkg==1.0.0 ; python_version<\"3.9\"']\n")
    assert deps.pin_mismatches(pyproject) == []
    r = deps.report(pyproject)
    assert r["conditionalDependencies"] == ['no-such-pkg==1.0.0 ; python_version<"3.9"']
    assert r["installedMatchesDeclared"] is True


#: 휠 설치본의 `Requires-Dist` 모양 — dev extra 가 함께 실린다.
_WHEEL_REQUIRES = ["tree-sitter==0.23.2", "tree-sitter-java==0.23.5",
                   "tree-sitter-kotlin==1.1.0", "networkx==3.6.1",
                   'pytest>=8.0; extra == "dev"']


@pytest.fixture
def wheel_install(monkeypatch):
    """소스 트리가 없고 설치 메타데이터만 있는 상태.

    주변에 설치된 것을 그대로 읽으면 테스트가 **엉뚱한 이유로** 통과한다 — 이 작업 중에 실제로
    낡은 0.1.0 설치(`networkx>=3.0`)와 빌드 부산물(egg-info)이 번갈아 잡혀 그랬다. 그래서 선언을
    주입해 판정 로직만 잰다. 휠 설치 자체가 도는지는 리포 밖 venv 로 따로 확인한다.
    """
    monkeypatch.setattr(deps, "_DEFAULT_PYPROJECT", pathlib.Path("/nonexistent/pyproject.toml"))
    monkeypatch.setattr(deps, "_dist_requires", lambda: list(_WHEEL_REQUIRES))


def test_pins_are_readable_without_a_source_tree(wheel_install):
    """F1 — 휠로 설치된 수집기에도 선언은 있다(`Requires-Dist`). 소스 트리가 없다고 죽지 않는다.

    `provenance._version()` 은 이미 같은 폴백을 가진다 — 두 모듈이 같은 상황에서 다르게
    행동하면, 재현 대상을 읽는 경로가 설치 방식에 따라 갈린다.
    """
    assert deps.declared_pins()["networkx"] == "3.6.1"
    assert deps.unpinned_dependencies() == []


def test_optional_dependencies_are_not_counted_as_runtime(wheel_install):
    """폴백 경로의 함정 — `Requires-Dist` 에는 dev extra(`pytest>=8.0`)도 들어 있다.

    걸러내지 않으면 개발 의존성이 런타임 미고정으로 잡혀, 고칠 수 없는 실패가 상시로 남는다.
    """
    assert "pytest" not in deps.declared_pins()
    assert not [r for r in deps.unpinned_dependencies() if "pytest" in r]


def test_a_foreign_installation_is_not_read_as_ours(monkeypatch):
    """같은 이름의 **다른 설치본**의 선언을 재현 대상으로 적지 않는다.

    낡은 설치가 남아 있으면 `importlib.metadata` 는 그쪽을 돌려준다. 그 선언을 그대로 쓰면
    이 파일이 지목하는 것은 이 산출물을 만든 코드가 아니게 된다 — 조용히 틀리느니 죽는 게 맞다.
    """
    monkeypatch.setattr(deps, "_DEFAULT_PYPROJECT", pathlib.Path("/nonexistent/pyproject.toml"))
    monkeypatch.setattr(deps, "_dist_requires", lambda: None)
    with pytest.raises(RuntimeError):
        deps.declared_pins()


@pytest.mark.parametrize("req", [
    "networkx",                              # 버전이 아예 없다 — 가장 열린 선언이다
    "pkg @ https://example.com/pkg.whl",     # 직접 참조 — `==` 가 아니다
    "networkx >= 3.0",                       # 연산자 앞뒤 공백
])
def test_a_dependency_without_a_pin_is_reported_not_raised(tmp_path, req):
    """고정되지 않은 선언은 **목록으로** 나와야 한다 — 예외로 죽으면 무엇이 문제인지 말하지 못한다.

    맨 이름(`networkx`)은 가장 열린 선언인데, 이걸 '해석 불가' 로 던지면 프로브가 "networkx 가
    고정되지 않았다" 대신 알 수 없는 오류로 죽는다. 판정할 수 있는 것은 판정해서 보고한다.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\ndependencies = ["%s"]\n' % req)
    assert deps.declared_pins(pyproject) == {}
    assert deps.unpinned_dependencies(pyproject) == [req]


def test_an_upper_bounded_range_is_still_unpinned(tmp_path):
    """상한이 있어도 범위는 범위다 — 상한 **안에서** 구현이 바뀔 자리가 남는다(정책의 명시 요구)."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\ndependencies = ["networkx>=3.0,<4.0"]\n')
    assert deps.declared_pins(pyproject) == {}
    assert deps.unpinned_dependencies(pyproject) == ["networkx>=3.0,<4.0"]


def test_the_same_package_pinned_twice_to_different_versions_is_refused(tmp_path):
    """LOD-181 — 같은 이름이 서로 다른 버전으로 두 번 선언되면 뒤가 앞을 덮어써 **조용히 사라진다**.

    이 PR 이 없애려던 것과 같은 부류다: 고정 선언 하나가 흔적 없이 없어지는데 목록도 불일치도
    비어 있어 아무 데도 걸리지 않는다.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "x"\ndependencies = ["networkx==3.1", "networkx==3.6.1"]\n')
    with pytest.raises(ValueError, match="networkx"):
        deps.declared_pins(pyproject)


def test_the_same_package_declared_twice_identically_is_not_an_error(tmp_path):
    """중복이되 **같은 값**이면 잃는 것이 없다 — 거짓 경보를 만들지 않는다."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "x"\ndependencies = ["networkx==3.6.1", "networkx==3.6.1"]\n')
    assert deps.declared_pins(pyproject) == {"networkx": "3.6.1"}


@pytest.mark.parametrize("req", ["== 3.6.1", "!!!"])
def test_declared_pins_rejects_a_dependency_it_cannot_name(tmp_path, req):
    """패키지 이름조차 읽히지 않으면 조용히 건너뛰지 않는다 — 건너뛰면 목록에서 사라진다."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\ndependencies = ["%s"]\n' % req)
    with pytest.raises(ValueError):
        deps.declared_pins(pyproject)
