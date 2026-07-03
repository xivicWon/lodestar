package com.ontostudio.ai

import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/ai")
class AiController(
    private val enricher: SemanticEnricher,
    private val scoredEnricher: ScoredEnricher,
    private val chat: ChatService,
) {

    /** E3-2: 번들 샘플 레거시를 AI로 의미 추정 → 후보 목록(사람 검수 대상). */
    @PostMapping("/enrich/sample")
    fun enrichSample(): List<EnrichmentCandidate> = enricher.enrichSample()

    /** E12: 현재 로드된 온톨로지(라이브/DDL/샘플)를 대상으로 의미 추정. */
    @PostMapping("/enrich")
    fun enrichCurrent(): List<EnrichmentCandidate> = enricher.enrichCurrent()

    /** E12+E7: 현재 온톨로지를 N회 반복 추론해 합의율 신뢰도를 붙인다. runs 기본 5, [1,10] 클램프. */
    @PostMapping("/enrich/scored")
    fun scoredEnrichCurrent(@RequestParam(defaultValue = "5") runs: Int): List<ScoredCandidate> =
        scoredEnricher.scoredEnrichCurrent(runs.coerceIn(1, 10))

    /** E6: 현재 온톨로지를 컨텍스트로 삼아 자연어 질문에 답한다. */
    @PostMapping("/chat")
    fun chat(@RequestBody req: ChatQuestion): ChatAnswer = chat.ask(req.question)
}
