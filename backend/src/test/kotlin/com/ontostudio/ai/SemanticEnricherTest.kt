package com.ontostudio.ai

import com.ontostudio.rdb.MetadataService
import com.ontostudio.rdb.SampleLegacyDb
import com.ontostudio.rdb.SchemaToOwlMapper
import com.ontostudio.savepoint.ConfirmationStore
import com.ontostudio.savepoint.ConfirmedFact
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.fail

class SemanticEnricherTest {

    private val tmp = Files.createTempFile("confirmations", ".json")

    @AfterTest fun cleanup() { Files.deleteIfExists(tmp) }

    private fun store() = ConfirmationStore(tmp.toString())

    /** 프롬프트를 붙잡아두고 고정 JSON을 돌려주는 페이크 AI. */
    private class FakeAdvisor(val json: String) : AiAdvisor {
        var lastPrompt: String = ""
        override fun ask(prompt: String): String { lastPrompt = prompt; return prompt.let { json } }
    }

    /** 호출되면 실패시키는 페이크 AI(미호출 검증용). */
    private class ThrowingAdvisor : AiAdvisor {
        override fun ask(prompt: String): String = fail("advisor.ask 는 호출되면 안 된다")
    }

    private fun enricher(json: String, store: ConfirmationStore = store()): Pair<SemanticEnricher, FakeAdvisor> {
        val fake = FakeAdvisor(json)
        return SemanticEnricher(fake, SampleLegacyDb(), MetadataService(), SchemaToOwlMapper(), store) to fake
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

        // 프롬프트에 컬럼과 샘플 데이터가 포함됐는지 = "샘플행 포함" 검증.
        // #115/#85: 샘플 행은 들어가지만 **마스킹된 뒤**다 — 마스킹 이전 원문은 AI 요청으로 나가지 않는다.
        assertTrue(fake.lastPrompt.contains("TB_CUST_MST"))
        assertTrue(fake.lastPrompt.contains("BIZ_NO="), "샘플 행 값이 프롬프트에 들어가야 함")
        assertFalse(fake.lastPrompt.contains("120-88-12345"), "PII 형태 원문이 AI 요청에 실렸다(#85)")
    }

    @Test fun `unknown tables in ai response are ignored`() {
        val (svc, _) = enricher("""[{"table":"NOPE_TABLE","label":"x","description":"y"}]""")
        assertTrue(svc.enrichSample().isEmpty())
    }

    @Test fun `grounding excludes confirmed table from targets and injects it as anchor`() {
        val store = store()
        // 승인된 사실을 미리 저장(TB_CUST_MST → 고객 마스터).
        store.confirm(ConfirmedFact("http://lodestar/rdb/legacy#TB_CUST_MST", "고객 마스터", "class"))
        val (svc, fake) = enricher(
            """[{"table":"TB_ORD_HD","label":"주문 헤더","description":"주문 전표 헤더"}]""",
            store,
        )
        val candidates = svc.enrichSample()

        // 확정된 사실 섹션에는 있고, 추정 대상(### 헤더)에는 없다.
        assertTrue(fake.lastPrompt.contains("## 이미 확정된 사실"))
        assertTrue(fake.lastPrompt.contains("TB_CUST_MST = 고객 마스터"), "확정 라벨이 앵커로 주입돼야 함")
        assertFalse(fake.lastPrompt.contains("### TB_CUST_MST"), "확정 테이블은 추정 대상에서 제외돼야 함")
        // 미확정 테이블은 여전히 추정 대상.
        assertTrue(fake.lastPrompt.contains("### TB_ORD_HD"))

        // 후보에서 확정 테이블은 제외된다.
        assertFalse(candidates.any { it.currentName == "TB_CUST_MST" })
    }

    @Test fun `zero confirmations preserves original behavior`() {
        val (svc, fake) = enricher("""[{"table":"TB_CUST_MST","label":"고객 마스터","description":"x"}]""")
        val candidates = svc.enrichSample()
        assertFalse(fake.lastPrompt.contains("## 이미 확정된 사실"))
        assertTrue(fake.lastPrompt.contains("### TB_CUST_MST"))
        assertTrue(candidates.any { it.currentName == "TB_CUST_MST" })
    }

    @Test fun `all tables confirmed returns empty without calling advisor`() {
        val store = store()
        // 샘플의 모든 테이블을 확정 처리.
        SampleLegacyDb().open().use { conn ->
            for (t in MetadataService().extract(conn).tables) {
                store.confirm(ConfirmedFact("http://lodestar/rdb/legacy#${SchemaToOwlMapper().slug(t.name)}", t.name, "class"))
            }
        }
        val svc = SemanticEnricher(ThrowingAdvisor(), SampleLegacyDb(), MetadataService(), SchemaToOwlMapper(), store)
        assertTrue(svc.enrichSample().isEmpty())
    }
}
