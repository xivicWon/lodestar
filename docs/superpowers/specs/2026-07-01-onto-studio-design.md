# onto-studio — 설계 문서

> 작성일: 2026-07-01
> 상태: **설계 중 (구현 전)**

## 1. 개요 (Overview)

Protégé(온톨로지 편집 분야 1등 제품)의 **실제로 가장 많이 쓰이는 핵심 기능**을
현대적인 웹 UX로 다시 만들고, Protégé에 **없는 AI 품질 검사(린트) 기능**으로 차별화하는
온톨로지 편집기.

**한 줄 정의:** "가벼운 웹 기반 OWL 온톨로지 편집기 + AI 품질 검사기"

### 1.1 만드는 이유 (차별점)
- 원본 Protégé는 Java Swing 기반이라 무겁고 구식 → **현대적·빠른 웹 UX**
- 추론기가 "모순"만 알려주고 *고치는 법*은 안 줌 → **AI가 품질 문제를 사람 말로 설명·수정 제안**
- 핵심 7개 기능 중 실무에서 쓰는 것만 골라 **단순하고 직관적으로**

## 2. 기능 범위 (Scope)

### 2.1 MVP 포함 (In Scope)
| # | 기능 | 설명 |
|---|------|------|
| F1 | **클래스 계층 편집** | 클래스 생성/삭제/이름변경, subclass 트리(드래그로 상하위 이동) |
| F2 | **속성 정의** | Object Property / Data Property / Annotation Property. domain·range, 특성(transitive/symmetric/functional 등) |
| F3 | **개체(Individual) 관리** | 클래스 인스턴스 생성, property assertion(속성값 부여) |
| F4 | **OWL/RDF 입출력** | Turtle, RDF/XML 우선. 파일 로드·저장, owl:imports |
| F5 | **추론기** | HermiT 연동. 일관성 검사 + 자동 분류(inferred hierarchy) + Explanation |
| F6 | **AI 품질 검사 (차별화)** | 린트 규칙 + Claude 기반 일관성 제안. (3.4절 상세) |
| — | 검색/Usage | F1~F3을 쓰려면 필수인 보조 기능. 엔티티 검색, 사용처 찾기 |
| — | 어노테이션 편집 | rdfs:label / rdfs:comment. F1~F3 편집 패널에 통합 |

### 2.2 MVP 제외 (Out of Scope, 추후)
- SPARQL 쿼리 탭 (외부 트리플스토어로 빠지는 기능)
- 그래프 시각화(OntoGraf 류) — 노드 많으면 실무에서 안 씀
- 실시간 다중 사용자 협업
- OBO / OWL-XML / JSON-LD 등 부가 직렬화 포맷
- 사용자 정의 Datatype, 복잡한 카디널리티 빌더
- 대량 CSV→온톨로지 매핑

## 3. 아키텍처 (Architecture)

```
┌─────────────────────────────┐         ┌──────────────────────────────────┐
│  Frontend (Vue 3 + TS)      │         │  Backend (Kotlin + Spring Boot)  │
│                             │  REST   │                                  │
│  - 클래스/속성/개체 트리뷰  │ ◀────▶  │  - OntologyService (OWL API)     │
│  - 편집 폼 패널             │  JSON   │  - ReasonerService (HermiT)      │
│  - 린트 결과 패널           │         │  - IoService (Turtle/RDFXML)     │
│  - 추론 결과(inferred) 토글 │         │  - LintService                   │
│                             │         │      ├─ RuleEngine (정적 규칙)   │
└─────────────────────────────┘         │      └─ AiAdvisor → Claude API   │
                                        │  - 인메모리 OWLOntology 모델     │
                                        └──────────────────────────────────┘
```

### 3.1 기술 스택
- **백엔드**: Kotlin, Spring Boot (REST), **OWL API**(온톨로지 모델·입출력), **HermiT**(추론)
  - Protégé 자체가 OWL API 기반 → 동일한 검증된 토대
- **프론트**: Vue 3 + TypeScript, 트리/폼 중심 UI (그래프 라이브러리 불필요)
- **AI**: Claude API (`claude-opus-4-8` 등 최신 모델) — 린트 자연어 설명·수정 제안
- **빌드**: 백엔드 Gradle, 프론트 Vite

