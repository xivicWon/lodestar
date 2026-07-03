package com.ontostudio.rel

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.DataPropertyDto
import org.springframework.stereotype.Service

/** 같은 소스 컬럼이 매칭한 다른 대상(모호성 근거, E13). */
data class AltTarget(
    val toIri: String,
    val toLabel: String,
    val confidence: Double,
    val matchType: String, // "exact" | "token"
)

/** 관계 후보 판단 근거(E13). 실 DB 재접속 없이 온톨로지 메타데이터만으로 산출. */
data class RelationEvidence(
    val matchType: String,               // "exact"(0.9) | "token"(0.6)
    val matchStem: String,               // viaColumn 스템 (예: GROUP)
    val matchedOn: String,               // 매칭된 대상 코어/토큰 (예: group)
    val viaType: String?,                // via 컬럼 range 짧은 이름 (예: string), 없으면 null
    val viaFunctional: Boolean,          // via 컬럼 functional 여부
    val targetHasSameColumn: Boolean,    // 대상에 viaColumn 과 같은 이름 컬럼이 있나
    val targetSimilarKeys: List<String>, // 대상에서 같은 스템을 가진 컬럼(자기 이름 제외)
    val cardinality: String,             // "N:1 추정" | "불명"
    val cardinalityReason: String,       // 추정 근거 한 줄
    val alternatives: List<AltTarget>,   // 같은 소스 컬럼이 매칭한 다른 대상(자기 제외)
    val fromLabel: String,
    val toLabel: String,
    val fromColumns: List<String>,       // 소스 전체 컬럼(짧은 이름)
    val toColumns: List<String>,         // 대상 전체 컬럼(짧은 이름)
)

/** FK 없이도 컬럼 이름 패턴으로 클래스 간 암시적 관계를 발굴한다 (E2 + E13 근거). */
data class RelationCandidate(
    val fromIri: String,
    val toIri: String,
    val viaColumn: String,
    val confidence: Double,
    val suggestedName: String,
    val evidence: RelationEvidence,
)

