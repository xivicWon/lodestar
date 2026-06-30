package com.ontostudio.core

import com.ontostudio.dto.OntologyMetaDto
import org.semanticweb.owlapi.model.IRI
import org.springframework.stereotype.Component

@Component
class OntologyMapper(private val holder: OntologyHolder) {

    fun labelOf(iri: IRI): String? = synchronized(holder.lock) {
        val rdfsLabel = holder.dataFactory.rdfsLabel.iri
        // annotationAssertionAxioms returns Java Stream; toList() is Java 16+ terminal op
        holder.ontology.annotationAssertionAxioms(iri)
            .toList()
            .mapNotNull { ax ->
                // OWL API 5.x asLiteral() returns java.util.Optional<OWLLiteral>
                if (ax.property.iri == rdfsLabel) ax.value.asLiteral().orElse(null)?.literal else null
            }
            .firstOrNull()
    }

    fun meta(): OntologyMetaDto = synchronized(holder.lock) {
        val o = holder.ontology
        // OWL API 5.x OWLOntologyID.getOntologyIRI() returns java.util.Optional<IRI>
        val ontologyIriStr = o.ontologyID.ontologyIRI.orElse(null)?.toString()
        OntologyMetaDto(
            ontologyIri = ontologyIriStr,
            baseIri = holder.baseIri,
            prefixes = emptyMap(),
            counts = mapOf(
                "classes"     to o.classesInSignature().count().toInt(),
                "objectProps" to o.objectPropertiesInSignature().count().toInt(),
                "dataProps"   to o.dataPropertiesInSignature().count().toInt(),
                "individuals" to o.individualsInSignature().count().toInt()
            )
        )
    }
}
