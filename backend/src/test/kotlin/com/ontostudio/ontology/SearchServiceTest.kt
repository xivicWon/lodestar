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
