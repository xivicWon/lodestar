package com.ontostudio.ontology

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.ApiException
import org.springframework.http.HttpStatus
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

    @Test fun `delete standalone class with cascade false succeeds`() {
        val (s, _, _) = svc()
        val animal = s.create("Animal", null)
        s.delete(animal.iri, cascade = false)
        assertEquals(0, s.list().size)
    }

    @Test fun `delete class referenced by subclass with cascade false throws 409`() {
        val (s, _, _) = svc()
        val animal = s.create("Animal", null)
        s.create("Dog", animal.iri)
        val e = assertFailsWith<ApiException> { s.delete(animal.iri, cascade = false) }
        assertEquals(HttpStatus.CONFLICT, e.status)
    }

    @Test fun `tree does not stack overflow on cyclic hierarchy`() {
        val (s, h, _) = svc()
        val a = s.create("A", null)
        val b = s.create("B", null)
        val df = h.dataFactory
        val mgr = h.manager
        val ont = h.ontology
        // Add A ⊑ B and B ⊑ A (cycle)
        mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(a.iri)), df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(b.iri))))
        mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(b.iri)), df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(a.iri))))
        assertNotNull(s.tree())
    }
}
