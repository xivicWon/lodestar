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

/** 실제 claude 호출 없이 judged 엔드포인트 파이프라인을 검증(E10). */
@SpringBootTest
@AutoConfigureMockMvc
class RelationJudgeControllerTest {
    @Autowired lateinit var mvc: MockMvc
    @MockitoBean lateinit var advisor: AiAdvisor

    @Test fun `judged endpoint returns candidates with keep and reason fields`() {
        given(advisor.ask(anyString())).willReturn(
            """[{"i":0,"keep":true,"reason":"말이 됨"}]"""
        )
        // 샘플 임포트로 후보가 생기는 온톨로지 상태를 만든다.
        mvc.perform(post("/api/rdb/import/sample")).andExpect(status().isOk)

        mvc.perform(post("/api/rel/suggest/judged"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$[0].keep").exists())
            .andExpect(jsonPath("$[0].reason").exists())
    }
}
