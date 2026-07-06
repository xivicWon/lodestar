# E15-1 참조 온톨로지 + SKOS 정렬 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 복원 온톨로지를 별도 read-only 참조 온톨로지에 SKOS로 수동 정렬하고, 그 연결을 표준 트리플로 export한다.

**Architecture:** 소스(복원)와 참조(업로드)를 각각 별도 `OWLOntology`로 격리한다. 둘을 잇는 정렬은 소스 온톨로지에 `AnnotationAssertion(skos:<match> <src> <tgt>)` 공리로 저장하고, 신뢰도·출처는 그 공리의 axiom annotation에 담는다. 프론트는 소스/참조를 분리 표시하고 정렬 모달·뱃지·그래프 점선으로 노출한다.

**Tech Stack:** Kotlin + Spring Boot, OWL API 5.5 (H2 테스트), Vue 3 + TS + Pinia, vis-network, Vitest, kotlin.test.

## Global Constraints

- read-only 원칙: 실 DB·참조 온톨로지 불변. 모든 변경은 소스 온톨로지/로컬에만.
- 매치 타입 = SKOS 술어. SKOS NS = `http://www.w3.org/2004/02/skos/core#`.
- Lodestar 메타 IRI: confidence = `http://lodestar/meta#confidence`, provenance = `http://lodestar/meta#provenance`.
- provenance 값: 수동 정렬은 `"manual"`.
- 참조는 파이프라인·추론(HermiT) 대상에서 제외.
- 백엔드 컨트롤러는 `/api` 하위. 프론트 API 클라이언트는 `apiGet/apiPost/apiDelete/apiUpload`(`BASE='/api'`).
- 커밋 말미: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 품질 게이트: 백엔드 `./gradlew test` 그린, 프론트 `npx vitest run` + `npx vue-tsc -b` 그린. TDD.

---

## File Structure

**백엔드 (신규)**
- `backend/src/main/kotlin/com/ontostudio/dto/AlignmentDtos.kt` — `MatchType`, `ReferenceMetaDto`, `AlignmentDto`, `AlignmentRequest`
- `backend/src/main/kotlin/com/ontostudio/align/SkosVocab.kt` — SKOS/Lodestar IRI 상수 + MatchType↔IRI
- `backend/src/main/kotlin/com/ontostudio/reference/ReferenceHolder.kt` — 참조 `OWLOntology` 보관(@Component)
- `backend/src/main/kotlin/com/ontostudio/reference/ReferenceService.kt` — load/classes/meta/clear/containsClass(@Service)
- `backend/src/main/kotlin/com/ontostudio/reference/ReferenceController.kt` — `/api/reference/*`
- `backend/src/main/kotlin/com/ontostudio/align/AlignmentService.kt` — create/list/delete(@Service)
- `backend/src/main/kotlin/com/ontostudio/align/AlignmentController.kt` — `/api/alignments`
- 테스트: `reference/ReferenceServiceTest.kt`, `align/AlignmentServiceTest.kt`

**프론트 (신규/수정)**
- `frontend/src/api/types.ts` (수정) — `MatchType`, `ReferenceMetaDto`, `AlignmentDto`
- `frontend/src/stores/ontologyStore.ts` (수정) — 참조·정렬 상태·액션
- `frontend/src/lib/alignmentGraph.ts` (신규) — 정렬 노드/엣지 순수 함수
- `frontend/src/components/ClassTree.vue` (수정) — 참조 섹션 + 로드
- `frontend/src/components/AlignmentModal.vue` (신규)
- `frontend/src/components/NodeSidePanel.vue` (수정) — 정렬 뱃지 섹션 + 액션
- `frontend/src/components/RelationsGraph.vue` (수정) — 참조 노드/점선 엣지
- `frontend/src/App.vue` (수정) — 정렬 모달 상태 배선

---

## Issue #a — 백엔드: 참조 컨테이너 + 로드 API

### Task 1: 정렬 DTO + SKOS 어휘 상수

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/dto/AlignmentDtos.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/align/SkosVocab.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/align/SkosVocabTest.kt`

**Interfaces:**
- Produces: `MatchType{EXACT,CLOSE,BROAD,NARROW,RELATED}`; `ReferenceMetaDto(ontologyIri:String?, source:String?, classCount:Int)`; `AlignmentDto(sourceIri:String, targetIri:String, matchType:MatchType, confidence:Double?, provenance:String)`; `AlignmentRequest(sourceIri:String, targetIri:String, matchType:MatchType, confidence:Double?=null)`; `SkosVocab.iriFor(MatchType):String`; `SkosVocab.matchTypeFor(String):MatchType?`; `SkosVocab.CONFIDENCE`, `SkosVocab.PROVENANCE`.

- [ ] **Step 1: Write the failing test**

```kotlin
// backend/src/test/kotlin/com/ontostudio/align/SkosVocabTest.kt
package com.ontostudio.align

