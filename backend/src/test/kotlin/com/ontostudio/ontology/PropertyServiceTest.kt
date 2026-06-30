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
