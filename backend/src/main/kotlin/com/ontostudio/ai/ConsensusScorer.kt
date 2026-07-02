package com.ontostudio.ai

import org.springframework.stereotype.Component

/** 라벨 하나의 원문과 등장 횟수. */
data class Variant(val label: String, val count: Int)

/** 반복 추론된 라벨 집합의 합의 결과. */
data class Consensus(
    val consensusLabel: String,
    val agreement: Double,
    val variants: List<Variant>,
)

/**
 * 순수·결정론적 합의 채점기(E7). 정답표 없이 "출력끼리 얼마나 뭉치나"(자기일관성)를 측정한다.
 *
 * 각 라벨을 정규화(소문자, 공백/괄호/구두점 제거)해 토큰화하고, 토큰 Jaccard >= 0.5 로 군집화한다.
 * 최빈 군집의 크기/전체 = agreement, consensusLabel = 최빈 군집 내 최다 원문 라벨.
 */
@Component
class ConsensusScorer {

    fun score(labels: List<String>): Consensus {
        if (labels.isEmpty()) return Consensus("", 0.0, emptyList())

        // 그리디 군집화: 각 라벨을 기존 군집 대표와 Jaccard>=0.5 면 합류, 아니면 새 군집.
        val clusters = mutableListOf<MutableList<String>>()
        val repTokens = mutableListOf<Set<String>>()
        for (label in labels) {
            val tokens = tokenize(label)
            val idx = repTokens.indexOfFirst { jaccard(it, tokens) >= 0.5 }
            if (idx >= 0) clusters[idx].add(label)
            else { clusters.add(mutableListOf(label)); repTokens.add(tokens) }
        }

        val modal = clusters.maxByOrNull { it.size }!!
        val agreement = modal.size.toDouble() / labels.size
        val consensusLabel = modal.groupingBy { it }.eachCount().maxByOrNull { it.value }!!.key
        val variants = labels.groupingBy { it }.eachCount().entries
            .sortedByDescending { it.value }
            .map { Variant(it.key, it.value) }
        return Consensus(consensusLabel, agreement, variants)
    }

    /** 소문자화 후 괄호·구두점을 공백으로 치환하고 공백 기준으로 토큰화한다. */
    private fun tokenize(label: String): Set<String> =
        label.lowercase()
            .replace(Regex("[\\p{Punct}]+"), " ")
            .split(Regex("\\s+"))
            .filter { it.isNotBlank() }
            .toSet()

    private fun jaccard(a: Set<String>, b: Set<String>): Double {
        if (a.isEmpty() && b.isEmpty()) return 1.0
        val union = a.union(b).size
        if (union == 0) return 0.0
        return a.intersect(b).size.toDouble() / union
    }
}
