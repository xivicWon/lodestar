# Lodestar E15-1 — 참조 온톨로지 + SKOS 정렬(토대) 설계

> 작성일: 2026-07-06
> 상태: **설계 승인됨 (스코프 = 참조 컨테이너 + 수동 SKOS 정렬)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: P5(RDB→OWL), E12(현재 온톨로지 의미추정), E13(관계 근거 카드), E14(화면 재설계)
> 후속: E15-2(AI 정렬 제안) · E15-3(내부 동치·역관계) · E15-4(식별키·특성 UI) · E15-5(링크 출처·신뢰도 시각화)

## 0. 배경 & 문제

Lodestar는 레거시 DB를 OWL 온톨로지로 복원한다. 그러나 복원 결과는 **고립된 섬**이다 —
표준 어휘나 전사(canonical) 온톨로지에 연결돼 있지 않아, 다른 팀·도구가 "이 테이블이
어떤 표준 개념인가"를 알 수 없다.

시맨틱웹에서 이질적 온톨로지를 잇는 표준 방식은 **SKOS 매핑**(`exactMatch`/`closeMatch`/
`broadMatch`/`narrowMatch`/`relatedMatch`)이다. E15-1은 이 연결 조직의 **토대**를 놓는다:
외부 참조 온톨로지를 로드하고, 복원 클래스를 그 클래스에 SKOS로 **수동** 정렬한다.

이 방향은 Graphify(코드 지식그래프)의 "모든 엣지는 설명 가능·출처가 새겨진다" 철학과
같은 뿌리이며, 장기적으로 Lodestar를 "RDB→OWL 변환기"가 아니라 **"구조화된 소스(무엇이든)
→ 연결된 시맨틱 지식그래프"** 플랫폼으로 세운다. E15-1은 그 차별화 축의 첫 벽돌이다.

## 1. 목표 / 비목표

**목표**
- 외부 참조 온톨로지(OWL/RDF/Turtle)를 **별도 read-only 컨테이너**로 로드.
- 복원 클래스 ↔ 참조 클래스를 **SKOS 매핑**으로 수동 정렬. 링크마다 매치타입 + 신뢰도 + 출처 기록.
- 소스/참조를 화면에서 분리 표시, 정렬 뱃지·그래프 점선.
- 매핑이 표준(SKOS) 트리플로 **export**에 포함.
- 출처·신뢰도 데이터 모델을 처음부터 심어 E15-2/E15-5가 값싸게 얹히게 함.

**비목표 (후속으로 명시)**
- AI 자동 정렬 제안(E15-2), 정교한 출처/신뢰도 시각화(E15-5).
- 내부 동치·역관계(E15-3), 식별키·특성 UI(E15-4).
- 정렬 자체의 일관성 추론.

## 2. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 참조 온톨로지는 **별도 컨테이너**(소스와 격리, read-only, 파이프라인·추론 제외) | 외부 개념이 DB 테이블인 척 섞이거나 AI/추론기가 남의 온톨로지를 건드리는 것 방지 |
| D2 | 매핑 공리는 **소스 온톨로지에 보관(방식 A)**, 단 식별 가능하게 태깅 | 최소 배관. 나중에 별도 Alignment 그래프(방식 C)로 분리할 여지 남김 |
| D3 | 매치 타입 = **SKOS 술어 그 자체**(exact/close/broad/narrow/related) | 별도 필드 불필요, 표준 그대로 |
| D4 | 신뢰도·출처 = **OWL 공리 annotation**(`lodestar:confidence`, `lodestar:provenance`) | export 시 표준 annotated axiom으로 남음. Graphify EXTRACTED/INFERRED 개념의 형식화 |
| D5 | 매핑은 **AnnotationAssertion**(`skos:closeMatch <src> <tgt>`)으로 표현 | 클래스 간 관계를 OWL DL 문제없이 표현(객체속성 아님) |
| D6 | 그래프엔 **정렬된 참조 노드만** 등장 | 83+N 노드 폭주 방지 |
| D7 | IRI/네임스페이스를 **소스 종류 무관**하게 취급(매핑은 소스IRI→참조IRI) | 코드/문서 소스 확장 시 같은 정렬 틀 재사용(확장 여지) |
| D8 | 추론기(HermiT)는 **소스만** 대상 | 참조 불일치가 소스 추론을 깨뜨리지 않게 |

## 3. 아키텍처 (컨테이너)

