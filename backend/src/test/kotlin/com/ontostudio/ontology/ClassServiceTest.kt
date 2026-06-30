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

    @Test fun `tree includes multi-parent class under both parents`() {
        // diamond: A and B are children of owl:Thing; C is child of both A and B; D is child of C
        // With global visited set, C is visited first via one parent and gets D as child,
        // but via the other parent C is already visited → childrenOf(C) returns [] → D is missing.
        // With ancestors-path fix, both paths are independent → D appears correctly under both.
        val (s, h, _) = svc()
        val owlThingIri = h.dataFactory.owlThing.iri.toString()
        val a = s.create("A", owlThingIri)
        val b = s.create("B", owlThingIri)
        val c = s.create("C", null)
        val d = s.create("D", null)
        val df = h.dataFactory
        val mgr = h.manager
        val ont = h.ontology
        mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(
            df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(c.iri)),
            df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(a.iri))))
        mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(
            df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(c.iri)),
            df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(b.iri))))
        mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(
            df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(d.iri)),
            df.getOWLClass(org.semanticweb.owlapi.model.IRI.create(c.iri))))
        val treeResult = s.tree()
        val aNode = treeResult.find { it.iri == a.iri }
        val bNode = treeResult.find { it.iri == b.iri }
        assertNotNull(aNode, "A should be in tree root")
        assertNotNull(bNode, "B should be in tree root")
        val cUnderA = aNode!!.children.find { it.iri == c.iri }
        val cUnderB = bNode!!.children.find { it.iri == c.iri }
        assertNotNull(cUnderA, "C should appear under A")
        assertNotNull(cUnderB, "C should appear under B")
        assertTrue(cUnderA!!.children.any { it.iri == d.iri }, "D should appear under C (via A path)")
        assertTrue(cUnderB!!.children.any { it.iri == d.iri }, "D should appear under C (via B path)")
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
