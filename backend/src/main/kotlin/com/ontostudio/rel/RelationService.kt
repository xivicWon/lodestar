package com.ontostudio.rel

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import org.springframework.stereotype.Service

/** FK 없이도 컬럼 이름 패턴으로 클래스 간 암시적 관계를 발굴한다 (E2). */
data class RelationCandidate(
    val fromIri: String,
    val toIri: String,
    val viaColumn: String,
    val confidence: Double,
    val suggestedName: String
)

@Service
class RelationService(
    private val holder: OntologyHolder,
    private val mapper: OntologyMapper
) {
    // case-insensitive 접미사: 스템 추출 시 제거한다.
    private val suffixes = listOf("_NO", "_CD", "_ID", "_KEY", "_SEQ")

    private fun shortName(iri: String): String {
        val frag = iri.substringAfterLast('#', "")
        return if (frag.isNotEmpty()) frag else iri.substringAfterLast('/')
    }

    /** 공통 프리픽스(TB_)를 제거한 클래스 코어 이름. */
    private fun coreName(name: String): String =
        if (name.startsWith("TB_", ignoreCase = true)) name.substring(3) else name

    /** 컬럼명에서 접미사를 벗겨낸 스템. 예: CUST_NO → CUST */
    private fun stemOf(column: String): String {
        for (s in suffixes) {
            if (column.endsWith(s, ignoreCase = true)) return column.dropLast(s.length)
        }
        return column
    }

    private fun capitalize(s: String): String =
        s.lowercase().replaceFirstChar { it.uppercase() }

    fun suggest(): List<RelationCandidate> = synchronized(holder.lock) {
        val ont = holder.ontology
        val classes = ont.classesInSignature()
            .filter { !it.isOWLThing && !it.isOWLNothing }
            .toList()
        val coreByIri = classes.associate { c ->
            c.iri.toString() to coreName(shortName(c.iri.toString()))
        }
        // 각 데이터프로퍼티의 DTO를 한 번만 계산 (domains 포함).
        val dataProps = ont.dataPropertiesInSignature().toList().map { mapper.dataPropertyDto(it) }

        val out = mutableListOf<RelationCandidate>()
        for (a in classes) {
            val aIri = a.iri.toString()
            val columns = dataProps.filter { it.domains.contains(aIri) }
            for (dp in columns) {
                val colName = dp.label ?: shortName(dp.iri).substringAfterLast('.')
                val stem = stemOf(colName)
                if (stem.length < 2) continue
                for (b in classes) {
                    val bIri = b.iri.toString()
                    if (bIri == aIri) continue
                    val bCore = coreByIri.getValue(bIri)
                    val tokens = bCore.split("_").filter { it.isNotBlank() }
                    val matches = bCore.contains(stem, ignoreCase = true) ||
                        tokens.any { it.equals(stem, ignoreCase = true) }
                    if (!matches) continue
                    val confidence = if (bCore.equals(stem, ignoreCase = true)) 0.9 else 0.6
                    out.add(RelationCandidate(aIri, bIri, colName, confidence, "has" + capitalize(stem)))
                }
            }
        }
        out
    }
}
