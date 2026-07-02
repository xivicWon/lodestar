package com.ontostudio.ai

import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/ai")
class AiController(
    private val enricher: SemanticEnricher,
    private val chat: ChatService,
) {

    /** E3-2: 번들 샘플 레거시를 AI로 의미 추정 → 후보 목록(사람 검수 대상). */
    @PostMapping("/enrich/sample")
    fun enrichSample(): List<EnrichmentCandidate> = enricher.enrichSample()

    /** E6: 현재 온톨로지를 컨텍스트로 삼아 자연어 질문에 답한다. */
    @PostMapping("/chat")
    fun chat(@RequestBody req: ChatQuestion): ChatAnswer = chat.ask(req.question)
}
