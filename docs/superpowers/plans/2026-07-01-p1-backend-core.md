# P1 Backend Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프론트엔드 없이 단독 동작하는 온톨로지 코어 백엔드(REST API) — OWL 파일 로드/저장 + 클래스·속성·개체 CRUD.

**Architecture:** Spring Boot REST 서버가 단일 `OWLOntology`를 인메모리 상태로 보유. 컨트롤러는 얇게(검증+위임), 서비스가 OWL API로 모델을 조작, Mapper가 OWLObject↔DTO 변환. 모든 변경은 `OntologyHolder`를 통해서만 일어남.

**Tech Stack:** Kotlin, JDK 17, Spring Boot 3, OWL API 5.5.x, Gradle (Kotlin DSL), JUnit 5 + MockMvc.

## Global Constraints

- 언어: Kotlin, JDK 17 이상
- 엔티티 식별자는 항상 **IRI(String)**. `label`은 표시용(rdfs:label).
- 단일 온톨로지 인메모리 가정 (멀티 온톨로지/인증/DB 영속성은 P1 범위 밖).
- 모든 모델 변경은 `OntologyHolder`를 경유하고 동기화(synchronized)된다.
- REST 베이스 경로: `/api`. 에러 응답 형식: `{ "error": String, "message": String, "targetIri": String? }`.
- TDD: 각 동작은 실패 테스트 → 최소 구현 → 통과 순. 작은 단위로 자주 커밋.
- 라운드트립 회귀 테스트(로드→수정→export→재로드 동일성)를 핵심 안전망으로 유지.

---

## File Structure

```
backend/
├─ build.gradle.kts
├─ settings.gradle.kts
└─ src/
   ├─ main/kotlin/com/ontostudio/
   │  ├─ OntoStudioApplication.kt
   │  ├─ core/OntologyHolder.kt
   │  ├─ core/IriFactory.kt
   │  ├─ core/OntologyMapper.kt
   │  ├─ io/IoService.kt
   │  ├─ ontology/ClassService.kt
   │  ├─ ontology/PropertyService.kt
   │  ├─ ontology/IndividualService.kt
   │  ├─ ontology/SearchService.kt
   │  ├─ api/OntologyController.kt
   │  ├─ api/ClassController.kt
   │  ├─ api/PropertyController.kt
   │  ├─ api/IndividualController.kt
   │  ├─ api/SearchController.kt
   │  ├─ api/ApiExceptionHandler.kt
   │  ├─ dto/Dtos.kt
   │  └─ dto/Errors.kt
   └─ test/kotlin/com/ontostudio/
      ├─ core/OntologyHolderTest.kt
      ├─ io/IoServiceTest.kt
      ├─ ontology/ClassServiceTest.kt
      ├─ ontology/PropertyServiceTest.kt
      ├─ ontology/IndividualServiceTest.kt
      ├─ ontology/SearchServiceTest.kt
      ├─ api/RoundTripIntegrationTest.kt
      └─ fixtures/mini-ontology.ttl
```

---

## Task 1: 프로젝트 스켈레톤 + 헬스 체크 (P1.1)

**Files:**
- Create: `backend/settings.gradle.kts`
- Create: `backend/build.gradle.kts`
- Create: `backend/src/main/kotlin/com/ontostudio/OntoStudioApplication.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/api/HealthController.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/api/HealthControllerTest.kt`

**Interfaces:**
- Produces: 부팅 가능한 Spring Boot 앱, `GET /api/health → {"status":"ok"}`.

- [ ] **Step 1: settings + build 파일 작성**

`backend/settings.gradle.kts`:
```kotlin
rootProject.name = "onto-studio-backend"
```

`backend/build.gradle.kts`:
```kotlin
plugins {
    kotlin("jvm") version "1.9.25"
    kotlin("plugin.spring") version "1.9.25"
    id("org.springframework.boot") version "3.3.4"
    id("io.spring.dependency-management") version "1.1.6"
}

group = "com.ontostudio"
version = "0.1.0"
java.sourceCompatibility = JavaVersion.VERSION_17

repositories { mavenCentral() }

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.jetbrains.kotlin:kotlin-reflect")
    implementation("net.sourceforge.owlapi:owlapi-distribution:5.5.0")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
}

tasks.test { useJUnitPlatform() }
kotlin { jvmToolchain(17) }
```

- [ ] **Step 2: 실패 테스트 작성**

`HealthControllerTest.kt`:
```kotlin
package com.ontostudio.api

import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.*
import kotlin.test.Test

@WebMvcTest(HealthController::class)
class HealthControllerTest {
    @Autowired lateinit var mvc: MockMvc

    @Test fun `health returns ok`() {
        mvc.perform(get("/api/health"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.status").value("ok"))
    }
}
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd backend && ./gradlew test --tests "*HealthControllerTest*"`
Expected: FAIL — `HealthController` 클래스 없음(컴파일 에러).

- [ ] **Step 4: 최소 구현**

`OntoStudioApplication.kt`:
```kotlin
package com.ontostudio

import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.runApplication

@SpringBootApplication
class OntoStudioApplication

fun main(args: Array<String>) { runApplication<OntoStudioApplication>(*args) }
```

`HealthController.kt`:
```kotlin
package com.ontostudio.api

import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api")
class HealthController {
    @GetMapping("/health")
    fun health(): Map<String, String> = mapOf("status" to "ok")
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd backend && ./gradlew test --tests "*HealthControllerTest*"`
Expected: PASS.

- [ ] **Step 6: 커밋**

```bash
git add backend
git commit -m "feat(p1): spring boot 스켈레톤 + health 엔드포인트"
```

---

## Task 2: OntologyHolder + IriFactory (P1.1)

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/core/OntologyHolder.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/core/IriFactory.kt`
- Test: `backend/src/test/kotlin/com/ontostudio/core/OntologyHolderTest.kt`

**Interfaces:**
- Produces:
  - `OntologyHolder.manager: OWLOntologyManager`
  - `OntologyHolder.dataFactory: OWLDataFactory`
  - `OntologyHolder.ontology: OWLOntology` (현재 상태)
  - `OntologyHolder.newOntology(ontologyIri: String?, baseIri: String)` → 빈 온톨로지로 교체
  - `OntologyHolder.replace(ont: OWLOntology, baseIri: String)`
  - `OntologyHolder.baseIri: String`
  - `OntologyHolder.lock` (synchronized용 객체)
  - `IriFactory(baseIri).forLabel(label: String, existing: Set<IRI>): IRI` → slug 기반 충돌 회피 IRI

- [ ] **Step 1: 실패 테스트 작성**

`OntologyHolderTest.kt`:
```kotlin
package com.ontostudio.core

