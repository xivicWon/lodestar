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
