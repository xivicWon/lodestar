# P5. RDB → 온톨로지 변환 (SchemaToOwlMapper) v1 — 설계 문서

> 작성일: 2026-07-01
> 상태: **설계 승인됨 (구현 전)**
> 제품명: **Lodestar** (길 잃은 레거시의 길잡이 별) · 유저 페르소나: **Prospector**(탐광자) · 리포 코드네임: `onto-studio`
> 상위 제품 맥락: `Product-Definition-Draft.md` (Legacy DB Knowledge Recovery Platform)

## 0. 배경 & 목적

`Product-Definition-Draft.md`가 정의하는 "레거시 DB 지식 복원 플랫폼"의 첫 vertical slice.
제품의 핵심 난제(온톨로지 모델·추론·KG·직렬화)는 기존 onto-studio가 이미 갖고 있다.
**빠져 있는 것은 "DB → 온톨로지" 입력 파이프라인**이며, 이 문서는 그 파이프라인의 v1을 정의한다.

**v1의 목적(purpose-embedded):** 단순히 RDB를 보여주는 것이 아니라
"**테이블 간 관계를 온톨로지 구조로 복원하고, 사람이 의미를 보정하는 한 사이클**"을 실제로 경험하는 것.
이 경험을 토대로 v2(자동/AI 관계 추정, 그래프 시각화, 데이터 행, 다른 DB 벤더)를 설계한다.

**한 줄 정의:** "PostgreSQL 스키마를 **라이브 연결 또는 DDL 스크립트로** 읽어 테이블/컬럼/FK를
OWL 클래스/속성/관계로 변환하고, 기존 onto-studio 편집기에서 관계를 보정·저장하는 최소 파이프라인."

## 1. 핵심 결정 (Q&A로 확정)

| # | 결정 | 근거 |
|---|------|------|
| D1 | "관계 등록" = **테이블 간 관계** (컬럼·행 레벨 아님) | 사용자 확정 |
| D2 | 관계 출처 = **FK 제약 자동 생성 + 엔지니어 수동 보정** | 레거시 현실 대응. AI/자동 추정은 v2 |
| D3 | 온톨로지 범위 = **스키마만 (TBox)**, 행 데이터(ABox) 제외 | 데이터 폭발 회피, "구조·관계 복원"에 집중 |
| D4 | DB 입력 = **두 경로 모두 지원** — (A) 라이브 JDBC 연결(PostgreSQL 1종) + (B) DDL 스크립트 업로드 | DB 접속 없이도 스키마 등록 가능(B). 두 경로 모두 동일 `SchemaModel`로 수렴하므로 매퍼는 불변 |
| D5 | 표시 = **관계 목록 + 클래스별 관계 패널** (그래프 아님) | 관계가 데이터로 정확히 잡히는지 먼저 검증. 그래프는 v2 |
| D6 | 관계 수동 보정 = **기존 PropertyController API 재사용** (신규 개발 없음) | 재사용 설계의 핵심 배당금 |

## 2. 아키텍처 & 데이터 흐름

핵심 원칙: **SchemaToOwlMapper의 출력 = 기존 onto-studio가 이미 다루는 `OWLOntology`.**
새로 만드는 것은 "DB → 온톨로지" 입력 파이프라인뿐이며, 이후(편집·추론·저장·표시)는 기존 자산 재사용.

```
경로 A) [PostgreSQL]                          경로 B) [DDL 스크립트 (CREATE TABLE ...)]
   │ 접속정보                                      │ SQL 텍스트
   ▼                                              ▼
DbConnector ─► JDBC Connection               DdlParser (JSqlParser)   ← 신규
   │ DatabaseMetaData 스캔                        │ CREATE TABLE / FK 파싱
   ▼                                              ▼
MetadataService ─► SchemaModel  ◄───── 두 경로가 동일 SchemaModel로 수렴 ─────►  SchemaModel
                        │  { tables[], columns[], primaryKey, foreignKeys[] }   ← 신규, 순수 데이터
                        │ 변환
                        ▼
                SchemaToOwlMapper ─► OWLOntology (table→Class, column→DataProp, FK→ObjectProp)  ← 신규, 심장
                        │ 주입
                        ▼
OntologyHolder (기존) ◄── 여기부터 전부 재사용 ──►
   ├─ ClassController / PropertyController (기존)  → 관계 수동 추가·수정
   ├─ ReasonerController (기존 HermiT)             → 일관성·분류
   ├─ IoService (기존)                             → Turtle 저장
   └─ Vue3 트리 + 편집폼 (기존)                    → 표시·편집
                                                    + RelationView (신규, 최소 목록/패널)
```

