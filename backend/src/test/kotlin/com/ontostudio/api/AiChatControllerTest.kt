package com.ontostudio.api

import com.ontostudio.ai.AiAdvisor
import org.mockito.ArgumentMatchers.anyString
import org.mockito.BDDMockito.given
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.http.MediaType
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import kotlin.test.Test

/** AI 어드바이저를 목킹해 실제 claude 호출 없이 챗 엔드포인트를 검증. */
@SpringBootTest
@AutoConfigureMockMvc
class AiChatControllerTest {
    @Autowired lateinit var mvc: MockMvc
    @MockitoBean lateinit var advisor: AiAdvisor

    @Test fun `chat returns advisor answer for a question`() {
        given(advisor.ask(anyString())).willReturn("이 온톨로지에는 고객과 주문이 있습니다.")
        mvc.perform(
            post("/api/ai/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"question":"무엇이 있나요?"}""")
        )
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.answer").value("이 온톨로지에는 고객과 주문이 있습니다."))
    }
}
