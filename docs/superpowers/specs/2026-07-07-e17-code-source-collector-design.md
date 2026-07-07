# Lodestar E17 — 코드 소스 수집기 (Code Source Collector)

> 작성일: 2026-07-07
> 상태: **설계 승인 대기 (스펙 리뷰용)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: E16(read-model/MCP). E16 스펙 line 185 "코드/문서 소스 수집기 — 후속"의 실현.
> 착안: Graphify의 **노드화 방식**(tree-sitter 근사 AST → 노드/엣지 → 군집)을 **직접 구현**. Graphify를 호출하지 않음.

## 0. 배경 & 문제

Lodestar의 기존 수집기는 **DB 스키마→OWL**(`DdlParser`/`SchemaToOwlMapper`)뿐이다. 소스 **코드**를 지식 그래프로
가져오는 경로는 없다. E16은 이를 "스코프 밖(후속)"으로 명시했다(line 185).

앞서 "Graphify 방식을 가져와 구현" 요청은 E16에서 **개념만**(provenance 3단계, 커뮤니티→도메인) 녹였고,
**코드를 노드화하는 추출 방식 자체**는 구현되지 않았다. E17이 그 조각을 채운다: Lodestar가 **직접** 소스 코드를
파싱해 노드/엣지로 만들고, Graphify의 `graph.json`에 해당하는 **정적 파일 `codegraph.json`** 을 산출한다.

## 1. 범위 경계 (중요)

```
소스코드 트리
 → [E17: 코드 수집기]  tree-sitter 근사 AST → 노드/엣지 → 호출해석 → 군집/degree
 → codegraph.json      ← 정적 산출물 (이 스펙의 최종 결과물)
 ─────────────────────  ✂  여기까지가 E17
 → (후속 별도 이슈) SQLite 적재 / OWL 정본 반영 / MCP 노출
```

- ✅ **포함**: 소스 walk → 파싱 → 노드/엣지 추출 → 호출 provenance 해석 → Louvain 군집·degree·god-node → `codegraph.json` 쓰기. `.codegraphignore` 지원. pytest 검증.
- ❌ **제외(후속)**: `codegraph.json → SQLite` 적재, OWL 반영, MCP. (사용자 지시: "정적 파일 먼저, 그 이후에 sqlite에 넣는다")
- ❌ **제외**: 실행/런타임 콜그래프(동적 분석), 타입 완전 해석(컴파일러급). E17은 Graphify처럼 **근사 정적** 분석.

## 2. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | **Python + tree-sitter** 로 구현 | Graphify 방식 그대로. Java/Kotlin(및 확장 언어) 근사 파싱이 싸고 언어무관. E16-2 MCP(Python)와 스택 일치 |
| D2 | 리포 루트 **`codegraph/`** (별도 Python 프로젝트, `backend/`·`frontend/`와 형제) | A안 확정. 산출물이 정적 파일이라 백엔드와 결합 없음 |
| D3 | 산출물 = 정적 **`codegraph.json`**, 기본 `./codegraph-out/`, `-o`로 override | Graphify `graph.json` 관례. 파일 하나로 후속 단계에 넘김 |
| D4 | JSON 스키마를 **E16 SQLite class/relation과 정렬** | 후속 적재가 단순 매핑이 되도록 |
| D5 | 노드 granularity = **file · type · function** 3단계 | Graphify처럼 함수 단위까지. 필드/프로퍼티는 v1 제외(YAGNI) |
| D6 | 호출 해석 provenance = **EXTRACTED / INFERRED / AMBIGUOUS** | E16-0 어휘 재사용. 정밀도를 버리지 않고 신뢰도로 표기 |
| D7 | 군집 = **Louvain**(networkx), god-node = degree 상위 | E16 D7과 동일 철학. 커뮤니티를 도메인 후보로 승격 준비 |
| D8 | 대상 언어 v1 = **Java + Kotlin** (vtm/api) | 실제 테스트 대상. 문법 추가로 확장 가능하게 설계 |

## 3. 산출 파일 스키마 (`codegraph.json`)

