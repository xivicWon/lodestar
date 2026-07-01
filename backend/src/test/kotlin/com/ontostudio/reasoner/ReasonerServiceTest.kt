package com.ontostudio.reasoner

import com.ontostudio.core.OntologyHolder
import com.ontostudio.io.IoService
import kotlin.test.*

class ReasonerServiceTest {
    private fun load(fixture: String): OntologyHolder {
        val h = OntologyHolder(); h.newOntology(null, "http://ex#")
        val bytes = this::class.java.getResourceAsStream("/com/ontostudio/fixtures/$fixture")!!.readBytes()
        IoService(h).load(bytes, "http://ex#")
        return h
    }

    @Test fun `consistent ontology reports consistent`() {
        val h = load("inconsistent.ttl") // reused below; here use a consistent one
        // build a trivially consistent ontology instead:
        h.newOntology(null, "http://ex#")
        val r = ReasonerService(h).reason()
        assertTrue(r.consistent)
        assertTrue(r.unsatisfiableClasses.isEmpty())
    }

    @Test fun `disjoint classes with shared individual is inconsistent`() {
        val h = load("inconsistent.ttl")
        val r = ReasonerService(h).reason()
        assertFalse(r.consistent)
    }
}
