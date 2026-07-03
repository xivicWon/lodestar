package com.ontostudio.ai

import org.springframework.stereotype.Service

/** 반복 추론의 합의율(agreement) 신뢰도가 붙은 의미 후보(E7). */
data class ScoredCandidate(
    val targetIri: String,
    val currentName: String,
    val consensusLabel: String,
    val description: String,
    val agreement: Double,
    val n: Int,
    val variants: List<Variant>,
)

/**
 * 기존 [SemanticEnricher]를 N회 호출해 targetIri별 라벨을 모으고 [ConsensusScorer]로 집계한다(E7).
 * 신규 AI 로직 없음 — 반복 + 결정론적 채점만 한다. agreement 오름차순(흔들리는 것 먼저)으로 반환.
 */
@Service
class ScoredEnricher(
    private val enricher: SemanticEnricher,
    private val scorer: ConsensusScorer,
) {
    fun scoredEnrich(runs: Int): List<ScoredCandidate> = aggregate(runs) { enricher.enrichSample() }

    /** E12: 현재 온톨로지 대상 enrichCurrent 를 N회 반복해 동일 집계 로직으로 신뢰도를 붙인다. */
    fun scoredEnrichCurrent(runs: Int): List<ScoredCandidate> = aggregate(runs) { enricher.enrichCurrent() }

    private inline fun aggregate(runs: Int, run: () -> List<EnrichmentCandidate>): List<ScoredCandidate> {
        val byIri = LinkedHashMap<String, MutableList<EnrichmentCandidate>>()
        repeat(runs) {
            for (c in run()) byIri.getOrPut(c.targetIri) { mutableListOf() }.add(c)
        }
        return byIri.map { (iri, cands) ->
            val labels = cands.map { it.suggestedLabel }
            // 분모는 총 실행 횟수(runs): 일부 실행에서 누락된 항목은 신뢰도가 낮아야 한다.
            val consensus = scorer.score(labels, denominator = runs)
            // description: consensus 군집 대표(=consensusLabel) 후보 것, 없으면 첫 후보 것.
            val description = cands.firstOrNull { it.suggestedLabel == consensus.consensusLabel }?.description
                ?: cands.first().description
            ScoredCandidate(
                targetIri = iri,
                currentName = cands.first().currentName,
                consensusLabel = consensus.consensusLabel,
                description = description,
                agreement = consensus.agreement,
                n = runs,
                variants = consensus.variants,
            )
        }.sortedBy { it.agreement }
    }
}