**결정 근거:** 매퍼가 `OntologyHolder`에 온톨로지를 채우는 순간, 관계(ObjectProperty)
추가/수정/이름부여는 이미 존재하는 PropertyController API로 그대로 동작한다.
→ "수동 보정" 기능을 새로 만들 필요가 없다.

## 3. 백엔드 신규 컴포넌트

기존 패키지 관례(`com.ontostudio.*`)를 따라 새 패키지 `com.ontostudio.rdb`를 추가한다.

### 3.1 데이터 모델 (`rdb/SchemaModel.kt`)
DB에서 읽은 날것의 스키마. OWL 지식 없음, 순수 Kotlin data class:

```kotlin
data class SchemaModel(val tables: List<TableInfo>)
data class TableInfo(
    val name: String, val columns: List<ColumnInfo>,
    val primaryKey: List<String>,                        // PK 컬럼명들
    val foreignKeys: List<ForeignKeyInfo>
)
data class ColumnInfo(val name: String, val sqlType: String, val nullable: Boolean)
data class ForeignKeyInfo(
    val fkColumns: List<String>,                         // 이 테이블의 컬럼
    val refTable: String, val refColumns: List<String>   // 가리키는 대상
)
```

입력 소스는 두 가지(라이브 DB / DDL 스크립트)이며, 둘 다 `SchemaModel`을 산출한다.

### 3.2 `DbConnector` (경로 A — 라이브 DB)
접속정보(host/port/db/user/password) → JDBC `Connection`.
PostgreSQL 드라이버 의존성 추가. 연결 실패는 명확한 에러 DTO로 (기존 `dto/Errors.kt` 관례).

### 3.3 `MetadataService` (경로 A — 라이브 DB)
`Connection` → `SchemaModel`.
`DatabaseMetaData.getTables / getColumns / getPrimaryKeys / getImportedKeys` 표준 API 사용.
**이 단계까지 OWL 개념이 전혀 없음** — 순수 추출, 테스트 용이.

### 3.3b `DdlParser` (경로 B — DDL 스크립트)
`CREATE TABLE ...` SQL 텍스트 → `SchemaModel`.
검증된 **JSqlParser** 라이브러리로 파싱 (직접 파서 구현 회피).
- `CREATE TABLE` → TableInfo, 컬럼 정의 → ColumnInfo (타입은 SQL 원문 문자열 보존)
- `PRIMARY KEY (...)` → primaryKey
- `FOREIGN KEY (...) REFERENCES t(...)` (테이블 제약 + 컬럼 인라인 `REFERENCES` 둘 다) → ForeignKeyInfo
- 파싱 불가 구문(트리거·함수 등)은 건너뛰고 경고 수집 (전체 실패 아님)
**경로 A와 완전히 동일한 `SchemaModel`을 산출** → 이후 매퍼·주입은 소스와 무관하게 동일.

### 3.4 `SchemaToOwlMapper` (심장)
`SchemaModel` → OWL API로 `OWLOntology` 구성. 매핑 규칙은 §4.
**핵심 단위 테스트 대상** (SchemaModel 입력 → 기대 OWL 공리 검증, DB 불필요).

### 3.5 `RdbImportController`
입력 소스별 엔드포인트 2개. 둘 다 `SchemaModel` 확보 → SchemaToOwlMapper → `OntologyHolder` 주입 →
`OntologyMetaDto`(기존) 반환. 이후 클라이언트는 기존 API로 온톨로지를 다룬다.
- `POST /api/rdb/import/connection` : 접속정보 → 3.2 → 3.3 → SchemaModel
- `POST /api/rdb/import/ddl` : SQL 텍스트 → 3.3b → SchemaModel

