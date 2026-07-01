package com.ontostudio.dto

data class AnnotationDto(val property: String, val value: String, val lang: String? = null)

data class ClassDto(
    val iri: String, val label: String?,
    val superClasses: List<String>, val annotations: List<AnnotationDto>
)

data class ObjectPropertyDto(
    val iri: String, val label: String?,
    val domains: List<String>, val ranges: List<String>,
    val characteristics: List<String>, val inverseOf: String?,
    val annotations: List<AnnotationDto>
)

data class DataPropertyDto(
    val iri: String, val label: String?,
    val domains: List<String>, val range: String?,
    val functional: Boolean, val annotations: List<AnnotationDto>
)

data class PropertyAssertionDto(val property: String, val value: String, val isLiteral: Boolean)

data class IndividualDto(
    val iri: String, val label: String?, val types: List<String>,
    val assertions: List<PropertyAssertionDto>, val annotations: List<AnnotationDto>
)

data class OntologyMetaDto(
    val ontologyIri: String?, val baseIri: String,
    val prefixes: Map<String, String>, val counts: Map<String, Int>
)

data class NewOntologyRequest(val ontologyIri: String?, val baseIri: String)

data class ClassNode(val iri: String, val label: String?, val children: List<ClassNode>)

data class InferredEdgeDto(val sub: String, val sup: String)
data class ReasonResultDto(
    val consistent: Boolean,
    val unsatisfiableClasses: List<String>,
    val inferredSubClassOf: List<InferredEdgeDto>
)
