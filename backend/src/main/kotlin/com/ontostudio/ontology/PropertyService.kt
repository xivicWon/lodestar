package com.ontostudio.ontology

import com.ontostudio.core.IriFactory
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.core.externalReferencingAxioms
import com.ontostudio.dto.ApiException
import com.ontostudio.dto.DataPropertyDto
import com.ontostudio.dto.ObjectPropertyDto
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLAxiom
import org.semanticweb.owlapi.model.OWLEntity
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service

@Service
class PropertyService(private val holder: OntologyHolder, private val mapper: OntologyMapper) {
    private val df get() = holder.dataFactory
    private val ont get() = holder.ontology
    private val mgr get() = holder.manager

    fun listObject(): List<ObjectPropertyDto> = synchronized(holder.lock) {
        ont.objectPropertiesInSignature().map { mapper.objectPropertyDto(it) }.toList()
    }

    fun listData(): List<DataPropertyDto> = synchronized(holder.lock) {
        ont.dataPropertiesInSignature().map { mapper.dataPropertyDto(it) }.toList()
    }

    fun createObject(label: String, domains: List<String>, ranges: List<String>): ObjectPropertyDto =
        synchronized(holder.lock) {
            val iri = IriFactory(holder.baseIri).forLabel(
                label,
                ont.objectPropertiesInSignature().map { it.iri }.toList().toHashSet()
            )
            val p = df.getOWLObjectProperty(iri)
            mgr.addAxiom(ont, df.getOWLDeclarationAxiom(p))
            mgr.addAxiom(
                ont,
                df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label)))
            )
            domains.forEach { mgr.addAxiom(ont, df.getOWLObjectPropertyDomainAxiom(p, df.getOWLClass(IRI.create(it)))) }
            ranges.forEach { mgr.addAxiom(ont, df.getOWLObjectPropertyRangeAxiom(p, df.getOWLClass(IRI.create(it)))) }
            mapper.objectPropertyDto(p)
        }

    fun createData(label: String, domains: List<String>, range: String?): DataPropertyDto =
        synchronized(holder.lock) {
            val iri = IriFactory(holder.baseIri).forLabel(
                label,
                ont.dataPropertiesInSignature().map { it.iri }.toList().toHashSet()
            )
            val p = df.getOWLDataProperty(iri)
            mgr.addAxiom(ont, df.getOWLDeclarationAxiom(p))
            mgr.addAxiom(
                ont,
                df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label)))
            )
            domains.forEach { mgr.addAxiom(ont, df.getOWLDataPropertyDomainAxiom(p, df.getOWLClass(IRI.create(it)))) }
            if (range != null)
                mgr.addAxiom(ont, df.getOWLDataPropertyRangeAxiom(p, df.getOWLDatatype(IRI.create(range))))
            mapper.dataPropertyDto(p)
        }

    fun setObjectLabel(iri: String, label: String): ObjectPropertyDto = synchronized(holder.lock) {
        val owlIri = IRI.create(iri)
        if (!ont.containsObjectPropertyInSignature(owlIri))
            throw ApiException(HttpStatus.NOT_FOUND, "not_found", "속성 없음", iri)
        val p = df.getOWLObjectProperty(owlIri)
        ont.annotationAssertionAxioms(p.iri).toList()
            .filter { it.property.iri == df.rdfsLabel.iri }
            .forEach { mgr.removeAxiom(ont, it) }
        mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
            p.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
        mapper.objectPropertyDto(p)
    }

    fun setObjectCharacteristics(iri: String, chars: List<String>): ObjectPropertyDto =
        synchronized(holder.lock) {
            val p = df.getOWLObjectProperty(IRI.create(iri))
            // Materialize streams with .toList() BEFORE mutation to avoid ConcurrentModificationException
            ont.functionalObjectPropertyAxioms(p).toList().forEach { mgr.removeAxiom(ont, it) }
            ont.transitiveObjectPropertyAxioms(p).toList().forEach { mgr.removeAxiom(ont, it) }
            ont.symmetricObjectPropertyAxioms(p).toList().forEach { mgr.removeAxiom(ont, it) }
            chars.forEach { c ->
                val ax: OWLAxiom = when (c.uppercase()) {
                    "FUNCTIONAL" -> df.getOWLFunctionalObjectPropertyAxiom(p)
                    "TRANSITIVE" -> df.getOWLTransitiveObjectPropertyAxiom(p)
                    "SYMMETRIC"  -> df.getOWLSymmetricObjectPropertyAxiom(p)
                    else -> throw ApiException(HttpStatus.BAD_REQUEST, "bad_characteristic", "알 수 없는 특성: $c", iri)
                }
                mgr.addAxiom(ont, ax)
            }
            mapper.objectPropertyDto(p)
        }

    fun delete(type: String, iri: String, cascade: Boolean) = synchronized(holder.lock) {
        val owlIri = IRI.create(iri)
        val entity: OWLEntity = when (type) {
            "object" -> {
                if (!ont.containsObjectPropertyInSignature(owlIri))
                    throw ApiException(HttpStatus.NOT_FOUND, "not_found", "속성 없음", iri)
                df.getOWLObjectProperty(owlIri)
            }
            "data" -> {
                if (!ont.containsDataPropertyInSignature(owlIri))
                    throw ApiException(HttpStatus.NOT_FOUND, "not_found", "속성 없음", iri)
                df.getOWLDataProperty(owlIri)
            }
            else -> {
                if (!ont.containsAnnotationPropertyInSignature(owlIri))
                    throw ApiException(HttpStatus.NOT_FOUND, "not_found", "속성 없음", iri)
                df.getOWLAnnotationProperty(owlIri)
            }
        }
        if (!cascade && externalReferencingAxioms(ont, entity).isNotEmpty())
            throw ApiException(HttpStatus.CONFLICT, "in_use", "사용 중인 속성입니다", iri)
        // Materialize with .toList() first to avoid ConcurrentModificationException
        mgr.removeAxioms(ont, ont.referencingAxioms(entity).toList().stream())
    }
}
