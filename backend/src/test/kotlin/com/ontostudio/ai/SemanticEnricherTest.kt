package com.ontostudio.ai

import com.ontostudio.rdb.MetadataService
import com.ontostudio.rdb.SampleLegacyDb
import com.ontostudio.rdb.SchemaToOwlMapper
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SemanticEnricherTest {

    /** 프롬프트를 붙잡아두고 고정 JSON을 돌려주는 페이크 AI. */
    private class FakeAdvisor(val json: String) : AiAdvisor {
        var lastPrompt: String = ""
        override fun ask(prompt: String): String { lastPrompt = prompt; return prompt.let { json } }
    }

    private fun enricher(json: String): Pair<SemanticEnricher, FakeAdvisor> {
        val fake = FakeAdvisor(json)
        return SemanticEnricher(fake, SampleLegacyDb(), MetadataService(), SchemaToOwlMapper()) to fake
    }

    @Test fun `enrich maps ai labels to candidates with correct target iri`() {
        val (svc, fake) = enricher(
            """여기 결과입니다:
            [
              {"table":"TB_CUST_MST","label":"고객 마스터","description":"거래처 기본정보"},
              {"table":"TB_ORD_HD","label":"주문 헤더","description":"주문 전표 헤더"}
            ]"""
        )
        val candidates = svc.enrichSample()

        val cust = candidates.first { it.currentName == "TB_CUST_MST" }
        assertEquals("http://lodestar/rdb/legacy#TB_CUST_MST", cust.targetIri)
        assertEquals("고객 마스터", cust.suggestedLabel)
        assertTrue(candidates.any { it.currentName == "TB_ORD_HD" })

        // 프롬프트에 컬럼과 샘플 데이터(사업자번호 값)가 포함됐는지 = "샘플행 포함" 검증
        assertTrue(fake.lastPrompt.contains("TB_CUST_MST"))
        assertTrue(fake.lastPrompt.contains("120-88-12345"), "샘플 행 값이 프롬프트에 들어가야 함")
    }

    @Test fun `unknown tables in ai response are ignored`() {
        val (svc, _) = enricher("""[{"table":"NOPE_TABLE","label":"x","description":"y"}]""")
        assertTrue(svc.enrichSample().isEmpty())
    }
}
