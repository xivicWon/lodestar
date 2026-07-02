package com.ontostudio.ai

import com.fasterxml.jackson.core.type.TypeReference
import com.fasterxml.jackson.databind.ObjectMapper
import com.ontostudio.dto.ApiException
import com.ontostudio.rdb.MetadataService
import com.ontostudio.rdb.SampleLegacyDb
import com.ontostudio.rdb.SchemaToOwlMapper
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import java.sql.Connection

/** AI가 제안한 한 엔티티의 의미 후보. 사람이 검수 후 온톨로지에 반영(E3-3). */
data class EnrichmentCandidate(
    val targetIri: String,
    val currentName: String,
    val suggestedLabel: String,
    val description: String,
)

/**
 * 번들 샘플 레거시(스키마 + 샘플행)를 AI(claude -p)로 의미 추정한다.
 * 암호 같은 이름 + 컬럼 + 샘플 데이터 → 한국어 비즈니스 라벨/설명 후보.
 */
@Service
class SemanticEnricher(
    private val advisor: AiAdvisor,
    private val sampleDb: SampleLegacyDb,
    private val metadata: MetadataService,
    private val mapper: SchemaToOwlMapper,
) {
    private val baseIri = "http://lodestar/rdb/legacy#"
    private val json = ObjectMapper()

    fun enrichSample(): List<EnrichmentCandidate> {
        val (prompt, tableNames) = sampleDb.open().use { conn -> buildPrompt(conn) }
        val response = advisor.ask(prompt)
        return parse(response, tableNames)
    }

    /** 프롬프트와 (원본 테이블명 집합)을 만든다. */
    internal fun buildPrompt(conn: Connection): Pair<String, Set<String>> {
        val schema = metadata.extract(conn)
        val sb = StringBuilder()
        sb.appendLine("다음은 레거시 DB 테이블 목록이다. 암호 같은 이름·컬럼·샘플 데이터를 보고 각 테이블의")
        sb.appendLine("비즈니스 의미를 추정하라. 반드시 아래 JSON 배열만 출력한다(그 외 텍스트 금지):")
        sb.appendLine("""[{"table":"<원본테이블명>","label":"<한국어 비즈니스 이름>","description":"<한 줄 설명>"}]""")
        sb.appendLine()
        for (t in schema.tables) {
            sb.appendLine("### ${t.name}")
            sb.appendLine("컬럼: " + t.columns.joinToString(", ") { it.name })
            val rows = sampleRows(conn, t.name, 3)
            if (rows.isNotEmpty()) {
                sb.appendLine("샘플:")
                for (r in rows) sb.appendLine("  - " + r.entries.joinToString(", ") { "${it.key}=${it.value}" })
            }
            sb.appendLine()
        }
        return sb.toString() to schema.tables.map { it.name }.toSet()
    }

    private fun sampleRows(conn: Connection, table: String, limit: Int): List<Map<String, String>> {
        val out = mutableListOf<Map<String, String>>()
        conn.createStatement().use { st ->
            st.executeQuery("SELECT * FROM \"$table\" FETCH FIRST $limit ROWS ONLY").use { rs ->
                val md = rs.metaData
                while (rs.next()) {
                    val m = LinkedHashMap<String, String>()
                    for (i in 1..md.columnCount) m[md.getColumnName(i)] = rs.getString(i) ?: "NULL"
                    out.add(m)
                }
            }
        }
        return out
    }

    /** AI 응답에서 JSON 배열을 관대하게 추출·파싱하고, 알려진 테이블만 후보로 만든다. */
    internal fun parse(response: String, tableNames: Set<String>): List<EnrichmentCandidate> {
        val start = response.indexOf('[')
        val end = response.lastIndexOf(']')
        if (start < 0 || end <= start)
            throw ApiException(HttpStatus.BAD_GATEWAY, "ai_parse", "AI 응답에서 JSON 배열을 찾지 못함", null)
        val arr: List<Map<String, String>> = try {
            json.readValue(response.substring(start, end + 1), object : TypeReference<List<Map<String, String>>>() {})
        } catch (e: Exception) {
            throw ApiException(HttpStatus.BAD_GATEWAY, "ai_parse", "AI 응답 JSON 파싱 실패: ${e.message}", null)
        }
        return arr.mapNotNull { item ->
            val table = item["table"]?.trim() ?: return@mapNotNull null
            if (table !in tableNames) return@mapNotNull null
            val label = item["label"]?.trim().orEmpty()
            if (label.isEmpty()) return@mapNotNull null
            EnrichmentCandidate(
                targetIri = baseIri + mapper.slug(table),
                currentName = table,
                suggestedLabel = label,
                description = item["description"]?.trim().orEmpty(),
            )
        }
    }
}
