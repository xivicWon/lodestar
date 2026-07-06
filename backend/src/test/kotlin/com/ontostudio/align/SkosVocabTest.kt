package com.ontostudio.align

import com.ontostudio.dto.MatchType
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class SkosVocabTest {
    @Test fun `iriFor maps each match type to its SKOS predicate`() {
        assertEquals("http://www.w3.org/2004/02/skos/core#exactMatch", SkosVocab.iriFor(MatchType.EXACT))
        assertEquals("http://www.w3.org/2004/02/skos/core#closeMatch", SkosVocab.iriFor(MatchType.CLOSE))
        assertEquals("http://www.w3.org/2004/02/skos/core#relatedMatch", SkosVocab.iriFor(MatchType.RELATED))
    }

    @Test fun `matchTypeFor is the inverse of iriFor`() {
        for (m in MatchType.values()) assertEquals(m, SkosVocab.matchTypeFor(SkosVocab.iriFor(m)))
    }

    @Test fun `matchTypeFor returns null for non-SKOS predicates`() {
        assertNull(SkosVocab.matchTypeFor("http://www.w3.org/2000/01/rdf-schema#label"))
    }
}
