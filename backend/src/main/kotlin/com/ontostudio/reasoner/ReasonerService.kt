package com.ontostudio.reasoner

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.InferredEdgeDto
import com.ontostudio.dto.ReasonResultDto
import org.semanticweb.HermiT.ReasonerFactory
import org.semanticweb.owlapi.reasoner.InconsistentOntologyException
import org.semanticweb.owlapi.reasoner.OWLReasoner
import org.springframework.stereotype.Service

@Service
class ReasonerService(private val holder: OntologyHolder) {

    private fun inferredEdges(reasoner: OWLReasoner): List<InferredEdgeDto> {
        val ont = holder.ontology
        val edges = mutableListOf<InferredEdgeDto>()
        ont.classesInSignature().filter { !it.isOWLThing && !it.isOWLNothing }.toList().forEach { c ->
            val asserted = ont.subClassAxiomsForSubClass(c).toList()
                .map { it.superClass }.filter { !it.isAnonymous }
                .map { it.asOWLClass() }.toSet()
            reasoner.getSuperClasses(c, true).entities().toList()
                .filter { !it.isOWLThing && !it.isOWLNothing }
                .forEach { sup ->
                    if (sup != c && sup !in asserted && ont.containsClassInSignature(sup.iri)) {
                        edges.add(InferredEdgeDto(c.iri.toString(), sup.iri.toString()))
                    }
                }
        }
        return edges
    }

    fun reason(): ReasonResultDto = synchronized(holder.lock) {
        val reasoner: OWLReasoner = ReasonerFactory().createReasoner(holder.ontology)
        try {
            val consistent = try {
                reasoner.isConsistent
            } catch (e: InconsistentOntologyException) {
                false
            }
            if (!consistent) {
                ReasonResultDto(false, emptyList(), emptyList())
            } else {
                ReasonResultDto(true, emptyList(), inferredEdges(reasoner))
            }
        } finally {
            reasoner.dispose()
        }
    }
}
