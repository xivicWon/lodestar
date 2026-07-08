package com.ontostudio.provenance

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.PropertyService
import org.semanticweb.owlapi.model.IRI
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class ProvenanceRoundTripTest {
    private fun svc(): Pair<PropertyService, OntologyHolder> {
        val holder = OntologyHolder()
        val df = holder.dataFactory
        // 소스/타깃 클래스 선언
        listOf("http://ex#a", "http://ex#b").forEach {
            holder.manager.addAxiom(holder.ontology, df.getOWLDeclarationAxiom(df.getOWLClass(IRI.create(it))))
        }
        return PropertyService(holder, OntologyMapper(holder)) to holder
    }

    @Test fun `createObject persists kind provenance confidence and mapper reads them back`() {
        val (service, _) = svc()
        val dto = service.createObject(
            "placedBy", listOf("http://ex#a"), listOf("http://ex#b"),
            ProvenanceDto(RelationKind.NAMEPATTERN, Provenance.INFERRED, 0.6),
        )
        assertEquals(RelationKind.NAMEPATTERN, dto.provenance?.kind)
        assertEquals(Provenance.INFERRED, dto.provenance?.provenance)
        assertEquals(0.6, dto.provenance?.confidence)
    }

    @Test fun `createObject without provenance defaults to manual EXTRACTED`() {
        val (service, _) = svc()
        val dto = service.createObject("rel", listOf("http://ex#a"), listOf("http://ex#b"), null)
        assertEquals(RelationKind.MANUAL, dto.provenance?.kind)
        assertEquals(Provenance.EXTRACTED, dto.provenance?.provenance)
        assertNull(dto.provenance?.confidence)
    }
}
