package com.ontostudio.api

import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.http.MediaType
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import java.nio.file.Files
import kotlin.test.Test

/**
 * E8 통합: 샘플 임포트 → POST /api/enrich/confirm → 온톨로지 라벨 반영(/api/classes) +
 * 확정 저장소 등장(/api/confirmations)을 실 컨텍스트로 검증.
 */
@SpringBootTest
@AutoConfigureMockMvc
class ConfirmControllerTest {
    @Autowired lateinit var mvc: MockMvc

    companion object {
        // 확정 파일을 임시 경로로 오버라이드(리포에 data/ 를 만들지 않음).
        private val tmp = Files.createTempFile("confirmations-it", ".json").also { Files.deleteIfExists(it) }

        @JvmStatic
        @DynamicPropertySource
        fun props(reg: DynamicPropertyRegistry) {
            reg.add("lodestar.confirmations.file") { tmp.toString() }
        }
    }

    @Test fun `confirm applies label to ontology and records savepoint`() {
        mvc.perform(post("/api/rdb/import/sample")).andExpect(status().isOk)

        val iri = "http://lodestar/rdb/legacy#PUBLIC/TB_CUST_MST"
        mvc.perform(
            post("/api/enrich/confirm")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"targetIri":"$iri","label":"고객 마스터"}""")
        ).andExpect(status().isOk)

        // 온톨로지에 라벨 반영됨
        mvc.perform(get("/api/classes")).andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.label=='고객 마스터')]").exists())

        // 확정 저장소에 등장
        mvc.perform(get("/api/confirmations")).andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.iri=='$iri')]").exists())
            .andExpect(jsonPath("$[?(@.label=='고객 마스터')]").exists())
    }
}