```
SourceOntology (복원, 편집·파이프라인·추론 대상)   ← 지금 그대로
   └─ [SKOS 매핑 공리] ── skos:closeMatch ──▶ ReferenceOntology (업로드, read-only)
        + axiom annotation: lodestar:confidence, lodestar:provenance
```

- `SourceService`/기존 온톨로지 = 소스. `GET /classes`엔 참조가 절대 안 섞임.
- `ReferenceService` = 참조 `OWLOntology` 별도 보관.
- `AlignmentService` = 소스에 매핑(annotation assertion + axiom annotation) 생성/조회/삭제.

## 4. 데이터 모델 (백엔드, `dto/Dtos.kt`)

```kotlin
enum class MatchType { EXACT, CLOSE, BROAD, NARROW, RELATED }   // = SKOS 술어

data class ReferenceMetaDto(
    val ontologyIri: String?,
    val source: String?,        // 업로드 파일명/식별자
    val classCount: Int,
)

data class AlignmentDto(
    val sourceIri: String,      // 복원 온톨로지 클래스
    val targetIri: String,      // 참조 온톨로지 클래스
    val matchType: MatchType,
    val confidence: Double?,    // 0~1, 수동은 사용자 입력(선택)
    val provenance: String,     // "manual" (E15-2에서 "ai")
)
// 참조 클래스는 기존 ClassDto 재사용

data class AlignmentRequest(
    val sourceIri: String,
    val targetIri: String,
    val matchType: MatchType,
    val confidence: Double? = null,
)
```

**SKOS IRI 매핑:** `EXACT→skos:exactMatch`, `CLOSE→skos:closeMatch`, `BROAD→skos:broadMatch`,
`NARROW→skos:narrowMatch`, `RELATED→skos:relatedMatch`
(`http://www.w3.org/2004/02/skos/core#...`).
**Lodestar 어휘:** `http://lodestar/meta#confidence`, `http://lodestar/meta#provenance`.

## 5. API (`/api`, 기존 컨트롤러 패턴)

| 메서드 | 요청/응답 | 용도 |
|---|---|---|
| `POST /reference/load` | multipart file → `ReferenceMetaDto` | 참조 온톨로지 로드 (기존 `/ontology/load` 미러) |
| `GET /reference/meta` | → `ReferenceMetaDto?` | 참조 메타 |
| `GET /reference/classes` | → `List<ClassDto>` | 참조 클래스 목록 |
| `DELETE /reference` | → 204 | 참조 컨테이너 비우기 |
| `POST /alignments` | `AlignmentRequest` → `AlignmentDto` | 정렬 링크 생성 |
| `GET /alignments` | → `List<AlignmentDto>` | 정렬 목록 |
| `DELETE /alignments` | `?sourceIri&targetIri&matchType` → 204 | 링크 삭제 |

## 6. 백엔드 서비스

- **`ReferenceService`**
  - `load(file): ReferenceMetaDto` — 참조 `OWLOntology`로 파싱·보관(소스와 별도 매니저/모델).
  - `classes(): List<ClassDto>` — 기존 `OntologyMapper` 재사용해 참조 클래스 읽기.
  - `clear()` — 참조 초기화.
  - **격리 불변식:** 참조 로드가 소스 클래스/공리에 영향 없음.
- **`AlignmentService`**
  - `create(req): AlignmentDto` — `AnnotationAssertion(skos:<match> <src> <tgt>)` 생성 + axiom annotation `confidence`/`provenance="manual"` 부착. 소스 온톨로지에 추가.
  - `list(): List<AlignmentDto>` — 소스에서 SKOS 매핑 assertion 스캔 → DTO. axiom annotation에서 신뢰도·출처 복원.
  - `delete(src, tgt, matchType)` — 해당 공리 제거.
  - 소스 IRI가 소스 클래스인지·타깃 IRI가 참조 클래스인지 검증(모르면 400).
- **추론:** `runReasoner`는 소스만. 참조·매핑 공리 미포함.
- **export:** 소스 export(Turtle)에 `<src> skos:closeMatch <tgt>` + annotated axiom 포함.
- **read-only 원칙:** 참조·실 DB 불변. 매핑은 온톨로지 메타에만 기록.

## 7. 프론트엔드

**스토어(`ontologyStore`) 추가**
- 상태: `referenceClasses`, `referenceMeta`, `alignments`
- 액션: `loadReference(file)`, `clearReference()`, `fetchAlignments()`,
  `createAlignment(sourceIri, targetIri, matchType, confidence?)`, `deleteAlignment(sourceIri, targetIri, matchType)`
