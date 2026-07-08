# Lodestar E16 — 지식 Read-Model(SQLite) + MCP 서버 설계

> 작성일: 2026-07-07
> 상태: **설계 승인 대기 (아키텍처 확정, 스펙 리뷰용)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: P5(RDB→OWL), E2(이름 패턴 관계), E10(AI 판정), E13(근거 카드), E5(영속화), E8(세이브포인트), E15(SKOS 정렬)
> 착안: Graphify(코드 지식그래프)의 "AI가 grep 대신 그래프를 질의" 개념을, **개념만** 온톨로지 방식에 녹임

## 0. 배경 & 문제

Lodestar는 소스를 OWL 온톨로지로 복원한다(추론·SKOS·근거·확정). 하지만 이 지식을 **AI/도구가 질의**하려면:
- OWL/SPARQL은 무겁고, in-memory `OWLOntology`는 외부 도구가 못 붙는다.
- 현재 E6 채팅은 온톨로지 접근이 임시적(메모리의 "claude CLI subprocess").

Graphify는 "AI가 grep 대신 그래프를 본다"를 skill/hook(파일 가리키기)으로 어설프게 했다. Lodestar는
이를 **표준(MCP) + 빠른 저장(SQLite)** 으로 제대로 한다. 단 Graphify를 이식하지 않고 **개념만** 녹인다:
확정론적 추출 + 이름 추론 + 신뢰도 태깅은 Lodestar가 이미 DB판(E2/E13/E10)으로 가졌으니, **어휘·모델을
통일**하고 **조회층**을 새로 얹는다.

## 1. 핵심 아키텍처 = CQRS 분리

```
소스(DB/코드/문서)
 → Lodestar 수집 (EXTRACTED 공리 + INFERRED 후보 + 근거 + 신뢰도)
 → OWL 온톨로지            ← 진실원(write side): 추론·SKOS·계층·확정    [기존]
 → SQLite read-model 투영   ← 조회용(read side): 비정규화·인덱스        [E16 신규]
 → 독립 Python MCP 서버      ← .db 파일만 읽어 질의 도구 노출            [E16 신규]
 → AI(Claude 등)가 MCP 도구 호출
```

- **쓰기·추론 = OWL, 읽기·질의 = SQLite.** SQLite는 **순수 투영(read-model)** — 직접 수정 금지. 변경은 OWL에 하고 재투영.
- SQLite는 파일 하나 → **E5 영속화/E8 세이브포인트의 자연스러운 산출물**(프로젝트당 `.db`).

## 2. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | OWL=진실원, SQLite=파생 read-model (CQRS) | 추론·표준은 OWL 유지, 조회는 빠른 관계형. 단일 진실원 |
| D2 | SQLite는 **직접 수정 불가**, OWL 변경 후 **재투영**만 | 파생물이 진실원을 오염시키지 않게 |
| D3 | MCP 서버 = **독립 Python 프로세스**, `.db` 파일만 읽음 | JVM과 결합 최소, stdlib sqlite3 무의존, 이식 쉬움. (대안: Kotlin MCP SDK) |
| D4 | provenance **3단계 통일**: `EXTRACTED · INFERRED · AMBIGUOUS` (+ `kind`, `confidence`) | E2/E10/E13/E15를 한 척도로. Graphify 개념의 온톨로지-네이티브화 |
| D5 | MCP 도구는 **원시(primitive)** — 복합 추론은 AI가 조합 | Graphify BFS `query`보다 유연, 도구 단순 |
| D6 | 투영기는 **Kotlin 백엔드**가 담당(OWL→SQLite), MCP는 순수 리더 | OWL 접근은 JVM에만 있음. 역할 분리 |
| D7 | 도메인 = object property 그래프 **군집(Louvain)** 결과를 사람이 이름 확정 | Graphify 커뮤니티를 불투명 ID가 아닌 **명명·확정 모듈**로 승격 |
| D8 | MCP 서버는 **읽기 전용** — 온톨로지/DB 변경 도구 없음 | read-only 원칙, 안전 |

## 3. SQLite 스키마 (조회친화 비정규화)

