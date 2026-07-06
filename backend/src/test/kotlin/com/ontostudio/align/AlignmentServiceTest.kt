package com.ontostudio.align

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.ApiException
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.MatchType
import com.ontostudio.reference.ReferenceHolder
import com.ontostudio.reference.ReferenceService
import org.semanticweb.owlapi.model.IRI
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class AlignmentServiceTest {
    private val srcIri = "http://lodestar/rdb/ex#tbl_a"
    private val tgtIri = "http://example.org/ref#Person"
    private val refTtl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/ref#> .
        <http://example.org/ref> a owl:Ontology .
        ex:Person a owl:Class .
    """.trimIndent().toByteArray()

    // 소스 온톨로지에 클래스 tbl_a 를 심고, 참조엔 Person 을 로드한 서비스 세트
    private fun fixture(): AlignmentService {
        val holder = OntologyHolder()
        val df = holder.dataFactory
        holder.manager.addAxiom(holder.ontology, df.getOWLDeclarationAxiom(df.getOWLClass(IRI.create(srcIri))))
        val ref = ReferenceService(ReferenceHolder()).also { it.load(refTtl, "ref.ttl") }
        return AlignmentService(holder, ref)
    }

    @Test fun `create adds a SKOS closeMatch annotation assertion with confidence and provenance`() {
        val svc = fixture()
        val dto = svc.create(AlignmentRequest(srcIri, tgtIri, MatchType.CLOSE, 0.8))
        assertEquals(srcIri, dto.sourceIri)
        assertEquals(tgtIri, dto.targetIri)
        assertEquals(MatchType.CLOSE, dto.matchType)
        assertEquals(0.8, dto.confidence)
        assertEquals("manual", dto.provenance)
    }

    @Test fun `create rejects an unknown source class`() {
        val svc = fixture()
        val ex = assertFailsWith<ApiException> {
            svc.create(AlignmentRequest("http://lodestar/rdb/ex#nope", tgtIri, MatchType.CLOSE, null))
        }
        assertTrue(ex.error.contains("source"))
    }

    @Test fun `create rejects an unknown target class`() {
        val svc = fixture()
        assertFailsWith<ApiException> {
            svc.create(AlignmentRequest(srcIri, "http://example.org/ref#Nope", MatchType.CLOSE, null))
        }
    }
}
