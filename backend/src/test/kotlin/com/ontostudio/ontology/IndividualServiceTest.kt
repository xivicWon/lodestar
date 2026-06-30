package com.ontostudio.ontology

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.ApiException
import org.springframework.http.HttpStatus
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

    @Test fun `delete unknown individual throws 404`() {
        val s = svc()
        val e = assertFailsWith<ApiException> { s.delete("http://ex#nobody", false) }
        assertEquals(HttpStatus.NOT_FOUND, e.status)
    }

    @Test fun `delete individual referenced by assertion cascade false throws 409`() {
        val h = OntologyHolder(); h.newOntology(null, "http://ex#")
        val s = IndividualService(h, OntologyMapper(h))
        val fido = s.create("Fido", listOf("http://ex#Dog"))
        val owner = s.create("Owner", emptyList())
        s.addObjectAssertion(owner.iri, "http://ex#owns", fido.iri)
        val e = assertFailsWith<ApiException> { s.delete(fido.iri, false) }
        assertEquals(HttpStatus.CONFLICT, e.status)
    }
}
