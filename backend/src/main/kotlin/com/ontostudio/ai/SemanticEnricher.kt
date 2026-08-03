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
import com.ontostudio.rdb.TableInfo
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

    /**
     * 후보의 대상 IRI 는 **임포트가 만든 IRI 와 같아야** 한다 — 다르면 확정을 붙일 자리가 없다.
     * 그래서 이름으로 조립하지 않고 매퍼의 IRI 생성을 그대로 쓴다(소속 한정 포함 · #126).
     */
    private fun classIri(table: TableInfo) = mapper.classIri(baseIri, table).toString()

    fun enrichSample(): List<EnrichmentCandidate> {
        val (prompt, iriByTable) = sampleDb.open().use { conn -> buildPrompt(conn) }
        // 미확정(추정 대상) 테이블이 하나도 없으면 AI를 호출하지 않고 빈 결과(E8 그라운딩).
        if (iriByTable.isEmpty()) return emptyList()
        val response = advisor.ask(prompt)
        return parse(response, iriByTable)
    }

    /**
     * 프롬프트와 (추정 대상 테이블명 → 대상 IRI)를 만든다. AI 응답은 이름만 돌려주므로, 그 이름을
     * 임포트가 만든 IRI 로 되돌리는 표가 함께 있어야 한다 — 이름으로 IRI 를 다시 조립하면 소속이
     * 있는 테이블에서 임포트 IRI 와 어긋난다(#126).
     *
     * 확정된 테이블은 추정 대상에서 제외하고, 확정 라벨을 "이미 확정된 사실" 앵커로 주입한다(E8 그라운딩).
     */
    internal fun buildPrompt(conn: Connection): Pair<String, Map<String, String>> {
        // 번들 샘플을 적재한 커넥션이다(enrichSample → sampleDb.open) — gold 가 고정한 신원을 쓴다.
        val schema = metadata.extract(
            conn, sourceId = SampleSource.SOURCE_ID, revisionScheme = SampleSource.REVISION_SCHEME)
        val confirmedHere = schema.tables.filter { confirmations.isConfirmed(classIri(it)) }
        val targets = schema.tables.filter { !confirmations.isConfirmed(classIri(it)) }
        val labelByIri = confirmations.all().associate { it.iri to it.label }

        val sb = StringBuilder()
        if (confirmedHere.isNotEmpty()) {
            sb.appendLine("## 이미 확정된 사실 (변경 금지, 이 의미에 일관되게 추론하라)")
            for (t in confirmedHere) {
                sb.appendLine("- ${t.name} = ${labelByIri[classIri(t)].orEmpty()}")
            }
            sb.appendLine()
        }
        sb.appendLine("## 추정 대상")
        sb.appendLine("다음은 레거시 DB 테이블 목록이다. 암호 같은 이름·컬럼·샘플 데이터를 보고 각 테이블의")
        sb.appendLine("비즈니스 의미를 추정하라. 반드시 아래 JSON 배열만 출력한다(그 외 텍스트 금지):")
        sb.appendLine("""[{"table":"<원본테이블명>","label":"<한국어 비즈니스 이름>","description":"<한 줄 설명>"}]""")
        sb.appendLine()
        // 소속이 달라 이름만 같은 테이블은 이름으로 되돌릴 수 없다. 프롬프트에서 빼면 조용한
        // 누락이고, 넣고 응답을 버리면 물어보고 버리는 것이다 — E12(enrichCurrent)와 같은 방식으로
        // 청크 안에서 고유 키(`name__2`)를 준다.
        val seen = HashMap<String, Int>()
        val keyed = targets.map { t ->
            val n = seen.merge(t.name, 1, Int::plus)!!
            (if (n == 1) t.name else "${t.name}__$n") to t
        }
        for ((key, t) in keyed) {
            sb.appendLine("### $key")
            sb.appendLine("컬럼: " + t.columns.joinToString(", ") { it.name })
            val rows = sampleRows(conn, t, 3)
            if (rows.isNotEmpty()) {
                sb.appendLine("샘플:")
                // #115/#85: 마스킹은 저장·로그·**AI 요청**보다 먼저다. 적재 경로가 이미 마스킹하지만
                // 라이브 JDBC 소스의 행은 원문이므로, 요청 경계에서 한 번 더 통과시킨다(다중 방어).
                for (r in rows) sb.appendLine(masker.maskField(
                    "  - " + r.entries.joinToString(", ") { "${it.key}=${it.value}" }))
            }
            sb.appendLine()
        }
        return sb.toString() to keyed.associate { (key, t) -> key to classIri(t) }
    }

    /**
     * 근거로 쓸 샘플 행. 조회는 **소속까지 한정**한다(#126) — 한정하지 않으면 소속이 다른 동명
     * 테이블에서 검색 경로가 고른 쪽의 행이 실려 다른 테이블의 값이 이 테이블의 근거가 되고,
     * 기본 스키마 밖의 테이블은 아예 조회되지 않는다(라이브 PostgreSQL 의 비-public 스키마).
     */
    private fun sampleRows(conn: Connection, table: TableInfo, limit: Int): List<Map<String, String>> {
        val qualified = table.schema?.let { "\"$it\".\"${table.name}\"" } ?: "\"${table.name}\""
        val out = mutableListOf<Map<String, String>>()
        conn.createStatement().use { st ->
            st.executeQuery("SELECT * FROM $qualified FETCH FIRST $limit ROWS ONLY").use { rs ->
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
    internal fun parse(response: String, iriByTable: Map<String, String>): List<EnrichmentCandidate> {
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
            val iri = iriByTable[table] ?: return@mapNotNull null
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
