# lodestar-codegraph

소스코드(Java+Kotlin) → 정적 `codegraph.json` (노드/엣지/군집). Graphify 방식의 네이티브 구현.

## 설치
    pip install -e .[dev]

## 실행
    python -m lodestar_codegraph <source_root> -o out/codegraph.json

## 테스트
    pytest

## 런타임 의존성 (#123)

`pyproject.toml` 의 런타임 의존성은 **전부 `==` 로 고정**한다. 산출물의 바이트가 그 목록에 달려
있기 때문이다 — 군집 라벨은 networkx 의 louvain 구현이, 파스 트리는 tree-sitter 문법이 만든다.
정책과 선언은 `lodestar_codegraph.deps` 가 읽고 `tests/test_deps.py` 가 검사한다.

    python -m lodestar_codegraph.deps    # 고정 선언 + 설치 환경과의 일치 여부

버전을 올릴 때는 `pyproject.toml` 에서 올리고, 산출물이 달라지는지 확인한 뒤 L0 프로브를 다시
남긴다 — 절차는 `docs/superpowers/specs/bench/l0/README.md` 의 "런타임 의존성 고정과 교차 버전 확인".

산출물은 `out/`(gitignore). 스키마·설계: `docs/superpowers/specs/2026-07-07-e17-code-source-collector-design.md`.

`--god-node-percentile`은 nearest-rank 방식으로 임계 degree를 구해 `degree ≥ threshold`인 노드를 god_node로 표시하므로, 노드 수가 적거나 동일 degree가 많은(tie-heavy) 그래프에서는 지정한 상위 N%보다 더 많은 노드가 플래그될 수 있다.
