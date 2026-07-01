package com.ontostudio.api

import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.http.MediaType
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import kotlin.test.Test

@SpringBootTest
@AutoConfigureMockMvc
class RdbImportControllerTest {
    @Autowired lateinit var mvc: MockMvc

    private val ddl = """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(100));
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER,
            CONSTRAINT fk FOREIGN KEY (customer_id) REFERENCES customers(id));
    """.trimIndent()

    @Test fun `import ddl creates classes and object property reachable via existing apis`() {
        val body = """{"sql": ${org.json.JSONObject.quote(ddl)}, "schemaName": "shop"}"""
        mvc.perform(post("/api/rdb/import/ddl").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.counts.classes").value(2))

        // 기존 클래스 API로 조회 가능해야 한다
        mvc.perform(get("/api/classes")).andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.label=='orders')]").exists())

        // 기존 속성 API로 FK 관계(ObjectProperty)가 보여야 한다
        mvc.perform(get("/api/properties/object")).andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.iri=~/.*orders_customer_id_ref/)]").exists())
    }
}
