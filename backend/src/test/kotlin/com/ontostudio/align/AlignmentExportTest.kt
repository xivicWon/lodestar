package com.ontostudio.align

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.MatchType
import com.ontostudio.io.IoService
import com.ontostudio.reference.ReferenceHolder
import com.ontostudio.reference.ReferenceService
import org.semanticweb.owlapi.model.IRI
import kotlin.test.Test
import kotlin.test.assertTrue

class AlignmentExportTest {
    @Test fun `created alignment appears as a skos closeMatch triple in the Turtle export`() {
        val holder = OntologyHolder()
        val df = holder.dataFactory
        val srcIri = "http://lodestar/rdb/ex#tbl_a"
        val tgtIri = "http://example.org/ref#Person"
        holder.manager.addAxiom(holder.ontology, df.getOWLDeclarationAxiom(df.getOWLClass(IRI.create(srcIri))))
        val refTtl = """
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix ex: <http://example.org/ref#> .
            ex:Person a owl:Class .
        """.trimIndent().toByteArray()
        val ref = ReferenceService(ReferenceHolder()).also { it.load(refTtl, "ref.ttl") }
        AlignmentService(holder, ref).create(AlignmentRequest(srcIri, tgtIri, MatchType.CLOSE, 0.8))

        val turtle = String(IoService(holder).export("turtle"))
        assertTrue(turtle.contains("closeMatch"), "export should contain skos:closeMatch; was:\n$turtle")
        assertTrue(turtle.contains("tbl_a"))
    }
}
