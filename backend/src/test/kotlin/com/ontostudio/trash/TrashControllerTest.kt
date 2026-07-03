package com.ontostudio.trash

import org.hamcrest.Matchers.hasSize
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.http.MediaType
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import java.nio.file.Files
import kotlin.test.Test

@SpringBootTest
@AutoConfigureMockMvc
class TrashControllerTest {
    @Autowired lateinit var mvc: MockMvc

    companion object {
        private val trashFile = Files.createTempFile("trash-it", ".json")
        private val confFile = Files.createTempFile("conf-it", ".json")

        @JvmStatic
        @DynamicPropertySource
        fun props(reg: DynamicPropertyRegistry) {
            reg.add("lodestar.trash.file") { trashFile.toString() }
            reg.add("lodestar.confirmations.file") { confFile.toString() }
        }
    }

    private val iri = "http://lodestar/rdb/legacy#TB_CUST_MST"

    @Test fun `trash then restore a class round-trips via api`() {
        mvc.perform(post("/api/rdb/import/sample")).andExpect(status().isOk)
        mvc.perform(get("/api/classes"))
            .andExpect(jsonPath("$[?(@.label=='TB_CUST_MST')]").exists())

        mvc.perform(post("/api/trash")
            .contentType(MediaType.APPLICATION_JSON).content("{\"iri\":\"$iri\"}"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.iri").value(iri))

        mvc.perform(get("/api/classes"))
            .andExpect(jsonPath("$[?(@.label=='TB_CUST_MST')]").doesNotExist())
        mvc.perform(get("/api/trash"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$[?(@.iri=='$iri')]", hasSize<Any>(1)))

        mvc.perform(post("/api/trash/restore").param("iri", iri)).andExpect(status().isOk)
        mvc.perform(get("/api/classes"))
            .andExpect(jsonPath("$[?(@.label=='TB_CUST_MST')]").exists())
        mvc.perform(delete("/api/trash").param("iri", iri)).andExpect(status().isOk)
    }
}
