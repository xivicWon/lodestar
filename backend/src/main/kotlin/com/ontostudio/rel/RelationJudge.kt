package com.ontostudio.rel

import com.fasterxml.jackson.databind.ObjectMapper
import com.ontostudio.ai.AiAdvisor
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import org.springframework.stereotype.Service

/**
 * AI가 판정한 관계 후보(E10). E2 [RelationCandidate] 필드 + AI 필터 결과([keep], [reason]).
 * AI는 필터/랭킹만 하고 승인은 항상 사람 몫(D4).
 */
data class JudgedCandidate(
    val fromIri: String,
    val toIri: String,
    val viaColumn: String,
    val confidence: Double,
    val suggestedName: String,
    val keep: Boolean,
    val reason: String,
    val evidence: RelationEvidence,
)

/**
 * E2 후보를 배치 1회 AI 호출로 판정해 말이 되는 관계만 남긴다(E10).
 * 입력은 이름 + 양쪽 컬럼 목록(메타데이터만, 데이터 행 미열람 — D2).
 */
@Service
class RelationJudge(
    private val advisor: AiAdvisor,
    private val holder: OntologyHolder,
    private val mapper: OntologyMapper,
) {
    private val json = ObjectMapper()

    private fun shortName(iri: String): String {
        val frag = iri.substringAfterLast('#', "")
        return if (frag.isNotEmpty()) frag else iri.substringAfterLast('/')
    }

    /** 클래스 IRI를 domain 으로 갖는 데이터프로퍼티들의 짧은 컬럼명. */
    private fun columnsOf(classIri: String, dataProps: List<com.ontostudio.dto.DataPropertyDto>): List<String> =
        dataProps.filter { it.domains.contains(classIri) }
            .map { dp -> dp.label ?: shortName(dp.iri).substringAfterLast('.') }

    fun judge(candidates: List<RelationCandidate>): List<JudgedCandidate> {
        // 후보가 없으면 AI를 호출하지 않는다(D1 배치 호출은 후보가 있을 때만).
        if (candidates.isEmpty()) return emptyList()

        val dataProps = synchronized(holder.lock) {
            holder.ontology.dataPropertiesInSignature().toList().map { mapper.dataPropertyDto(it) }
        }

        val sb = StringBuilder()
        sb.appendLine("각 후보 관계가 말이 되는지 keep(true/false)와 한 줄 이유(reason)를 판정하라.")
        sb.appendLine("아래 JSON 배열만 출력한다(그 외 텍스트 금지): [{\"i\":n,\"keep\":true,\"reason\":\"...\"}]")
        sb.appendLine()
        candidates.forEachIndexed { i, c ->
            val fromShort = shortName(c.fromIri)
            val toShort = shortName(c.toIri)
            val fromCols = columnsOf(c.fromIri, dataProps).joinToString(", ")
            val toCols = columnsOf(c.toIri, dataProps).joinToString(", ")
            sb.appendLine("[$i] $fromShort.${c.viaColumn} -> $toShort  | from컬럼: $fromCols  | to컬럼: $toCols")
        }
        val prompt = sb.toString()

        val response = advisor.ask(prompt)
        val verdicts = parse(response)

        val judged = candidates.mapIndexed { i, c ->
            val v = verdicts[i]
            JudgedCandidate(
                fromIri = c.fromIri,
                toIri = c.toIri,
                viaColumn = c.viaColumn,
                confidence = c.confidence,
                suggestedName = c.suggestedName,
                keep = v?.first ?: false,
                reason = v?.second ?: "판정 없음",
                evidence = c.evidence,
            )
        }
        // keep=true 우선, 그다음 confidence 내림차순.
        return judged.sortedWith(
            compareByDescending<JudgedCandidate> { it.keep }.thenByDescending { it.confidence }
        )
    }

    /** AI 응답에서 JSON 배열을 관대하게 추출(첫 '[' .. 마지막 ']')하고 인덱스 i → (keep, reason) 으로 매핑. */
    private fun parse(response: String): Map<Int, Pair<Boolean, String>> {
        val start = response.indexOf('[')
        val end = response.lastIndexOf(']')
        if (start < 0 || end <= start) return emptyMap()
        val arr: List<Map<String, Any?>> = try {
            @Suppress("UNCHECKED_CAST")
            json.readValue(response.substring(start, end + 1), List::class.java) as List<Map<String, Any?>>
        } catch (e: Exception) {
            return emptyMap()
        }
        val out = HashMap<Int, Pair<Boolean, String>>()
        for (item in arr) {
            val i = (item["i"] as? Number)?.toInt() ?: continue
            val keep = item["keep"] as? Boolean ?: false
            val reason = (item["reason"] as? String)?.trim().orEmpty()
            out[i] = keep to reason
        }
        return out
    }
}