### 3.2 왜 이 구조인가 (핵심 결정 근거)
- 온톨로지 편집기의 **가장 큰 난제는 추론기**. OWL DL 추론기를 직접 구현하는 건 비현실적.
- 모든 주요 추론기(HermiT/Pellet/ELK)는 **JVM 네이티브** → Kotlin 백엔드가 가장 정통한 선택.
- 추론·입출력은 검증된 라이브러리에 위임하고, **우리의 가치(현대적 UX + AI 린트)에 집중**.

### 3.3 데이터 모델 (개념)
백엔드는 OWL API의 `OWLOntology`를 **단일 진실원본(in-memory)**으로 유지.
프론트로는 트리/폼에 필요한 **경량 DTO**만 직렬화.

```
Ontology
 ├─ classes:      [ { iri, label, superClasses[], annotations{} } ]
 ├─ objectProps:  [ { iri, label, domain[], range[], characteristics[] } ]
 ├─ dataProps:    [ { iri, label, domain[], range(datatype) } ]
 ├─ individuals:  [ { iri, label, types[], assertions[ {prop, value} ] } ]
 └─ meta:         { ontologyIri, prefixes{} }
```
- **IRI**가 모든 엔티티의 식별자. label은 표시용.
- 편집은 **명령(command) 단위**로 백엔드에 전달 → 모델 변경 → 갱신된 DTO 반환.
- 추론 후엔 `inferred` 플래그가 붙은 추가 관계를 별도로 내려보냄(asserted와 구분).

### 3.4 AI 품질 검사 (린트) 설계 — 차별화 기능
두 단계로 구성:

**(1) 정적 규칙 엔진 (RuleEngine, AI 불필요·빠름)**
- 누락: label 없는 클래스, 정의(comment) 없는 클래스
- 구조: 고아 클래스(상위 없음), 사이클, 미사용 속성
- 일관성: domain/range 누락, 중복으로 의심되는 라벨
- → 각 항목을 `{severity, ruleId, targetIri, message}`로 반환

**(2) AI 어드바이저 (AiAdvisor → Claude API)**
- 정적 규칙이 잡은 항목 + 온톨로지 컨텍스트를 Claude에 전달
- 출력:
  - **자연어 설명**: "이 클래스는 정의가 없어 의미가 모호합니다"
  - **수정 제안**: 권장 label/정의 문구, 누락된 domain/range 후보, 병합 후보
  - **모순 해설**: 추론기가 inconsistent를 반환하면, explanation을 받아 *쉬운 말 + 고치는 법*으로 변환
- 제안은 **항상 사람이 승인(veto)**해야 적용 (자동 반영 금지)

## 4. 컴포넌트 분해 & 단계 (Phases)

전체를 한 스펙으로 구현하기엔 큼 → **단계별 vertical slice**로 분해.
각 단계는 독립 스펙→플랜→구현 사이클을 가짐.

| Phase | 범위 | 산출물 |
|-------|------|--------|
| **P1. 백엔드 코어 + 입출력** | OWL API로 온톨로지 로드/저장(Turtle·RDFXML), 클래스/속성/개체 CRUD REST API | 동작하는 백엔드 API (프론트 없이 테스트) |
| **P2. 프론트 편집기** | Vue 3 트리뷰(클래스/속성/개체) + 편집 폼, P1 API 연동 | 사람이 클릭으로 온톨로지 편집 |
| **P3. 추론 통합** | HermiT 연동, 일관성 검사·자동 분류, asserted vs inferred 토글 | 추론 결과 화면 |
| **P4. AI 린트** | RuleEngine + Claude AiAdvisor + 린트 결과 패널 | 차별화 기능 완성 |

**첫 구현 대상: P1** (이 문서 승인 후 P1을 별도로 상세 설계·플랜)

## 5. 성공 기준 (Success Criteria)
- 작은 OWL 파일(예: pizza.owl)을 로드 → 클래스 트리·속성·개체가 정확히 표시
- 클래스/속성/개체를 추가·수정·삭제 후 Turtle로 저장 → 표준 도구(Protégé)에서 정상 로드
- 일부러 모순을 넣으면 추론기가 inconsistent 감지
- AI 린트가 누락된 정의/라벨을 찾아내고, 사람이 읽을 수 있는 수정 제안 제시

## 6. 미해결 질문 (Open Questions)
- 멀티 온톨로지 동시 편집 지원? (MVP는 1개 온톨로지 가정)
- 영속성: 파일 시스템만? 추후 DB/저장소?
- 인증/멀티유저: MVP는 단일 로컬 사용자 가정
- 배포 형태: 로컬 실행 vs 호스팅 (플랫폼은 추후 결정 — 사용자 보류)
