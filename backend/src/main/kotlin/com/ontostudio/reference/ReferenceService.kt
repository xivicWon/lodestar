package com.ontostudio.reference

import com.ontostudio.dto.AnnotationDto
import com.ontostudio.dto.ApiException
import com.ontostudio.dto.ClassDto
import com.ontostudio.dto.ReferenceMetaDto
import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLOntology
import org.semanticweb.owlapi.model.OWLOntologyCreationException
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import java.io.ByteArrayInputStream

@Service
class ReferenceService(private val refHolder: ReferenceHolder) {

    fun load(bytes: ByteArray, source: String?): ReferenceMetaDto = synchronized(refHolder.lock) {
        val mgr = OWLManager.createOWLOntologyManager()
        val ont = try {
            mgr.loadOntologyFromOntologyDocument(ByteArrayInputStream(bytes))
        } catch (e: OWLOntologyCreationException) {
            throw ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "reference_load_failed",
                "참조 온톨로지를 읽을 수 없습니다: ${e.message}", null)
        }
        refHolder.set(mgr, ont, source)
        meta()
    }

    fun classes(): List<ClassDto> = synchronized(refHolder.lock) {
        val ont = refHolder.ontology ?: return emptyList()
        ont.classesInSignature().toList()
            .filter { !it.isOWLThing && !it.isOWLNothing }
            .map { cls -> ClassDto(cls.iri.toString(), labelOf(ont, cls.iri), emptyList(), annotationsOf(ont, cls.iri)) }
    }

    fun meta(): ReferenceMetaDto = synchronized(refHolder.lock) {
        val ont = refHolder.ontology
        ReferenceMetaDto(
            ontologyIri = ont?.ontologyID?.ontologyIRI?.orElse(null)?.toString(),
            source = refHolder.source,
            classCount = ont?.classesInSignature()?.toList()?.count { !it.isOWLThing && !it.isOWLNothing } ?: 0,
        )
    }

    fun clear() = refHolder.clear()

    fun containsClass(iri: String): Boolean = synchronized(refHolder.lock) {
        refHolder.ontology?.containsClassInSignature(IRI.create(iri)) ?: false
    }

    private fun labelOf(ont: OWLOntology, iri: IRI): String? {
        val rdfsLabel = IRI.create("http://www.w3.org/2000/01/rdf-schema#label")
        return ont.annotationAssertionAxioms(iri).toList()
            .mapNotNull { ax -> if (ax.property.iri == rdfsLabel) ax.value.asLiteral().orElse(null)?.literal else null }
            .firstOrNull()
    }

    private fun annotationsOf(ont: OWLOntology, iri: IRI): List<AnnotationDto> =
        ont.annotationAssertionAxioms(iri).map {
            val lit = it.value.asLiteral().orElse(null)
            AnnotationDto(it.property.iri.toString(), lit?.literal ?: it.value.toString(), lit?.lang?.ifBlank { null })
        }.toList()
}