import org.semanticweb.owlapi.model.IRI
import kotlin.test.*

class OntologyHolderTest {
    @Test fun `newOntology creates empty ontology with base iri`() {
        val holder = OntologyHolder()
        holder.newOntology(ontologyIri = "http://ex/onto", baseIri = "http://ex/onto#")
        assertEquals(0, holder.ontology.classesInSignature().count())
        assertEquals("http://ex/onto#", holder.baseIri)
    }

    @Test fun `iri factory slugs label and avoids collision`() {
        val f = IriFactory("http://ex#")
        val first = f.forLabel("Red Wine", emptySet())
        assertEquals("http://ex#Red_Wine", first.toString())
        val second = f.forLabel("Red Wine", setOf(first))
        assertEquals("http://ex#Red_Wine_2", second.toString())
    }
}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && ./gradlew test --tests "*OntologyHolderTest*"`
Expected: FAIL — 클래스 없음.

- [ ] **Step 3: 최소 구현**

`IriFactory.kt`:
```kotlin
package com.ontostudio.core

import org.semanticweb.owlapi.model.IRI

class IriFactory(private val baseIri: String) {
    fun forLabel(label: String, existing: Set<IRI>): IRI {
        val slug = label.trim().replace(Regex("\\s+"), "_").replace(Regex("[^A-Za-z0-9_]"), "")
            .ifBlank { "Entity" }
        var candidate = IRI.create(baseIri + slug)
        var n = 2
        while (existing.contains(candidate)) {
            candidate = IRI.create(baseIri + slug + "_" + n); n++
        }
        return candidate
    }
}
```

`OntologyHolder.kt`:
```kotlin
package com.ontostudio.core

import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.model.*
import org.springframework.stereotype.Component

@Component
class OntologyHolder {
    val lock = Any()
    var manager: OWLOntologyManager = OWLManager.createOWLOntologyManager()
        private set
    val dataFactory: OWLDataFactory get() = manager.owlDataFactory
    lateinit var ontology: OWLOntology
        private set
    var baseIri: String = "http://onto-studio/ex#"
        private set

    init { newOntology(null, baseIri) }

    fun newOntology(ontologyIri: String?, baseIri: String) = synchronized(lock) {
        manager = OWLManager.createOWLOntologyManager()
        ontology = if (ontologyIri != null)
            manager.createOntology(IRI.create(ontologyIri))
        else manager.createOntology()
        this.baseIri = baseIri
    }

    fun replace(ont: OWLOntology, baseIri: String) = synchronized(lock) {
        this.manager = ont.owlOntologyManager
        this.ontology = ont
        this.baseIri = baseIri
    }
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && ./gradlew test --tests "*OntologyHolderTest*"`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add backend
git commit -m "feat(p1): OntologyHolder + IriFactory"
```

---

## Task 3: DTO + IoService + OntologyController (P1.1)

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/dto/Dtos.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/dto/Errors.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/io/IoService.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/core/OntologyMapper.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/api/OntologyController.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/api/ApiExceptionHandler.kt`
- Create: `backend/src/test/kotlin/com/ontostudio/fixtures/mini-ontology.ttl`
- Test: `backend/src/test/kotlin/com/ontostudio/io/IoServiceTest.kt`

**Interfaces:**
- Consumes: `OntologyHolder` (Task 2)
- Produces:
  - DTOs (설계 4절): `ClassDto, ObjectPropertyDto, DataPropertyDto, DataPropertyDto, IndividualDto, AnnotationDto, PropertyAssertionDto, OntologyMetaDto`
  - `ApiError(error, message, targetIri)` + `ApiException(status, error, message, targetIri)`
  - `IoService.load(bytes: ByteArray, baseIri: String)`, `IoService.export(format: String): ByteArray`
  - `OntologyMapper.meta(): OntologyMetaDto`, `labelOf(iri: IRI): String?`
  - `GET /api/ontology/meta`, `POST /api/ontology/new`, `POST /api/ontology/load`, `GET /api/ontology/export`

- [ ] **Step 1: 픽스처 작성** — `mini-ontology.ttl`:
```turtle
@prefix : <http://ex#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
:Animal a owl:Class ; rdfs:label "Animal" .
:Dog a owl:Class ; rdfs:subClassOf :Animal ; rdfs:label "Dog" .
```

- [ ] **Step 2: 실패 테스트 작성** — `IoServiceTest.kt`:
```kotlin
package com.ontostudio.io

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import kotlin.test.*

class IoServiceTest {
    private fun fixture() = this::class.java
        .getResourceAsStream("/com/ontostudio/fixtures/mini-ontology.ttl")!!.readBytes()

