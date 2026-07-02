package com.ontostudio.ai

import com.ontostudio.rdb.MetadataService
import com.ontostudio.rdb.SampleLegacyDb
import com.ontostudio.rdb.SchemaToOwlMapper
import kotlin.test.Test
import kotlin.test.assertEquals

/** 반복 추론 → 합의율 집계를 실 AI 없이 검증(E7). */
class ScoredEnricherTest {

    /** 호출마다 다른 JSON을 회전 반환하는 페이크 AI(비결정론 시뮬). */
    private class RotatingAdvisor(private val responses: List<String>) : AiAdvisor {
        private var i = 0
        override fun ask(prompt: String): String = responses[i++ % responses.size]
    }

    @Test fun `agreement reflects modal fraction across runs`() {
        // 3회 중 TB_CUST_MST 라벨: "고객 마스터" x2, "거래처 정보" x1 → 최빈군집 2/3
        val advisor = RotatingAdvisor(
            listOf(
                """[{"table":"TB_CUST_MST","label":"고객 마스터","description":"거래처 기본정보"}]""",
                """[{"table":"TB_CUST_MST","label":"고객 마스터","description":"거래처 기본정보"}]""",
                """[{"table":"TB_CUST_MST","label":"거래처 정보","description":"거래처"}]""",
            )
        )
        val enricher = SemanticEnricher(advisor, SampleLegacyDb(), MetadataService(), SchemaToOwlMapper())
        val scored = ScoredEnricher(enricher, ConsensusScorer()).scoredEnrich(runs = 3)

        val cust = scored.first { it.currentName == "TB_CUST_MST" }
        assertEquals(2.0 / 3.0, cust.agreement, 1e-9)
        assertEquals("고객 마스터", cust.consensusLabel)
        assertEquals(3, cust.n)
        // description은 consensus 군집 대표 후보의 것
        assertEquals("거래처 기본정보", cust.description)
    }

    @Test fun `item missing from some runs is not inflated (denominator = runs)`() {
        // 3회 중 TB_CUST_MST 는 1회만 등장 → agreement 는 1/3 (부풀려진 1.0 아님).
        val advisor = RotatingAdvisor(
            listOf(
                """[{"table":"TB_CUST_MST","label":"고객 마스터","description":"x"}]""",
                """[{"table":"TB_ORD_HD","label":"주문 헤더","description":"y"}]""",
                """[{"table":"TB_ORD_HD","label":"주문 헤더","description":"y"}]""",
            )
        )
        val enricher = SemanticEnricher(advisor, SampleLegacyDb(), MetadataService(), SchemaToOwlMapper())
        val scored = ScoredEnricher(enricher, ConsensusScorer()).scoredEnrich(runs = 3)

        val cust = scored.first { it.currentName == "TB_CUST_MST" }
        assertEquals(1.0 / 3.0, cust.agreement, 1e-9)
        assertEquals(3, cust.n)
        // 흔들리는 항목이 앞으로 정렬됨(가장 낮은 agreement)
        assertEquals("TB_CUST_MST", scored.first().currentName)
    }
}
