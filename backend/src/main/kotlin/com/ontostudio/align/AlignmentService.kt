package com.ontostudio.align

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.AlignmentDto
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.ApiException
import com.ontostudio.reference.ReferenceService
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLAnnotation
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service

@Service
class AlignmentService(
    private val holder: OntologyHolder,
    private val reference: ReferenceService,
) {
    fun create(req: AlignmentRequest): AlignmentDto = synchronized(holder.lock) {
        if (!holder.ontology.containsClassInSignature(IRI.create(req.sourceIri)))
            throw ApiException(HttpStatus.BAD_REQUEST, "invalid_source",
                "소스 클래스를 찾을 수 없습니다: ${req.sourceIri}", req.sourceIri)
        if (!reference.containsClass(req.targetIri))
            throw ApiException(HttpStatus.BAD_REQUEST, "invalid_target",
                "참조 클래스를 찾을 수 없습니다: ${req.targetIri}", req.targetIri)

        val df = holder.dataFactory
        val provenance = "manual"
        val annos = buildList<OWLAnnotation> {
            req.confidence?.let {
                add(df.getOWLAnnotation(df.getOWLAnnotationProperty(IRI.create(SkosVocab.CONFIDENCE)), df.getOWLLiteral(it)))
            }
            add(df.getOWLAnnotation(df.getOWLAnnotationProperty(IRI.create(SkosVocab.PROVENANCE)), df.getOWLLiteral(provenance)))
        }
        val ax = df.getOWLAnnotationAssertionAxiom(
            df.getOWLAnnotationProperty(IRI.create(SkosVocab.iriFor(req.matchType))),
            IRI.create(req.sourceIri),
            IRI.create(req.targetIri),
            annos,
        )
        holder.manager.addAxiom(holder.ontology, ax)
        AlignmentDto(req.sourceIri, req.targetIri, req.matchType, req.confidence, provenance)
    }
}
