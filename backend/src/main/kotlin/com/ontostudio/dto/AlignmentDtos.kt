package com.ontostudio.dto

enum class MatchType { EXACT, CLOSE, BROAD, NARROW, RELATED }

data class ReferenceMetaDto(
    val ontologyIri: String?,
    val source: String?,
    val classCount: Int,
)

data class AlignmentDto(
    val sourceIri: String,
    val targetIri: String,
    val matchType: MatchType,
    val confidence: Double?,
    val provenance: String,
)

data class AlignmentRequest(
    val sourceIri: String,
    val targetIri: String,
    val matchType: MatchType,
    val confidence: Double? = null,
)
