package com.ontostudio.ai

import com.ontostudio.rdb.MetadataService
import com.ontostudio.rdb.SampleLegacyDb
import com.ontostudio.rdb.SchemaToOwlMapper
import com.ontostudio.savepoint.ConfirmationStore
import java.nio.file.Files
import java.sql.DriverManager
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * #126 — 소속(schema)이 의미추정 경로에 미치는 영향.
 *
 * 라이브 JDBC 로 임포트한 카탈로그에는 소속이 다른 동명 테이블이 있을 수 있다. 그때
 *  1) 프롬프트의 근거(샘플 행)가 **그 테이블의 행**이어야 하고,
 *  2) AI 응답의 이름이 어느 테이블인지 되돌릴 수 있어야 한다.
 * 둘 다 이름만으로는 성립하지 않는다.
 */
class SemanticEnricherOwnershipTest {

    private val tmp = Files.createTempFile("confirmations-ownership", ".json").also { Files.deleteIfExists(it) }

    @AfterTest fun cleanup() { Files.deleteIfExists(tmp) }

    private class SilentAdvisor : AiAdvisor {
        override fun ask(prompt: String): String = "[]"
    }

    private fun enricher() = SemanticEnricher(
        SilentAdvisor(), SampleLegacyDb(), MetadataService(), SchemaToOwlMapper(),
        ConfirmationStore(tmp.toString()))

    /** 소속이 다른 동명 테이블 둘. 행 값으로 어느 쪽인지 구별된다. */
    private fun openTwoSchemas(): java.sql.Connection {
        val conn = DriverManager.getConnection("jdbc:h2:mem:enrich_ownership;DB_CLOSE_DELAY=-1", "sa", "")
        conn.createStatement().use { st ->
            st.execute("DROP ALL OBJECTS")
            st.execute("CREATE SCHEMA SALES")
            st.execute("CREATE SCHEMA ARCHIVE")
            st.execute("CREATE TABLE SALES.ORDERS (ID INTEGER PRIMARY KEY, MEMO VARCHAR(50))")
            st.execute("CREATE TABLE ARCHIVE.ORDERS (ID INTEGER PRIMARY KEY, MEMO VARCHAR(50))")
            st.execute("INSERT INTO SALES.ORDERS VALUES (1, 'ROW_FROM_SALES')")
            st.execute("INSERT INTO ARCHIVE.ORDERS VALUES (1, 'ROW_FROM_ARCHIVE')")
        }
        return conn
    }

    @Test fun `동명 테이블의 샘플 행은 각자의 스키마에서 나온다`() {
        openTwoSchemas().use { conn ->
            val (prompt, _) = enricher().buildPrompt(conn)
            // 소속 없이 조회하면 검색 경로가 고른 한쪽 행이 두 번 실린다 — 다른 테이블의 값이
            // 그 테이블의 근거로 AI 요청에 나간다.
            assertTrue(prompt.contains("ROW_FROM_SALES"), "sales.orders 의 행이 없다:\n$prompt")
            assertTrue(prompt.contains("ROW_FROM_ARCHIVE"), "archive.orders 의 행이 없다:\n$prompt")
        }
    }

    @Test fun `동명 테이블도 응답을 되돌릴 수 있는 키로 프롬프트에 실린다`() {
        openTwoSchemas().use { conn ->
            val (prompt, iriByTable) = enricher().buildPrompt(conn)
            // 조용히 빠지지 않는다: 둘 다 대상이고, 키가 서로 다르며, 각자의 IRI 로 되돌아간다.
            assertEquals(2, iriByTable.size, "동명 테이블이 대상에서 조용히 사라졌다: $iriByTable")
            assertEquals(
                setOf("http://lodestar/rdb/legacy#SALES/ORDERS", "http://lodestar/rdb/legacy#ARCHIVE/ORDERS"),
                iriByTable.values.toSet())
            for (key in iriByTable.keys) assertTrue(prompt.contains("### $key"),
                "프롬프트에 없는 키를 되돌리려 한다: $key\n$prompt")
        }
    }

    @Test fun `되돌린 키로 만든 후보가 그 테이블의 IRI 를 가리킨다`() {
        openTwoSchemas().use { conn ->
            val svc = enricher()
            val (_, iriByTable) = svc.buildPrompt(conn)
            val key = iriByTable.keys.first()
            val candidates = svc.parse("""[{"table":"$key","label":"주문","description":"d"}]""", iriByTable)
            assertEquals(listOf(iriByTable[key]), candidates.map { it.targetIri })
        }
    }
}
