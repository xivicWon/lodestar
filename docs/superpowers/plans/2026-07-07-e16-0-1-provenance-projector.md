# E16-0 + E16-1 구현 계획 — Provenance 통일 + OWL→SQLite 투영기

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모든 관계 생성에 kind/provenance/confidence를 표준 기록(E16-0)하고, OWL 온톨로지를 조회용 SQLite read-model로 투영(E16-1)한다.

**Architecture:** 관계(object property) 생성 시 provenance 3종을 OWL axiom annotation으로 property IRI에 부착하고, OntologyMapper가 읽어 DTO로 노출한다. `ReadModelProjector`(Kotlin)가 OWL(클래스·관계·정렬·확정)을 읽어 sqlite-jdbc로 `.db` 파일에 비정규화 스키마로 쓴다. SQLite는 순수 파생(read-only 소비).

**Tech Stack:** Kotlin + Spring Boot, OWL API 5.5, `org.xerial:sqlite-jdbc`, Vue 3 + TS + Pinia, kotlin.test, Vitest.

## Global Constraints

- read-only 원칙: 실 DB·SQLite read-model은 소비 전용. 변경은 OWL/로컬만.
- Provenance 어휘: `Provenance ∈ {EXTRACTED, INFERRED, AMBIGUOUS}`, `RelationKind ∈ {FK, NAMEPATTERN, AI, MANUAL}`.
- Lodestar 메타 IRI: `lodestar:kind = http://lodestar/meta#kind`, `lodestar:provenance = http://lodestar/meta#provenance`, `lodestar:confidence = http://lodestar/meta#confidence`. (E15 SkosVocab의 provenance/confidence IRI와 동일 문자열; E16이 provenance 값공간을 3단계 tier로 정의)
- name-match를 공리로 단정 금지 — 후보→확정 후에만 relation. 투영은 실재 관계를 모두 넣되 provenance로 구분.
- 기본값(provenance 미지정 createObject): kind=MANUAL, provenance=EXTRACTED, confidence=null.
- 커밋 말미: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 품질 게이트: 백엔드 `./gradlew test` 그린, 프론트 `npx vitest run` + `npx vue-tsc -b` 그린. TDD.

---

## File Structure

**백엔드 (신규/수정)**
- `backend/src/main/kotlin/com/ontostudio/provenance/ProvenanceVocab.kt` — IRI 상수 + `Provenance`/`RelationKind` enum + `ProvenanceDto`
- `backend/src/main/kotlin/com/ontostudio/dto/Dtos.kt` (수정) — `ObjectPropertyDto`에 `provenance: ProvenanceDto?` 추가
- `backend/src/main/kotlin/com/ontostudio/core/OntologyMapper.kt` (수정) — provenance 읽기
- `backend/src/main/kotlin/com/ontostudio/ontology/PropertyService.kt` (수정) — createObject provenance 저장
- `backend/src/main/kotlin/com/ontostudio/api/PropertyController.kt` (수정) — 요청 DTO 확장
- `backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelProjector.kt` — OWL→SQLite
- `backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelController.kt` — `/api/readmodel/project`
- `backend/build.gradle.kts` (수정) — sqlite-jdbc
- 테스트: `provenance/ProvenanceRoundTripTest.kt`, `readmodel/ReadModelProjectorTest.kt`

**프론트 (수정)**
- `frontend/src/api/types.ts` — `RelationProvenance` 타입 + `ObjectPropertyDto.provenance`
- `frontend/src/stores/ontologyStore.ts` — `applyRelation` provenance 인자
- `frontend/src/components/RelationSuggestPanel.vue` · `RelationLinkModal.vue` · `RelationsGraph.vue` — 호출부

---

## Issue #A (E16-0) — Provenance 3단계 통일

### Task 1: Provenance 어휘·enum·DTO

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/provenance/ProvenanceVocab.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/provenance/ProvenanceVocabTest.kt`

**Interfaces:**
- Produces: `enum Provenance{EXTRACTED,INFERRED,AMBIGUOUS}`; `enum RelationKind{FK,NAMEPATTERN,AI,MANUAL}`; `data class ProvenanceDto(kind:RelationKind, provenance:Provenance, confidence:Double?)`; `ProvenanceVocab.KIND/PROVENANCE/CONFIDENCE:String`.

- [ ] **Step 1: Write the failing test**

```kotlin
// backend/src/test/kotlin/com/ontostudio/provenance/ProvenanceVocabTest.kt
package com.ontostudio.provenance

import kotlin.test.Test
import kotlin.test.assertEquals