두 엔드포인트는 SchemaModel 확보 이후 로직(3.4 매핑 + 주입)을 공유한다.

**경계가 깔끔한 이유:** DbConnector(연결)·MetadataService(추출)·DdlParser(파싱)·SchemaToOwlMapper(변환)가
각각 한 가지 일만 하고, `SchemaModel`이라는 순수 데이터로만 소통 → 매퍼·입력소스가 서로 독립적으로 테스트 가능.

## 4. 매핑 규칙 (SchemaToOwlMapper 상세)

Base IRI: `http://onto-studio/rdb/{db이름}#`. 이름은 IRI-안전하게 변환.

**규칙 1 — 테이블 → 클래스**
- 테이블 `T` → `owl:Class` IRI `:T`
- `rdfs:label` = 원본 테이블명 (표시용 원형 보존)

**규칙 2 — 일반 컬럼(비-FK) → DataProperty**
- 컬럼 `T.c` → `owl:DatatypeProperty` IRI `:T.c` (테이블명 접두로 충돌 방지)
- `rdfs:domain = :T`, `rdfs:range` = SQL타입→XSD 매핑
  (varchar→xsd:string, int→xsd:integer, numeric→xsd:decimal,
   timestamp→xsd:dateTime, bool→xsd:boolean, 그 외→xsd:string + 주석)
- `rdfs:label` = 원본 컬럼명

**규칙 3 — FK → ObjectProperty (테이블 간 관계, 핵심)**
- FK(`Order.customer_id → Customer.id`) → `owl:ObjectProperty` IRI `:Order_customer_id_ref` (결정론적 이름)
- `rdfs:domain = :Order`, `rdfs:range = :Customer`
- `rdfs:label` = `"Order → Customer (customer_id)"` (사람이 나중에 "placedBy"로 바꿀 초안)
- **FK 컬럼 자체는 DataProperty로 중복 생성하지 않음** (관계로만 표현) — 물리 흔적이 아닌 의미 관계로 승격

**규칙 4 — PK → 주석으로만 기록**
- v1은 개체(행) 없음 → PK로 식별자 만들 필요 없음.
- 각 클래스에 `rdfs:comment "PK: id"` 로 흔적만 남김 (v2에서 개체 IRI 생성에 사용)

**결정론적 이름 규칙의 중요성:** 같은 DB를 재임포트하면 같은 IRI가 나와야,
사람이 붙인 의미 라벨/수정이 재임포트 후에도 매칭될 수 있다 (v2 재동기화 토대).

**엣지 케이스 v1 처리**
- 복합 FK(여러 컬럼) → ObjectProperty 하나, 라벨에 컬럼 나열
- 자기참조 FK(`employee.manager_id → employee`) → domain=range=같은 클래스 (허용)
- FK 없는 테이블 → 클래스만 생성, 관계 없음 (사람이 수동 추가 대상)
- 뷰(View) → **v1 제외** (테이블만)

## 5. 관계 등록 (자동 + 수동)

**자동 등록** — §4 규칙 3이 곧 자동 등록. 임포트 시 FK가 전부 ObjectProperty로 생성. 사람 개입 0.

**수동 등록/보정 — 새 백엔드 코드 없이 기존 API 재사용:**

| 사람이 하고 싶은 것 | 사용하는 기존 기능 |
|---|---|
| FK 없던 숨은 관계 추가 (예: `emp.dept_no ↔ dept.no`) | `PropertyController`로 새 ObjectProperty 생성 (domain=Emp, range=Dept) |
| 관계에 의미 이름 부여 (`placedBy`, "주문 접수자") | 기존 라벨/rename 편집 |
| 역관계 등록 (`placedOrders`) | 기존 `inverseOf` 필드 (ObjectPropertyDto에 존재) |
| 관계 특성 (functional, transitive 등) | 기존 characteristics 필드 |
| 오탐 FK 관계 삭제 | 기존 property 삭제 |

→ v1의 "수동 보정"은 신규 백엔드 개발이 사실상 없다. 프론트에 편집 진입점만 확보하면 된다.

