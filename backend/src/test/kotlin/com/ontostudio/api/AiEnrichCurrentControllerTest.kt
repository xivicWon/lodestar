package com.ontostudio.api

import com.ontostudio.ai.AiAdvisor
import org.mockito.ArgumentMatchers.anyString
import org.mockito.BDDMockito.given
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import java.nio.file.Files
import kotlin.test.Test

/** E12: 샘플 임포트로 온톨로지가 존재하는 상태에서 현재-온톨로지 의미추정 엔드포인트를 검증. */
@SpringBootTest
@AutoConfigureMockMvc
class AiEnrichCurrentControllerTest {
    @Autowired lateinit var mvc: MockMvc
    @MockitoBean lateinit var advisor: AiAdvisor

    companion object {
        // 확정 파일을 임시 경로로 오버라이드(리포에 data/ 를 만들지 않음, 확정 오염 방지).
        private val tmp = Files.createTempFile("confirmations-e12", ".json").also { Files.deleteIfExists(it) }

        @JvmStatic
        @DynamicPropertySource
        fun props(reg: DynamicPropertyRegistry) {
            reg.add("lodestar.confirmations.file") { tmp.toString() }
        }
    }

    @Test fun `enrich current returns candidates from ai response`() {
        // 샘플 임포트 → holder 에 온톨로지 주입(TB_CUST_MST 등 실제 클래스 존재)
        mvc.perform(post("/api/rdb/import/sample")).andExpect(status().isOk)

        given(advisor.ask(anyString())).willReturn(
            """[{"table":"TB_CUST_MST","label":"고객 마스터","description":"거래처 기본정보"}]"""
        )
        mvc.perform(post("/api/ai/enrich"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.currentName=='TB_CUST_MST')].suggestedLabel").value(
                org.hamcrest.Matchers.hasItem("고객 마스터")))
    }

    @Test fun `enrich current scored returns candidates with agreement`() {
        mvc.perform(post("/api/rdb/import/sample")).andExpect(status().isOk)

        given(advisor.ask(anyString())).willReturn(
            """[{"table":"TB_CUST_MST","label":"고객 마스터","description":"거래처 기본정보"}]"""
        )
        mvc.perform(post("/api/ai/enrich/scored?runs=3"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.currentName=='TB_CUST_MST')].agreement").value(
                org.hamcrest.Matchers.hasItem(1.0)))
    }
}