    @Test fun `load reads classes and roundtrips`() {
        val holder = OntologyHolder()
        val io = IoService(holder)
        val mapper = OntologyMapper(holder)

        io.load(fixture(), "http://ex#")
        assertEquals(2, mapper.meta().counts["classes"])

        val out = io.export("turtle")
        // 재로드 후 동일 클래스 수 (라운드트립)
        io.load(out, "http://ex#")
        assertEquals(2, mapper.meta().counts["classes"])
    }
}
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd backend && ./gradlew test --tests "*IoServiceTest*"`
Expected: FAIL — `IoService`/`OntologyMapper` 없음.

- [ ] **Step 4: 최소 구현**

`dto/Dtos.kt`:
```kotlin
package com.ontostudio.dto

data class AnnotationDto(val property: String, val value: String, val lang: String? = null)

data class ClassDto(
    val iri: String, val label: String?,
    val superClasses: List<String>, val annotations: List<AnnotationDto>
)
data class ObjectPropertyDto(
    val iri: String, val label: String?,
    val domains: List<String>, val ranges: List<String>,
    val characteristics: List<String>, val inverseOf: String?,
    val annotations: List<AnnotationDto>
)
data class DataPropertyDto(
    val iri: String, val label: String?,
    val domains: List<String>, val range: String?,
    val functional: Boolean, val annotations: List<AnnotationDto>
)
data class PropertyAssertionDto(val property: String, val value: String, val isLiteral: Boolean)
data class IndividualDto(
    val iri: String, val label: String?, val types: List<String>,
    val assertions: List<PropertyAssertionDto>, val annotations: List<AnnotationDto>
)
data class OntologyMetaDto(
    val ontologyIri: String?, val baseIri: String,
    val prefixes: Map<String, String>, val counts: Map<String, Int>
)
```

`dto/Errors.kt`:
```kotlin
package com.ontostudio.dto

import org.springframework.http.HttpStatus

data class ApiError(val error: String, val message: String, val targetIri: String? = null)

class ApiException(
    val status: HttpStatus, val error: String,
    override val message: String, val targetIri: String? = null
) : RuntimeException(message)
```

`io/IoService.kt`:
```kotlin
package com.ontostudio.io

import com.ontostudio.core.OntologyHolder
import org.semanticweb.owlapi.formats.RDFXMLDocumentFormat
import org.semanticweb.owlapi.formats.TurtleDocumentFormat
import org.semanticweb.owlapi.model.OWLDocumentFormat
import org.springframework.stereotype.Service
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

@Service
class IoService(private val holder: OntologyHolder) {
    fun load(bytes: ByteArray, baseIri: String) = synchronized(holder.lock) {
        val mgr = org.semanticweb.owlapi.apibinding.OWLManager.createOWLOntologyManager()
        val ont = mgr.loadOntologyFromOntologyDocument(ByteArrayInputStream(bytes))
        holder.replace(ont, baseIri)
    }

    fun export(format: String): ByteArray = synchronized(holder.lock) {
        val docFormat: OWLDocumentFormat = when (format.lowercase()) {
            "rdfxml" -> RDFXMLDocumentFormat()
            else -> TurtleDocumentFormat()
        }
        val out = ByteArrayOutputStream()
        holder.manager.saveOntology(holder.ontology, docFormat, out)
        out.toByteArray()
    }
}
```

`core/OntologyMapper.kt`:
```kotlin
package com.ontostudio.core

import com.ontostudio.dto.*
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.vocab.OWLRDFVocabulary
import org.springframework.stereotype.Component

@Component
class OntologyMapper(private val holder: OntologyHolder) {
    fun labelOf(iri: IRI): String? {
        val rdfsLabel = holder.dataFactory.rdfsLabel.iri
        return holder.ontology.annotationAssertionAxioms(iri)
            .filter { it.property.iri == rdfsLabel }
            .map { (it.value.asLiteral().orNull())?.literal }
            .firstOrNull { it != null }
    }