```sql
-- 클래스(테이블→OWL 클래스)
CREATE TABLE class (
  iri         TEXT PRIMARY KEY,
  label       TEXT,
  orig_table  TEXT,            -- shortName(iri)
  domain_id   INTEGER,         -- 군집→도메인 (nullable)
  community   INTEGER,         -- 원시 군집 id
  degree      INTEGER,         -- 중심성(연결 수)
  confirmed   INTEGER          -- 의미복원 확정 여부(0/1)
);
-- 관계(object property)
CREATE TABLE relation (
  id          INTEGER PRIMARY KEY,
  from_iri    TEXT, to_iri TEXT,
  name        TEXT,            -- 관계 라벨
  kind        TEXT,            -- fk | namepattern | ai | manual | skos
  provenance  TEXT,            -- EXTRACTED | INFERRED | AMBIGUOUS
  confidence  REAL             -- 0..1
);
-- 근거(E13)
CREATE TABLE evidence (
  relation_id INTEGER,         -- FK relation.id
  match_type  TEXT, matched_on TEXT,
  alternatives_json TEXT, cardinality TEXT
);
-- SKOS 정렬(E15)
CREATE TABLE alignment (
  source_iri  TEXT, target_iri TEXT,
  match_type  TEXT,            -- EXACT|CLOSE|BROAD|NARROW|RELATED
  confidence  REAL, provenance TEXT
);
-- 도메인(E16-3)
CREATE TABLE domain (
  id INTEGER PRIMARY KEY, name TEXT, member_count INTEGER
);
CREATE TABLE meta ( key TEXT PRIMARY KEY, value TEXT );  -- 소스, 생성시각, 온톨로지 IRI 등
-- 인덱스
CREATE INDEX idx_rel_from ON relation(from_iri);
CREATE INDEX idx_rel_to   ON relation(to_iri);
CREATE INDEX idx_class_comm ON class(community);
CREATE INDEX idx_class_label ON class(label);
CREATE INDEX idx_class_table ON class(orig_table);
```

이웃/경로는 **recursive CTE**로 계산(MCP 서버가 SQL로). 저장은 스냅샷(투영 시점의 그래프).

## 4. 투영기 (OWL → SQLite) — Kotlin 백엔드

- **`ReadModelProjector`** (@Service): `OntologyHolder`의 OWL을 읽어 위 스키마로 SQLite(`org.xerial:sqlite-jdbc`) 파일에 쓴다.
  - class: `classesInSignature` + label + shortName + confirmations(E8) + degree(관계 수) + community(E16-3).
  - relation: object property → from/to + name + kind/provenance/confidence(공리 annotation에서, E16-0).
  - evidence: E13 근거(있으면).
  - alignment: E15 SKOS 매핑.
- **엔드포인트**: `POST /readmodel/project?path=<db경로>` → 지정 경로에 `.db` 생성/갱신. (기본 경로 = 프로젝트 영속화 디렉토리)
- **투영 시점**: 명시 호출 + (선택) import/confirm/정렬/군집확정 후 자동. 순수 파생이라 언제든 재빌드.

## 5. MCP 서버 (독립 Python) + 도구

- 위치: 리포 내 `mcp-server/`(별도 Python 프로젝트). 실행: `python -m lodestar_mcp --db <경로>` (또는 stdio MCP).
- 의존: 표준 `sqlite3` + `mcp`(FastMCP). **읽기 전용**.
- 환경/인자로 `.db` 경로 지정. 서버는 그 파일만 연다.

**도구 표면 (원시, 읽기 전용):**
| 도구 | 인자 | 반환 |
|---|---|---|
| `get_class` | iri | 라벨·원본테이블·도메인·확정·degree + 나가는/들어오는 관계 요약 |
| `neighbors` | iri, depth=1 | depth-hop 이웃 클래스 목록(관계명 포함) |
| `path` | from_iri, to_iri, max_depth=5 | 관계 경로(recursive CTE) 또는 없음 |
| `search` | term | 라벨·원본테이블명 부분매칭 클래스 |
| `domains` | — | 도메인 목록(이름·멤버수) |
| `list_domain` | name | 그 도메인 소속 클래스 |
| `hubs` | top=20 | degree 상위(코어 엔티티) |
| `evidence` | relation_id | E13 근거 상세 |
| `alignments` | iri | 그 클래스의 SKOS 매핑 |
| `stats` | — | 클래스/관계/도메인 수, provenance 분포, 생성시각 |

각 도구는 SQL 한두 방으로 응답. 복합 질문("인증 흐름")은 AI가 `search`→`neighbors`→`path` 조합.

## 6. Provenance 3단계 통일 (E16-0, 정지작업)

- 모든 관계/공리 생성 시 **kind + provenance + confidence**를 OWL axiom annotation으로 표준 기록:
  - FK 제약 → `EXTRACTED` (1.0), kind=`fk`
  - E2 이름 패턴 → `INFERRED` (E13 confidence), kind=`namepattern`; 대안 다수면 `AMBIGUOUS`
  - E10 AI 확정 → kind=`ai`
  - 수동 → kind=`manual`
  - E15 SKOS → alignment 테이블(별도), provenance 그대로
