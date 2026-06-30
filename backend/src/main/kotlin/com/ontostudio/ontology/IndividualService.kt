package com.ontostudio.ontology

import com.ontostudio.core.IriFactory
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.IndividualDto
import org.semanticweb.owlapi.model.IRI
import org.springframework.stereotype.Service

@Service
class IndividualService(private val holder: OntologyHolder, private val mapper: OntologyMapper) {
    private val df get() = holder.dataFactory
    private val ont get() = holder.ontology
    private val mgr get() = holder.manager

    fun list(typeFilter: String?): List<IndividualDto> = synchronized(holder.lock) {
        ont.individualsInSignature().map { mapper.individualDto(it) }
            .filter { typeFilter == null || it.types.contains(typeFilter) }.toList()
    }

    fun create(label: String, types: List<String>): IndividualDto = synchronized(holder.lock) {
        val iri = IriFactory(holder.baseIri).forLabel(label, ont.individualsInSignature().map { it.iri }.toList().toHashSet())
        val ind = df.getOWLNamedIndividual(iri)
        mgr.addAxiom(ont, df.getOWLDeclarationAxiom(ind))
        mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
        types.forEach { mgr.addAxiom(ont, df.getOWLClassAssertionAxiom(df.getOWLClass(IRI.create(it)), ind)) }
        mapper.individualDto(ind)
    }

    fun addObjectAssertion(iri: String, prop: String, targetIri: String): IndividualDto = synchronized(holder.lock) {
        val ind = df.getOWLNamedIndividual(IRI.create(iri))
        mgr.addAxiom(ont, df.getOWLObjectPropertyAssertionAxiom(
            df.getOWLObjectProperty(IRI.create(prop)), ind, df.getOWLNamedIndividual(IRI.create(targetIri))))
        mapper.individualDto(ind)
    }

    fun addDataAssertion(iri: String, prop: String, literal: String): IndividualDto = synchronized(holder.lock) {
        val ind = df.getOWLNamedIndividual(IRI.create(iri))
        mgr.addAxiom(ont, df.getOWLDataPropertyAssertionAxiom(
            df.getOWLDataProperty(IRI.create(prop)), ind, df.getOWLLiteral(literal)))
        mapper.individualDto(ind)
    }

    fun delete(iri: String) = synchronized(holder.lock) {
        val ind = df.getOWLNamedIndividual(IRI.create(iri))
        val axioms = ont.referencingAxioms(ind).toList()
        mgr.removeAxioms(ont, axioms.stream())
    }
}
