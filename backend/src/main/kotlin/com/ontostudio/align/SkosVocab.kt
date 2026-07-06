package com.ontostudio.align

import com.ontostudio.dto.MatchType

object SkosVocab {
    const val NS = "http://www.w3.org/2004/02/skos/core#"
    const val CONFIDENCE = "http://lodestar/meta#confidence"
    const val PROVENANCE = "http://lodestar/meta#provenance"

    fun iriFor(m: MatchType): String = NS + when (m) {
        MatchType.EXACT -> "exactMatch"
        MatchType.CLOSE -> "closeMatch"
        MatchType.BROAD -> "broadMatch"
        MatchType.NARROW -> "narrowMatch"
        MatchType.RELATED -> "relatedMatch"
    }

    fun matchTypeFor(iri: String): MatchType? = when (iri) {
        NS + "exactMatch" -> MatchType.EXACT
        NS + "closeMatch" -> MatchType.CLOSE
        NS + "broadMatch" -> MatchType.BROAD
        NS + "narrowMatch" -> MatchType.NARROW
        NS + "relatedMatch" -> MatchType.RELATED
        else -> null
    }
}