import com.ontostudio.dto.MatchType
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class SkosVocabTest {
    @Test fun `iriFor maps each match type to its SKOS predicate`() {
        assertEquals("http://www.w3.org/2004/02/skos/core#exactMatch", SkosVocab.iriFor(MatchType.EXACT))
        assertEquals("http://www.w3.org/2004/02/skos/core#closeMatch", SkosVocab.iriFor(MatchType.CLOSE))
        assertEquals("http://www.w3.org/2004/02/skos/core#relatedMatch", SkosVocab.iriFor(MatchType.RELATED))
    }

    @Test fun `matchTypeFor is the inverse of iriFor`() {
        for (m in MatchType.values()) assertEquals(m, SkosVocab.matchTypeFor(SkosVocab.iriFor(m)))
    }

    @Test fun `matchTypeFor returns null for non-SKOS predicates`() {
        assertNull(SkosVocab.matchTypeFor("http://www.w3.org/2000/01/rdf-schema#label"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.align.SkosVocabTest"`
Expected: FAIL — `SkosVocab` / `MatchType` unresolved (compile error).

- [ ] **Step 3: Write the DTOs**

```kotlin
// backend/src/main/kotlin/com/ontostudio/dto/AlignmentDtos.kt
package com.ontostudio.dto

enum class MatchType { EXACT, CLOSE, BROAD, NARROW, RELATED }

data class ReferenceMetaDto(
    val ontologyIri: String?,
    val source: String?,
    val classCount: Int,
)

data class AlignmentDto(
    val sourceIri: String,
    val targetIri: String,
    val matchType: MatchType,
    val confidence: Double?,
    val provenance: String,
)

data class AlignmentRequest(
    val sourceIri: String,
    val targetIri: String,
    val matchType: MatchType,
    val confidence: Double? = null,
)
```

- [ ] **Step 4: Write the vocab object**

```kotlin
// backend/src/main/kotlin/com/ontostudio/align/SkosVocab.kt
package com.ontostudio.align

import com.ontostudio.dto.MatchType

object SkosVocab {
    const val NS = "http://www.w3.org/2004/02/skos/core#"
    const val CONFIDENCE = "http://lodestar/meta#confidence"
    const val PROVENANCE = "http://lodestar/meta#provenance"

    fun iriFor(m: MatchType): String = NS + when (m) {
        MatchType.EXACT -> "exactMatch"
        MatchType.CLOSE -> "closeMatch"
        MatchType.BROAD -> "broadMatch"
        MatchType.NARROW -> "narrowMatch"
        MatchType.RELATED -> "relatedMatch"
    }

    fun matchTypeFor(iri: String): MatchType? = when (iri) {
        NS + "exactMatch" -> MatchType.EXACT
        NS + "closeMatch" -> MatchType.CLOSE
        NS + "broadMatch" -> MatchType.BROAD
        NS + "narrowMatch" -> MatchType.NARROW
        NS + "relatedMatch" -> MatchType.RELATED
        else -> null
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.align.SkosVocabTest"`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/dto/AlignmentDtos.kt \
        backend/src/main/kotlin/com/ontostudio/align/SkosVocab.kt \
        backend/src/test/kotlin/com/ontostudio/align/SkosVocabTest.kt
git commit -m "feat(e15): 정렬 DTO + SKOS 어휘 상수

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 참조 컨테이너 + ReferenceService + 컨트롤러

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/reference/ReferenceHolder.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/reference/ReferenceService.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/reference/ReferenceController.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/reference/ReferenceServiceTest.kt`

**Interfaces:**
- Consumes: `ReferenceMetaDto`, `ClassDto`.
- Produces: `ReferenceHolder` (@Component, `lock`, `ontology:OWLOntology?`, `set(mgr,ont)`, `clear()`); `ReferenceService(refHolder)` with `load(bytes:ByteArray, source:String?):ReferenceMetaDto`, `classes():List<ClassDto>`, `meta():ReferenceMetaDto`, `clear()`, `containsClass(iri:String):Boolean`.

- [ ] **Step 1: Write the failing test**

```kotlin
// backend/src/test/kotlin/com/ontostudio/reference/ReferenceServiceTest.kt
package com.ontostudio.reference

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ReferenceServiceTest {
    // 클래스 ex:Person(label "Person") 하나를 가진 최소 Turtle 참조 온톨로지
    private val ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/ref#> .
        <http://example.org/ref> a owl:Ontology .
        ex:Person a owl:Class ; rdfs:label "Person" .
    """.trimIndent().toByteArray()

    private fun service() = ReferenceService(ReferenceHolder())

    @Test fun `load then classes returns the reference class with its label`() {
        val svc = service()
        svc.load(ttl, "ref.ttl")
        val classes = svc.classes()
        assertEquals(1, classes.size)
        assertEquals("http://example.org/ref#Person", classes[0].iri)
        assertEquals("Person", classes[0].label)
    }

    @Test fun `meta reports the class count and source`() {
        val svc = service()
        svc.load(ttl, "ref.ttl")
        val meta = svc.meta()
        assertEquals(1, meta.classCount)
        assertEquals("ref.ttl", meta.source)
    }

    @Test fun `containsClass is true only for loaded reference classes`() {
        val svc = service()
        svc.load(ttl, "ref.ttl")
        assertTrue(svc.containsClass("http://example.org/ref#Person"))
        assertFalse(svc.containsClass("http://example.org/ref#Nope"))
    }

    @Test fun `clear empties the reference container`() {
        val svc = service()
        svc.load(ttl, "ref.ttl")
        svc.clear()
        assertEquals(0, svc.classes().size)
        assertEquals(0, svc.meta().classCount)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.reference.ReferenceServiceTest"`
Expected: FAIL — `ReferenceService`/`ReferenceHolder` unresolved.

- [ ] **Step 3: Write ReferenceHolder**

```kotlin
// backend/src/main/kotlin/com/ontostudio/reference/ReferenceHolder.kt
package com.ontostudio.reference

import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.model.OWLDataFactory
import org.semanticweb.owlapi.model.OWLOntology
import org.semanticweb.owlapi.model.OWLOntologyManager
import org.springframework.stereotype.Component

/** 참조(외부) 온톨로지를 소스와 완전히 분리해 보관한다. 없을 수 있다(null). */
@Component
class ReferenceHolder {
    val lock = Any()
    private var _manager: OWLOntologyManager = OWLManager.createOWLOntologyManager()
    private var _ontology: OWLOntology? = null
    var source: String? = null
        private set

    val manager: OWLOntologyManager get() = _manager
    val dataFactory: OWLDataFactory get() = _manager.owlDataFactory
    val ontology: OWLOntology? get() = _ontology

    fun set(mgr: OWLOntologyManager, ont: OWLOntology, source: String?) = synchronized(lock) {
        _manager = mgr; _ontology = ont; this.source = source
    }

    fun clear() = synchronized(lock) { _ontology = null; source = null }
}
```

- [ ] **Step 4: Write ReferenceService**

```kotlin
// backend/src/main/kotlin/com/ontostudio/reference/ReferenceService.kt
package com.ontostudio.reference

import com.ontostudio.dto.AnnotationDto
import com.ontostudio.dto.ApiException
import com.ontostudio.dto.ClassDto
import com.ontostudio.dto.ReferenceMetaDto
import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLOntology
import org.semanticweb.owlapi.model.OWLOntologyCreationException
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import java.io.ByteArrayInputStream

@Service
class ReferenceService(private val refHolder: ReferenceHolder) {

    fun load(bytes: ByteArray, source: String?): ReferenceMetaDto = synchronized(refHolder.lock) {
        val mgr = OWLManager.createOWLOntologyManager()
        val ont = try {
            mgr.loadOntologyFromOntologyDocument(ByteArrayInputStream(bytes))
        } catch (e: OWLOntologyCreationException) {
            throw ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "reference_load_failed",
                "참조 온톨로지를 읽을 수 없습니다: ${e.message}", null)
        }
        refHolder.set(mgr, ont, source)
        meta()
    }

    fun classes(): List<ClassDto> = synchronized(refHolder.lock) {
        val ont = refHolder.ontology ?: return emptyList()
        ont.classesInSignature().toList()
            .filter { !it.isOWLThing && !it.isOWLNothing }
            .map { cls -> ClassDto(cls.iri.toString(), labelOf(ont, cls.iri), emptyList(), annotationsOf(ont, cls.iri)) }
    }

    fun meta(): ReferenceMetaDto = synchronized(refHolder.lock) {
        val ont = refHolder.ontology
        ReferenceMetaDto(
            ontologyIri = ont?.ontologyID?.ontologyIRI?.orElse(null)?.toString(),
            source = refHolder.source,
            classCount = ont?.classesInSignature()?.toList()?.count { !it.isOWLThing && !it.isOWLNothing } ?: 0,
        )
    }

    fun clear() = refHolder.clear()

    fun containsClass(iri: String): Boolean = synchronized(refHolder.lock) {
        refHolder.ontology?.containsClassInSignature(IRI.create(iri)) ?: false
    }

    private fun labelOf(ont: OWLOntology, iri: IRI): String? {
        val rdfsLabel = IRI.create("http://www.w3.org/2000/01/rdf-schema#label")
        return ont.annotationAssertionAxioms(iri).toList()
            .mapNotNull { ax -> if (ax.property.iri == rdfsLabel) ax.value.asLiteral().orElse(null)?.literal else null }
            .firstOrNull()
    }

    private fun annotationsOf(ont: OWLOntology, iri: IRI): List<AnnotationDto> =
        ont.annotationAssertionAxioms(iri).map {
            val lit = it.value.asLiteral().orElse(null)
            AnnotationDto(it.property.iri.toString(), lit?.literal ?: it.value.toString(), lit?.lang?.ifBlank { null })
        }.toList()
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.reference.ReferenceServiceTest"`
Expected: PASS (4 tests).

- [ ] **Step 6: Write the controller**

```kotlin
// backend/src/main/kotlin/com/ontostudio/reference/ReferenceController.kt
package com.ontostudio.reference

import com.ontostudio.dto.ClassDto
import com.ontostudio.dto.ReferenceMetaDto
import org.springframework.web.bind.annotation.*
import org.springframework.web.multipart.MultipartFile

@RestController
@RequestMapping("/api/reference")
class ReferenceController(private val service: ReferenceService) {

    @PostMapping("/load")
    fun load(@RequestParam file: MultipartFile): ReferenceMetaDto =
        service.load(file.bytes, file.originalFilename)

    @GetMapping("/meta")
    fun meta(): ReferenceMetaDto = service.meta()

    @GetMapping("/classes")
    fun classes(): List<ClassDto> = service.classes()

    @DeleteMapping
    fun clear() = service.clear()
}
```

- [ ] **Step 7: Compile + full backend test**

Run: `cd backend && ./gradlew test`
Expected: PASS (전체 그린; 컨트롤러 컴파일 확인).

- [ ] **Step 8: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/reference/ \
        backend/src/test/kotlin/com/ontostudio/reference/ReferenceServiceTest.kt
git commit -m "feat(e15): 참조 온톨로지 컨테이너 + 로드 API (#a)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Issue #b — 백엔드: SKOS 정렬 공리 + API

### Task 3: AlignmentService.create

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/align/AlignmentService.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/align/AlignmentServiceTest.kt`

**Interfaces:**
- Consumes: `OntologyHolder` (소스, `manager`, `ontology`, `dataFactory`, `lock`), `ReferenceService.containsClass`, `SkosVocab`, `AlignmentRequest`, `AlignmentDto`, `ApiException`.
- Produces: `AlignmentService(holder, reference)` with `create(req:AlignmentRequest):AlignmentDto` (뒤 Task에서 `list()`, `delete(src,tgt,matchType)` 추가).

- [ ] **Step 1: Write the failing test**

```kotlin
// backend/src/test/kotlin/com/ontostudio/align/AlignmentServiceTest.kt
package com.ontostudio.align

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.ApiException
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.MatchType
import com.ontostudio.reference.ReferenceHolder
import com.ontostudio.reference.ReferenceService
import org.semanticweb.owlapi.model.IRI
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class AlignmentServiceTest {
    private val srcIri = "http://lodestar/rdb/ex#tbl_a"
    private val tgtIri = "http://example.org/ref#Person"
    private val refTtl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/ref#> .
        <http://example.org/ref> a owl:Ontology .
        ex:Person a owl:Class .
    """.trimIndent().toByteArray()

    // 소스 온톨로지에 클래스 tbl_a 를 심고, 참조엔 Person 을 로드한 서비스 세트
    private fun fixture(): AlignmentService {
        val holder = OntologyHolder()
        val df = holder.dataFactory
        holder.manager.addAxiom(holder.ontology, df.getOWLDeclarationAxiom(df.getOWLClass(IRI.create(srcIri))))
        val ref = ReferenceService(ReferenceHolder()).also { it.load(refTtl, "ref.ttl") }
        return AlignmentService(holder, ref)
    }

    @Test fun `create adds a SKOS closeMatch annotation assertion with confidence and provenance`() {
        val svc = fixture()
        val dto = svc.create(AlignmentRequest(srcIri, tgtIri, MatchType.CLOSE, 0.8))
        assertEquals(srcIri, dto.sourceIri)
        assertEquals(tgtIri, dto.targetIri)
        assertEquals(MatchType.CLOSE, dto.matchType)
        assertEquals(0.8, dto.confidence)
        assertEquals("manual", dto.provenance)
    }

    @Test fun `create rejects an unknown source class`() {
        val svc = fixture()
        val ex = assertFailsWith<ApiException> {
            svc.create(AlignmentRequest("http://lodestar/rdb/ex#nope", tgtIri, MatchType.CLOSE, null))
        }
        assertTrue(ex.error.contains("source"))
    }

    @Test fun `create rejects an unknown target class`() {
        val svc = fixture()
        assertFailsWith<ApiException> {
            svc.create(AlignmentRequest(srcIri, "http://example.org/ref#Nope", MatchType.CLOSE, null))
        }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.align.AlignmentServiceTest"`
Expected: FAIL — `AlignmentService` unresolved.

- [ ] **Step 3: Write AlignmentService (create only)**

```kotlin
// backend/src/main/kotlin/com/ontostudio/align/AlignmentService.kt
package com.ontostudio.align

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.AlignmentDto
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.ApiException
import com.ontostudio.reference.ReferenceService
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLAnnotation
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service

@Service
class AlignmentService(
    private val holder: OntologyHolder,
    private val reference: ReferenceService,
) {
    fun create(req: AlignmentRequest): AlignmentDto = synchronized(holder.lock) {
        if (!holder.ontology.containsClassInSignature(IRI.create(req.sourceIri)))
            throw ApiException(HttpStatus.BAD_REQUEST, "invalid_source",
                "소스 클래스를 찾을 수 없습니다: ${req.sourceIri}", req.sourceIri)
        if (!reference.containsClass(req.targetIri))
            throw ApiException(HttpStatus.BAD_REQUEST, "invalid_target",
                "참조 클래스를 찾을 수 없습니다: ${req.targetIri}", req.targetIri)

        val df = holder.dataFactory
        val provenance = "manual"
        val annos = buildList<OWLAnnotation> {
            req.confidence?.let {
                add(df.getOWLAnnotation(df.getOWLAnnotationProperty(IRI.create(SkosVocab.CONFIDENCE)), df.getOWLLiteral(it)))
            }
            add(df.getOWLAnnotation(df.getOWLAnnotationProperty(IRI.create(SkosVocab.PROVENANCE)), df.getOWLLiteral(provenance)))
        }
        val ax = df.getOWLAnnotationAssertionAxiom(
            df.getOWLAnnotationProperty(IRI.create(SkosVocab.iriFor(req.matchType))),
            IRI.create(req.sourceIri),
            IRI.create(req.targetIri),
            annos,
        )
        holder.manager.addAxiom(holder.ontology, ax)
        AlignmentDto(req.sourceIri, req.targetIri, req.matchType, req.confidence, provenance)
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.align.AlignmentServiceTest"`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/align/AlignmentService.kt \
        backend/src/test/kotlin/com/ontostudio/align/AlignmentServiceTest.kt
git commit -m "feat(e15): SKOS 정렬 공리 생성(AlignmentService.create)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: AlignmentService.list + delete

**Files:**
- Modify: `backend/src/main/kotlin/com/ontostudio/align/AlignmentService.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/align/AlignmentServiceTest.kt` (추가)

**Interfaces:**
- Produces: `AlignmentService.list():List<AlignmentDto>`, `AlignmentService.delete(sourceIri:String, targetIri:String, matchType:MatchType)`.

- [ ] **Step 1: Add failing tests**

```kotlin
// AlignmentServiceTest.kt 에 메서드 추가
    @Test fun `list round-trips created alignments including confidence and match type`() {
        val svc = fixture()
        svc.create(AlignmentRequest(srcIri, tgtIri, MatchType.CLOSE, 0.8))
        val all = svc.list()
        assertEquals(1, all.size)
        assertEquals(srcIri, all[0].sourceIri)
        assertEquals(tgtIri, all[0].targetIri)
        assertEquals(MatchType.CLOSE, all[0].matchType)
        assertEquals(0.8, all[0].confidence)
        assertEquals("manual", all[0].provenance)
    }

    @Test fun `delete removes the matching alignment`() {
        val svc = fixture()
        svc.create(AlignmentRequest(srcIri, tgtIri, MatchType.CLOSE, 0.8))
        svc.delete(srcIri, tgtIri, MatchType.CLOSE)
        assertEquals(0, svc.list().size)
    }
```

Add imports at top of the test file:
```kotlin
import com.ontostudio.dto.AlignmentDto
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.align.AlignmentServiceTest"`
Expected: FAIL — `list`/`delete` unresolved.

- [ ] **Step 3: Implement list + delete**

Add to `AlignmentService` (imports: `import org.semanticweb.owlapi.model.AxiomType`, `import org.semanticweb.owlapi.model.OWLAnnotationAssertionAxiom`):

```kotlin
    fun list(): List<AlignmentDto> = synchronized(holder.lock) {
        holder.ontology.axioms(AxiomType.ANNOTATION_ASSERTION).toList().mapNotNull { ax -> toDto(ax) }
    }

    fun delete(sourceIri: String, targetIri: String, matchType: com.ontostudio.dto.MatchType) = synchronized(holder.lock) {
        val skos = SkosVocab.iriFor(matchType)
        val target = holder.ontology.axioms(AxiomType.ANNOTATION_ASSERTION).toList().firstOrNull { ax ->
            ax.property.iri.toString() == skos &&
                (ax.subject as? IRI)?.toString() == sourceIri &&
                ax.value.asIRI().orElse(null)?.toString() == targetIri
        }
        if (target != null) holder.manager.removeAxiom(holder.ontology, target)
    }

    private fun toDto(ax: OWLAnnotationAssertionAxiom): AlignmentDto? {
        val matchType = SkosVocab.matchTypeFor(ax.property.iri.toString()) ?: return null
        val src = (ax.subject as? IRI)?.toString() ?: return null
        val tgt = ax.value.asIRI().orElse(null)?.toString() ?: return null
        var confidence: Double? = null
        var provenance = "manual"
        ax.annotations().toList().forEach { a ->
            when (a.property.iri.toString()) {
                SkosVocab.CONFIDENCE -> confidence = a.value.asLiteral().orElse(null)?.parseDouble()
                SkosVocab.PROVENANCE -> provenance = a.value.asLiteral().orElse(null)?.literal ?: "manual"
            }
        }
        return AlignmentDto(src, tgt, matchType, confidence, provenance)
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.align.AlignmentServiceTest"`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/align/AlignmentService.kt \
        backend/src/test/kotlin/com/ontostudio/align/AlignmentServiceTest.kt
git commit -m "feat(e15): 정렬 목록·삭제(AlignmentService.list/delete)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: AlignmentController + export 검증

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/align/AlignmentController.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/align/AlignmentExportTest.kt`

**Interfaces:**
- Consumes: `AlignmentService`, `IoService.export`.
- Produces: `/api/alignments` (POST/GET/DELETE) 엔드포인트.

- [ ] **Step 1: Write export test (매핑이 Turtle에 SKOS로 나오는지)**

```kotlin
// backend/src/test/kotlin/com/ontostudio/align/AlignmentExportTest.kt
package com.ontostudio.align

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.MatchType
import com.ontostudio.io.IoService
import com.ontostudio.reference.ReferenceHolder
import com.ontostudio.reference.ReferenceService
import org.semanticweb.owlapi.model.IRI
import kotlin.test.Test
import kotlin.test.assertTrue

class AlignmentExportTest {
    @Test fun `created alignment appears as a skos closeMatch triple in the Turtle export`() {
        val holder = OntologyHolder()
        val df = holder.dataFactory
        val srcIri = "http://lodestar/rdb/ex#tbl_a"
        val tgtIri = "http://example.org/ref#Person"
        holder.manager.addAxiom(holder.ontology, df.getOWLDeclarationAxiom(df.getOWLClass(IRI.create(srcIri))))
        val refTtl = """
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix ex: <http://example.org/ref#> .
            ex:Person a owl:Class .
        """.trimIndent().toByteArray()
        val ref = ReferenceService(ReferenceHolder()).also { it.load(refTtl, "ref.ttl") }
        AlignmentService(holder, ref).create(AlignmentRequest(srcIri, tgtIri, MatchType.CLOSE, 0.8))

        val turtle = String(IoService(holder).export("turtle"))
        assertTrue(turtle.contains("closeMatch"), "export should contain skos:closeMatch; was:\n$turtle")
        assertTrue(turtle.contains("tbl_a"))
    }
}
```

- [ ] **Step 2: Run to verify pass (구현 이미 존재 → 바로 통과 기대)**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.align.AlignmentExportTest"`
Expected: PASS — export가 소스 온톨로지를 직렬화하므로 매핑 공리가 포함됨. (실패 시: `holder.manager.addAxiom` 대상이 `holder.ontology`인지 확인.)

- [ ] **Step 3: Write the controller**

```kotlin
// backend/src/main/kotlin/com/ontostudio/align/AlignmentController.kt
package com.ontostudio.align

import com.ontostudio.dto.AlignmentDto
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.MatchType
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api/alignments")
class AlignmentController(private val service: AlignmentService) {

    @PostMapping
    fun create(@RequestBody req: AlignmentRequest): AlignmentDto = service.create(req)

    @GetMapping
    fun list(): List<AlignmentDto> = service.list()

    @DeleteMapping
    fun delete(
        @RequestParam sourceIri: String,
        @RequestParam targetIri: String,
        @RequestParam matchType: MatchType,
    ) = service.delete(sourceIri, targetIri, matchType)
}
```

- [ ] **Step 4: Full backend gate**

Run: `cd backend && ./gradlew test`
Expected: PASS (전체 그린).

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/align/AlignmentController.kt \
        backend/src/test/kotlin/com/ontostudio/align/AlignmentExportTest.kt
git commit -m "feat(e15): 정렬 API 컨트롤러 + export SKOS 검증 (#b)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Issue #c — 프론트: 참조 분리 표시 + 로드

### Task 6: 프론트 타입 + 스토어 참조 상태·액션

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/stores/ontologyStore.ts`
- Test: `frontend/src/stores/ontologyStore.reference.test.ts`

**Interfaces:**
- Produces: types `MatchType='EXACT'|'CLOSE'|'BROAD'|'NARROW'|'RELATED'`, `ReferenceMetaDto`, `AlignmentDto`; store `referenceClasses`, `referenceMeta`, `alignments`, `loadReference(file)`, `clearReference()`, `fetchReference()`.

- [ ] **Step 1: Add types**

```typescript
// frontend/src/api/types.ts 끝에 추가
export type MatchType = 'EXACT' | 'CLOSE' | 'BROAD' | 'NARROW' | 'RELATED'
export interface ReferenceMetaDto { ontologyIri: string | null; source: string | null; classCount: number }
export interface AlignmentDto {
  sourceIri: string; targetIri: string; matchType: MatchType; confidence: number | null; provenance: string
}
```

- [ ] **Step 2: Write the failing store test**

```typescript
// frontend/src/stores/ontologyStore.reference.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))

describe('ontologyStore reference', () => {
  it('fetchReference loads reference classes and meta separately from source classes', async () => {
    const s = useOntologyStore()
    s.classes = [{ iri: 'src#a', label: 'A', superClasses: [], annotations: [] }]
    vi.spyOn(client, 'apiGet').mockImplementation(async (path: string) => {
      if (path === '/reference/classes') return [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }] as any
      if (path === '/reference/meta') return { ontologyIri: 'ref', source: 'r.ttl', classCount: 1 } as any
      return [] as any
    })
    await s.fetchReference()
    expect(s.referenceClasses.map(c => c.iri)).toEqual(['ref#Person'])
    expect(s.referenceMeta?.classCount).toBe(1)
    expect(s.classes.map(c => c.iri)).toEqual(['src#a']) // 소스 불변
  })

  it('clearReference empties reference state', async () => {
    const s = useOntologyStore()
    s.referenceClasses = [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }]
    vi.spyOn(client, 'apiDelete').mockResolvedValue(undefined)
    await s.clearReference()
    expect(s.referenceClasses).toEqual([])
    expect(s.referenceMeta).toBeNull()
  })
})
```

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npx vitest run src/stores/ontologyStore.reference.test.ts`
Expected: FAIL — `fetchReference` undefined.

- [ ] **Step 4: Implement in store**

In `frontend/src/stores/ontologyStore.ts`: add imports and state/actions.

Add to the type import from `../api/types`: `ReferenceMetaDto, AlignmentDto`.

Add state (near other refs):
```typescript
  const referenceClasses = ref<ClassDto[]>([])
  const referenceMeta = ref<ReferenceMetaDto | null>(null)
  const alignments = ref<AlignmentDto[]>([])
```

Add actions (before the return):
```typescript
  async function fetchReference() {
    try {
      referenceMeta.value = await apiGet<ReferenceMetaDto>('/reference/meta')
      referenceClasses.value = await apiGet<ClassDto[]>('/reference/classes')
    } catch (e) { setError(e) }
  }

  async function loadReference(file: File) {
    error.value = null
    try { await apiUpload<ReferenceMetaDto>('/reference/load', file); await fetchReference() }
    catch (e) { setError(e) }
  }

  async function clearReference() {
    error.value = null
    try {
      await apiDelete('/reference')
      referenceClasses.value = []
      referenceMeta.value = null
    } catch (e) { setError(e) }
  }
```

Add to the returned object: `referenceClasses, referenceMeta, alignments, fetchReference, loadReference, clearReference,`.

- [ ] **Step 5: Run to verify pass + type check**

Run: `cd frontend && npx vitest run src/stores/ontologyStore.reference.test.ts && npx vue-tsc -b`
Expected: PASS + tsc exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/stores/ontologyStore.ts \
        frontend/src/stores/ontologyStore.reference.test.ts
git commit -m "feat(e15): 프론트 참조 온톨로지 상태·액션 (#c)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 목록에 참조 섹션 + 로드 UI

**Files:**
- Modify: `frontend/src/components/ClassTree.vue`
- Test: `frontend/src/components/ClassTree.reference.test.ts`

**Interfaces:**
- Consumes: store `referenceClasses`, `referenceMeta`, `loadReference`, `fetchReference`.
- Produces: `.reference-section`, `.reference-load-btn` (미로드 시), `.reference-item` per 참조 클래스.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/ClassTree.reference.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ClassTree from './ClassTree.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ClassTree reference section', () => {
  it('shows a load button when no reference ontology is loaded', () => {
    useOntologyStore()
    const w = mount(ClassTree)
    expect(w.find('.reference-load-btn').exists()).toBe(true)
  })

  it('lists reference classes under a reference section when loaded', () => {
    const s = useOntologyStore()
    s.referenceMeta = { ontologyIri: 'ref', source: 'r.ttl', classCount: 1 }
    s.referenceClasses = [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }]
    const w = mount(ClassTree)
    expect(w.find('.reference-section').exists()).toBe(true)
    expect(w.text()).toContain('Person')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/ClassTree.reference.test.ts`
Expected: FAIL — `.reference-load-btn` 없음.

- [ ] **Step 3: Implement reference section in ClassTree.vue**

In `<script setup>` add:
```typescript
import { onMounted } from 'vue'
const fileInput = ref<HTMLInputElement | null>(null)
onMounted(() => { store.fetchReference().catch(() => {}) })
function onPickFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) store.loadReference(f)
}
```

In `<template>`, after the existing `.tree-root`/empty block (still inside `.class-tree`), add:
```html
    <div class="reference-section">
      <div class="reference-head">
        <span class="reference-title">참조 온톨로지<span v-if="store.referenceMeta"> · {{ store.referenceMeta.classCount }}</span></span>
        <button v-if="store.referenceMeta" class="reference-clear" title="참조 비우기" @click="store.clearReference()">×</button>
      </div>
      <button v-if="!store.referenceMeta" class="reference-load-btn" @click="fileInput?.click()">＋ 참조 온톨로지 로드</button>
      <input ref="fileInput" type="file" accept=".ttl,.owl,.rdf,.xml,.n3" hidden @change="onPickFile" />
      <ul v-if="store.referenceClasses.length" class="reference-list">
        <li v-for="rc in store.referenceClasses" :key="rc.iri" class="reference-item"
            :class="{ selected: store.selectedIri === rc.iri }" @click="store.select(rc.iri)">
          {{ rc.label ?? rc.iri }}
        </li>
      </ul>
    </div>
```

In `<style scoped>` add:
```css
.reference-section { border-top: 1px solid #e5e7eb; margin-top: 8px; padding: 8px; }
.reference-head { display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 6px; }
.reference-title { font-size: 11px; font-weight: 800; letter-spacing: 0.04em; color: #64748b; text-transform: uppercase; }
.reference-clear { border: none; background: transparent; color: #94a3b8; font-size: 15px; cursor: pointer; line-height: 1; }
.reference-load-btn { width: 100%; padding: 8px; border: 1px dashed #cbd5e1; border-radius: 8px; background: #f8fafc; color: #475569; font-size: 12.5px; cursor: pointer; }
.reference-load-btn:hover { background: #f1f5f9; }
.reference-list { list-style: none; margin: 6px 0 0; padding: 0; }
.reference-item { padding: 7px 10px; border-radius: 7px; font-size: 13px; color: #334155; background: #f8fafc; border: 1px solid #eef2f7; margin-bottom: 4px; cursor: pointer; }
.reference-item:hover { background: #eef2f7; }
.reference-item.selected { background: #e2e8f0; border-color: #cbd5e1; font-weight: 600; }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/components/ClassTree.reference.test.ts && npx vue-tsc -b`
Expected: PASS + tsc exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ClassTree.vue frontend/src/components/ClassTree.reference.test.ts
git commit -m "feat(e15): 목록에 참조 온톨로지 섹션 + 로드 UI (#c)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Issue #d — 프론트: 정렬 모달 + 뱃지 + 그래프 점선

### Task 8: 스토어 정렬 액션

**Files:**
- Modify: `frontend/src/stores/ontologyStore.ts`
- Test: `frontend/src/stores/ontologyStore.alignment.test.ts`

**Interfaces:**
- Produces: store `fetchAlignments()`, `createAlignment(sourceIri, targetIri, matchType, confidence?)`, `deleteAlignment(sourceIri, targetIri, matchType)`, `alignmentsOf(iri)`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/stores/ontologyStore.alignment.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))

describe('ontologyStore alignments', () => {
  it('createAlignment posts and refreshes the alignment list', async () => {
    const s = useOntologyStore()
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({
      sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8, provenance: 'manual',
    } as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([
      { sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8, provenance: 'manual' },
    ] as any)
    await s.createAlignment('src#a', 'ref#Person', 'CLOSE', 0.8)
    expect(post).toHaveBeenCalledWith('/alignments', { sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8 })
    expect(s.alignments).toHaveLength(1)
  })

  it('alignmentsOf filters by source class', () => {
    const s = useOntologyStore()
    s.alignments = [
      { sourceIri: 'src#a', targetIri: 'ref#P', matchType: 'CLOSE', confidence: null, provenance: 'manual' },
      { sourceIri: 'src#b', targetIri: 'ref#Q', matchType: 'EXACT', confidence: null, provenance: 'manual' },
    ]
    expect(s.alignmentsOf('src#a').map(a => a.targetIri)).toEqual(['ref#P'])
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/stores/ontologyStore.alignment.test.ts`
Expected: FAIL — `createAlignment` undefined.

- [ ] **Step 3: Implement**

Add to store (needs `MatchType` in the types import; `computed` is already imported):
```typescript
  async function fetchAlignments() {
    try { alignments.value = await apiGet<AlignmentDto[]>('/alignments') }
    catch (e) { setError(e) }
  }

  async function createAlignment(sourceIri: string, targetIri: string, matchType: MatchType, confidence?: number) {
    error.value = null
    try {
      await apiPost<AlignmentDto>('/alignments', { sourceIri, targetIri, matchType, confidence: confidence ?? null })
      await fetchAlignments()
    } catch (e) { setError(e) }
  }

  async function deleteAlignment(sourceIri: string, targetIri: string, matchType: MatchType) {
    error.value = null
    try {
      await apiDelete(`/alignments?sourceIri=${encodeURIComponent(sourceIri)}&targetIri=${encodeURIComponent(targetIri)}&matchType=${matchType}`)
      await fetchAlignments()
    } catch (e) { setError(e) }
  }

  function alignmentsOf(iri: string): AlignmentDto[] {
    return alignments.value.filter(a => a.sourceIri === iri)
  }
```

Add to the types import: `MatchType`. Add to the returned object: `fetchAlignments, createAlignment, deleteAlignment, alignmentsOf,`.

- [ ] **Step 4: Run to verify pass + tsc**

Run: `cd frontend && npx vitest run src/stores/ontologyStore.alignment.test.ts && npx vue-tsc -b`
Expected: PASS + tsc exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/ontologyStore.ts frontend/src/stores/ontologyStore.alignment.test.ts
git commit -m "feat(e15): 프론트 정렬 액션(create/list/delete/alignmentsOf) (#d)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: AlignmentModal

**Files:**
- Create: `frontend/src/components/AlignmentModal.vue`
- Test: `frontend/src/components/AlignmentModal.test.ts`

**Interfaces:**
- Consumes: store `classes`(소스), `referenceClasses`, `selectedIri`, `createAlignment`.
- Produces: emits `close`; `.from-select`, `.to-select`, `.match-select`, `.conf-input`, `.submit-btn`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/AlignmentModal.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import AlignmentModal from './AlignmentModal.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

function seed() {
  const s = useOntologyStore()
  s.classes = [{ iri: 'src#a', label: '자산', superClasses: [], annotations: [] }]
  s.referenceClasses = [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }]
  s.selectedIri = 'src#a'
  return s
}

describe('AlignmentModal', () => {
  it('defaults the source to the selected class and lists reference classes as targets', () => {
    seed()
    const w = mount(AlignmentModal)
    expect((w.find('.from-select').element as HTMLSelectElement).value).toBe('src#a')
    expect(w.findAll('.to-select option').some(o => o.text().includes('Person'))).toBe(true)
  })

  it('creates the alignment with the chosen match type and emits close', async () => {
    const s = seed()
    const spy = vi.spyOn(s, 'createAlignment').mockResolvedValue(undefined as never)
    const w = mount(AlignmentModal)
    await w.find('.to-select').setValue('ref#Person')
    await w.find('.match-select').setValue('CLOSE')
    await w.find('.conf-input').setValue('0.8')
    await w.find('.submit-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('src#a', 'ref#Person', 'CLOSE', 0.8)
    expect(w.emitted('close')).toBeTruthy()
  })

  it('keeps submit disabled until a target is chosen', () => {
    seed()
    const w = mount(AlignmentModal)
    expect((w.find('.submit-btn').element as HTMLButtonElement).disabled).toBe(true)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/AlignmentModal.test.ts`
Expected: FAIL — component missing.

- [ ] **Step 3: Write AlignmentModal.vue**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
import { shortName } from '../lib/shortName'
import type { MatchType } from '../api/types'

const store = useOntologyStore()
const emit = defineEmits<{ (e: 'close'): void }>()

const fromIri = ref<string>(store.selectedIri ?? '')
const toIri = ref<string>('')
const matchType = ref<MatchType>('CLOSE')
const confidence = ref<string>('')

const MATCHES: { value: MatchType; label: string }[] = [
  { value: 'EXACT', label: 'exactMatch (동일)' },
  { value: 'CLOSE', label: 'closeMatch (거의 같음)' },
  { value: 'BROAD', label: 'broadMatch (상위)' },
  { value: 'NARROW', label: 'narrowMatch (하위)' },
  { value: 'RELATED', label: 'relatedMatch (관련)' },
]

function opt(iri: string, label: string | null): string {
  const orig = shortName(iri)
  const l = label ?? orig
  return l === orig ? l : `${l} (${orig})`
}
const sourceOpts = computed(() => store.classes.map(c => ({ iri: c.iri, text: opt(c.iri, c.label) })))
const targetOpts = computed(() => store.referenceClasses.map(c => ({ iri: c.iri, text: opt(c.iri, c.label) })))

const canSubmit = computed(() => !!fromIri.value && !!toIri.value)

async function submit() {
  if (!canSubmit.value) return
  const conf = confidence.value.trim() === '' ? undefined : Number(confidence.value)
  await store.createAlignment(fromIri.value, toIri.value, matchType.value, conf)
  emit('close')
}
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="al-title">
      <div class="modal-head">
        <h3 id="al-title">온톨로지 정렬 — SKOS 매핑</h3>
        <p>복원 클래스를 참조 온톨로지 클래스에 연결합니다. 실 DB는 변경되지 않습니다.</p>
        <button class="modal-x" aria-label="닫기" @click="emit('close')">×</button>
      </div>
      <div class="modal-body">
        <div class="maprow">
          <div class="field">
            <label for="al-from">소스 클래스 (복원)</label>
            <select id="al-from" class="select from-select" v-model="fromIri">
              <option value="" disabled>클래스 선택…</option>
              <option v-for="o in sourceOpts" :key="o.iri" :value="o.iri">{{ o.text }}</option>
            </select>
          </div>
          <div class="mid" aria-hidden="true">→</div>
          <div class="field">
            <label for="al-to">참조 클래스</label>
            <select id="al-to" class="select to-select" v-model="toIri">
              <option value="" disabled>클래스 선택…</option>
              <option v-for="o in targetOpts" :key="o.iri" :value="o.iri">{{ o.text }}</option>
            </select>
          </div>
        </div>
        <div class="maprow">
          <div class="field">
            <label for="al-match">매치 타입</label>
            <select id="al-match" class="select match-select" v-model="matchType">
              <option v-for="m in MATCHES" :key="m.value" :value="m.value">{{ m.label }}</option>
            </select>
          </div>
          <div class="mid" aria-hidden="true"></div>
          <div class="field">
            <label for="al-conf">신뢰도 <span class="hint">(선택, 0~1)</span></label>
            <input id="al-conf" class="text conf-input" v-model="confidence" placeholder="예: 0.8" />
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="ghost" @click="emit('close')">취소</button>
        <button class="primary submit-btn" :disabled="!canSubmit" @click="submit">정렬 만들기</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; z-index: 40; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(15,23,41,.42); }
.modal { width: min(520px,100%); background: #fff; border: 1px solid #e3e7ee; border-radius: 16px; box-shadow: 0 12px 48px rgba(15,23,41,.22); overflow: hidden; }
.modal-head { position: relative; padding: 16px 20px 12px; border-bottom: 1px solid #eef1f5; }
.modal-head h3 { margin: 0; font-size: 15.5px; font-weight: 700; color: #0f1729; }
.modal-head p { margin: 5px 0 0; font-size: 12px; color: #47536b; max-width: 44ch; }
.modal-x { position: absolute; top: 12px; right: 14px; border: none; background: transparent; font-size: 22px; color: #8592a8; cursor: pointer; }
.modal-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.field label { font-size: 11.5px; font-weight: 700; color: #47536b; }
.field label .hint { font-weight: 400; color: #8592a8; }
.select, .text { width: 100%; border: 1px solid #cdd4e0; border-radius: 9px; padding: 9px 11px; font-size: 13px; background: #f7f8fa; color: #0f1729; box-sizing: border-box; }
.select:focus, .text:focus { outline: 2px solid #4f46e5; outline-offset: -1px; background: #fff; }
.maprow { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: end; }
.maprow .mid { color: #8592a8; font-size: 14px; padding-bottom: 9px; text-align: center; }
.modal-foot { padding: 14px 20px 18px; display: flex; justify-content: flex-end; gap: 9px; border-top: 1px solid #eef1f5; }
.modal-foot button { font-size: 13px; font-weight: 700; border-radius: 9px; padding: 9px 16px; cursor: pointer; }
.ghost { background: transparent; border: 1px solid #cdd4e0; color: #47536b; }
.primary { background: #4f46e5; border: 1px solid #4f46e5; color: #fff; }
.primary:disabled { opacity: .5; cursor: not-allowed; }
</style>
```

- [ ] **Step 4: Run to verify pass + tsc**

Run: `cd frontend && npx vitest run src/components/AlignmentModal.test.ts && npx vue-tsc -b`
Expected: PASS (3 tests) + tsc exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AlignmentModal.vue frontend/src/components/AlignmentModal.test.ts
git commit -m "feat(e15): 온톨로지 정렬 모달(AlignmentModal) (#d)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: side panel 정렬 뱃지 + 진입점

**Files:**
- Modify: `frontend/src/components/NodeSidePanel.vue`
- Test: `frontend/src/components/NodeSidePanel.alignment.test.ts`

**Interfaces:**
- Consumes: store `alignmentsOf`, `referenceClasses`, `deleteAlignment`.
- Produces: emits `add-alignment`; `.alignments` 섹션, `.alignment` 항목, `.align-add-btn`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/NodeSidePanel.alignment.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import NodeSidePanel from './NodeSidePanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

function seed() {
  const s = useOntologyStore()
  s.classes = [{ iri: 'src#a', label: '자산', superClasses: [], annotations: [] }]
  s.referenceClasses = [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }]
  s.alignments = [{ sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8, provenance: 'manual' }]
  s.selectedIri = 'src#a'
  return s
}

describe('NodeSidePanel alignments', () => {
  it('shows alignment badges for the selected class with target label and match type', () => {
    seed()
    const w = mount(NodeSidePanel)
    const t = w.find('.alignments').text()
    expect(t).toContain('Person')
    expect(t.toLowerCase()).toContain('closematch')
  })

  it('emits add-alignment from the action button', async () => {
    seed()
    const w = mount(NodeSidePanel)
    await w.find('.align-add-btn').trigger('click')
    expect(w.emitted('add-alignment')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/NodeSidePanel.alignment.test.ts`
Expected: FAIL — `.alignments` 없음.

- [ ] **Step 3: Implement in NodeSidePanel.vue**

Update emits line:
```typescript
const emit = defineEmits<{ (e: 'close'): void; (e: 'add-relation'): void; (e: 'add-alignment'): void }>()
```

Add computed + helpers in `<script setup>`:
```typescript
const SKOS_LABEL: Record<string, string> = { EXACT: 'exactMatch', CLOSE: 'closeMatch', BROAD: 'broadMatch', NARROW: 'narrowMatch', RELATED: 'relatedMatch' }
const myAlignments = computed(() => (store.selectedIri ? store.alignmentsOf(store.selectedIri) : []))
function refLabel(iri: string): string {
  return store.referenceClasses.find(c => c.iri === iri)?.label ?? shortName(iri)
}
```

In `<template>`, add a section right after the mappings block (before the 영향 분석 section):
```html
      <div class="sec-title">온톨로지 정렬 · {{ myAlignments.length }}</div>
      <p v-if="myAlignments.length === 0" class="empty">정렬된 참조 클래스가 없습니다.</p>
      <div v-else class="alignments">
        <div v-for="a in myAlignments" :key="a.targetIri + a.matchType" class="alignment">
          <span class="al-match" :class="'m-' + a.matchType.toLowerCase()">{{ SKOS_LABEL[a.matchType] }}</span>
          <span class="al-target">→ {{ refLabel(a.targetIri) }}</span>
          <span v-if="a.confidence != null" class="al-conf">{{ a.confidence.toFixed(2) }}</span>
          <button class="al-del" title="정렬 삭제" @click="store.deleteAlignment(a.sourceIri, a.targetIri, a.matchType)">×</button>
        </div>
      </div>
```

Update the actions block at the bottom to add the align button:
```html
    <div class="sp-actions">
      <button class="act add-rel-btn" @click="emit('add-relation')">＋ 관계 연동</button>
      <button class="act ghost align-add-btn" @click="emit('add-alignment')">＋ 온톨로지 정렬</button>
    </div>
```

Add CSS:
```css
.alignments { display: flex; flex-direction: column; gap: 7px; }
.alignment { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid #eef1f5; border-radius: 9px; background: #f8fafc; font-size: 12.5px; }
.al-match { flex: 0 0 auto; font-family: ui-monospace, Menlo, monospace; font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 5px; background: #eef0fe; color: #3730a3; }
.al-match.m-related, .al-match.m-broad, .al-match.m-narrow { background: #f1f5f9; color: #64748b; }
.al-target { flex: 1; min-width: 0; font-weight: 600; }
.al-conf { flex: 0 0 auto; font-variant-numeric: tabular-nums; color: #8592a8; font-size: 11.5px; }
.al-del { flex: 0 0 auto; border: none; background: transparent; color: #94a3b8; font-size: 15px; cursor: pointer; line-height: 1; }
.al-del:hover { color: #dc2626; }
.act.ghost { background: #fff; color: #4f46e5; border: 1px solid #c7d2fe; margin-top: 8px; }
```

- [ ] **Step 4: Run to verify pass + existing side-panel tests still green**

Run: `cd frontend && npx vitest run src/components/NodeSidePanel.alignment.test.ts src/components/NodeSidePanel.test.ts && npx vue-tsc -b`
Expected: PASS + tsc exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/NodeSidePanel.vue frontend/src/components/NodeSidePanel.alignment.test.ts
git commit -m "feat(e15): side panel 정렬 뱃지 + 정렬 진입점 (#d)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: 그래프 참조 노드/점선 + App 배선

**Files:**
- Create: `frontend/src/lib/alignmentGraph.ts`
- Test: `frontend/src/lib/alignmentGraph.test.ts`
- Modify: `frontend/src/components/RelationsGraph.vue`
- Modify: `frontend/src/App.vue`

**Interfaces:**
- Consumes: `GraphData`, store `alignments`, `referenceClasses`.
- Produces: `alignmentGraph(alignments, refLabelOf): { nodes: GraphNode[]; edges: GraphEdge[] }` (참조 노드 group `'ref'`, 점선 매핑 엣지 `dashes:true`).

- [ ] **Step 1: Write the failing pure-function test**

```typescript
// frontend/src/lib/alignmentGraph.test.ts
import { describe, it, expect } from 'vitest'
import { alignmentGraph } from './alignmentGraph'
import type { AlignmentDto } from '../api/types'

const aligns: AlignmentDto[] = [
  { sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8, provenance: 'manual' },
]

describe('alignmentGraph', () => {
  it('adds a reference node per aligned target and a dashed edge labelled by match type', () => {
    const g = alignmentGraph(aligns, iri => (iri === 'ref#Person' ? 'Person' : iri))
    expect(g.nodes).toEqual([{ id: 'ref#Person', label: 'Person', group: 'ref' }])
    expect(g.edges).toEqual([{ from: 'src#a', to: 'ref#Person', label: 'closeMatch', arrows: 'to', dashes: true }])
  })

  it('dedupes reference nodes when multiple sources map to the same target', () => {
    const g = alignmentGraph(
      [aligns[0], { sourceIri: 'src#b', targetIri: 'ref#Person', matchType: 'EXACT', confidence: null, provenance: 'manual' }],
      () => 'Person',
    )
    expect(g.nodes).toHaveLength(1)
    expect(g.edges).toHaveLength(2)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/lib/alignmentGraph.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Write alignmentGraph.ts**

```typescript
// frontend/src/lib/alignmentGraph.ts
import type { AlignmentDto } from '../api/types'
import type { GraphNode, GraphEdge } from './buildGraphData'

const SKOS_LABEL: Record<string, string> = {
  EXACT: 'exactMatch', CLOSE: 'closeMatch', BROAD: 'broadMatch', NARROW: 'narrowMatch', RELATED: 'relatedMatch',
}

/** 정렬 링크를 그래프 조각(참조 노드 + 점선 엣지)으로 만든다. 참조 노드는 group 'ref'. */
export function alignmentGraph(
  alignments: AlignmentDto[],
  refLabelOf: (iri: string) => string,
): { nodes: (GraphNode & { group: string })[]; edges: (GraphEdge & { dashes: boolean })[] } {
  const nodes = new Map<string, GraphNode & { group: string }>()
  const edges: (GraphEdge & { dashes: boolean })[] = []
  for (const a of alignments) {
    if (!nodes.has(a.targetIri)) nodes.set(a.targetIri, { id: a.targetIri, label: refLabelOf(a.targetIri), group: 'ref' })
    edges.push({ from: a.sourceIri, to: a.targetIri, label: SKOS_LABEL[a.matchType], arrows: 'to', dashes: true })
  }
  return { nodes: [...nodes.values()], edges }
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/lib/alignmentGraph.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Wire into RelationsGraph.vue**

Add import:
```typescript
import { alignmentGraph } from '../lib/alignmentGraph'
```

In `rebuild()`, after `let g = ...` and the focus filter, before `const sig = signature(g)`, append alignment nodes/edges:
```typescript
  if (store.alignments.length) {
    const refLabelOf = (iri: string) => store.referenceClasses.find(c => c.iri === iri)?.label ?? iri
    // 정렬된 소스가 현재 그래프에 있는 것만
    const present = new Set(g.nodes.map(n => n.id))
    const visible = store.alignments.filter(a => present.has(a.sourceIri))
    const extra = alignmentGraph(visible, refLabelOf)
    g = { nodes: [...g.nodes, ...extra.nodes], edges: [...g.edges, ...extra.edges] }
  }
```

Add group styling to the `Network` options `nodes` — add a `groups` option in the options object passed to `new Network(...)`:
```typescript
    groups: { ref: { color: { background: '#ecfeff', border: '#0891b2' }, shape: 'ellipse', font: { color: '#0e7490' } } },
```

Extend the watch to also rebuild when alignments/reference change:
```typescript
watch(() => [store.classes, store.objectProperties, store.alignments, store.referenceClasses], rebuild, { deep: true })
```

- [ ] **Step 6: Wire the modal into App.vue**

In `App.vue` `<script setup>` add:
```typescript
import AlignmentModal from './components/AlignmentModal.vue'
const showAlign = ref(false)
```

In the `<section class="right">`, update the side panel usage to handle the new event and render the modal (place `AlignmentModal` next to `RelationLinkModal`):
```html
        <Transition name="slide">
          <NodeSidePanel
            v-if="store.selectedIri && !panelDismissed"
            @close="panelDismissed = true"
            @add-relation="showLink = true"
            @add-alignment="showAlign = true"
          />
        </Transition>
```
And after `<RelationLinkModal ... />`:
```html
    <AlignmentModal v-if="showAlign" @close="showAlign = false" />
```

Ensure alignments load on mount — in `App.vue` `onMounted`, add:
```typescript
  store.fetchAlignments().catch(() => {})
```

- [ ] **Step 7: Full frontend gate**

Run: `cd frontend && npx vitest run && npx vue-tsc -b`
Expected: PASS (전체) + tsc exit 0. (기존 RelationsGraph/App 테스트가 새 watch·groups로 깨지지 않는지 확인 — NetworkMock은 이미 `setOptions`/`stabilize` 보유; App.test는 RelationsView 스텁이라 영향 없음.)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/alignmentGraph.ts frontend/src/lib/alignmentGraph.test.ts \
        frontend/src/components/RelationsGraph.vue frontend/src/App.vue
git commit -m "feat(e15): 그래프에 참조 노드·SKOS 점선 엣지 + 정렬 모달 배선 (#d)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 최종 검증 & PR

- [ ] **백엔드 게이트:** `cd backend && ./gradlew test` → 그린
- [ ] **프론트 게이트:** `cd frontend && npx vitest run && npx vue-tsc -b` → 그린 + exit 0
- [ ] **수동 검증(선택):** 앱 기동 → 참조 TTL 로드 → 소스 클래스 선택 → 온톨로지 정렬 모달로 closeMatch 생성 → side panel 뱃지·그래프 점선 확인 → export에 `skos:closeMatch` 포함 확인
- [ ] **PR:** `Closes #a #b #c #d`, 마일스톤 `E15 Ontology Alignment`, 본문에 설계 문서 링크. PR 트레일러 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

---

## Self-Review (계획 vs 스펙)

- **스펙 커버리지:** 참조 컨테이너·로드(Task2), SKOS 매핑 공리+annotation(Task3), 목록·삭제(Task4), export(Task5), 소스/참조 분리 표시(Task7), 정렬 모달(Task9), 뱃지(Task10), 그래프 점선(Task11), 출처·신뢰도 저장(Task3의 axiom annotation) — 스펙 §4~§8 항목 모두 태스크 존재. 추론 격리는 구조적으로 참조가 별도 온톨로지라 자동 충족(별도 테스트 불요, 스펙 §6 준수).
- **Placeholder:** 없음(모든 스텝에 실제 코드·명령·기대값).
- **타입 일관성:** `MatchType`(백/프론트), `AlignmentDto` 필드(sourceIri/targetIri/matchType/confidence/provenance), `createAlignment(source,target,matchType,confidence?)`, `deleteAlignment(...matchType)`, `alignmentGraph(alignments, refLabelOf)` — 태스크 간 시그니처 일치.
