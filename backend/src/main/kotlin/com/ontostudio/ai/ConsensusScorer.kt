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

    /**
     * @param labels 반복 추론으로 모은 라벨들(누락 실행은 여기 없음).
     * @param denominator agreement 분모. 기본은 labels.size 이지만, 반복 실행 신뢰도에서는
     *   총 실행 횟수(runs)를 넘겨 "일부 실행에서 누락된 항목의 신뢰도가 부풀려지는" 것을 막는다.
     *
     * 군집화는 distinct 라벨에 대한 union-find(연결요소)로 수행해 **입력 순서와 무관**하게 결정적이다.
     */
    fun score(labels: List<String>, denominator: Int = labels.size): Consensus {
        if (labels.isEmpty()) return Consensus("", 0.0, emptyList())

        val counts = labels.groupingBy { it }.eachCount()          // 원문 라벨 → 횟수
        val distinct = counts.keys.sorted()                        // 결정적 순서
        val tokens = distinct.associateWith { tokenize(it) }

        // union-find: distinct[i], distinct[j] 의 Jaccard>=0.5 면 병합 (순서 무관, 연결요소).
        val parent = IntArray(distinct.size) { it }
        fun find(x: Int): Int { var r = x; while (parent[r] != r) r = parent[r]
            var c = x; while (parent[c] != c) { val n = parent[c]; parent[c] = r; c = n }; return r }
        fun union(a: Int, b: Int) { val ra = find(a); val rb = find(b)
            if (ra != rb) parent[maxOf(ra, rb)] = minOf(ra, rb) }
        for (i in distinct.indices) for (j in i + 1 until distinct.size)
            if (jaccard(tokens.getValue(distinct[i]), tokens.getValue(distinct[j])) >= 0.5) union(i, j)

        val clusters = HashMap<Int, MutableList<Int>>()
        for (i in distinct.indices) clusters.getOrPut(find(i)) { mutableListOf() }.add(i)
        fun total(c: List<Int>) = c.sumOf { counts.getValue(distinct[it]) }

        // 최빈 군집: 총 횟수 최대, 동률이면 가장 작은 라벨 인덱스(=사전순) 우선 → 결정적.
        val modal = clusters.values.sortedWith(
            compareByDescending<List<Int>> { total(it) }.thenBy { it.minOrNull()!! }
        ).first()

        val denom = if (denominator > 0) denominator else labels.size
        val agreement = total(modal).toDouble() / denom
        // 대표 라벨: 최빈 군집 내 최다 원문, 동률이면 사전순.
        val consensusLabel = modal.map { distinct[it] }
            .sortedWith(compareByDescending<String> { counts.getValue(it) }.thenBy { it })
            .first()
        val variants = distinct
            .sortedWith(compareByDescending<String> { counts.getValue(it) }.thenBy { it })
            .map { Variant(it, counts.getValue(it)) }
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
