# P1 — 백엔드 코어 + 입출력 상세 설계

> 작성일: 2026-07-01
> 상태: **설계 중 (구현 전)**
> 상위 문서: [2026-07-01-onto-studio-design.md](./2026-07-01-onto-studio-design.md)

## 0. P1의 목표

상위 설계의 **Phase 1**. 프론트엔드 없이 **백엔드 단독으로 동작·검증 가능한** 온톨로지 코어 API.

> **원칙: 점진적 구현.** P1 안에서도 "기본부터 동작하게" 단계를 쪼갠다.
> 초안(P1.1~P1.4)은 핵심 CRUD가 돌아가는 것이 목표, 부가 기능(P1.5)은 그 뒤.

**P1 완료 정의(Definition of Done):**
- 표준 OWL 파일(pizza.owl)을 로드 → 클래스/속성/개체를 JSON으로 조회 가능
- REST API로 클래스/속성/개체를 추가·수정·삭제
- 다시 Turtle로 저장 → Protégé에서 정상 로드(라운드트립 검증)
- (추론·AI·프론트는 P1 범위 아님)

## 1. 범위 (Scope)

### 포함
- 온톨로지 생명주기: 새로 만들기 / 로드(파일 업로드) / 저장(다운로드) / 메타데이터 조회
- 클래스 CRUD + subclass 계층
- 속성 CRUD: Object / Data / Annotation Property (domain·range·characteristics)
- 개체(Individual) CRUD + 타입 지정 + property assertion
- 어노테이션(rdfs:label, rdfs:comment) 편집
- 검색 / Usage 조회 (P1.5)

### 제외 (다른 Phase)
- 추론(P3), AI 린트(P4), 프론트엔드(P2)
- 멀티 온톨로지 동시 편집, 인증, DB 영속성 → P1은 **단일 온톨로지 인메모리** 가정

## 2. 기술 구성

- **언어/런타임**: Kotlin, JDK 17+
- **프레임워크**: Spring Boot 3 (spring-web)
- **온톨로지 라이브러리**: OWL API 5.x (`org.semanticweb.owlapi`)
- **빌드**: Gradle (Kotlin DSL)
- **테스트**: JUnit 5 + Spring MockMvc

## 3. 모듈 구조

```
backend/
├─ build.gradle.kts
└─ src/main/kotlin/com/ontostudio/
   ├─ OntoStudioApplication.kt        # Spring Boot 진입점
   ├─ core/
   │  ├─ OntologyHolder.kt            # 인메모리 OWLOntology + OWLOntologyManager (단일 상태)
   │  ├─ IriFactory.kt                # baseIri + fragment로 IRI 생성/파싱
   │  └─ OntologyMapper.kt            # OWLObject ↔ DTO 변환
   ├─ io/
   │  └─ IoService.kt                 # load/save (Turtle, RDF/XML), 포맷 감지
   ├─ ontology/
   │  ├─ ClassService.kt              # 클래스 CRUD + 계층
   │  ├─ PropertyService.kt           # object/data/annotation property CRUD
   │  ├─ IndividualService.kt         # 개체 CRUD + assertion
   │  └─ SearchService.kt             # 검색/usage
   ├─ api/
   │  ├─ OntologyController.kt        # /api/ontology...
   │  ├─ ClassController.kt           # /api/classes...
   │  ├─ PropertyController.kt        # /api/properties...
   │  ├─ IndividualController.kt      # /api/individuals...
   │  └─ SearchController.kt          # /api/search...
   └─ dto/                            # 요청/응답 DTO (data class)
```

설계 원칙(상위 문서): 각 Service는 **하나의 책임**, Controller는 얇게(검증+위임),
모델 변경은 모두 `OntologyHolder`를 통해서만.

## 4. 데이터 모델 (DTO)

모든 엔티티의 식별자는 **IRI**(문자열). `label`은 표시용(rdfs:label).

```kotlin
// 공통
data class AnnotationDto(val property: String, val value: String, val lang: String? = null)

// 클래스
data class ClassDto(
    val iri: String,
    val label: String?,
    val superClasses: List<String>,        // 상위 클래스 IRI
    val annotations: List<AnnotationDto>
)
// 트리 표현은 평면 리스트(superClasses)로 내려보내고 프론트에서 트리 구성
// (또는 /api/classes/tree 에서 중첩 노드 제공 — 4.1 참고)

// Object Property
data class ObjectPropertyDto(
    val iri: String,
    val label: String?,
    val domains: List<String>,
    val ranges: List<String>,
    val characteristics: List<String>,     // FUNCTIONAL, TRANSITIVE, SYMMETRIC, ...
    val inverseOf: String?,
    val annotations: List<AnnotationDto>
)

// Data Property
data class DataPropertyDto(
    val iri: String,
    val label: String?,
    val domains: List<String>,
    val range: String?,                    // xsd datatype IRI
    val functional: Boolean,
    val annotations: List<AnnotationDto>
)

// Individual
data class PropertyAssertionDto(
    val property: String,                  // object 또는 data property IRI
    val value: String,                     // 대상 individual IRI 또는 리터럴 값
    val isLiteral: Boolean
)
data class IndividualDto(
    val iri: String,
    val label: String?,
    val types: List<String>,               // 소속 클래스 IRI
    val assertions: List<PropertyAssertionDto>,
    val annotations: List<AnnotationDto>
)

// 메타
data class OntologyMetaDto(
    val ontologyIri: String?,
    val baseIri: String,
    val prefixes: Map<String, String>,
    val counts: Map<String, Int>           // classes, objectProps, dataProps, individuals
)
```