    fun meta(): OntologyMetaDto {
        val o = holder.ontology
        return OntologyMetaDto(
            ontologyIri = o.ontologyID.ontologyIRI.orNull()?.toString(),
            baseIri = holder.baseIri,
            prefixes = emptyMap(),
            counts = mapOf(
                "classes" to o.classesInSignature().count().toInt(),
                "objectProps" to o.objectPropertiesInSignature().count().toInt(),
                "dataProps" to o.dataPropertiesInSignature().count().toInt(),
                "individuals" to o.individualsInSignature().count().toInt()
            )
        )
    }
}
```
> 참고: OWL API의 `Optional`은 Kotlin에서 `.orNull()`(Guava) 또는 `.orElse(null)` 사용. 빌드 시 import 확인.

`api/ApiExceptionHandler.kt`:
```kotlin
package com.ontostudio.api

import com.ontostudio.dto.ApiError
import com.ontostudio.dto.ApiException
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.RestControllerAdvice

@RestControllerAdvice
class ApiExceptionHandler {
    @ExceptionHandler(ApiException::class)
    fun handle(e: ApiException): ResponseEntity<ApiError> =
        ResponseEntity.status(e.status).body(ApiError(e.error, e.message, e.targetIri))
}
```

`api/OntologyController.kt`:
```kotlin
package com.ontostudio.api

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.OntologyMetaDto
import com.ontostudio.io.IoService
import org.springframework.http.HttpHeaders
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import org.springframework.web.multipart.MultipartFile

data class NewOntologyRequest(val ontologyIri: String?, val baseIri: String)

@RestController
@RequestMapping("/api/ontology")
class OntologyController(
    private val holder: OntologyHolder,
    private val io: IoService,
    private val mapper: OntologyMapper
) {
    @PostMapping("/new")
    fun new(@RequestBody req: NewOntologyRequest): OntologyMetaDto {
        holder.newOntology(req.ontologyIri, req.baseIri); return mapper.meta()
    }

    @PostMapping("/load")
    fun load(@RequestParam file: MultipartFile,
             @RequestParam(defaultValue = "http://onto-studio/ex#") baseIri: String): OntologyMetaDto {
        io.load(file.bytes, baseIri); return mapper.meta()
    }

    @GetMapping("/meta") fun meta(): OntologyMetaDto = mapper.meta()

    @GetMapping("/export")
    fun export(@RequestParam(defaultValue = "turtle") format: String): ResponseEntity<ByteArray> {
        val bytes = io.export(format)
        val ext = if (format.lowercase() == "rdfxml") "owl" else "ttl"
        return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=ontology.$ext")
            .body(bytes)
    }
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd backend && ./gradlew test --tests "*IoServiceTest*"`
Expected: PASS. (실패 시 `.orNull()` import를 `com.google.common.base.Optional` 또는 `java.util.Optional.orElse(null)`로 조정)

- [ ] **Step 6: 커밋**

```bash
git add backend
git commit -m "feat(p1): DTO + IoService + OntologyController (load/save/meta)"
```

---

## Task 4: ClassService + ClassController (P1.2)

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/ontology/ClassService.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/api/ClassController.kt`
- Modify: `backend/src/main/kotlin/com/ontostudio/core/OntologyMapper.kt` (classDto 추가)
- Test: `backend/src/test/kotlin/com/ontostudio/ontology/ClassServiceTest.kt`

**Interfaces:**
- Consumes: `OntologyHolder`, `OntologyMapper`, `IriFactory`
- Produces:
  - `ClassService.list(): List<ClassDto>`
  - `ClassService.get(iri: String): ClassDto`
  - `ClassService.create(label: String, superClass: String?): ClassDto`
  - `ClassService.setLabel(iri: String, label: String): ClassDto`
  - `ClassService.setSuperClasses(iri: String, supers: List<String>): ClassDto`
  - `ClassService.delete(iri: String, cascade: Boolean)`
  - `OntologyMapper.classDto(cls: OWLClass): ClassDto`
  - REST: `GET/POST /api/classes`, `GET/PATCH/DELETE /api/classes/{iri}`

- [ ] **Step 1: 실패 테스트 작성** — `ClassServiceTest.kt`:
```kotlin
package com.ontostudio.ontology

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import kotlin.test.*

class ClassServiceTest {
    private fun svc(): Triple<ClassService, OntologyHolder, OntologyMapper> {
        val h = OntologyHolder(); h.newOntology(null, "http://ex#")
        val m = OntologyMapper(h)
        return Triple(ClassService(h, m), h, m)
    }

    @Test fun `create class with label`() {
        val (s, _, _) = svc()
        val dto = s.create("Animal", null)
        assertEquals("http://ex#Animal", dto.iri)
        assertEquals("Animal", dto.label)
        assertEquals(1, s.list().size)
    }

    @Test fun `create subclass records superclass`() {
        val (s, _, _) = svc()
        val animal = s.create("Animal", null)
        val dog = s.create("Dog", animal.iri)
        assertTrue(dog.superClasses.contains(animal.iri))
    }

    @Test fun `delete removes class`() {
        val (s, _, _) = svc()
        val a = s.create("Animal", null)
        s.delete(a.iri, cascade = true)
        assertEquals(0, s.list().size)
    }
}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && ./gradlew test --tests "*ClassServiceTest*"`
Expected: FAIL — `ClassService` 없음.

- [ ] **Step 3: 최소 구현**

`OntologyMapper.kt`에 추가:
```kotlin
import org.semanticweb.owlapi.model.OWLClass

fun annotationsOf(iri: IRI): List<AnnotationDto> =
    holder.ontology.annotationAssertionAxioms(iri).map {
        val lit = it.value.asLiteral().orNull()
        AnnotationDto(it.property.iri.toString(), lit?.literal ?: it.value.toString(),
            lit?.lang?.ifBlank { null })
    }.toList()

fun classDto(cls: OWLClass): ClassDto {
    val supers = holder.ontology.subClassAxiomsForSubClass(cls)
        .map { it.superClass }.filter { !it.isAnonymous }
        .map { it.asOWLClass().iri.toString() }.toList()
    return ClassDto(cls.iri.toString(), labelOf(cls.iri), supers, annotationsOf(cls.iri))
}
```

`ontology/ClassService.kt`:
```kotlin
package com.ontostudio.ontology

import com.ontostudio.core.IriFactory
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.ClassDto
import com.ontostudio.dto.ApiException
import org.semanticweb.owlapi.model.*
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service

@Service
class ClassService(private val holder: OntologyHolder, private val mapper: OntologyMapper) {
    private val df get() = holder.dataFactory
    private val ont get() = holder.ontology
    private val mgr get() = holder.manager

    private fun classOrThrow(iri: String): OWLClass {
        val c = df.getOWLClass(IRI.create(iri))
        if (!ont.containsClassInSignature(c.iri))
            throw ApiException(HttpStatus.NOT_FOUND, "not_found", "클래스 없음", iri)
        return c
    }

    fun list(): List<ClassDto> = synchronized(holder.lock) {
        ont.classesInSignature().filter { !it.isOWLThing }.map { mapper.classDto(it) }.toList()
    }

    fun get(iri: String): ClassDto = synchronized(holder.lock) { mapper.classDto(classOrThrow(iri)) }

    fun create(label: String, superClass: String?): ClassDto = synchronized(holder.lock) {
        val iri = IriFactory(holder.baseIri).forLabel(label, ont.classesInSignature().map { it.iri }.toSet())
        val cls = df.getOWLClass(iri)
        mgr.addAxiom(ont, df.getOWLDeclarationAxiom(cls))
        mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
        if (superClass != null)
            mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(cls, df.getOWLClass(IRI.create(superClass))))
        mapper.classDto(cls)
    }

    fun setLabel(iri: String, label: String): ClassDto = synchronized(holder.lock) {
        val cls = classOrThrow(iri)
        ont.annotationAssertionAxioms(cls.iri)
            .filter { it.property.iri == df.rdfsLabel.iri }
            .forEach { mgr.removeAxiom(ont, it) }
        mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(cls.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
        mapper.classDto(cls)
    }

    fun setSuperClasses(iri: String, supers: List<String>): ClassDto = synchronized(holder.lock) {
        val cls = classOrThrow(iri)
        ont.subClassAxiomsForSubClass(cls).forEach { mgr.removeAxiom(ont, it) }
        supers.forEach { mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(cls, df.getOWLClass(IRI.create(it)))) }
        mapper.classDto(cls)
    }

    fun delete(iri: String, cascade: Boolean) = synchronized(holder.lock) {
        val cls = classOrThrow(iri)
        val referencing = ont.referencingAxioms(cls).toList()
        if (referencing.isNotEmpty() && !cascade)
            throw ApiException(HttpStatus.CONFLICT, "in_use", "사용 중인 클래스입니다", iri)
        mgr.removeAxioms(ont, referencing.stream())
    }
}
```

`api/ClassController.kt`:
```kotlin
package com.ontostudio.api

import com.ontostudio.dto.ClassDto
import com.ontostudio.ontology.ClassService
import org.springframework.web.bind.annotation.*

data class CreateClassRequest(val label: String, val superClass: String? = null)
data class PatchClassRequest(val label: String? = null, val superClasses: List<String>? = null)

@RestController
@RequestMapping("/api/classes")
class ClassController(private val service: ClassService) {
    @GetMapping fun list(): List<ClassDto> = service.list()
    @GetMapping("/{iri}") fun get(@PathVariable iri: String): ClassDto = service.get(iri)
    @PostMapping fun create(@RequestBody r: CreateClassRequest): ClassDto = service.create(r.label, r.superClass)

    @PatchMapping("/{iri}")
    fun patch(@PathVariable iri: String, @RequestBody r: PatchClassRequest): ClassDto {
        r.label?.let { service.setLabel(iri, it) }
        r.superClasses?.let { service.setSuperClasses(iri, it) }
        return service.get(iri)
    }

    @DeleteMapping("/{iri}")
    fun delete(@PathVariable iri: String, @RequestParam(defaultValue = "false") cascade: Boolean) =
        service.delete(iri, cascade)
}
```
> 주의: `{iri}` 경로 변수는 인코딩된 전체 IRI. 프론트는 `encodeURIComponent` 사용. (P1.5에서 디코딩 검증 보강)

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && ./gradlew test --tests "*ClassServiceTest*"`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add backend
git commit -m "feat(p1): 클래스 CRUD + 계층 (ClassService/Controller)"
```

---

## Task 5: PropertyService + PropertyController (P1.3)

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/ontology/PropertyService.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/api/PropertyController.kt`
- Modify: `backend/src/main/kotlin/com/ontostudio/core/OntologyMapper.kt` (objectPropertyDto, dataPropertyDto 추가)
- Test: `backend/src/test/kotlin/com/ontostudio/ontology/PropertyServiceTest.kt`

**Interfaces:**
- Consumes: `OntologyHolder`, `OntologyMapper`, `IriFactory`
- Produces:
  - `PropertyService.listObject() / listData()`
  - `PropertyService.createObject(label, domains, ranges): ObjectPropertyDto`
  - `PropertyService.createData(label, domains, range): DataPropertyDto`
  - `PropertyService.setObjectCharacteristics(iri, chars: List<String>): ObjectPropertyDto`
  - `PropertyService.delete(type: String, iri: String)`
  - `OntologyMapper.objectPropertyDto(...)`, `dataPropertyDto(...)`

- [ ] **Step 1: 실패 테스트 작성** — `PropertyServiceTest.kt`:
```kotlin
package com.ontostudio.ontology

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import kotlin.test.*

class PropertyServiceTest {
    private fun svc(): PropertyService {
        val h = OntologyHolder(); h.newOntology(null, "http://ex#")
        return PropertyService(h, OntologyMapper(h))
    }

    @Test fun `create object property with domain and range`() {
        val s = svc()
        val p = s.createObject("hasPart", listOf("http://ex#Car"), listOf("http://ex#Wheel"))
        assertEquals("http://ex#hasPart", p.iri)
        assertTrue(p.domains.contains("http://ex#Car"))
        assertTrue(p.ranges.contains("http://ex#Wheel"))
    }

    @Test fun `set transitive characteristic`() {
        val s = svc()
        val p = s.createObject("hasPart", emptyList(), emptyList())
        val updated = s.setObjectCharacteristics(p.iri, listOf("TRANSITIVE"))
        assertTrue(updated.characteristics.contains("TRANSITIVE"))
    }

    @Test fun `create data property with range`() {
        val s = svc()
        val p = s.createData("age", listOf("http://ex#Person"), "http://www.w3.org/2001/XMLSchema#int")
        assertEquals("http://www.w3.org/2001/XMLSchema#int", p.range)
    }
}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && ./gradlew test --tests "*PropertyServiceTest*"`
Expected: FAIL — `PropertyService` 없음.

- [ ] **Step 3: 최소 구현**

`OntologyMapper.kt`에 추가:
```kotlin
import org.semanticweb.owlapi.model.*

fun objectPropertyDto(p: OWLObjectProperty): ObjectPropertyDto {
    val o = holder.ontology
    val chars = buildList {
        if (o.functionalObjectPropertyAxioms(p).findAny().isPresent) add("FUNCTIONAL")
        if (o.transitiveObjectPropertyAxioms(p).findAny().isPresent) add("TRANSITIVE")
        if (o.symmetricObjectPropertyAxioms(p).findAny().isPresent) add("SYMMETRIC")
    }
    return ObjectPropertyDto(
        p.iri.toString(), labelOf(p.iri),
        o.objectPropertyDomainAxioms(p).map { it.domain }.filter { !it.isAnonymous }.map { it.asOWLClass().iri.toString() }.toList(),
        o.objectPropertyRangeAxioms(p).map { it.range }.filter { !it.isAnonymous }.map { it.asOWLClass().iri.toString() }.toList(),
        chars, null, annotationsOf(p.iri)
    )
}

fun dataPropertyDto(p: OWLDataProperty): DataPropertyDto {
    val o = holder.ontology
    val range = o.dataPropertyRangeAxioms(p).map { it.range }.firstOrNull()?.asOWLDatatype()?.iri?.toString()
    return DataPropertyDto(
        p.iri.toString(), labelOf(p.iri),
        o.dataPropertyDomainAxioms(p).map { it.domain }.filter { !it.isAnonymous }.map { it.asOWLClass().iri.toString() }.toList(),
        range, o.functionalDataPropertyAxioms(p).findAny().isPresent, annotationsOf(p.iri)
    )
}
```

`ontology/PropertyService.kt`:
```kotlin
package com.ontostudio.ontology

import com.ontostudio.core.IriFactory
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.*
import org.semanticweb.owlapi.model.*
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service

@Service
class PropertyService(private val holder: OntologyHolder, private val mapper: OntologyMapper) {
    private val df get() = holder.dataFactory
    private val ont get() = holder.ontology
    private val mgr get() = holder.manager

    fun listObject() = synchronized(holder.lock) {
        ont.objectPropertiesInSignature().map { mapper.objectPropertyDto(it) }.toList()
    }
    fun listData() = synchronized(holder.lock) {
        ont.dataPropertiesInSignature().map { mapper.dataPropertyDto(it) }.toList()
    }

    fun createObject(label: String, domains: List<String>, ranges: List<String>): ObjectPropertyDto =
        synchronized(holder.lock) {
            val iri = IriFactory(holder.baseIri).forLabel(label, ont.objectPropertiesInSignature().map { it.iri }.toSet())
            val p = df.getOWLObjectProperty(iri)
            mgr.addAxiom(ont, df.getOWLDeclarationAxiom(p))
            mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
            domains.forEach { mgr.addAxiom(ont, df.getOWLObjectPropertyDomainAxiom(p, df.getOWLClass(IRI.create(it)))) }
            ranges.forEach { mgr.addAxiom(ont, df.getOWLObjectPropertyRangeAxiom(p, df.getOWLClass(IRI.create(it)))) }
            mapper.objectPropertyDto(p)
        }

    fun createData(label: String, domains: List<String>, range: String?): DataPropertyDto =
        synchronized(holder.lock) {
            val iri = IriFactory(holder.baseIri).forLabel(label, ont.dataPropertiesInSignature().map { it.iri }.toSet())
            val p = df.getOWLDataProperty(iri)
            mgr.addAxiom(ont, df.getOWLDeclarationAxiom(p))
            mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
            domains.forEach { mgr.addAxiom(ont, df.getOWLDataPropertyDomainAxiom(p, df.getOWLClass(IRI.create(it)))) }
            if (range != null) mgr.addAxiom(ont, df.getOWLDataPropertyRangeAxiom(p, df.getOWLDatatype(IRI.create(range))))
            mapper.dataPropertyDto(p)
        }

    fun setObjectCharacteristics(iri: String, chars: List<String>): ObjectPropertyDto =
        synchronized(holder.lock) {
            val p = df.getOWLObjectProperty(IRI.create(iri))
            // 기존 특성 공리 제거
            ont.functionalObjectPropertyAxioms(p).forEach { mgr.removeAxiom(ont, it) }
            ont.transitiveObjectPropertyAxioms(p).forEach { mgr.removeAxiom(ont, it) }
            ont.symmetricObjectPropertyAxioms(p).forEach { mgr.removeAxiom(ont, it) }
            chars.forEach { c ->
                val ax: OWLAxiom = when (c.uppercase()) {
                    "FUNCTIONAL" -> df.getOWLFunctionalObjectPropertyAxiom(p)
                    "TRANSITIVE" -> df.getOWLTransitiveObjectPropertyAxiom(p)
                    "SYMMETRIC" -> df.getOWLSymmetricObjectPropertyAxiom(p)
                    else -> throw ApiException(HttpStatus.BAD_REQUEST, "bad_characteristic", "알 수 없는 특성: $c", iri)
                }
                mgr.addAxiom(ont, ax)
            }
            mapper.objectPropertyDto(p)
        }

    fun delete(type: String, iri: String) = synchronized(holder.lock) {
        val entity: OWLEntity = when (type) {
            "object" -> df.getOWLObjectProperty(IRI.create(iri))
            "data" -> df.getOWLDataProperty(IRI.create(iri))
            else -> df.getOWLAnnotationProperty(IRI.create(iri))
        }
        mgr.removeAxioms(ont, ont.referencingAxioms(entity).stream())
    }
}
```

`api/PropertyController.kt`:
```kotlin
package com.ontostudio.api

import com.ontostudio.dto.*
import com.ontostudio.ontology.PropertyService
import org.springframework.web.bind.annotation.*

data class CreateObjectPropRequest(val label: String, val domains: List<String> = emptyList(), val ranges: List<String> = emptyList())
data class CreateDataPropRequest(val label: String, val domains: List<String> = emptyList(), val range: String? = null)
data class CharacteristicsRequest(val characteristics: List<String>)

@RestController
@RequestMapping("/api/properties")
class PropertyController(private val service: PropertyService) {
    @GetMapping("/object") fun listObject(): List<ObjectPropertyDto> = service.listObject()
    @GetMapping("/data") fun listData(): List<DataPropertyDto> = service.listData()

    @PostMapping("/object")
    fun createObject(@RequestBody r: CreateObjectPropRequest): ObjectPropertyDto =
        service.createObject(r.label, r.domains, r.ranges)

    @PostMapping("/data")
    fun createData(@RequestBody r: CreateDataPropRequest): DataPropertyDto =
        service.createData(r.label, r.domains, r.range)

    @PatchMapping("/object/{iri}")
    fun setChars(@PathVariable iri: String, @RequestBody r: CharacteristicsRequest): ObjectPropertyDto =
        service.setObjectCharacteristics(iri, r.characteristics)

    @DeleteMapping("/{type}/{iri}")
    fun delete(@PathVariable type: String, @PathVariable iri: String) = service.delete(type, iri)
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && ./gradlew test --tests "*PropertyServiceTest*"`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add backend
git commit -m "feat(p1): 속성 CRUD (object/data, domain/range/characteristics)"
```

---

## Task 6: IndividualService + IndividualController (P1.4)

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/ontology/IndividualService.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/api/IndividualController.kt`
- Modify: `backend/src/main/kotlin/com/ontostudio/core/OntologyMapper.kt` (individualDto 추가)
- Test: `backend/src/test/kotlin/com/ontostudio/ontology/IndividualServiceTest.kt`

**Interfaces:**
- Consumes: `OntologyHolder`, `OntologyMapper`, `IriFactory`
- Produces:
  - `IndividualService.list(typeFilter: String?): List<IndividualDto>`
  - `IndividualService.create(label, types: List<String>): IndividualDto`
  - `IndividualService.addObjectAssertion(iri, prop, targetIri): IndividualDto`
  - `IndividualService.addDataAssertion(iri, prop, literal): IndividualDto`
  - `IndividualService.delete(iri)`
  - `OntologyMapper.individualDto(ind: OWLNamedIndividual)`

- [ ] **Step 1: 실패 테스트 작성** — `IndividualServiceTest.kt`:
```kotlin
package com.ontostudio.ontology

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import kotlin.test.*

class IndividualServiceTest {
    private fun svc(): IndividualService {
        val h = OntologyHolder(); h.newOntology(null, "http://ex#")
        return IndividualService(h, OntologyMapper(h))
    }

    @Test fun `create individual with type`() {
        val s = svc()
        val i = s.create("Fido", listOf("http://ex#Dog"))
        assertEquals("http://ex#Fido", i.iri)
        assertTrue(i.types.contains("http://ex#Dog"))
    }

    @Test fun `add data assertion`() {
        val s = svc()
        val i = s.create("Fido", listOf("http://ex#Dog"))
        val updated = s.addDataAssertion(i.iri, "http://ex#age", "3")
        assertTrue(updated.assertions.any { it.property == "http://ex#age" && it.value == "3" && it.isLiteral })
    }
}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && ./gradlew test --tests "*IndividualServiceTest*"`
Expected: FAIL — `IndividualService` 없음.

- [ ] **Step 3: 최소 구현**

`OntologyMapper.kt`에 추가:
```kotlin
fun individualDto(ind: OWLNamedIndividual): IndividualDto {
    val o = holder.ontology
    val types = o.classAssertionAxioms(ind).map { it.classExpression }
        .filter { !it.isAnonymous }.map { it.asOWLClass().iri.toString() }.toList()
    val objAssertions = o.objectPropertyAssertionAxioms(ind).map {
        PropertyAssertionDto(it.property.asOWLObjectProperty().iri.toString(),
            it.getObject().asOWLNamedIndividual().iri.toString(), false)
    }.toList()
    val dataAssertions = o.dataPropertyAssertionAxioms(ind).map {
        PropertyAssertionDto(it.property.asOWLDataProperty().iri.toString(), it.getObject().literal, true)
    }.toList()
    return IndividualDto(ind.iri.toString(), labelOf(ind.iri), types,
        objAssertions + dataAssertions, annotationsOf(ind.iri))
}
```

`ontology/IndividualService.kt`:
```kotlin
package com.ontostudio.ontology

import com.ontostudio.core.IriFactory
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.IndividualDto
import org.semanticweb.owlapi.model.*
import org.springframework.stereotype.Service

@Service
class IndividualService(private val holder: OntologyHolder, private val mapper: OntologyMapper) {
    private val df get() = holder.dataFactory
    private val ont get() = holder.ontology
    private val mgr get() = holder.manager

    fun list(typeFilter: String?): List<IndividualDto> = synchronized(holder.lock) {
        ont.individualsInSignature().map { mapper.individualDto(it) }
            .filter { typeFilter == null || it.types.contains(typeFilter) }.toList()
    }

    fun create(label: String, types: List<String>): IndividualDto = synchronized(holder.lock) {
        val iri = IriFactory(holder.baseIri).forLabel(label, ont.individualsInSignature().map { it.iri }.toSet())
        val ind = df.getOWLNamedIndividual(iri)
        mgr.addAxiom(ont, df.getOWLDeclarationAxiom(ind))
        mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
        types.forEach { mgr.addAxiom(ont, df.getOWLClassAssertionAxiom(df.getOWLClass(IRI.create(it)), ind)) }
        mapper.individualDto(ind)
    }

    fun addObjectAssertion(iri: String, prop: String, targetIri: String): IndividualDto = synchronized(holder.lock) {
        val ind = df.getOWLNamedIndividual(IRI.create(iri))
        mgr.addAxiom(ont, df.getOWLObjectPropertyAssertionAxiom(
            df.getOWLObjectProperty(IRI.create(prop)), ind, df.getOWLNamedIndividual(IRI.create(targetIri))))
        mapper.individualDto(ind)
    }

    fun addDataAssertion(iri: String, prop: String, literal: String): IndividualDto = synchronized(holder.lock) {
        val ind = df.getOWLNamedIndividual(IRI.create(iri))
        mgr.addAxiom(ont, df.getOWLDataPropertyAssertionAxiom(
            df.getOWLDataProperty(IRI.create(prop)), ind, df.getOWLLiteral(literal)))
        mapper.individualDto(ind)
    }

    fun delete(iri: String) = synchronized(holder.lock) {
        val ind = df.getOWLNamedIndividual(IRI.create(iri))
        mgr.removeAxioms(ont, ont.referencingAxioms(ind).stream())
    }
}
```

`api/IndividualController.kt`:
```kotlin
package com.ontostudio.api

import com.ontostudio.dto.IndividualDto
import com.ontostudio.ontology.IndividualService
import org.springframework.web.bind.annotation.*

data class CreateIndividualRequest(val label: String, val types: List<String> = emptyList())
data class AssertionRequest(val property: String, val value: String, val isLiteral: Boolean)

@RestController
@RequestMapping("/api/individuals")
class IndividualController(private val service: IndividualService) {
    @GetMapping fun list(@RequestParam(required = false) type: String?): List<IndividualDto> = service.list(type)
    @PostMapping fun create(@RequestBody r: CreateIndividualRequest): IndividualDto = service.create(r.label, r.types)

    @PostMapping("/{iri}/assertions")
    fun addAssertion(@PathVariable iri: String, @RequestBody r: AssertionRequest): IndividualDto =
        if (r.isLiteral) service.addDataAssertion(iri, r.property, r.value)
        else service.addObjectAssertion(iri, r.property, r.value)

    @DeleteMapping("/{iri}") fun delete(@PathVariable iri: String) = service.delete(iri)
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && ./gradlew test --tests "*IndividualServiceTest*"`
Expected: PASS.

- [ ] **Step 5: 라운드트립 통합 테스트 작성** — `api/RoundTripIntegrationTest.kt`:
```kotlin
package com.ontostudio.api

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.io.IoService
import com.ontostudio.ontology.ClassService
import com.ontostudio.ontology.IndividualService
import kotlin.test.*

class RoundTripIntegrationTest {
    @Test fun `create then export then reload preserves entities`() {
        val h = OntologyHolder(); h.newOntology("http://ex/onto", "http://ex#")
        val m = OntologyMapper(h); val io = IoService(h)
        val cls = ClassService(h, m); val ind = IndividualService(h, m)

        val dog = cls.create("Dog", null)
        ind.create("Fido", listOf(dog.iri))

        val ttl = io.export("turtle")
        io.load(ttl, "http://ex#")

        assertEquals(1, m.meta().counts["classes"])
        assertEquals(1, m.meta().counts["individuals"])
    }
}
```

- [ ] **Step 6: 라운드트립 테스트 통과 확인**

Run: `cd backend && ./gradlew test --tests "*RoundTripIntegrationTest*"`
Expected: PASS.

- [ ] **Step 7: 커밋 (초안 완료 지점)**

```bash
git add backend
git commit -m "feat(p1): 개체 CRUD + assertion + 라운드트립 테스트 (초안 기본기능 완료)"
```

---

## Task 7: 검색/Usage + 트리 엔드포인트 (P1.5 — 부가 기능)

**Files:**
- Create: `backend/src/main/kotlin/com/ontostudio/ontology/SearchService.kt`
- Create: `backend/src/main/kotlin/com/ontostudio/api/SearchController.kt`
- Modify: `backend/src/main/kotlin/com/ontostudio/api/ClassController.kt` (tree 엔드포인트 추가)
- Modify: `backend/src/main/kotlin/com/ontostudio/ontology/ClassService.kt` (tree 빌드 추가)
- Test: `backend/src/test/kotlin/com/ontostudio/ontology/SearchServiceTest.kt`

**Interfaces:**
- Consumes: `OntologyHolder`, `OntologyMapper`
- Produces:
  - `SearchService.search(q: String): List<SearchHit>` where `SearchHit(iri, label, kind)`
  - `SearchService.usage(iri: String): List<String>` (공리 문자열 목록)
  - `ClassService.tree(): List<ClassNode>` where `ClassNode(iri, label, children)`

- [ ] **Step 1: 실패 테스트 작성** — `SearchServiceTest.kt`:
```kotlin
package com.ontostudio.ontology

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import kotlin.test.*

class SearchServiceTest {
    @Test fun `search finds class by label`() {
        val h = OntologyHolder(); h.newOntology(null, "http://ex#")
        val m = OntologyMapper(h)
        ClassService(h, m).create("Animal", null)
        val hits = SearchService(h, m).search("anim")
        assertTrue(hits.any { it.label == "Animal" })
    }
}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && ./gradlew test --tests "*SearchServiceTest*"`
Expected: FAIL — `SearchService` 없음.

- [ ] **Step 3: 최소 구현**

`ontology/SearchService.kt`:
```kotlin
package com.ontostudio.ontology

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import org.semanticweb.owlapi.model.IRI
import org.springframework.stereotype.Service

data class SearchHit(val iri: String, val label: String?, val kind: String)

@Service
class SearchService(private val holder: OntologyHolder, private val mapper: OntologyMapper) {
    fun search(q: String): List<SearchHit> = synchronized(holder.lock) {
        val o = holder.ontology; val ql = q.lowercase()
        fun match(iri: IRI, kind: String): SearchHit? {
            val label = mapper.labelOf(iri)
            val hit = iri.toString().lowercase().contains(ql) || (label?.lowercase()?.contains(ql) == true)
            return if (hit) SearchHit(iri.toString(), label, kind) else null
        }
        buildList {
            o.classesInSignature().forEach { match(it.iri, "class")?.let(::add) }
            o.objectPropertiesInSignature().forEach { match(it.iri, "objectProperty")?.let(::add) }
            o.dataPropertiesInSignature().forEach { match(it.iri, "dataProperty")?.let(::add) }
            o.individualsInSignature().forEach { match(it.iri, "individual")?.let(::add) }
        }
    }

    fun usage(iri: String): List<String> = synchronized(holder.lock) {
        val entity = holder.dataFactory.getOWLClass(IRI.create(iri))
        holder.ontology.referencingAxioms(entity).map { it.toString() }.toList()
    }
}
```

`ClassService.kt`에 tree 추가:
```kotlin
import com.ontostudio.dto.ClassNode  // dto/Dtos.kt 에 추가
// data class ClassNode(val iri: String, val label: String?, val children: List<ClassNode>)

fun tree(): List<com.ontostudio.dto.ClassNode> = synchronized(holder.lock) {
    val thing = df.owlThing
    fun childrenOf(parent: OWLClass): List<com.ontostudio.dto.ClassNode> =
        ont.classesInSignature().filter { c ->
            ont.subClassAxiomsForSubClass(c).any { !it.superClass.isAnonymous && it.superClass.asOWLClass() == parent }
        }.map { com.ontostudio.dto.ClassNode(it.iri.toString(), mapper.labelOf(it.iri), childrenOf(it)) }.toList()
    childrenOf(thing)
}
```
> `dto/Dtos.kt`에 `data class ClassNode(val iri: String, val label: String?, val children: List<ClassNode>)` 추가.

`api/SearchController.kt`:
```kotlin
package com.ontostudio.api

import com.ontostudio.ontology.SearchHit
import com.ontostudio.ontology.SearchService
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api")
class SearchController(private val service: SearchService) {
    @GetMapping("/search") fun search(@RequestParam q: String): List<SearchHit> = service.search(q)
    @GetMapping("/usage/{iri}") fun usage(@PathVariable iri: String): List<String> = service.usage(iri)
}
```

`ClassController.kt`에 tree 엔드포인트 추가:
```kotlin
@GetMapping("/tree")
fun tree(): List<com.ontostudio.dto.ClassNode> = service.tree()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && ./gradlew test --tests "*SearchServiceTest*"`
Expected: PASS.

- [ ] **Step 5: 전체 테스트 실행**

Run: `cd backend && ./gradlew test`
Expected: 전체 PASS.

- [ ] **Step 6: 커밋**

```bash
git add backend
git commit -m "feat(p1): 검색/usage + 클래스 트리 엔드포인트 (P1.5 부가기능)"
```

---

## Self-Review 결과

- **스펙 커버리지**: 설계 5절 API 전부 태스크 매핑됨 — ontology(T3)/classes(T4)/properties(T5)/individuals(T6)/search(T7). 추론·AI·프론트는 의도적으로 P1 범위 밖.
- **점진성**: T1~T6이 "기본 기능 동작"(초안), T7이 부가 기능 — 사용자 요청 원칙 반영.
- **타입 일관성**: DTO 명칭(ClassDto/ObjectPropertyDto/DataPropertyDto/IndividualDto)과 Service 시그니처가 태스크 간 일치.
- **알려진 빌드 주의점(실행 시 확인)**:
  - OWL API의 `Optional`은 Guava `Optional` — `.orNull()` 또는 `.asLiteral().orNull()` import 경로 확인.
  - OWL API 5.x 스트림 API(`*InSignature()`, `*Axioms()`)는 Java Stream → Kotlin에서 `.map{}.toList()` 사용.
  - `{iri}` PathVariable은 URL 인코딩된 전체 IRI 가정(프론트 `encodeURIComponent`).
  - Gradle wrapper(`./gradlew`)는 T1에서 `gradle wrapper`로 생성 필요할 수 있음.
