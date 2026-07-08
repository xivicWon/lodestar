package com.ontostudio.provenance

enum class Provenance { EXTRACTED, INFERRED, AMBIGUOUS }
enum class RelationKind { FK, NAMEPATTERN, AI, MANUAL }

data class ProvenanceDto(
    val kind: RelationKind,
    val provenance: Provenance,
    val confidence: Double?,
)

object ProvenanceVocab {
    const val KIND = "http://lodestar/meta#kind"
    const val PROVENANCE = "http://lodestar/meta#provenance"
    const val CONFIDENCE = "http://lodestar/meta#confidence"

    fun provenanceOf(s: String?): Provenance? =
        s?.let { runCatching { Provenance.valueOf(it.uppercase()) }.getOrNull() }

    fun kindOf(s: String?): RelationKind? =
        s?.let { runCatching { RelationKind.valueOf(it.uppercase()) }.getOrNull() }
}