```json
{
  "meta": {
    "source_root": "/abs/path/to/vtm/api",
    "languages": ["java", "kotlin"],
    "generated_by": "lodestar-codegraph v1",
    "node_count": 0,
    "edge_count": 0,
    "community_count": 0
  },
  "nodes": [
    {
      "id": "type:com.x.FooService",         // 안정적 고유 id: "<kind>:<qualified_name>"
      "kind": "file | type | function",
      "label": "FooService",                  // 짧은 이름
      "qualified_name": "com.x.FooService",   // type/function; file은 상대경로
      "path": "vtm-api/src/main/kotlin/com/x/FooService.kt",
      "lang": "kotlin",
      "community": 12,                         // Louvain 군집 id (nullable)
      "degree": 7,                             // in+out 연결 수
      "god_node": false                        // degree 상위 임계 초과 여부
    }
  ],
  "edges": [
    {
      "id": 1,
      "from": "function:com.x.FooService.create",
      "to": "function:com.x.Repo.save",
      "kind": "contains | imports | extends | implements | calls",
      "provenance": "EXTRACTED | INFERRED | AMBIGUOUS",
      "confidence": 0.6,                       // 1.0=EXTRACTED, <1=이름해석, 후보수로 감쇠
      "alternatives": ["function:com.y.Repo.save"]  // AMBIGUOUS일 때 후보 id들 (없으면 [])
    }
  ]
}
```

**id 규칙**: `file:<상대경로>`, `type:<FQN>`, `function:<FQN.메서드명>`. 파싱으로 FQN 확정 불가 시 파일경로 기반 fallback id.

## 4. 추출 파이프라인 (`codegraph/`)

```
lodestar_codegraph/
  __main__.py          # CLI: python -m lodestar_codegraph <root> [-o out] [--lang ...]
  walk.py              # 소스 트리 walk + .codegraphignore 적용 + 언어 판별(확장자)
  parse.py             # tree-sitter 로더(java/kotlin 문법) → 파일별 AST
  extract.py           # AST → 노드(file/type/function) + 구조 엣지(contains/imports/extends/implements)
  resolve.py           # calls 엣지 해석 → provenance/confidence/alternatives
  cluster.py           # networkx 그래프 구성 → Louvain 군집 + degree + god-node 태깅
  emit.py              # codegraph.json 직렬화
  model.py             # Node/Edge dataclass + 스키마
tests/
  fixtures/            # 소형 Java/Kotlin 샘플 트리
  test_extract.py test_resolve.py test_cluster.py test_emit.py
pyproject.toml         # 의존: tree-sitter, tree-sitter-java, tree-sitter-kotlin, networkx
.codegraphignore       # (선택) 대상 리포에 두거나 --ignore로
```

### 4.1 walk (`walk.py`)
- source_root 하위 재귀. `.codegraphignore`(gitignore 문법) 적용. 확장자로 언어 판별(`.java`→java, `.kt`/`.kts`→kotlin).
- 산출: `(path, lang, source_bytes)` 목록.

### 4.2 parse (`parse.py`)
- tree-sitter 문법을 언어별로 로드. 파일당 1회 파싱 → concrete syntax tree.
- 파싱 실패(문법 오류) 파일은 **스킵 + meta.skipped에 기록**(무시하지 않음).

### 4.3 extract (`extract.py`) — 노드 + 구조 엣지 (전부 EXTRACTED)
- **file 노드**: 파일마다 1개.
- **type 노드**: class/interface/object/enum 선언. FQN = package + 이름(중첩 시 `Outer.Inner`).
- **function 노드**: method/function/constructor 선언. FQN = type FQN + 메서드명(오버로드는 파라미터 arity 접미사).
- **contains 엣지**: file→type, type→function (구조적, EXTRACTED, confidence=1.0).
- **imports 엣지**: import 문 → 대상 FQN. 대상이 이번 수집 트리 안의 type이면 file→type 엣지, 밖이면 외부 노드 생략(내부 그래프만). (EXTRACTED)
- **extends/implements 엣지**: type→상위 type (내부에 있으면). (EXTRACTED)

### 4.4 resolve (`resolve.py`) — calls 엣지 (provenance 핵심)
호출 표현식(`obj.method(...)`, `method(...)`)을 함수 노드로 해석:
- **EXTRACTED (1.0)**: 같은 파일/같은 type 내 정의로 명확히 해석, 또는 import된 단일 type의 메서드로 유일 해석.
- **INFERRED (0.4~0.8)**: 리시버 타입 미상. 메서드명이 전역 function 노드 중 **정확히 1개**와 매칭 → 그 노드. confidence는 매칭 유일성/이름 특이성으로.
- **AMBIGUOUS (≤0.4)**: 메서드명이 **여러** function 노드와 매칭 → 최빈/최근접 후보를 `to`, 나머지는 `alternatives[]`. 매칭 0개면 엣지 생성 안 함(외부/표준라이브러리 호출로 간주, meta 카운트).
- **원칙(E16-0 준수)**: 애매한 호출을 확정 관계로 단정하지 않음 — provenance로 명시하고 confidence로 감쇠.

