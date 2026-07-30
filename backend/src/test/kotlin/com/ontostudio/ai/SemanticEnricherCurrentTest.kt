package com.ontostudio.ai

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.rdb.ColumnInfo
import com.ontostudio.rdb.MetadataService
import com.ontostudio.rdb.SampleLegacyDb
import com.ontostudio.rdb.SchemaModel
import com.ontostudio.rdb.SchemaToOwlMapper
import com.ontostudio.rdb.TableInfo
import com.ontostudio.savepoint.ConfirmationStore
import com.ontostudio.savepoint.ConfirmedFact
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.fail

/** E12: 현재 로드된 온톨로지 대상 의미추정(enrichCurrent)을 실 AI/DB 없이 검증. */
class SemanticEnricherCurrentTest {

    private val tmp = Files.createTempFile("confirmations", ".json")
    private val baseIri = "http://lodestar/rdb/current#"

    @AfterTest fun cleanup() { Files.deleteIfExists(tmp) }

    private fun store() = ConfirmationStore(tmp.toString())

    /** 프롬프트를 붙잡아두고 고정 JSON을 돌려주는 페이크 AI. */
    private class FakeAdvisor(val json: String) : AiAdvisor {
        var lastPrompt: String = ""
        var calls: Int = 0
        override fun ask(prompt: String): String { lastPrompt = prompt; calls++; return json }
    }

    /** 호출되면 실패시키는 페이크 AI(미호출 검증용). */
    private class ThrowingAdvisor : AiAdvisor {
        override fun ask(prompt: String): String = fail("advisor.ask 는 호출되면 안 된다")
    }

    private fun col(name: String) = ColumnInfo(name, "VARCHAR", true)

    /** 두 테이블(TB_CUST_MST, TB_ORD_HD)로 구성한 온톨로지를 holder 에 주입. */
    private fun holderWith(vararg tables: TableInfo): OntologyHolder {
        val holder = OntologyHolder()
        val ont = SchemaToOwlMapper().build(SchemaModel.of(tables.toList(), "db:test:semanticenrichercurrenttest"), baseIri)
        holder.replace(ont, baseIri)
        return holder
    }

    private fun enricher(
        advisor: AiAdvisor,
        holder: OntologyHolder,
        store: ConfirmationStore = store(),
        chunkSize: Int = 40,
    ) = SemanticEnricher(
        advisor, SampleLegacyDb(), MetadataService(), SchemaToOwlMapper(), store,
        holder, OntologyMapper(holder), chunkSize,
    )

    @Test fun `enrichCurrent maps ai labels to real class iris and prompt carries name and column`() {
        val holder = holderWith(
            TableInfo("TB_CUST_MST", listOf(col("CUST_NO"), col("CUST_NM")), emptyList(), emptyList()),
            TableInfo("TB_ORD_HD", listOf(col("ORD_NO")), emptyList(), emptyList()),
        )
        val fake = FakeAdvisor(
            """여기 결과입니다:
            [
              {"table":"TB_CUST_MST","label":"고객 마스터","description":"거래처 기본정보"},
              {"table":"TB_ORD_HD","label":"주문 헤더","description":"주문 전표 헤더"}
            ]"""
        )
        val candidates = enricher(fake, holder).enrichCurrent()

        val cust = candidates.first { it.currentName == "TB_CUST_MST" }
        assertEquals(baseIri + "TB_CUST_MST", cust.targetIri, "targetIri 는 실제 클래스 IRI")
        assertEquals("고객 마스터", cust.suggestedLabel)
        assertTrue(candidates.any { it.currentName == "TB_ORD_HD" })

        // 프롬프트에 클래스 이름과 컬럼 이름이 포함(샘플 행 없음)
        assertTrue(fake.lastPrompt.contains("TB_CUST_MST"), "프롬프트에 클래스명 포함")
        assertTrue(fake.lastPrompt.contains("CUST_NO"), "프롬프트에 컬럼명 포함")
    }

