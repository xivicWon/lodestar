package com.ontostudio.align

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.AlignmentDto
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.ApiException
import com.ontostudio.reference.ReferenceService
import org.semanticweb.owlapi.model.AxiomType
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLAnnotation
import org.semanticweb.owlapi.model.OWLAnnotationAssertionAxiom
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

    fun list(): List<AlignmentDto> = synchronized(holder.lock) {
        holder.ontology.axioms(AxiomType.ANNOTATION_ASSERTION).toList().mapNotNull { ax -> toDto(ax) }
    }

    fun delete(sourceIri: String, targetIri: String, matchType: com.ontostudio.dto.MatchType) = synchronized(holder.lock) {
        val skos = SkosVocab.iriFor(matchType)
        val target = holder.ontology.axioms(AxiomType.ANNOTATION_ASSERTION).toList().firstOrNull { ax ->
            ax.property.iri.toString() == skos &&
                (ax.subject as? IRI)?.toString() == sourceIri &&
                ax.value.asIRI().orElse(null)?.toString() == targetIri
        }
        if (target != null) holder.manager.removeAxiom(holder.ontology, target)
    }

    private fun toDto(ax: OWLAnnotationAssertionAxiom): AlignmentDto? {
        val matchType = SkosVocab.matchTypeFor(ax.property.iri.toString()) ?: return null
        val src = (ax.subject as? IRI)?.toString() ?: return null
        val tgt = ax.value.asIRI().orElse(null)?.toString() ?: return null
        var confidence: Double? = null
        var provenance = "manual"
        ax.annotations().toList().forEach { a ->
            when (a.property.iri.toString()) {
                SkosVocab.CONFIDENCE -> confidence = a.value.asLiteral().orElse(null)?.parseDouble()
                SkosVocab.PROVENANCE -> provenance = a.value.asLiteral().orElse(null)?.literal ?: "manual"
            }
        }
        return AlignmentDto(src, tgt, matchType, confidence, provenance)
    }
}
