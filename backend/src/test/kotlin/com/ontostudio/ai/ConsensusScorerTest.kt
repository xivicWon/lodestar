package com.ontostudio.ai

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** 결정론적 합의 채점(정규화+토큰 Jaccard 군집화) 단위 검증(E7). */
class ConsensusScorerTest {
    private val scorer = ConsensusScorer()

    @Test fun `identical labels x5 give agreement 1_0`() {
        val c = scorer.score(List(5) { "고객 마스터" })
        assertEquals(1.0, c.agreement)
        assertEquals("고객 마스터", c.consensusLabel)
    }

    @Test fun `three vs two split gives modal agreement 0_6`() {
        val c = scorer.score(
            listOf("고객 마스터", "고객 마스터", "고객 마스터", "거래처 정보", "거래처 정보")
        )
        assertEquals(0.6, c.agreement, 1e-9)
        assertEquals("고객 마스터", c.consensusLabel)
        // 두 원문 모두 variants에 등장
        assertTrue(c.variants.any { it.label == "고객 마스터" && it.count == 3 })
        assertTrue(c.variants.any { it.label == "거래처 정보" && it.count == 2 })
    }

    @Test fun `parenthesized variant clusters with base via token overlap`() {
        // "거래처(고객) 마스터" 정규화→{거래처,고객,마스터}, "고객 마스터"→{고객,마스터}, Jaccard 2/3>=0.5 → 같은 군집
        val c = scorer.score(listOf("고객 마스터", "고객 마스터", "거래처(고객) 마스터"))
        assertEquals(1.0, c.agreement, 1e-9)
        // 최다 원문이 대표
        assertEquals("고객 마스터", c.consensusLabel)
    }

    @Test fun `empty list gives zero agreement and empty label`() {
        val c = scorer.score(emptyList())
        assertEquals(0.0, c.agreement)
        assertEquals("", c.consensusLabel)
        assertTrue(c.variants.isEmpty())
    }
}