    @Test fun `confirmed class excluded from targets and injected as anchor`() {
        val holder = holderWith(
            TableInfo("TB_CUST_MST", listOf(col("CUST_NO")), emptyList(), emptyList()),
            TableInfo("TB_ORD_HD", listOf(col("ORD_NO")), emptyList(), emptyList()),
        )
        val store = store()
        store.confirm(ConfirmedFact(baseIri + "TB_CUST_MST", "고객 마스터", "class"))
        val fake = FakeAdvisor("""[{"table":"TB_ORD_HD","label":"주문 헤더","description":"주문 전표"}]""")
        val candidates = enricher(fake, holder, store).enrichCurrent()

        assertTrue(fake.lastPrompt.contains("## 이미 확정된 사실"))
        assertTrue(fake.lastPrompt.contains("TB_CUST_MST = 고객 마스터"), "확정 라벨이 앵커로 주입")
        assertFalse(fake.lastPrompt.contains("### TB_CUST_MST"), "확정 클래스는 추정 대상 제외")
        assertTrue(fake.lastPrompt.contains("### TB_ORD_HD"))
        assertFalse(candidates.any { it.currentName == "TB_CUST_MST" })
    }

    @Test fun `all confirmed returns empty without calling advisor`() {
        val holder = holderWith(
            TableInfo("TB_CUST_MST", listOf(col("CUST_NO")), emptyList(), emptyList()),
            TableInfo("TB_ORD_HD", listOf(col("ORD_NO")), emptyList(), emptyList()),
        )
        val store = store()
        store.confirm(ConfirmedFact(baseIri + "TB_CUST_MST", "고객 마스터", "class"))
        store.confirm(ConfirmedFact(baseIri + "TB_ORD_HD", "주문 헤더", "class"))
        val svc = enricher(ThrowingAdvisor(), holder, store)
        assertTrue(svc.enrichCurrent().isEmpty())
    }

    @Test fun `classes sharing a label do not collide (each maps to its own iri)`() {
        // 두 클래스에 같은 라벨을 달아 이름 충돌을 유발 → 청크 내 고유 키로 둘 다 매핑돼야 함.
        val holder = holderWith(
            TableInfo("TB_A", listOf(col("A1")), emptyList(), emptyList()),
            TableInfo("TB_B", listOf(col("B1")), emptyList(), emptyList()),
        )
        val cs = com.ontostudio.ontology.ClassService(holder, OntologyMapper(holder))
        cs.setLabel(baseIri + "TB_A", "고객")
        cs.setLabel(baseIri + "TB_B", "고객")
        // 정렬(IRI) 상 TB_A→"고객", TB_B→"고객__2" 로 키 부여됨.
        val fake = FakeAdvisor(
            """[{"table":"고객","label":"라벨A","description":"a"},{"table":"고객__2","label":"라벨B","description":"b"}]"""
        )
        val candidates = enricher(fake, holder).enrichCurrent()

        // 두 클래스 모두 후보를 받고, 서로 다른 실제 IRI 에 매핑(덮어쓰기 없음)
        assertEquals(
            setOf(baseIri + "TB_A", baseIri + "TB_B"),
            candidates.map { it.targetIri }.toSet(),
        )
    }

    @Test fun `chunking splits targets and merges all candidates`() {
        val tables = (1..5).map {
            TableInfo("TB_T$it", listOf(col("C$it")), emptyList(), emptyList())
        }.toTypedArray()
        val holder = holderWith(*tables)
        // 5개 클래스, chunk-size 2 → 3콜. 각 콜은 그 청크의 테이블만 후보로 인정하므로
        // 모든 테이블을 커버하는 JSON을 반환해도 청크별로 알맞게 필터링돼 5개로 병합된다.
        val fake = FakeAdvisor(
            (1..5).joinToString(",", "[", "]") {
                """{"table":"TB_T$it","label":"라벨$it","description":"d$it"}"""
            }
        )
        val candidates = enricher(fake, holder, chunkSize = 2).enrichCurrent()

        assertEquals(3, fake.calls, "5개 클래스 / chunk 2 → advisor 3회 호출")
        assertEquals(5, candidates.size, "모든 청크 결과 병합")
        assertEquals((1..5).map { baseIri + "TB_T$it" }.toSet(), candidates.map { it.targetIri }.toSet())
    }
}
