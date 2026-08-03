package com.ontostudio.api

import com.ontostudio.rdb.ConnectionInfo
import com.ontostudio.rdb.DbConnector
import com.ontostudio.rdb.SampleLegacyDb
import org.hamcrest.Matchers.greaterThanOrEqualTo
import org.hamcrest.Matchers.matchesPattern
import org.hamcrest.Matchers.not
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.context.TestConfiguration
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Primary
import org.springframework.http.MediaType
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import java.sql.Connection
import kotlin.test.Test

/**
 * #129 — 수집기가 반환형에 실은 제외·실패·부분수집(#114)이 **임포트 응답까지** 도달하는지.
 *
 * 이 테스트가 지키는 것은 집계가 아니라 **사유·좌표**다. 건수만 실린 응답은 gold R-F-2 기준으로
 * 미보고이므로, 항목별 `reasonCode`·`reason`·`locator`·`target` 이 응답에 있어야 통과한다.
 * 세 입력 경로(DDL 텍스트 · 라이브 JDBC · 샘플)를 각각 친다 — 한 경로만 실으면 나머지는 조용해진다.
 */
@SpringBootTest
@AutoConfigureMockMvc
class ImportCollectionReportTest {
    @Autowired lateinit var mvc: MockMvc

    /** 라이브 JDBC 경로를 실제 원격 DB 없이 친다 — 커넥션 공급만 샘플 H2로 갈아끼운다. */
    @TestConfiguration
    class StubConnector {
        @Bean @Primary
        fun stubDbConnector(sample: SampleLegacyDb): DbConnector = object : DbConnector() {
            override fun open(info: ConnectionInfo): Connection = sample.open()
        }
    }

    /** 성공 1건 · 정당한 제외(INSERT) 1건 · 실패(쉼표 누락) 1건 → 부분수집 1건. */
    private val ddl = """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(100));
        INSERT INTO customers VALUES (1, 'kim');
        CREATE TABLE broken (id INTEGER name VARCHAR(10));
    """.trimIndent()

    @Test fun `ddl import response carries skipped and failed with reason and locator`() {
        val body = """{"sql": ${org.json.JSONObject.quote(ddl)}, "schemaName": "shop"}"""
        mvc.perform(post("/api/rdb/import/ddl").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.collection.sourceKind").value("ddl"))
            .andExpect(jsonPath("$.collection.locatorScheme").value("line"))
            .andExpect(jsonPath("$.collection.collected").value(1))
            .andExpect(jsonPath("$.collection.skipped").value(1))
            .andExpect(jsonPath("$.collection.failed").value(1))
            // 정당한 제외: 사유코드·사유문·좌표·대상이 모두 실려야 한다
            .andExpect(jsonPath("$.collection.issues[?(@.reasonCode=='OUT_OF_SCOPE_BY_DESIGN')].kind")
                .value("SKIPPED"))
            .andExpect(jsonPath("$.collection.issues[?(@.reasonCode=='OUT_OF_SCOPE_BY_DESIGN')].locator")
                .value("#L2"))
            .andExpect(jsonPath("$.collection.issues[?(@.reasonCode=='OUT_OF_SCOPE_BY_DESIGN')].target")
                .value("INSERT INTO customers"))
            .andExpect(jsonPath("$.collection.issues[?(@.kind=='FAILED')].reasonCode")
                .value("PARSE_ERROR"))
            .andExpect(jsonPath("$.collection.issues[?(@.kind=='FAILED')].reason")
                .value(not("")))
            .andExpect(jsonPath("$.collection.issues[?(@.kind=='FAILED')].locator")
                .value("#L3"))
    }

    @Test fun `ddl import with failures is not reported as complete`() {
        val body = """{"sql": ${org.json.JSONObject.quote(ddl)}, "schemaName": "shop"}"""
        mvc.perform(post("/api/rdb/import/ddl").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.collection.complete").value(false))
            .andExpect(jsonPath("$.collection.partial").value(1))
            .andExpect(jsonPath("$.collection.partials[0].kind").value("PARTIAL"))
            .andExpect(jsonPath("$.collection.partials[0].reasonCode").value("PARTIAL_COLLECTION"))
    }

    /** 제외·실패가 없는 입력은 완전 수집으로 실린다 — 없는 경고를 만들지 않는다. */
    @Test fun `clean ddl import reports complete with empty issue lists`() {
        val clean = "CREATE TABLE only_one (id INTEGER PRIMARY KEY);"
        val body = """{"sql": ${org.json.JSONObject.quote(clean)}, "schemaName": "clean"}"""
        mvc.perform(post("/api/rdb/import/ddl").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.collection.complete").value(true))
            .andExpect(jsonPath("$.collection.issues").isEmpty)
            .andExpect(jsonPath("$.collection.partials").isEmpty)
    }

    @Test fun `sample import response carries jdbc object level exclusions`() {
        mvc.perform(post("/api/rdb/import/sample"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.collection.sourceKind").value("sample"))
            .andExpect(jsonPath("$.collection.locatorScheme").value("jdbc"))
            .andExpect(jsonPath("$.collection.collected").value(greaterThanOrEqualTo(25)))
            .andExpect(jsonPath("$.collection.skipped").value(greaterThanOrEqualTo(1)))
            .andExpect(jsonPath("$.collection.issues[0].reasonCode").value("UNSUPPORTED_OBJECT_TYPE"))
            // 좌표 규약: jdbc://<catalog>/<schema>/<object>
            .andExpect(jsonPath("$.collection.issues[0].locator")
                .value(matchesPattern("^jdbc://[^/]*/[^/]*/.+$")))
            .andExpect(jsonPath("$.collection.issues[0].target").value(not("")))
    }

    @Test fun `live jdbc import response carries the same report shape`() {
        val body = """{"host":"localhost","port":5432,"database":"legacy","user":"u","password":"p","vendor":"postgresql"}"""
        mvc.perform(post("/api/rdb/import/connection").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.collection.sourceKind").value("jdbc"))
            .andExpect(jsonPath("$.collection.locatorScheme").value("jdbc"))
            .andExpect(jsonPath("$.collection.skipped").value(greaterThanOrEqualTo(1)))
            .andExpect(jsonPath("$.collection.issues[0].locator")
                .value(matchesPattern("^jdbc://[^/]*/[^/]*/.+$")))
    }
}
