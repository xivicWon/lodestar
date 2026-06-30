package com.ontostudio.ontology

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import org.semanticweb.owlapi.model.IRI
import org.springframework.stereotype.Service

data class SearchHit(val iri: String, val label: String?, val kind: String)

@Service
class SearchService(private val holder: OntologyHolder, private val mapper: OntologyMapper) {
    fun search(q: String): List<SearchHit> = synchronized(holder.lock) {
        val o = holder.ontology; val ql = q.lowercase()
        fun match(iri: IRI, kind: String): SearchHit? {
            val label = mapper.labelOf(iri)
            val hit = iri.toString().lowercase().contains(ql) || (label?.lowercase()?.contains(ql) == true)
            return if (hit) SearchHit(iri.toString(), label, kind) else null
        }
        buildList {
            o.classesInSignature().forEach { match(it.iri, "class")?.let(::add) }
            o.objectPropertiesInSignature().forEach { match(it.iri, "objectProperty")?.let(::add) }
            o.dataPropertiesInSignature().forEach { match(it.iri, "dataProperty")?.let(::add) }
            o.individualsInSignature().forEach { match(it.iri, "individual")?.let(::add) }
        }
    }

    fun usage(iri: String): List<String> = synchronized(holder.lock) {
        val entity = holder.dataFactory.getOWLClass(IRI.create(iri))
        holder.ontology.referencingAxioms(entity).map { it.toString() }.toList()
    }
}
