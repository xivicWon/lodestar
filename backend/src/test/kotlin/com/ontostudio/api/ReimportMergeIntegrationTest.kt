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
 * E9 통합: 샘플 임포트 → 확정 → 재임포트 시 확정 라벨이 자동 복원됨(원본 테이블명으로 원복 안 됨).
 */
@SpringBootTest
@AutoConfigureMockMvc
class ReimportMergeIntegrationTest {
    @Autowired lateinit var mvc: MockMvc

    companion object {
        private val tmp = Files.createTempFile("confirmations-reimport", ".json").also { Files.deleteIfExists(it) }

        @JvmStatic
        @DynamicPropertySource
        fun props(reg: DynamicPropertyRegistry) {
            reg.add("lodestar.confirmations.file") { tmp.toString() }
        }
    }

    @Test fun `reimport restores confirmed label automatically`() {
        val iri = "http://lodestar/rdb/legacy#TB_CUST_MST"

        // 1. 최초 임포트
        mvc.perform(post("/api/rdb/import/sample")).andExpect(status().isOk)

        // 2. 확정
        mvc.perform(
            post("/api/enrich/confirm")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"targetIri":"$iri","label":"거래처 마스터"}""")
        ).andExpect(status().isOk)

        // 3. 재임포트 → 병합 요약에 재적용이 실려야 함
        mvc.perform(post("/api/rdb/import/sample"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.merge.reapplied").value(org.hamcrest.Matchers.greaterThanOrEqualTo(1)))

        // 4. 재임포트 후에도 확정 라벨이 유지됨(원본 테이블명으로 원복되지 않음)
        mvc.perform(get("/api/classes")).andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.iri=='$iri' && @.label=='거래처 마스터')]").exists())
    }
}