### 4.1 클래스 트리 표현
- 기본: 평면 리스트 + `superClasses`로 프론트가 트리 구성(다중상속 대응)
- 편의 엔드포인트: `GET /api/classes/tree` → owl:Thing 루트의 중첩 노드(단일 부모 기준, 다중상속은 복제 노드)

## 5. REST API 계약

베이스: `/api`. 요청/응답 JSON. 에러는 6절 표준 형식.

### 5.1 온톨로지 (OntologyController)
| Method | Path | 설명 |
|--------|------|------|
| POST | `/ontology/new` | 빈 온톨로지 생성 (body: `{ontologyIri, baseIri}`) |
| POST | `/ontology/load` | 파일 업로드(multipart) 로드. 포맷 자동 감지 |
| GET | `/ontology/meta` | 메타데이터(OntologyMetaDto) |
| GET | `/ontology/export?format=turtle\|rdfxml` | 직렬화 다운로드 |

### 5.2 클래스 (ClassController)
| Method | Path | 설명 |
|--------|------|------|
| GET | `/classes` | 전체 클래스 목록(평면) |
| GET | `/classes/tree` | 계층 트리 |
| GET | `/classes/{iri}` | 단건 |
| POST | `/classes` | 생성 `{label, superClass?}` → IRI 자동 생성 |
| PATCH | `/classes/{iri}` | label/annotations/superClasses 수정 |
| DELETE | `/classes/{iri}` | 삭제 (사용처 있으면 6절 정책에 따름) |

### 5.3 속성 (PropertyController)
| Method | Path | 설명 |
|--------|------|------|
| GET | `/properties/object` / `/properties/data` / `/properties/annotation` | 목록 |
| POST | `/properties/object` 등 | 생성 |
| PATCH | `/properties/object/{iri}` 등 | domain/range/characteristics 수정 |
| DELETE | `/properties/{type}/{iri}` | 삭제 |

### 5.4 개체 (IndividualController)
| Method | Path | 설명 |
|--------|------|------|
| GET | `/individuals` | 목록 (옵션 `?type={classIri}`) |
| GET | `/individuals/{iri}` | 단건 |
| POST | `/individuals` | 생성 `{label, types[]}` |
| PATCH | `/individuals/{iri}` | types/assertions/annotations 수정 |
| DELETE | `/individuals/{iri}` | 삭제 |

### 5.5 검색 (SearchController) — P1.5
| Method | Path | 설명 |
|--------|------|------|
| GET | `/search?q=...` | IRI/label/주석 텍스트 검색 |
| GET | `/usage/{iri}` | 해당 엔티티가 쓰인 곳(공리 목록) |

## 6. 에러 처리 & 정책
- 표준 에러 응답: `{ "error": "코드", "message": "사람이 읽는 설명", "targetIri": "..." }`
- HTTP: 400(검증 실패), 404(IRI 없음), 409(충돌·중복 IRI), 422(온톨로지 무결성 위반)
- **삭제 정책**: 참조 중인 엔티티 삭제 시 기본은 409 + 사용처 안내.
  `?cascade=true`면 관련 공리까지 제거.
- 모든 변경은 단일 스레드 안전하게(`OntologyHolder` 동기화) 처리 (MVP 단일 사용자).

## 7. 점진적 구현 순서 (P1 내부 단계)

> 각 단계는 그 자체로 동작·테스트 가능해야 함. 초안 = P1.1~P1.4.

| 단계 | 내용 | 검증(테스트) |
|------|------|------|
| **P1.1 기반** | Gradle/Spring Boot 스켈레톤 + OWL API 의존성, `OntologyHolder`, 새 온톨로지 생성, 로드/내보내기, `/ontology/meta` | pizza.owl 로드→meta의 counts 정확, Turtle 라운드트립 |
| **P1.2 클래스** | ClassService + ClassController CRUD + 계층 | 클래스 생성/이동/삭제→재조회 일치 |
| **P1.3 속성** | object/data/annotation property CRUD, domain·range·characteristics | 속성 생성·수정→export에 정확히 반영 |
| **P1.4 개체** | Individual CRUD + type/assertion | 개체+assertion 생성→export 라운드트립 |
| *— 초안 완료 —* | (여기까지가 "기본 기능 동작" 목표) | |
| **P1.5 부가** | 검색/usage, 삭제 cascade, 트리 엔드포인트, 에러 정책 정교화 | 검색 결과·usage 정확 |

## 8. 테스트 전략
- **단위**: 각 Service를 OWL API 인메모리 온톨로지로 직접 테스트(컨트롤러 없이)
- **통합**: MockMvc로 REST 왕복
- **라운드트립**: 로드→수정→export→재로드 후 동일성 검증(핵심 회귀 테스트)
- **픽스처**: 작은 OWL 샘플(자체 제작 mini-ontology) + pizza.owl

## 9. 미해결 질문 (P1)
- baseIri 기본값/사용자 지정 방식 — 새 온톨로지 생성 시 입력받음(기본 `http://onto-studio/ex#`)
- 신규 엔티티 IRI 생성 규칙: `baseIri + slug(label)` vs 랜덤 fragment — **slug 우선, 충돌 시 suffix**
- export 시 prefix 정렬·포매팅 수준(MVP는 OWL API 기본 출력)
- 동시성: MVP 단일 사용자 가정이나, 향후 멀티 온톨로지/세션은 P1 이후 재설계
