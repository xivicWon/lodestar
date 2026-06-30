package com.ontostudio.api

import com.ontostudio.dto.ClassDto
import com.ontostudio.ontology.ClassService
import org.mockito.BDDMockito.given
import org.mockito.ArgumentMatchers.anyString
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import kotlin.test.Test

@WebMvcTest(ClassController::class)
class ClassControllerTest {

    @Autowired lateinit var mvc: MockMvc
    @MockitoBean lateinit var service: ClassService

    @Test fun `GET by-iri with IRI containing slashes returns 200 not 400`() {
        val iri = "http://example.org/SomeClass"
        val dto = ClassDto(iri = iri, label = "SomeClass", superClasses = emptyList(), annotations = emptyList())
        given(service.get(anyString())).willReturn(dto)

        mvc.perform(get("/api/classes/by-iri").param("iri", iri))
            .andExpect(status().isOk)
    }
}
