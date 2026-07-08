# lodestar-codegraph

소스코드(Java+Kotlin) → 정적 `codegraph.json` (노드/엣지/군집). Graphify 방식의 네이티브 구현.

## 설치
    pip install -e .[dev]

## 실행
    python -m lodestar_codegraph <source_root> -o out/codegraph.json

## 테스트
    pytest

산출물은 `out/`(gitignore). 스키마·설계: `docs/superpowers/specs/2026-07-07-e17-code-source-collector-design.md`.