class ProvenanceVocabTest {
    @Test fun `meta IRIs are the lodestar meta namespace`() {
        assertEquals("http://lodestar/meta#kind", ProvenanceVocab.KIND)
        assertEquals("http://lodestar/meta#provenance", ProvenanceVocab.PROVENANCE)
        assertEquals("http://lodestar/meta#confidence", ProvenanceVocab.CONFIDENCE)
    }

    @Test fun `enums parse case-insensitively from stored strings`() {
        assertEquals(Provenance.INFERRED, ProvenanceVocab.provenanceOf("INFERRED"))
        assertEquals(RelationKind.NAMEPATTERN, ProvenanceVocab.kindOf("namepattern"))
        assertEquals(null, ProvenanceVocab.provenanceOf("nonsense"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.provenance.ProvenanceVocabTest"`
Expected: FAIL — unresolved references.

- [ ] **Step 3: Write the vocab**

```kotlin
// backend/src/main/kotlin/com/ontostudio/provenance/ProvenanceVocab.kt
package com.ontostudio.provenance

enum class Provenance { EXTRACTED, INFERRED, AMBIGUOUS }
enum class RelationKind { FK, NAMEPATTERN, AI, MANUAL }

data class ProvenanceDto(
    val kind: RelationKind,
    val provenance: Provenance,
    val confidence: Double?,
)

object ProvenanceVocab {
    const val KIND = "http://lodestar/meta#kind"
    const val PROVENANCE = "http://lodestar/meta#provenance"
    const val CONFIDENCE = "http://lodestar/meta#confidence"

    fun provenanceOf(s: String?): Provenance? =
        s?.let { runCatching { Provenance.valueOf(it.uppercase()) }.getOrNull() }

    fun kindOf(s: String?): RelationKind? =
        s?.let { runCatching { RelationKind.valueOf(it.uppercase()) }.getOrNull() }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.provenance.ProvenanceVocabTest"`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/provenance/ProvenanceVocab.kt \
        backend/src/test/kotlin/com/ontostudio/provenance/ProvenanceVocabTest.kt
git commit -m "feat(e16): provenance 어휘·enum·DTO

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: createObject가 provenance 저장 + Mapper가 읽어 DTO 노출

**Files:**
- Modify: `backend/src/main/kotlin/com/ontostudio/dto/Dtos.kt`
- Modify: `backend/src/main/kotlin/com/ontostudio/core/OntologyMapper.kt`
- Modify: `backend/src/main/kotlin/com/ontostudio/ontology/PropertyService.kt`
- Modify: `backend/src/main/kotlin/com/ontostudio/api/PropertyController.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/provenance/ProvenanceRoundTripTest.kt`

**Interfaces:**
- Consumes: `ProvenanceDto`, `Provenance`, `RelationKind`, `ProvenanceVocab`.
- Produces: `ObjectPropertyDto.provenance: ProvenanceDto?`; `PropertyService.createObject(label, domains, ranges, prov: ProvenanceDto?)`; `CreateObjectPropRequest` gains `kind/provenance/confidence`.

- [ ] **Step 1: Write the failing test**

```kotlin
// backend/src/test/kotlin/com/ontostudio/provenance/ProvenanceRoundTripTest.kt
package com.ontostudio.provenance

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.PropertyService
import org.semanticweb.owlapi.model.IRI
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class ProvenanceRoundTripTest {
    private fun svc(): Pair<PropertyService, OntologyHolder> {
        val holder = OntologyHolder()
        val df = holder.dataFactory
        // 소스/타깃 클래스 선언
        listOf("http://ex#a", "http://ex#b").forEach {
            holder.manager.addAxiom(holder.ontology, df.getOWLDeclarationAxiom(df.getOWLClass(IRI.create(it))))
        }
        return PropertyService(holder, OntologyMapper(holder)) to holder
    }

    @Test fun `createObject persists kind provenance confidence and mapper reads them back`() {
        val (service, _) = svc()
        val dto = service.createObject(
            "placedBy", listOf("http://ex#a"), listOf("http://ex#b"),
            ProvenanceDto(RelationKind.NAMEPATTERN, Provenance.INFERRED, 0.6),
        )
        assertEquals(RelationKind.NAMEPATTERN, dto.provenance?.kind)
        assertEquals(Provenance.INFERRED, dto.provenance?.provenance)
        assertEquals(0.6, dto.provenance?.confidence)
    }

    @Test fun `createObject without provenance defaults to manual EXTRACTED`() {
        val (service, _) = svc()
        val dto = service.createObject("rel", listOf("http://ex#a"), listOf("http://ex#b"), null)
        assertEquals(RelationKind.MANUAL, dto.provenance?.kind)
        assertEquals(Provenance.EXTRACTED, dto.provenance?.provenance)
        assertNull(dto.provenance?.confidence)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.provenance.ProvenanceRoundTripTest"`
Expected: FAIL — `createObject` 4-arg overload / `provenance` field 없음 (compile error).

- [ ] **Step 3: Add the DTO field**

In `backend/src/main/kotlin/com/ontostudio/dto/Dtos.kt`, change `ObjectPropertyDto` to append a nullable provenance field (import at top of file):
```kotlin
import com.ontostudio.provenance.ProvenanceDto
```
```kotlin
data class ObjectPropertyDto(
    val iri: String, val label: String?,
    val domains: List<String>, val ranges: List<String>,
    val characteristics: List<String>, val inverseOf: String?,
    val annotations: List<AnnotationDto>,
    val provenance: ProvenanceDto? = null,
)
```

- [ ] **Step 4: Mapper reads provenance from annotations**

In `backend/src/main/kotlin/com/ontostudio/core/OntologyMapper.kt`, add import `import com.ontostudio.provenance.*` and a helper, then use it in `objectPropertyDto`:

```kotlin
    private fun provenanceOf(iri: IRI): ProvenanceDto? = synchronized(holder.lock) {
        val ax = holder.ontology.annotationAssertionAxioms(iri).toList()
        fun lit(propIri: String): String? = ax.firstOrNull { it.property.iri.toString() == propIri }
            ?.value?.asLiteral()?.orElse(null)?.literal
        val kind = ProvenanceVocab.kindOf(lit(ProvenanceVocab.KIND)) ?: return null
        val prov = ProvenanceVocab.provenanceOf(lit(ProvenanceVocab.PROVENANCE)) ?: Provenance.EXTRACTED
        val conf = lit(ProvenanceVocab.CONFIDENCE)?.toDoubleOrNull()
        ProvenanceDto(kind, prov, conf)
    }
```
Then in `objectPropertyDto(...)`, change the returned `ObjectPropertyDto(...)` to pass `provenance = provenanceOf(p.iri)` as the final argument (after `annotationsOf(p.iri)`).

- [ ] **Step 5: PropertyService.createObject persists provenance**

In `backend/src/main/kotlin/com/ontostudio/ontology/PropertyService.kt` add import `import com.ontostudio.provenance.*` and change `createObject` signature + body:

```kotlin
    fun createObject(
        label: String, domains: List<String>, ranges: List<String>,
        prov: ProvenanceDto? = null,
    ): ObjectPropertyDto = synchronized(holder.lock) {
        val iri = IriFactory(holder.baseIri).forLabel(
            label, ont.objectPropertiesInSignature().map { it.iri }.toList().toHashSet())
        val p = df.getOWLObjectProperty(iri)
        mgr.addAxiom(ont, df.getOWLDeclarationAxiom(p))
        mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
        domains.forEach { mgr.addAxiom(ont, df.getOWLObjectPropertyDomainAxiom(p, df.getOWLClass(IRI.create(it)))) }
        ranges.forEach { mgr.addAxiom(ont, df.getOWLObjectPropertyRangeAxiom(p, df.getOWLClass(IRI.create(it)))) }
        // provenance annotations (기본값: MANUAL/EXTRACTED)
        val pv = prov ?: ProvenanceDto(RelationKind.MANUAL, Provenance.EXTRACTED, null)
        fun anno(propIri: String, value: String) = mgr.addAxiom(ont,
            df.getOWLAnnotationAssertionAxiom(iri,
                df.getOWLAnnotation(df.getOWLAnnotationProperty(IRI.create(propIri)), df.getOWLLiteral(value))))
        anno(ProvenanceVocab.KIND, pv.kind.name)
        anno(ProvenanceVocab.PROVENANCE, pv.provenance.name)
        pv.confidence?.let { anno(ProvenanceVocab.CONFIDENCE, it.toString()) }
        mapper.objectPropertyDto(p)
    }
```

- [ ] **Step 6: Extend controller request**

In `backend/src/main/kotlin/com/ontostudio/api/PropertyController.kt` add imports `import com.ontostudio.provenance.*` and change the request + handler:
```kotlin
data class CreateObjectPropRequest(
    val label: String,
    val domains: List<String> = emptyList(),
    val ranges: List<String> = emptyList(),
    val kind: RelationKind? = null,
    val provenance: Provenance? = null,
    val confidence: Double? = null,
)
```
```kotlin
    @PostMapping("/object")
    fun createObject(@RequestBody r: CreateObjectPropRequest): ObjectPropertyDto {
        val prov = r.kind?.let { ProvenanceDto(it, r.provenance ?: Provenance.INFERRED, r.confidence) }
        return service.createObject(r.label, r.domains, r.ranges, prov)
    }
```

- [ ] **Step 7: Run test + full suite**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.provenance.ProvenanceRoundTripTest"` → PASS (2 tests).
Then `cd backend && ./gradlew test` → 전체 그린 (기존 objectPropertyDto 소비처가 새 nullable 필드로 안 깨지는지 확인).

- [ ] **Step 8: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/dto/Dtos.kt \
        backend/src/main/kotlin/com/ontostudio/core/OntologyMapper.kt \
        backend/src/main/kotlin/com/ontostudio/ontology/PropertyService.kt \
        backend/src/main/kotlin/com/ontostudio/api/PropertyController.kt \
        backend/src/test/kotlin/com/ontostudio/provenance/ProvenanceRoundTripTest.kt
git commit -m "feat(e16): 관계 생성 시 provenance(kind/tier/confidence) 저장·노출 (#A)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 프론트 applyRelation provenance 스레딩

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/stores/ontologyStore.ts`
- Modify: `frontend/src/components/RelationSuggestPanel.vue`
- Test: `frontend/src/stores/ontologyStore.provenance.test.ts`

**Interfaces:**
- Produces: `RelationProvenance = { kind:'FK'|'NAMEPATTERN'|'AI'|'MANUAL'; provenance:'EXTRACTED'|'INFERRED'|'AMBIGUOUS'; confidence?: number }`; `applyRelation(fromIri, toIri, name, prov?)` posts `{label,domains,ranges,...prov fields}`.

- [ ] **Step 1: Add the type**

In `frontend/src/api/types.ts` append:
```typescript
export type Provenance = 'EXTRACTED' | 'INFERRED' | 'AMBIGUOUS'
export type RelationKind = 'FK' | 'NAMEPATTERN' | 'AI' | 'MANUAL'
export interface RelationProvenance { kind: RelationKind; provenance: Provenance; confidence?: number }
```

- [ ] **Step 2: Write the failing store test**

```typescript
// frontend/src/stores/ontologyStore.provenance.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))

describe('applyRelation provenance', () => {
  it('sends provenance fields to POST /properties/object', async () => {
    const s = useOntologyStore()
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(s, 'refresh').mockResolvedValue()
    await s.applyRelation('a', 'b', 'placedBy', { kind: 'NAMEPATTERN', provenance: 'INFERRED', confidence: 0.6 })
    expect(post).toHaveBeenCalledWith('/properties/object', {
      label: 'placedBy', domains: ['a'], ranges: ['b'],
      kind: 'NAMEPATTERN', provenance: 'INFERRED', confidence: 0.6,
    })
  })

  it('omits provenance fields when none passed (manual default on backend)', async () => {
    const s = useOntologyStore()
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(s, 'refresh').mockResolvedValue()
    await s.applyRelation('a', 'b', 'rel')
    expect(post).toHaveBeenCalledWith('/properties/object', { label: 'rel', domains: ['a'], ranges: ['b'] })
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/stores/ontologyStore.provenance.test.ts`
Expected: FAIL — applyRelation ignores 4th arg / posts without provenance.

- [ ] **Step 4: Implement in store**

In `frontend/src/stores/ontologyStore.ts` add `RelationProvenance` to the `../api/types` import, and change `applyRelation`:
```typescript
  async function applyRelation(fromIri: string, toIri: string, name: string, prov?: RelationProvenance) {
    error.value = null
    try {
      const body: Record<string, unknown> = { label: name, domains: [fromIri], ranges: [toIri] }
      if (prov) { body.kind = prov.kind; body.provenance = prov.provenance; if (prov.confidence != null) body.confidence = prov.confidence }
      await apiPost<ObjectPropertyDto>('/properties/object', body)
      relCandidates.value = relCandidates.value.filter(c => !(c.fromIri === fromIri && c.toIri === toIri && c.suggestedName === name))
      judgedRelations.value = judgedRelations.value.filter(c => !(c.fromIri === fromIri && c.toIri === toIri && c.suggestedName === name))
      await refresh()
    } catch (e) { setError(e) }
  }
```
(Keep the existing candidate-filter lines; only the body + signature change.)

- [ ] **Step 5: Thread kind at the candidate call sites**

In `frontend/src/components/RelationSuggestPanel.vue`: the two `승인` buttons call `store.applyRelation(c.fromIri, c.toIri, c.suggestedName)`. Identify which `v-for` each is: the E2 name-pattern candidates loop (over `store.relCandidates`) and the E10 judged loop (over `store.judgedRelations`). Change each button:
- name-pattern loop → `@click="store.applyRelation(c.fromIri, c.toIri, c.suggestedName, { kind: 'NAMEPATTERN', provenance: 'INFERRED', confidence: c.confidence })"`
- judged (AI) loop → `@click="store.applyRelation(c.fromIri, c.toIri, c.suggestedName, { kind: 'AI', provenance: 'INFERRED', confidence: c.confidence })"`

(`RelationLinkModal.vue` and `RelationsGraph.vue` manual paths stay as-is — no 4th arg → backend defaults to MANUAL/EXTRACTED.)

- [ ] **Step 6: Run tests + tsc**

Run: `cd frontend && npx vitest run src/stores/ontologyStore.provenance.test.ts && npx vue-tsc -b`
Expected: PASS + tsc exit 0. Then full `npx vitest run` — 기존 applyRelation 테스트(RelationsGraph 등)가 3-arg 그대로라 안 깨지는지 확인.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/stores/ontologyStore.ts \
        frontend/src/components/RelationSuggestPanel.vue \
        frontend/src/stores/ontologyStore.provenance.test.ts
git commit -m "feat(e16): 프론트 applyRelation provenance 스레딩(E2=namepattern/E10=ai) (#A)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Issue #B (E16-1) — OWL→SQLite 투영기

### Task 4: sqlite-jdbc 의존 + 스키마 생성

**Files:**
- Modify: `backend/build.gradle.kts`
- Create: `backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelProjector.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/readmodel/ReadModelProjectorTest.kt`

**Interfaces:**
- Produces: `ReadModelProjector(holder, mapper, classService, propertyService, alignmentService, confirmations)` with `project(dbPath: String)`; creates the schema tables.

- [ ] **Step 1: Add dependency**

In `backend/build.gradle.kts`, inside `dependencies { ... }` add:
```kotlin
    implementation("org.xerial:sqlite-jdbc:3.45.3.0")
```

- [ ] **Step 2: Write the failing test (schema exists after project)**

```kotlin
// backend/src/test/kotlin/com/ontostudio/readmodel/ReadModelProjectorTest.kt
package com.ontostudio.readmodel

import com.ontostudio.align.AlignmentService
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.ClassService
import com.ontostudio.ontology.PropertyService
import com.ontostudio.provenance.Provenance
import com.ontostudio.provenance.ProvenanceDto
import com.ontostudio.provenance.RelationKind
import com.ontostudio.reference.ReferenceHolder
import com.ontostudio.reference.ReferenceService
import com.ontostudio.savepoint.ConfirmationStore
import com.ontostudio.savepoint.ConfirmedFact
import org.semanticweb.owlapi.model.IRI
import java.nio.file.Files
import java.sql.DriverManager
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ReadModelProjectorTest {
    private val db = Files.createTempFile("readmodel", ".db")
    private val confFile = Files.createTempFile("conf", ".json")
    @AfterTest fun cleanup() { Files.deleteIfExists(db); Files.deleteIfExists(confFile) }

    private fun projector(): ReadModelProjector {
        val holder = OntologyHolder()
        val df = holder.dataFactory
        listOf("http://ex#a", "http://ex#b").forEach {
            holder.manager.addAxiom(holder.ontology, df.getOWLDeclarationAxiom(df.getOWLClass(IRI.create(it))))
            holder.manager.addAxiom(holder.ontology, df.getOWLAnnotationAssertionAxiom(
                IRI.create(it), df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(it.substringAfter('#')))))
        }
        val mapper = OntologyMapper(holder)
        val props = PropertyService(holder, mapper)
        props.createObject("placedBy", listOf("http://ex#a"), listOf("http://ex#b"),
            ProvenanceDto(RelationKind.NAMEPATTERN, Provenance.INFERRED, 0.6))
        val conf = ConfirmationStore(confFile.toString()).also { it.confirm(ConfirmedFact("http://ex#a", "a", "class")) }
        val ref = ReferenceService(ReferenceHolder())
        val align = AlignmentService(holder, ref)
        return ReadModelProjector(holder, mapper, ClassService(holder, mapper), props, align, conf)
    }

    @Test fun `project creates schema tables`() {
        projector().project(db.toString())
        DriverManager.getConnection("jdbc:sqlite:${db}").use { c ->
            val names = mutableSetOf<String>()
            c.createStatement().executeQuery("SELECT name FROM sqlite_master WHERE type='table'").use { rs ->
                while (rs.next()) names.add(rs.getString(1))
            }
            assertTrue(names.containsAll(setOf("class", "relation", "evidence", "alignment", "domain", "meta")), "tables: $names")
        }
    }
}
```
(Note: `ConfirmationStore` ctor takes a file path — verify the actual constructor signature in `savepoint/ConfirmationStore.kt` and adapt the one line if it differs.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.readmodel.ReadModelProjectorTest"`
Expected: FAIL — `ReadModelProjector` unresolved.

- [ ] **Step 4: Write projector with schema creation only**

```kotlin
// backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelProjector.kt
package com.ontostudio.readmodel

import com.ontostudio.align.AlignmentService
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.ClassService
import com.ontostudio.ontology.PropertyService
import com.ontostudio.savepoint.ConfirmationStore
import org.springframework.stereotype.Service
import java.sql.Connection
import java.sql.DriverManager

@Service
class ReadModelProjector(
    private val holder: OntologyHolder,
    private val mapper: OntologyMapper,
    private val classService: ClassService,
    private val propertyService: PropertyService,
    private val alignmentService: AlignmentService,
    private val confirmations: ConfirmationStore,
) {
    fun project(dbPath: String) = synchronized(holder.lock) {
        DriverManager.getConnection("jdbc:sqlite:$dbPath").use { c ->
            c.autoCommit = false
            createSchema(c)
            c.commit()
        }
    }

    private fun createSchema(c: Connection) {
        c.createStatement().use { st ->
            st.executeUpdate("DROP TABLE IF EXISTS class")
            st.executeUpdate("DROP TABLE IF EXISTS relation")
            st.executeUpdate("DROP TABLE IF EXISTS evidence")
            st.executeUpdate("DROP TABLE IF EXISTS alignment")
            st.executeUpdate("DROP TABLE IF EXISTS domain")
            st.executeUpdate("DROP TABLE IF EXISTS meta")
            st.executeUpdate("""CREATE TABLE class(iri TEXT PRIMARY KEY, label TEXT, orig_table TEXT,
                domain_id INTEGER, community INTEGER, degree INTEGER, confirmed INTEGER)""")
            st.executeUpdate("""CREATE TABLE relation(id INTEGER PRIMARY KEY, from_iri TEXT, to_iri TEXT,
                name TEXT, kind TEXT, provenance TEXT, confidence REAL)""")
            st.executeUpdate("""CREATE TABLE evidence(relation_id INTEGER, match_type TEXT, matched_on TEXT,
                alternatives_json TEXT, cardinality TEXT)""")
            st.executeUpdate("""CREATE TABLE alignment(source_iri TEXT, target_iri TEXT, match_type TEXT,
                confidence REAL, provenance TEXT)""")
            st.executeUpdate("CREATE TABLE domain(id INTEGER PRIMARY KEY, name TEXT, member_count INTEGER)")
            st.executeUpdate("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
            st.executeUpdate("CREATE INDEX idx_rel_from ON relation(from_iri)")
            st.executeUpdate("CREATE INDEX idx_rel_to ON relation(to_iri)")
            st.executeUpdate("CREATE INDEX idx_class_comm ON class(community)")
            st.executeUpdate("CREATE INDEX idx_class_label ON class(label)")
            st.executeUpdate("CREATE INDEX idx_class_table ON class(orig_table)")
        }
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.readmodel.ReadModelProjectorTest"`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add backend/build.gradle.kts backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelProjector.kt \
        backend/src/test/kotlin/com/ontostudio/readmodel/ReadModelProjectorTest.kt
git commit -m "feat(e16): SQLite read-model 스키마 투영기 (#B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 데이터 투영 (class·relation·alignment·meta)

**Files:**
- Modify: `backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelProjector.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/readmodel/ReadModelProjectorTest.kt` (추가)

**Interfaces:**
- Consumes: `ClassService.list():List<ClassDto>`, `PropertyService.listObject():List<ObjectPropertyDto>` (with provenance), `AlignmentService.list():List<AlignmentDto>`, `ConfirmationStore.isConfirmed(iri)`, `ProvenanceVocab` shortName.
- Produces: rows in class/relation/alignment/meta.

- [ ] **Step 1: Add failing assertions**

```kotlin
// ReadModelProjectorTest.kt 에 추가
    @Test fun `project writes class relation and alignment rows`() {
        projector().project(db.toString())
        DriverManager.getConnection("jdbc:sqlite:${db}").use { c ->
            fun count(t: String): Int = c.createStatement().executeQuery("SELECT COUNT(*) FROM $t").use { it.next(); it.getInt(1) }
            assertEquals(2, count("class"))
            assertEquals(1, count("relation"))
            // relation provenance round-trip
            c.createStatement().executeQuery("SELECT from_iri,to_iri,name,kind,provenance,confidence FROM relation").use { rs ->
                assertTrue(rs.next())
                assertEquals("http://ex#a", rs.getString("from_iri"))
                assertEquals("http://ex#b", rs.getString("to_iri"))
                assertEquals("placedBy", rs.getString("name"))
                assertEquals("NAMEPATTERN", rs.getString("kind"))
                assertEquals("INFERRED", rs.getString("provenance"))
                assertEquals(0.6, rs.getDouble("confidence"), 1e-9)
            }
            // confirmed flag from ConfirmationStore
            c.createStatement().executeQuery("SELECT confirmed FROM class WHERE iri='http://ex#a'").use { rs ->
                assertTrue(rs.next()); assertEquals(1, rs.getInt("confirmed"))
            }
            // degree: a has 1 relation
            c.createStatement().executeQuery("SELECT degree FROM class WHERE iri='http://ex#a'").use { rs ->
                assertTrue(rs.next()); assertEquals(1, rs.getInt("degree"))
            }
        }
    }
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.readmodel.ReadModelProjectorTest"`
Expected: FAIL — class/relation counts are 0 (no inserts yet).

- [ ] **Step 3: Implement data projection**

Add imports to `ReadModelProjector.kt`:
```kotlin
import com.ontostudio.provenance.RelationKind
```
Add a `shortName` helper and insert logic; call it from `project` after `createSchema`:

```kotlin
    fun project(dbPath: String) = synchronized(holder.lock) {
        val classes = classService.list()
        val rels = propertyService.listObject()
        val aligns = alignmentService.list()
        // degree = 관계에서 from/to로 등장한 횟수
        val degree = HashMap<String, Int>()
        rels.forEach { r ->
            r.domains.firstOrNull()?.let { degree[it] = (degree[it] ?: 0) + 1 }
            r.ranges.firstOrNull()?.let { degree[it] = (degree[it] ?: 0) + 1 }
        }
        DriverManager.getConnection("jdbc:sqlite:$dbPath").use { c ->
            c.autoCommit = false
            createSchema(c)
            c.prepareStatement("INSERT INTO class(iri,label,orig_table,domain_id,community,degree,confirmed) VALUES(?,?,?,?,?,?,?)").use { ps ->
                for (cl in classes) {
                    ps.setString(1, cl.iri); ps.setString(2, cl.label)
                    ps.setString(3, shortName(cl.iri))
                    ps.setObject(4, null); ps.setObject(5, null)
                    ps.setInt(6, degree[cl.iri] ?: 0)
                    ps.setInt(7, if (confirmations.isConfirmed(cl.iri)) 1 else 0)
                    ps.addBatch()
                }
                ps.executeBatch()
            }
            c.prepareStatement("INSERT INTO relation(from_iri,to_iri,name,kind,provenance,confidence) VALUES(?,?,?,?,?,?)").use { ps ->
                for (r in rels) {
                    val from = r.domains.firstOrNull() ?: continue
                    val to = r.ranges.firstOrNull() ?: continue
                    ps.setString(1, from); ps.setString(2, to)
                    ps.setString(3, r.label ?: shortName(r.iri))
                    ps.setString(4, (r.provenance?.kind ?: RelationKind.MANUAL).name)
                    ps.setString(5, (r.provenance?.provenance)?.name ?: "EXTRACTED")
                    if (r.provenance?.confidence != null) ps.setDouble(6, r.provenance!!.confidence!!) else ps.setNull(6, java.sql.Types.REAL)
                    ps.addBatch()
                }
                ps.executeBatch()
            }
            c.prepareStatement("INSERT INTO alignment(source_iri,target_iri,match_type,confidence,provenance) VALUES(?,?,?,?,?)").use { ps ->
                for (a in aligns) {
                    ps.setString(1, a.sourceIri); ps.setString(2, a.targetIri)
                    ps.setString(3, a.matchType.name)
                    if (a.confidence != null) ps.setDouble(4, a.confidence) else ps.setNull(4, java.sql.Types.REAL)
                    ps.setString(5, a.provenance)
                    ps.addBatch()
                }
                ps.executeBatch()
            }
            c.prepareStatement("INSERT INTO meta(key,value) VALUES(?,?)").use { ps ->
                fun put(k: String, v: String) { ps.setString(1, k); ps.setString(2, v); ps.addBatch() }
                put("classes", classes.size.toString())
                put("relations", rels.size.toString())
                put("alignments", aligns.size.toString())
                put("ontologyIri", holder.ontology.ontologyID.ontologyIRI.orElse(null)?.toString() ?: "")
                ps.executeBatch()
            }
            c.commit()
        }
    }

    private fun shortName(iri: String): String {
        val hash = iri.substringAfterLast('#', iri)
        return hash.substringAfterLast('/', hash)
    }
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `cd backend && ./gradlew test --tests "com.ontostudio.readmodel.ReadModelProjectorTest"` → PASS (2 tests).
Then `cd backend && ./gradlew test` → 전체 그린.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelProjector.kt \
        backend/src/test/kotlin/com/ontostudio/readmodel/ReadModelProjectorTest.kt
git commit -m "feat(e16): class·relation·alignment·meta 투영 + degree·confirmed (#B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 투영 엔드포인트

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelController.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/readmodel/ReadModelProjectorTest.kt` (엔드포인트 스모크는 서비스 테스트로 충분 — 컨트롤러는 얇은 위임)

**Interfaces:**
- Produces: `POST /api/readmodel/project?path=<db>` → `{ path, classes, relations }` (투영 후 요약).

- [ ] **Step 1: Write the controller**

```kotlin
// backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelController.kt
package com.ontostudio.readmodel

import org.springframework.web.bind.annotation.*

data class ProjectResult(val path: String, val ok: Boolean)

@RestController
@RequestMapping("/api/readmodel")
class ReadModelController(private val projector: ReadModelProjector) {
    @PostMapping("/project")
    fun project(@RequestParam path: String): ProjectResult {
        projector.project(path)
        return ProjectResult(path, true)
    }
}
```

- [ ] **Step 2: Full backend gate (컴파일 + 전체 그린)**

Run: `cd backend && ./gradlew test`
Expected: PASS (전체; 컨트롤러 컴파일 확인).

- [ ] **Step 3: Commit**

```bash
git add backend/src/main/kotlin/com/ontostudio/readmodel/ReadModelController.kt
git commit -m "feat(e16): read-model 투영 엔드포인트 /api/readmodel/project (#B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 최종 검증 & PR

- [ ] **백엔드:** `cd backend && ./gradlew test` → 그린
- [ ] **프론트:** `cd frontend && npx vitest run && npx vue-tsc -b` → 그린 + exit 0
- [ ] **수동 스모크(선택):** 앱 기동 → 관계 승인(E2/E10) → `POST /api/readmodel/project?path=/tmp/rm.db` → `sqlite3 /tmp/rm.db 'SELECT kind,provenance,confidence FROM relation'`로 provenance 확인
- [ ] **PR:** `Closes` E16-0/E16-1 이슈, 마일스톤 `E16 Knowledge Read-Model & MCP`, 본문에 설계 문서 링크. 트레일러 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

---

## Self-Review (계획 vs 스펙)

- **스펙 커버리지:** provenance 3단계 통일(Task1-3, 스펙 §6), OWL→SQLite 투영기+스키마(Task4-5, §3-4), 엔드포인트(Task6, §4). 도메인 군집(E16-3)·MCP 서버(E16-2)는 이 계획 범위 밖(별도) — 스펙 §9 단계 분해와 일치.
- **Placeholder:** 없음(모든 스텝 실제 코드·명령·기대값). 단 Task4 Step2에 `ConfirmationStore` 생성자 시그니처 확인 지시 1건(구현자가 실제 파일 대조).
- **타입 일관성:** `ProvenanceDto(kind,provenance,confidence)`·`RelationKind`·`Provenance` 백/프론트 일치, `createObject(...,prov?)` 4-arg, `applyRelation(...,prov?)`, `ObjectPropertyDto.provenance` 소비(Task5) 시그니처 일치.
- **주의(구현자 확인):** ① `ConfirmationStore` 실제 생성자(파일경로 인자) — Task4 테스트 한 줄 대조. ② `RelationSuggestPanel.vue`의 두 `v-for`가 각각 relCandidates(namepattern)/judgedRelations(ai)인지 확인 후 버튼 매핑(Task3 Step5). ③ 기존 `ObjectPropertyDto` 생성 지점이 mapper 한 곳뿐인지(새 nullable 필드 기본값으로 안전) — 전체 빌드로 검증.
```
