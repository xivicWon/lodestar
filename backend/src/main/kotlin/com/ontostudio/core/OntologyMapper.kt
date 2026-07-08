package com.ontostudio.core

import com.ontostudio.dto.AnnotationDto
import com.ontostudio.dto.ClassDto
import com.ontostudio.dto.DataPropertyDto
import com.ontostudio.dto.IndividualDto
import com.ontostudio.dto.ObjectPropertyDto
import com.ontostudio.dto.OntologyMetaDto
import com.ontostudio.dto.PropertyAssertionDto
import com.ontostudio.provenance.*
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLClass
import org.semanticweb.owlapi.model.OWLDataProperty
import org.semanticweb.owlapi.model.OWLDatatype
import org.semanticweb.owlapi.model.OWLNamedIndividual
import org.semanticweb.owlapi.model.OWLObjectProperty
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

    fun annotationsOf(iri: IRI): List<AnnotationDto> = synchronized(holder.lock) {
        holder.ontology.annotationAssertionAxioms(iri).map {
            val lit = it.value.asLiteral().orElse(null)
            AnnotationDto(
                it.property.iri.toString(),
                lit?.literal ?: it.value.toString(),
                lit?.lang?.ifBlank { null }
            )
        }.toList()
    }

    private fun provenanceOf(iri: IRI): ProvenanceDto? = synchronized(holder.lock) {
        val ax = holder.ontology.annotationAssertionAxioms(iri).toList()
        fun lit(propIri: String): String? = ax.firstOrNull { it.property.iri.toString() == propIri }
            ?.value?.asLiteral()?.orElse(null)?.literal
        val kind = ProvenanceVocab.kindOf(lit(ProvenanceVocab.KIND)) ?: return null
        val prov = ProvenanceVocab.provenanceOf(lit(ProvenanceVocab.PROVENANCE)) ?: Provenance.EXTRACTED
        val conf = lit(ProvenanceVocab.CONFIDENCE)?.toDoubleOrNull()
        ProvenanceDto(kind, prov, conf)
    }

    fun classDto(cls: OWLClass): ClassDto = synchronized(holder.lock) {
        val supers = holder.ontology.subClassAxiomsForSubClass(cls)
            .map { it.superClass }.filter { !it.isAnonymous }
            .map { it.asOWLClass().iri.toString() }.toList()
        return ClassDto(cls.iri.toString(), labelOf(cls.iri), supers, annotationsOf(cls.iri))
    }

    fun objectPropertyDto(p: OWLObjectProperty): ObjectPropertyDto = synchronized(holder.lock) {
        val o = holder.ontology
        val chars = buildList {
            if (o.functionalObjectPropertyAxioms(p).findAny().isPresent) add("FUNCTIONAL")
            if (o.transitiveObjectPropertyAxioms(p).findAny().isPresent) add("TRANSITIVE")
            if (o.symmetricObjectPropertyAxioms(p).findAny().isPresent) add("SYMMETRIC")
        }
        ObjectPropertyDto(
            p.iri.toString(), labelOf(p.iri),
            o.objectPropertyDomainAxioms(p).map { it.domain }.filter { !it.isAnonymous }
                .map { it.asOWLClass().iri.toString() }.toList(),
            o.objectPropertyRangeAxioms(p).map { it.range }.filter { !it.isAnonymous }
                .map { it.asOWLClass().iri.toString() }.toList(),
            chars, null, annotationsOf(p.iri),
            provenance = provenanceOf(p.iri)
        )
    }

    fun dataPropertyDto(p: OWLDataProperty): DataPropertyDto = synchronized(holder.lock) {
        val o = holder.ontology
        val range = o.dataPropertyRangeAxioms(p).map { it.range }
            .toList().filterIsInstance<OWLDatatype>().firstOrNull()?.iri?.toString()
        DataPropertyDto(
            p.iri.toString(), labelOf(p.iri),
            o.dataPropertyDomainAxioms(p).map { it.domain }.filter { !it.isAnonymous }
                .map { it.asOWLClass().iri.toString() }.toList(),
            range, o.functionalDataPropertyAxioms(p).findAny().isPresent, annotationsOf(p.iri)
        )
    }

    fun individualDto(ind: OWLNamedIndividual): IndividualDto = synchronized(holder.lock) {
        val o = holder.ontology
        val types = o.classAssertionAxioms(ind).map { it.classExpression }
            .filter { !it.isAnonymous }.map { it.asOWLClass().iri.toString() }.toList()
        val objAssertions = o.objectPropertyAssertionAxioms(ind).map {
            PropertyAssertionDto(
                it.property.asOWLObjectProperty().iri.toString(),
                it.`object`.asOWLNamedIndividual().iri.toString(),
                false
            )
        }.toList()
        val dataAssertions = o.dataPropertyAssertionAxioms(ind).map {
            PropertyAssertionDto(
                it.property.asOWLDataProperty().iri.toString(),
                it.`object`.literal,
                true
            )
        }.toList()
        IndividualDto(ind.iri.toString(), labelOf(ind.iri), types,
            objAssertions + dataAssertions, annotationsOf(ind.iri))
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