- Lodestar 메타 IRI 재사용/확장: `lodestar:confidence`, `lodestar:provenance`, 신규 `lodestar:kind`.
- **원칙(회귀 금지)**: name-match를 온톨로지 공리로 **단정하지 않음** — 후보→E13 근거→확정 게이트 통과 후에만 relation. 투영 규칙(확정): 온톨로지에 실재하는 관계는 **모두 투영**하되 `provenance`·`confidence`로 구분한다(INFERRED를 드롭하지 않음). 미확정 후보(candidate)는 애초에 OWL 관계가 아니므로 투영 대상 아님.

## 7. 도메인 군집 (E16-3, 병렬·선택)

- object property 그래프에 **Louvain**(networkx면 충분; graspologic 있으면 Leiden) → 군집.
- 군집을 **도메인 후보**로 제시(대표 라벨/디렉토리로 이름 제안) → 사람이 이름 확정(E8 패턴) → `domain` 테이블 + `class.domain_id` 반영.
- E15 SKOS와 직결: 도메인 단위로 외부 어휘 정렬 대상 좁히기.

## 8. 기존 자산과의 통합

| 기존 | E16에서 |
|---|---|
| E5 영속화 / E8 세이브포인트 | `.db`가 프로젝트별 read-model 산출물 |
| E6 AI Chat | (후속) 채팅을 MCP 클라이언트로 재구성 → 외부 AI와 같은 도구 공유 |
| E13 근거 | `evidence` 테이블 |
| E15 SKOS | `alignment` 테이블 |
| read-only 원칙 | MCP 읽기 전용, SQLite 순수 파생 |

## 9. 이슈 분해 (마일스톤 E16)

| 단계 | 이슈 | 범위 | 의존 |
|---|---|---|---|
| **E16-0** | provenance 3단계 어휘 통일 | 관계 생성 시 kind/provenance/confidence annotation 표준화 + 읽기 헬퍼 | — |
| **E16-1** | OWL→SQLite 투영기 + 스키마 | `ReadModelProjector`, `/readmodel/project`, sqlite-jdbc, 스키마·인덱스 | E16-0 |
| **E16-2** | 독립 Python MCP 서버 + 도구 | `mcp-server/`, FastMCP, 10개 도구, 읽기 전용 | E16-1 |
| **E16-3** | 도메인 군집(Louvain)→명명·확정 | 군집 계산 + 도메인 후보 UI/확정 + 투영 반영 | E16-1 (병렬) |

각 단계 독립 브랜치·PR. 품질 게이트: 백엔드 `./gradlew test`, MCP 서버 `pytest`, 프론트(해당 시) `vitest`+`vue-tsc`.

## 10. 테스트 전략 (TDD)

- **E16-0**: 관계 생성 후 axiom annotation에 kind/provenance/confidence가 기록·재조회되는지.
- **E16-1**: 알려진 소형 온톨로지 → 투영 → SQLite에 class/relation/alignment 행이 정확히 생성(개수·값). 재투영 멱등성.
- **E16-2**: 고정 `.db` 픽스처 → 각 MCP 도구가 기대 JSON 반환(get_class/neighbors/path/search/hubs…). 쓰기 도구 부재 확인.
- **E16-3**: 군집 함수가 소형 그래프를 기대 군집으로 분할.

## 11. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| read-model과 OWL 불일치(stale) | 순수 파생 + 명시/자동 재투영. `meta`에 생성시각·소스 해시 |
| SQLite JDBC 의존 추가 | `org.xerial:sqlite-jdbc`(경량, 표준). 테스트는 임시파일 |
| MCP 서버 배포/기동 복잡 | stdio MCP + `.db` 경로 인자 하나. 별도 프로세스라 백엔드와 독립 |
| name-match 노이즈가 read-model 오염 | E16-0 원칙: 확정된 관계만/`confirmed` 구분, INFERRED는 provenance로 명시 |

## 12. 스코프 밖 (후속)

- E6 채팅의 MCP 클라이언트화(별도).
- 코드/문서 소스 수집기(“구조화된 소스→온톨로지” 확장) — E16 read-model/MCP는 소스 무관하게 재사용 가능하도록 설계.
- MCP 쓰기 도구(정렬 제안 등) — 읽기 안정화 후.
- 실시간 투영(watch) — 지금은 명시/이벤트 트리거.
