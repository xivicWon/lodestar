package com.ontostudio.provenance

import kotlin.test.Test
import kotlin.test.assertEquals

class ProvenanceVocabTest {
    @Test fun `meta IRIs are the lodestar meta namespace`() {
        assertEquals("http://lodestar/meta#kind", ProvenanceVocab.KIND)
        assertEquals("http://lodestar/meta#provenance", ProvenanceVocab.PROVENANCE)
        assertEquals("http://lodestar/meta#confidence", ProvenanceVocab.CONFIDENCE)
    }

    @Test fun `enums parse case-insensitively from stored strings`() {
        assertEquals(Provenance.INFERRED, ProvenanceVocab.provenanceOf("INFERRED"))
        assertEquals(RelationKind.NAMEPATTERN, ProvenanceVocab.kindOf("namepattern"))
        assertEquals(null, ProvenanceVocab.provenanceOf("nonsense"))
    }
}