- 파생: `alignmentsOf(iri)` — 소스 클래스별 매핑

**① 소스/참조 분리 (왼쪽 목록)**
- 2섹션: **"내 스키마 (복원) · 83"** / **"참조 온톨로지 · N"**. 참조 미로드 시 "＋ 참조 온톨로지 로드"만.
- 참조 항목은 구분 색 톤(DB 테이블 아님을 즉시 인지).

**② 정렬 모달 (`AlignmentModal`, `RelationLinkModal` 패턴 재사용)**
- 소스 클래스(기본=선택) → 참조 클래스(참조에서 선택) → 매치타입(select) → 신뢰도(선택 0~1)
- "정렬 만들기" → `createAlignment`. 진입점: side panel "＋ 온톨로지 정렬" + 그래프 CTA.

**③ 매핑 뱃지 (side panel · 목록)**
- side panel "온톨로지 정렬 · k" 섹션: `→ ref:AssetInspection · closeMatch · 0.8` + 삭제. 뱃지 색 = 매치타입(exact 진하게 → related 흐리게).
- 목록 행: 정렬 있으면 작은 링크 아이콘.

**④ 그래프 구분 (E15-1 기본)**
- 참조 노드 = 다른 색/점선 보더, 매핑 엣지 = 점선 + 매치타입 라벨. (정교화는 E15-5)
- **정렬된** 참조 노드만 그래프 등장.

**정렬 흐름**
```
참조 로드 → 소스 클래스 선택 → "온톨로지 정렬" → 참조 클래스·매치타입 선택
→ 링크 생성(annotation assertion + 신뢰도/출처) → 뱃지·그래프 점선 → export에 SKOS 포함
```

## 8. 테스트 전략 (TDD)

**백엔드 (`./gradlew test`, H2)**
- `AlignmentServiceTest` — `MatchType.CLOSE`→`skos:closeMatch` assertion / axiom annotation에 confidence·provenance / 목록·삭제 / 잘못된 IRI 400.
- `ReferenceServiceTest` — 로드 후 참조 클래스 조회 / **격리**: 참조 로드해도 소스 `classes` 불변 / clear.
- `OntologyExportTest` — export Turtle에 `skos:closeMatch` + annotated axiom 포함.
- 추론 격리 — 참조 로드 상태에서 `runReasoner`가 소스만 대상.

**프론트 (`vitest` + `vue-tsc`)**
- store: `createAlignment`가 `POST /alignments` 호출·상태 갱신 / `loadReference` 후 `referenceClasses` 채움 / 소스 `classes`와 분리.
- `AlignmentModal`: 소스 기본값=선택, 매치타입 선택 시 submit 활성, 인자 검증, 취소.
- 목록: 참조 섹션 렌더 / 미로드 시 로드 버튼.
- side panel: 정렬 뱃지(매치타입·신뢰도) + 삭제.

## 9. 이슈 분해 (마일스톤 E15 Ontology Alignment)

| 이슈 | 범위 | 의존 |
|---|---|---|
| **#a 백엔드: 참조 컨테이너 + 로드 API** | `ReferenceService`, `/reference/*`, 격리, DTO | — |
| **#b 백엔드: SKOS 정렬 공리 + API** | `AlignmentService`, `/alignments`, annotation·export, MatchType↔SKOS | #a |
| **#c 프론트: 참조 분리 표시 + 로드** | 스토어 참조 상태, 목록 2섹션, 로드 UI | #a |
| **#d 프론트: 정렬 모달 + 뱃지 + 그래프 점선** | `AlignmentModal`, side panel 정렬 섹션, 그래프 참조노드/점선 | #b·#c |

- 브랜치: `feat/e15-1-<슬러그>` 이슈별. 백엔드(#a→#b) → 프론트(#c→#d).
- 품질 게이트: 백엔드 `./gradlew test` 그린, 프론트 `vitest` + `vue-tsc` 그린. TDD.

## 10. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| OWL API로 두 온톨로지 + 공리 annotation 저장 | 소스/참조 별도 `OWLOntologyManager`/모델. 매핑은 소스에 annotation assertion + axiom annotation |
| 참조 온톨로지 포맷 다양성(OWL/RDF/TTL) | OWL API 로더가 자동 판별. 실패 시 명확한 에러 |
| 그래프 노드 폭주(83+N) | 정렬된 참조 노드만 렌더(D6) |
| 매핑 방식 A의 장기 확장성 | 매핑 식별 태깅으로 방식 C 분리 여지 유지(D2) |
