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
