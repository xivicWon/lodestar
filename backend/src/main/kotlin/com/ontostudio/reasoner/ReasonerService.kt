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
                ReasonResultDto(true, emptyList(), emptyList()) // inferred edges: Task 2
            }
        } finally {
            reasoner.dispose()
        }
    }
}
