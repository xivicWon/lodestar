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

    @Test fun `usage finds axioms for an object property`() {
        val h = OntologyHolder(); h.newOntology(null, "http://ex#")
        val m = OntologyMapper(h)
        val ps = PropertyService(h, m)
        val p = ps.createObject("hasPart", listOf("http://ex#Car"), emptyList())
        val axioms = SearchService(h, m).usage(p.iri)
        assertTrue(axioms.isNotEmpty())
    }
}
