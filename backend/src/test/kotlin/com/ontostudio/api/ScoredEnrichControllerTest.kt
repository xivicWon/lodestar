package com.ontostudio.api

import com.ontostudio.ai.AiAdvisor
import org.mockito.ArgumentMatchers.anyString
import org.mockito.BDDMockito.given
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import kotlin.test.Test

/** 실제 claude 호출 없이 scored 엔드포인트 파이프라인을 검증(E7). */
@SpringBootTest
@AutoConfigureMockMvc
class ScoredEnrichControllerTest {
    @Autowired lateinit var mvc: MockMvc
    @MockitoBean lateinit var advisor: AiAdvisor

    @Test fun `scored endpoint returns candidates with agreement field`() {
        given(advisor.ask(anyString())).willReturn(
            """[{"table":"TB_CUST_MST","label":"고객 마스터","description":"거래처 기본정보"}]"""
        )
        mvc.perform(post("/api/ai/enrich/sample/scored?runs=3"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.currentName=='TB_CUST_MST')].agreement").value(
                org.hamcrest.Matchers.hasItem(1.0)))
    }
}