## 6. 표시 (안 A — 목록 + 클래스별 관계 패널)

현재 프론트는 클래스 트리 중심이고 ObjectProperty 표시가 약함. v1에 최소 표시를 추가:

1. **전체 관계 목록** — ObjectProperty를 `도메인 → 레인지 : 라벨` 형태 테이블로 나열
2. **클래스별 관계 패널** — 클래스 선택 시 "나가는 관계 / 들어오는 관계" 표시
3. **RDB 임포트 화면** — 탭 2개: (A) 접속정보 입력 폼 → `/api/rdb/import/connection`, (B) DDL 텍스트 붙여넣기/파일 → `/api/rdb/import/ddl`. 완료 후 트리/관계 표시로 전환

그래프 시각화(노드-엣지)는 **v2** — A를 써본 경험으로 시각화 방향을 결정 (되돌리기 비싼 결정을 미룸).

## 7. 범위 경계

**v1 In Scope**
- 입력 2경로: (A) PostgreSQL JDBC 라이브 연결, (B) DDL 스크립트(CREATE TABLE) 업로드 — 둘 다 동일 SchemaModel로 수렴
- 테이블→클래스, 컬럼→DataProperty, FK→ObjectProperty 변환 (TBox only)
- 기존 `OntologyHolder` 주입 → 기존 편집/추론/Turtle저장 재사용
- 관계 자동(FK) + 수동(기존 Property API)
- 프론트: 관계 목록 + 클래스별 관계 패널, RDB 임포트 화면

**v1 Out of Scope (v2 이후)**
- 다른 DB 벤더 (드라이버만 추가하면 확장)
- 행 데이터 → 개체(ABox)
- 뷰, 저장프로시저, 인덱스 의미화
- AI/자동 관계 추정, 재임포트 시 사람 수정본 병합/충돌 해결
- 관계 그래프 시각화
- Lineage / Impact Analysis / AI Chat / 문서 생성 (제품 정의의 나머지)

## 8. 테스트 전략

- `MetadataServiceTest`: 임베디드/컨테이너 PostgreSQL에 샘플 스키마 → SchemaModel 검증 (경로 A)
- `DdlParserTest`: **순수 단위 테스트** — 샘플 DDL 문자열 → SchemaModel 검증 (테이블·PK·FK·인라인 REFERENCES). DB 불필요 (경로 B)
- `SchemaToOwlMapperTest`: **순수 단위 테스트** — SchemaModel 입력 → OWL 공리(클래스 수, ObjectProperty domain/range, DataProperty range) 검증. DB 불필요, 핵심 회귀 안전망
- **동치성 테스트**: 같은 스키마를 경로 A(라이브 DB)와 경로 B(DDL)로 넣으면 동일한 SchemaModel(따라서 동일 온톨로지)이 나오는지 확인
- `RdbImportControllerTest`: 두 엔드포인트 임포트 후 기존 `/api/classes` 등이 정상 응답
- 프론트: 관계 목록/패널 컴포넌트 테스트, 임포트 화면 테스트

## 9. 성공 기준 (v1 완료 정의)

1. 샘플 스키마(customers/orders/order_items 등 3~4테이블 + FK)를 **라이브 DB와 DDL 스크립트 양쪽**으로 임포트 → 동일한 클래스·관계 정확히 생성
2. 자동 생성된 관계를 기존 편집기에서 이름 변경(`placedBy`)하고 새 관계 수동 추가 가능
3. Turtle로 저장 → Protégé에서 정상 로드 (기존 성공기준 계승)
4. 관계 목록/클래스별 관계 패널에서 "테이블 간 관계"가 눈에 보임

## 10. 미해결 질문 (v2에서 다룸)

- 자동/AI 관계 추정을 어떻게 할 것인가 (이름 규칙 기반 후보 제안 → 사람 승인 루프)
- 재임포트 시 사람이 붙인 의미(라벨/수동관계)를 어떻게 보존·병합할 것인가
- 관계 시각화의 최적 형태 (그래프 vs ERD vs 하이브리드)
- 스키마→논리모델(정규화 역추론) 단계를 별도로 둘 것인가
