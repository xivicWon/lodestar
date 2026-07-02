package com.ontostudio.impact

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import org.springframework.stereotype.Service

/** 클래스 IRI를 노드로, ObjectProperty(domain→range)를 방향 간선으로 보는 영향도 분석 (E4). */
data class ImpactResult(
    val iri: String,
    val upstream: List<String>,
    val downstream: List<String>
)

@Service
class ImpactService(
    private val holder: OntologyHolder,
    private val mapper: OntologyMapper
) {
    /** 현재 온톨로지의 ObjectProperty에서 방향 간선(domain → range)을 만든다. */
    private fun edges(): List<Pair<String, String>> = synchronized(holder.lock) {
        val ont = holder.ontology
        ont.objectPropertiesInSignature().toList()
            .map { mapper.objectPropertyDto(it) }
            .flatMap { dto -> dto.domains.flatMap { d -> dto.ranges.map { r -> d to r } } }
    }

    /** start에서 간선을 따라 도달 가능한 노드들 (자신 제외). 사이클 회피 BFS. */
    private fun reach(start: String, adjacency: Map<String, List<String>>): List<String> {
        val visited = LinkedHashSet<String>()
        val queue = ArrayDeque<String>()
        queue.add(start)
        val seen = hashSetOf(start)
        while (queue.isNotEmpty()) {
            val cur = queue.removeFirst()
            for (next in adjacency[cur].orEmpty()) {
                if (seen.add(next)) {
                    visited.add(next)
                    queue.add(next)
                }
            }
        }
        return visited.toList()
    }

    fun impact(iri: String): ImpactResult {
        val edges = edges()
        val out = HashMap<String, MutableList<String>>()
        val inn = HashMap<String, MutableList<String>>()
        for ((from, to) in edges) {
            out.getOrPut(from) { mutableListOf() }.add(to)
            inn.getOrPut(to) { mutableListOf() }.add(from)
        }
        return ImpactResult(
            iri = iri,
            downstream = reach(iri, out),
            upstream = reach(iri, inn)
        )
    }
}
