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
