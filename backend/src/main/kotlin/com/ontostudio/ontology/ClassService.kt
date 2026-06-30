package com.ontostudio.ontology

import com.ontostudio.core.IriFactory
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.ApiException
import com.ontostudio.dto.ClassDto
import com.ontostudio.dto.ClassNode
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLAnnotationAssertionAxiom
import org.semanticweb.owlapi.model.OWLClass
import org.semanticweb.owlapi.model.OWLDeclarationAxiom
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service

@Service
class ClassService(private val holder: OntologyHolder, private val mapper: OntologyMapper) {
    private val df get() = holder.dataFactory
    private val ont get() = holder.ontology
    private val mgr get() = holder.manager

    private fun classOrThrow(iri: String) = synchronized(holder.lock) {
        val c = df.getOWLClass(IRI.create(iri))
        if (!ont.containsClassInSignature(c.iri))
            throw ApiException(HttpStatus.NOT_FOUND, "not_found", "클래스 없음", iri)
        c
    }

    fun list(): List<ClassDto> = synchronized(holder.lock) {
        ont.classesInSignature().filter { !it.isOWLThing }.map { mapper.classDto(it) }.toList()
    }

    fun get(iri: String): ClassDto = synchronized(holder.lock) {
        mapper.classDto(classOrThrow(iri))
    }

    fun create(label: String, superClass: String?): ClassDto = synchronized(holder.lock) {
        val iri = IriFactory(holder.baseIri).forLabel(label, ont.classesInSignature().map { it.iri }.toList().toHashSet())
        val cls = df.getOWLClass(iri)
        mgr.addAxiom(ont, df.getOWLDeclarationAxiom(cls))
        mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
        if (superClass != null)
            mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(cls, df.getOWLClass(IRI.create(superClass))))
        mapper.classDto(cls)
    }

    fun setLabel(iri: String, label: String): ClassDto = synchronized(holder.lock) {
        val cls = classOrThrow(iri)
        ont.annotationAssertionAxioms(cls.iri).toList()
            .filter { it.property.iri == df.rdfsLabel.iri }
            .forEach { mgr.removeAxiom(ont, it) }
        mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(cls.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(label))))
        mapper.classDto(cls)
    }

    fun setSuperClasses(iri: String, supers: List<String>): ClassDto = synchronized(holder.lock) {
        val cls = classOrThrow(iri)
        ont.subClassAxiomsForSubClass(cls).toList().forEach { mgr.removeAxiom(ont, it) }
        supers.forEach { mgr.addAxiom(ont, df.getOWLSubClassOfAxiom(cls, df.getOWLClass(IRI.create(it)))) }
        mapper.classDto(cls)
    }

    fun tree(): List<ClassNode> = synchronized(holder.lock) {
        fun childrenOf(parent: OWLClass, visited: MutableSet<OWLClass>): List<ClassNode> {
            if (parent in visited) return emptyList()
            visited.add(parent)
            return ont.classesInSignature().filter { c ->
                ont.subClassAxiomsForSubClass(c).anyMatch { ax ->
                    !ax.superClass.isAnonymous && ax.superClass.asOWLClass() == parent
                }
            }.map { c -> ClassNode(c.iri.toString(), mapper.labelOf(c.iri), childrenOf(c, visited)) }.toList()
        }
        childrenOf(df.owlThing, mutableSetOf())
    }

    fun delete(iri: String, cascade: Boolean) = synchronized(holder.lock) {
        val cls = classOrThrow(iri)
        val allReferencing = ont.referencingAxioms(cls).toList()
        if (!cascade) {
            val external = allReferencing.filter {
                it !is OWLDeclarationAxiom &&
                !(it is OWLAnnotationAssertionAxiom && it.subject == cls.iri)
            }
            if (external.isNotEmpty())
                throw ApiException(HttpStatus.CONFLICT, "in_use", "사용 중인 클래스입니다", iri)
        }
        mgr.removeAxioms(ont, allReferencing.stream())
    }
}
