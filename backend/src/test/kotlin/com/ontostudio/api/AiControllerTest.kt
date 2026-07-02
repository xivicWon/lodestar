package com.ontostudio.api

import com.ontostudio.ai.AiAdvisor
import org.mockito.BDDMockito.given
import org.mockito.ArgumentMatchers.anyString
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import kotlin.test.Test

/** AI 어드바이저를 목킹해 실제 claude 호출 없이 엔드포인트 파이프라인을 검증. */
@SpringBootTest
@AutoConfigureMockMvc
class AiControllerTest {
    @Autowired lateinit var mvc: MockMvc
    @MockitoBean lateinit var advisor: AiAdvisor

    @Test fun `enrich sample returns candidates from ai response`() {
        given(advisor.ask(anyString())).willReturn(
            """[{"table":"TB_CUST_MST","label":"고객 마스터","description":"거래처 기본정보"}]"""
        )
        mvc.perform(post("/api/ai/enrich/sample"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.currentName=='TB_CUST_MST')].suggestedLabel").value(
                org.hamcrest.Matchers.hasItem("고객 마스터")))
    }
}
