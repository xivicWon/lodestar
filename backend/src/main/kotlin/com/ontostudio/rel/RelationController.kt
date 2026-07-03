package com.ontostudio.rel

import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/rel")
class RelationController(
    private val service: RelationService,
    private val judge: RelationJudge,
) {
    @PostMapping("/suggest")
    fun suggest(): List<RelationCandidate> = service.suggest()

    @PostMapping("/suggest/judged")
    fun suggestJudged(): List<JudgedCandidate> = judge.judge(service.suggest())
}