@Service
class RelationService(
    private val holder: OntologyHolder,
    private val mapper: OntologyMapper
) {
    // case-insensitive 접미사: 스템 추출 시 제거한다.
    private val suffixes = listOf("_NO", "_CD", "_ID", "_KEY", "_SEQ")

    // 대상이 코드/마스터 성격인지 판단하는 토큰(카디널리티 추정용).
    private val masterTokens = setOf("code", "cd", "master", "mst", "group", "grp", "type", "kind", "class")

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

    /** range full IRI → 짧은 타입명 (예: .../XMLSchema#string → string). */
    private fun shortType(range: String?): String? =
        range?.let { shortName(it) }

    /** 데이터프로퍼티의 짧은 컬럼명. */
    private fun colShort(dp: DataPropertyDto): String =
        dp.label ?: shortName(dp.iri).substringAfterLast('.')

    /** 매칭 1건의 원자료(그룹핑 후 근거로 가공). */
    private data class RawMatch(
        val aIri: String,
        val dp: DataPropertyDto,
        val colName: String,
        val stem: String,
        val bIri: String,
        val exact: Boolean,
        val matchedOn: String,
    )

    fun suggest(): List<RelationCandidate> = synchronized(holder.lock) {
        val ont = holder.ontology
        val classes = ont.classesInSignature()
            .filter { !it.isOWLThing && !it.isOWLNothing }
            .toList()
        val coreByIri = classes.associate { c ->
            c.iri.toString() to coreName(shortName(c.iri.toString()))
        }
        fun tokensOf(core: String) = core.split("_").filter { it.isNotBlank() }
        val tokensByIri = coreByIri.mapValues { tokensOf(it.value) }
        // 각 데이터프로퍼티의 DTO를 한 번만 계산 (domains 포함).
        val dataProps = ont.dataPropertiesInSignature().toList().map { mapper.dataPropertyDto(it) }
        // 클래스별 짧은 컬럼 목록 / 라벨 (근거용, 1회 계산).
        val columnsByIri: Map<String, List<String>> = classes.associate { c ->
            val iri = c.iri.toString()
            iri to dataProps.filter { it.domains.contains(iri) }.map { colShort(it) }.sorted()
        }
        val labelByIri: Map<String, String> = classes.associate { c ->
            c.iri.toString() to (mapper.labelOf(c.iri) ?: shortName(c.iri.toString()))
        }

        // 1) 원자료 매칭 수집.
        val raws = mutableListOf<RawMatch>()
        for (a in classes) {
            val aIri = a.iri.toString()
            val aCore = coreByIri.getValue(aIri)
            val aTokens = tokensByIri.getValue(aIri)
            val columns = dataProps.filter { it.domains.contains(aIri) }
            for (dp in columns) {
                val colName = colShort(dp)
                val stem = stemOf(colName)
                if (stem.length < 2) continue
                // 컬럼이 A 자신의 식별자(예: TB_ORD_HD.ORD_NO)면 외부 참조가 아니므로 제외 → 오탐 방지
                if (aCore.equals(stem, ignoreCase = true) ||
                    aTokens.any { it.equals(stem, ignoreCase = true) }) continue
                for (b in classes) {
                    val bIri = b.iri.toString()
                    if (bIri == aIri) continue
                    val bCore = coreByIri.getValue(bIri)
                    // 엄격 매칭: stem == B 코어 전체 또는 B의 한 토큰 (느슨한 substring 금지 → 오탐 방지)
                    val exact = bCore.equals(stem, ignoreCase = true)
                    val matchedToken = tokensByIri.getValue(bIri).firstOrNull { it.equals(stem, ignoreCase = true) }
                    if (!exact && matchedToken == null) continue
                    val matchedOn = if (exact) bCore else matchedToken!!
                    raws.add(RawMatch(aIri, dp, colName, stem, bIri, exact, matchedOn))
                }
            }
        }

        // 2) (소스클래스, 소스컬럼) 그룹으로 모아 모호성(대안) 산출.
        val groups = raws.groupBy { it.aIri to it.colName }

        // 3) 근거를 채워 후보 생성.
        val out = mutableListOf<RelationCandidate>()
        for ((_, matches) in groups) {
            for (m in matches) {
                val confidence = if (m.exact) 0.9 else 0.6
                val bIri = m.bIri
                val toCols = columnsByIri.getValue(bIri)
                val targetHasSame = toCols.any { it.equals(m.colName, ignoreCase = true) }
                val similarKeys = toCols.filter {
                    stemOf(it).equals(m.stem, ignoreCase = true) && !it.equals(m.colName, ignoreCase = true)
                }
                val bTokens = tokensByIri.getValue(bIri).map { it.lowercase() }
                val (cardinality, cardReason) = when {
                    m.dp.functional -> "N:1 추정" to "조인 컬럼이 함수형(소스당 1값)"
                    bTokens.any { it in masterTokens } -> "N:1 추정" to "대상이 코드/마스터 성격"
                    else -> "불명" to "함수형·대상 성격 신호 없음"
                }
                val alts = matches.filter { it.bIri != bIri }
                    .map {
                        AltTarget(
                            it.bIri,
                            labelByIri.getValue(it.bIri),
                            if (it.exact) 0.9 else 0.6,
                            if (it.exact) "exact" else "token",
                        )
                    }
                    .distinctBy { it.toIri }
                    .sortedByDescending { it.confidence }
                val evidence = RelationEvidence(
                    matchType = if (m.exact) "exact" else "token",
                    matchStem = m.stem,
                    matchedOn = m.matchedOn,
                    viaType = shortType(m.dp.range),
                    viaFunctional = m.dp.functional,
                    targetHasSameColumn = targetHasSame,
                    targetSimilarKeys = similarKeys,
                    cardinality = cardinality,
                    cardinalityReason = cardReason,
                    alternatives = alts,
                    fromLabel = labelByIri.getValue(m.aIri),
                    toLabel = labelByIri.getValue(bIri),
                    fromColumns = columnsByIri.getValue(m.aIri),
                    toColumns = toCols,
                )
                out.add(
                    RelationCandidate(
                        m.aIri, bIri, m.colName, confidence, "has" + capitalize(m.stem), evidence
                    )
                )
            }
        }
        out
    }
}
