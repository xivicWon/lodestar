package com.ontostudio.rel

import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/rel")
class RelationController(private val service: RelationService) {
    @PostMapping("/suggest")
    fun suggest(): List<RelationCandidate> = service.suggest()
}
