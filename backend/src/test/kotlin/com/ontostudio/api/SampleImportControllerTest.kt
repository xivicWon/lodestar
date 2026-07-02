package com.ontostudio.api

import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import kotlin.test.Test

/**
 * E1-2: "샘플 레거시 주입" — H2에 지저분한 샘플을 적재하고 라이브 JDBC 경로로 임포트,
 * 기존 클래스 API로 대규모 온톨로지가 조회되는지.
 */
@SpringBootTest
@AutoConfigureMockMvc
class SampleImportControllerTest {
    @Autowired lateinit var mvc: MockMvc

    @Test fun `import sample loads many classes reachable via existing api`() {
        mvc.perform(post("/api/rdb/import/sample"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.meta.counts.classes").value(org.hamcrest.Matchers.greaterThanOrEqualTo(25)))

        mvc.perform(get("/api/classes")).andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.label=='TB_CUST_MST')]").exists())
    }
}
