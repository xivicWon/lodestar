package com.ontostudio.api

import com.ontostudio.dto.ReasonResultDto
import com.ontostudio.reasoner.ReasonerService
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api")
class ReasonerController(private val service: ReasonerService) {
    @PostMapping("/reason")
    fun reason(): ReasonResultDto = service.reason()
}
