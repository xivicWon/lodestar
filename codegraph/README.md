# lodestar-codegraph

소스코드(Java+Kotlin) → 정적 `codegraph.json` (노드/엣지/군집). Graphify 방식의 네이티브 구현.

## 설치
    pip install -e .[dev]

## 실행
    python -m lodestar_codegraph <source_root> -o out/codegraph.json

## 테스트
    pytest

산출물은 `out/`(gitignore). 스키마·설계: `docs/superpowers/specs/2026-07-07-e17-code-source-collector-design.md`.

`--god-node-percentile`은 nearest-rank 방식으로 임계 degree를 구해 `degree ≥ threshold`인 노드를 god_node로 표시하므로, 노드 수가 적거나 동일 degree가 많은(tie-heavy) 그래프에서는 지정한 상위 N%보다 더 많은 노드가 플래그될 수 있다.
