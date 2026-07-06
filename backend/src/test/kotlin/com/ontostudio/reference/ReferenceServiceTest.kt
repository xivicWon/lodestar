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
