package com.ontostudio.ai

import com.fasterxml.jackson.core.type.TypeReference
import com.fasterxml.jackson.databind.ObjectMapper
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.ApiException
import com.ontostudio.rdb.MetadataService
import com.ontostudio.security.MaskingEngine
import com.ontostudio.rdb.SampleLegacyDb
import com.ontostudio.rdb.SampleSource
import com.ontostudio.rdb.SchemaToOwlMapper
import com.ontostudio.savepoint.ConfirmationStore
import org.semanticweb.owlapi.model.IRI
import org.springframework.beans.factory.annotation.Value
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
    private val confirmations: ConfirmationStore,
    // E12: 현재 로드된 온톨로지 대상(enrichCurrent). 기존 샘플 경로는 아래 필드를 쓰지 않는다.
    private val holder: OntologyHolder = OntologyHolder(),
    private val ontologyMapper: OntologyMapper = OntologyMapper(holder),
    @Value("\${lodestar.enrich.chunk-size:40}") private val chunkSize: Int = 40,
    private val masker: MaskingEngine = MaskingEngine(),
) {
    private val baseIri = "http://lodestar/rdb/legacy#"
    private val json = ObjectMapper()

    private fun classIri(tableName: String) = baseIri + mapper.slug(tableName)

    fun enrichSample(): List<EnrichmentCandidate> {
        val (prompt, tableNames) = sampleDb.open().use { conn -> buildPrompt(conn) }
        // 미확정(추정 대상) 테이블이 하나도 없으면 AI를 호출하지 않고 빈 결과(E8 그라운딩).
        if (tableNames.isEmpty()) return emptyList()
        val response = advisor.ask(prompt)
        return parse(response, tableNames)
    }

    /**
     * 프롬프트와 (추정 대상 테이블명 집합)을 만든다.
     * 확정된 테이블은 추정 대상에서 제외하고, 확정 라벨을 "이미 확정된 사실" 앵커로 주입한다(E8 그라운딩).
     */
    internal fun buildPrompt(conn: Connection): Pair<String, Set<String>> {
        // 번들 샘플을 적재한 커넥션이다(enrichSample → sampleDb.open) — gold 가 고정한 신원을 쓴다.
        val schema = metadata.extract(
            conn, sourceId = SampleSource.SOURCE_ID, revisionScheme = SampleSource.REVISION_SCHEME)
        val confirmedHere = schema.tables.filter { confirmations.isConfirmed(classIri(it.name)) }
        val targets = schema.tables.filter { !confirmations.isConfirmed(classIri(it.name)) }
        val labelByIri = confirmations.all().associate { it.iri to it.label }

        val sb = StringBuilder()
        if (confirmedHere.isNotEmpty()) {
            sb.appendLine("## 이미 확정된 사실 (변경 금지, 이 의미에 일관되게 추론하라)")
            for (t in confirmedHere) {
                sb.appendLine("- ${t.name} = ${labelByIri[classIri(t.name)].orEmpty()}")
            }
            sb.appendLine()
        }
        sb.appendLine("## 추정 대상")
        sb.appendLine("다음은 레거시 DB 테이블 목록이다. 암호 같은 이름·컬럼·샘플 데이터를 보고 각 테이블의")
        sb.appendLine("비즈니스 의미를 추정하라. 반드시 아래 JSON 배열만 출력한다(그 외 텍스트 금지):")
        sb.appendLine("""[{"table":"<원본테이블명>","label":"<한국어 비즈니스 이름>","description":"<한 줄 설명>"}]""")
        sb.appendLine()
        for (t in targets) {
            sb.appendLine("### ${t.name}")
            sb.appendLine("컬럼: " + t.columns.joinToString(", ") { it.name })
            val rows = sampleRows(conn, t.name, 3)
            if (rows.isNotEmpty()) {
                sb.appendLine("샘플:")
                // #115/#85: 마스킹은 저장·로그·**AI 요청**보다 먼저다. 적재 경로가 이미 마스킹하지만
                // 라이브 JDBC 소스의 행은 원문이므로, 요청 경계에서 한 번 더 통과시킨다(다중 방어).
                for (r in rows) sb.appendLine(masker.maskField(
                    "  - " + r.entries.joinToString(", ") { "${it.key}=${it.value}" }))
            }
            sb.appendLine()
        }
        return sb.toString() to targets.map { it.name }.toSet()
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

    // ---------------------------------------------------------------------------------------------
    // E12: 현재 로드된 온톨로지(라이브 JDBC·DDL·샘플 무엇으로 임포트했든) 대상 의미추정.
    //      근거 = 온톨로지의 클래스명 + 컬럼명(DataProperty)만. 샘플 행·DB 재접속 없음(D1).
    // ---------------------------------------------------------------------------------------------

    /** 한 클래스의 추정 컨텍스트: 실제 IRI, 표시 이름, 컬럼(짧은 이름) 목록. */
    internal data class ClassCtx(val iri: String, val name: String, val columns: List<String>)

    /** IRI fragment: '#' 뒤, 없으면 마지막 '/' 뒤. */
    private fun fragmentOf(iri: String): String =
        if (iri.contains('#')) iri.substringAfterLast('#') else iri.substringAfterLast('/')

    /** DataProperty 짧은 이름: 라벨 있으면 그것, 없으면 fragment 의 마지막 '.' 뒤. */
    private fun shortPropName(iri: IRI): String {
        ontologyMapper.labelOf(iri)?.let { return it }
        return fragmentOf(iri.toString()).substringAfterLast('.')
    }

    /**
     * 현재 온톨로지에서 클래스별 {실제 IRI, 이름, 컬럼[]}을 수집한다.
     * 컬럼 = 그 클래스를 domain 으로 갖는 DataProperty 들의 짧은 이름.
     */
    internal fun collectContext(): List<ClassCtx> = synchronized(holder.lock) {
        val ont = holder.ontology
        // 클래스 IRI → 컬럼 이름 목록(도메인 축 선계산).
        val colsByClass = LinkedHashMap<String, MutableList<String>>()
        ont.dataPropertiesInSignature().toList().forEach { dp ->
            val short = shortPropName(dp.iri)
            ont.dataPropertyDomainAxioms(dp).toList().forEach { ax ->
                val dom = ax.domain
                if (!dom.isAnonymous) {
                    colsByClass.getOrPut(dom.asOWLClass().iri.toString()) { mutableListOf() }.add(short)
                }
            }
        }
        ont.classesInSignature().toList()
            .filter { !it.isOWLThing }
            .map { cls ->
                val iri = cls.iri.toString()
                val name = ontologyMapper.labelOf(cls.iri) ?: fragmentOf(iri)
                ClassCtx(iri, name, colsByClass[iri]?.toList() ?: emptyList())
            }
            .sortedBy { it.iri } // 결정론적 순서(청크 경계·중복키 부여 안정화)
    }

    /**
     * E3 프롬프트 구조 재사용: (선택) 확정 앵커 섹션 + 추정 대상 섹션. 샘플 행 라인 없음.
     * anchors = (이름, 확정 라벨) 목록.
     */
    internal fun buildPromptFor(targets: List<ClassCtx>, anchors: List<Pair<String, String>>): String {
        val sb = StringBuilder()
        if (anchors.isNotEmpty()) {
            sb.appendLine("## 이미 확정된 사실 (변경 금지, 이 의미에 일관되게 추론하라)")
            for ((name, label) in anchors) sb.appendLine("- $name = $label")
            sb.appendLine()
        }
        sb.appendLine("## 추정 대상")
        sb.appendLine("다음은 레거시 DB 테이블 목록이다. 암호 같은 이름·컬럼을 보고 각 테이블의")
        sb.appendLine("비즈니스 의미를 추정하라. 반드시 아래 JSON 배열만 출력한다(그 외 텍스트 금지):")
        sb.appendLine("""[{"table":"<원본테이블명>","label":"<한국어 비즈니스 이름>","description":"<한 줄 설명>"}]""")
        sb.appendLine()
        for (t in targets) {
            sb.appendLine("### ${t.name}")
            sb.appendLine("컬럼: " + t.columns.joinToString(", "))
            sb.appendLine()
        }
        return sb.toString()
    }

    /** AI 응답에서 JSON 배열을 관대하게 추출하고, nameToIri 로 실제 클래스 IRI 를 매핑한다(모르는 table 무시). */
    internal fun parseCandidates(response: String, nameToIri: Map<String, String>): List<EnrichmentCandidate> {
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
            val iri = nameToIri[table] ?: return@mapNotNull null
            val label = item["label"]?.trim().orEmpty()
            if (label.isEmpty()) return@mapNotNull null
            EnrichmentCandidate(
                targetIri = iri,
                currentName = table,
                suggestedLabel = label,
                description = item["description"]?.trim().orEmpty(),
            )
        }
    }

    /**
     * 현재 온톨로지 대상 의미추정(E12). 확정 클래스는 제외 + 앵커 주입(E8), 대규모는 청크 분할(D3).
     * 미확정 대상이 없으면 AI 미호출 + 빈 결과.
     */
    fun enrichCurrent(): List<EnrichmentCandidate> {
        val ctx = collectContext()
        val targets = ctx.filter { !confirmations.isConfirmed(it.iri) }
        if (targets.isEmpty()) return emptyList()

        val labelByIri = confirmations.all().associate { it.iri to it.label }
        val anchors = ctx.filter { confirmations.isConfirmed(it.iri) }
            .map { it.name to labelByIri[it.iri].orEmpty() }

        val out = mutableListOf<EnrichmentCandidate>()
        for (chunk in targets.chunked(chunkSize.coerceAtLeast(1))) {
            // 같은 이름(중복 라벨/프래그먼트) 클래스가 서로 덮어쓰지 않도록 청크 내 고유 키 부여.
            val seen = HashMap<String, Int>()
            val keyed = chunk.map { c ->
                val n = seen.merge(c.name, 1, Int::plus)!!
                if (n == 1) c else c.copy(name = "${c.name}__$n")
            }
            val nameToIri = keyed.associate { it.name to it.iri }
            val response = advisor.ask(buildPromptFor(keyed, anchors))
            out += parseCandidates(response, nameToIri)
        }
        return out
    }
}
