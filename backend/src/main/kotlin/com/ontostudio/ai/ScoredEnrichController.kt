package com.ontostudio.ai

import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RestController

/** E7: 샘플 레거시를 N회 반복 추론해 각 제안에 합의율(agreement) 신뢰도를 붙여 반환한다. */
@RestController
@RequestMapping("/api/ai")
class ScoredEnrichController(
    private val scored: ScoredEnricher,
) {
    /** runs 기본 5, [1,10]로 클램프. agreement 오름차순(흔들리는 것 먼저). */
    @PostMapping("/enrich/sample/scored")
    fun scoredEnrich(@RequestParam(defaultValue = "5") runs: Int): List<ScoredCandidate> =
        scored.scoredEnrich(runs.coerceIn(1, 10))
}