### 4.5 cluster (`cluster.py`)
- 모든 노드/엣지로 networkx 무방향 그래프 구성(가중치=confidence 합).
- **Louvain**(`networkx.community.louvain_communities`) → 각 노드 `community` id.
- `degree` = 무방향 연결 수. `god_node` = degree가 상위 백분위(기본 상위 1% 또는 절대 임계, 설정값) 초과.

### 4.6 emit (`emit.py`)
- 노드/엣지/메타를 §3 스키마로 직렬화. 결정적 정렬(id 순)로 재현성 확보. `-o` 경로에 쓰기(기본 `./codegraph-out/codegraph.json`).

## 5. CLI

```bash
python -m lodestar_codegraph <source_root> \
  [-o <out.json>]              # 기본 ./codegraph-out/codegraph.json
  [--lang java,kotlin]         # 기본 자동판별
  [--ignore <file>]            # 기본 <source_root>/.codegraphignore
  [--god-node-percentile 99]   # god-node 임계

# vtm/api 테스트:
python -m lodestar_codegraph \
  /Users/wonjaeho/Workspace/withnetworks/withVTM2.0/api \
  -o /Users/wonjaeho/Workspace/onto-studio/codegraph/out/vtm-api.codegraph.json
```

산출물: **`onto-studio/codegraph/out/vtm-api.codegraph.json`**.

## 6. 테스트 전략 (TDD, pytest)

- **fixtures/**: 소형 Java+Kotlin 트리(2~3 type, 상호 호출/상속/import 포함, 애매 호출 1건).
- `test_extract`: 파일/타입/함수 노드 수·FQN·contains/imports/extends 엣지 정확.
- `test_resolve`: 명확 호출=EXTRACTED, 이름 유일=INFERRED, 다중후보=AMBIGUOUS(+alternatives), 외부호출=엣지 없음.
- `test_cluster`: 알려진 소형 그래프 → 기대 군집 분할, degree/god-node 계산.
- `test_emit`: 스키마 유효성 + 재현성(동일 입력 → 바이트 동일 출력).
- **재현성**: `Math.random`/시각 미사용, 정렬 결정적.

## 7. E16과의 정렬 (후속 적재 대비, 구현 안 함)

| codegraph.json | E16 SQLite | 매핑 |
|---|---|---|
| node(kind=type/function/file) | `class` | id→iri, label, community, degree |
| edge(kind, provenance, confidence) | `relation` | from/to, kind, provenance, confidence |
| edge.alternatives | `evidence` | AMBIGUOUS 후보 |
| community | `domain` (E16-3) | 군집→도메인 후보 |

→ 후속 이슈는 이 파일을 읽어 E16 스키마로 넣기만 하면 됨(파서 재실행 불필요).

## 8. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| tree-sitter Kotlin 문법 미성숙/노드타입 상이 | 문법별 노드타입을 `parse.py`에 매핑 테이블로 격리. 실패 파일은 skip+기록 |
| 이름기반 호출 해석 노이즈 | provenance/confidence로 명시, AMBIGUOUS 분리. 확정 아님 |
| 대형 리포 성능(vtm/api 수천 파일) | 파일 단위 파싱(스트리밍), 그래프는 메모리 내 1회 구성. 필요시 후속 최적화 |
| Java/Kotlin 외 언어 요구 | 문법 추가로 확장 가능하게 walk/parse 분리 |

## 9. 이슈 분해 (마일스톤 E17)

| 단계 | 이슈 | 범위 | 의존 |
|---|---|---|---|
| **E17-1** | 스캐폴드 + walk + parse | `codegraph/` 프로젝트, CLI, 트리 walk, tree-sitter 로더, `.codegraphignore` | — |
| **E17-2** | 노드 + 구조 엣지 추출 | file/type/function 노드, contains/imports/extends/implements | E17-1 |
| **E17-3** | calls 해석 (provenance) | EXTRACTED/INFERRED/AMBIGUOUS + confidence + alternatives | E17-2 |
| **E17-4** | 군집 + emit | Louvain/degree/god-node, codegraph.json 직렬화, 재현성 | E17-3 (모든 엣지 확정 후) |

각 단계 독립 커밋. 품질 게이트: `pytest` 그린. 순차 의존(E17-1→2→3→4); emit은 calls 포함 전체 엣지가 있어야 완전.

## 10. 스코프 밖 (후속 에픽)

- `codegraph.json → SQLite` 적재 (E16 read-model에 코드 그래프 합류).
- OWL 정본 반영(코드 노드를 온톨로지 클래스로) — 필요 시.
- 문서/기타 소스 수집기.
- 증분/watch 재수집.
