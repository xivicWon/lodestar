package com.ontostudio.rdb

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.node.ArrayNode
import com.fasterxml.jackson.databind.node.ObjectNode
import java.io.File
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * #88 L0 Source — DB 트랙 프로브.
 *
 * 이 테스트는 기능이 아니라 **계측기**다. 고정 revision(3c27259)의 `legacy-sample.sql` 을 입력으로
 * 실제 수집기(`DdlParser` · `SampleLegacyDb`)를 돌려 I1 §4.1 의 L0 무조건 게이트 4종을 측정하고,
 * 결과를 결정적 JSON 프로브 산출물로 남긴다. 보고서(Run Quality Report v0)는 이 산출물에서만 만든다.
 *
 * 측정 규칙과 판정은 docs/superpowers/specs/2026-07-30-m0-l0-source-validation.md 에 있다.
 *
 * 단언은 **측정된 사실**에 걸린다 — 계약 위반(메타데이터 0%·오류 가시성 0%)은 여기서 붉게 만들지
 * 않고 보고서의 게이트 FAIL 로 남긴다. 프로브가 스스로 붉어지면 그 이후를 측정할 수 없다.
 */
class L0DbSourceProbeTest {

    private val mapper = ObjectMapper()

    // ---- 측정 규칙 (선언) -------------------------------------------------------------
    // M-DB-1  입력 단위는 SQL 문장이다. ';' 로 나눈 뒤 '--' 주석 행을 걷어내고 남은 비어있지 않은
    //         조각 하나가 1건이다(I2 R-F-4). 이 규칙은 PL/pgSQL 본문이 없는 입력에서만 정확하므로
    //         전제를 테스트가 직접 확인한다(`pinned input has no nested statement bodies`).
    // M-DB-2  수집 성공(ACQUIRED) = 그 문장의 대상이 수집기 산출물에 나타난 것.
    // M-DB-3  CREATE VIEW = 미지원(UNSUPPORTED), INSERT = L0 최소저장 원칙상 범위 밖(OUT_OF_SCOPE).
    //         둘 다 '사유와 함께 보고되어야 하는 제외' 다.
    // M-DB-4  결정성 = 3회 실행의 정규화 산출물 해시 중 최대 동일 그룹 크기 / 3.
    private val requiredProvenanceFields =
        listOf("projectId", "sourceId", "revision", "contentHash", "collectorVersion")
    private val reportingChannelNames =
        listOf("failure", "failed", "error", "excluded", "exclusion", "skipped", "warning", "reported")

    private val repoRoot: File by lazy {
        var d = File("").absoluteFile
        while (!File(d, ".git").exists()) d = d.parentFile ?: error("리포 루트를 찾지 못했다")
        d
    }
    private val goldDir get() = File(repoRoot, "docs/superpowers/specs/gold")
    private val runDir get() = File(repoRoot, "docs/superpowers/specs/bench/l0/runs/run-l0-db-3c27259-001")
    private val pinnedSqlPath = "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql"

    private fun sha256(bytes: ByteArray): String =
        "sha256:" + MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }

    private fun manifest(): ObjectNode = mapper.readTree(File(goldDir, "manifest.json")) as ObjectNode

    private fun pinnedSource(sourceId: String): ObjectNode =
        (manifest()["pinnedSources"] as ArrayNode).first { it["sourceId"].asText() == sourceId } as ObjectNode

    /**
     * 문장 인벤토리 — M-DB-1. 좌표는 그 문장의 **첫 실제 코드 행**을 가리킨다
     * (주석·빈 줄을 세면 좌표가 원본에서 조회되지 않는다).
     */
    private fun statements(sql: String): List<Pair<Int, String>> {
        val out = mutableListOf<Pair<Int, String>>()
        var offset = 0
        for (chunk in sql.split(";")) {
            var lineOffset = offset
            var firstCodeOffset = -1
            for (line in chunk.split("\n")) {
                val t = line.trim()
                if (t.isNotEmpty() && !t.startsWith("--")) { firstCodeOffset = lineOffset; break }
                lineOffset += line.length + 1
            }
            val body = chunk.lineSequence()
                .filterNot { it.trim().startsWith("--") }
                .joinToString("\n").trim()
            if (body.isNotEmpty() && firstCodeOffset >= 0) {
                val lineNo = 1 + sql.substring(0, firstCodeOffset).count { it == '\n' }
                out.add(lineNo to body)
            }
            offset += chunk.length + 1
        }
        return out
    }

    private fun kindOf(body: String): String {
        val head = body.replace(Regex("\\s+"), " ").uppercase()
        return when {
            head.startsWith("CREATE TABLE") -> "CREATE_TABLE"
            head.startsWith("CREATE VIEW") -> "CREATE_VIEW"
            head.startsWith("INSERT") -> "INSERT"
            else -> "OTHER"
        }
    }

    private fun targetOf(kind: String, body: String): String {
        val re = when (kind) {
            "CREATE_TABLE" -> Regex("(?is)CREATE\\s+TABLE\\s+([\\w\"`.]+)")
            "CREATE_VIEW" -> Regex("(?is)CREATE\\s+VIEW\\s+([\\w\"`.]+)")
            "INSERT" -> Regex("(?is)INSERT\\s+INTO\\s+([\\w\"`.]+)")
            else -> Regex("^(\\S+)")
        }
        return re.find(body)?.groupValues?.get(1)?.trim('"', '`') ?: "?"
    }

    /** 수집기 산출물의 정규화 표현 — 결정성 해시와 PII 노출 검사의 대상이다. */
    private fun canonical(schema: SchemaModel): String {
        val root = mapper.createArrayNode()
        for (t in schema.tables.sortedBy { it.name }) {
            val n = mapper.createObjectNode()
            n.put("name", t.name)
            val cols = n.putArray("columns")
            for (c in t.columns) {
                val cn = mapper.createObjectNode()
                cn.put("name", c.name); cn.put("sqlType", c.sqlType); cn.put("nullable", c.nullable)
                cols.add(cn)
            }
            val pk = n.putArray("primaryKey"); t.primaryKey.forEach { pk.add(it) }
            val fks = n.putArray("foreignKeys")
            for (f in t.foreignKeys.sortedBy { it.refTable + it.fkColumns.joinToString(",") }) {
                val fn = mapper.createObjectNode()
                fn.put("refTable", f.refTable)
                fn.putArray("fkColumns").also { a -> f.fkColumns.forEach { a.add(it) } }
                fn.putArray("refColumns").also { a -> f.refColumns.forEach { a.add(it) } }
                fks.add(fn)
            }
            root.add(n)
        }
        return mapper.writeValueAsString(root)
    }

    // ---- 프로브 -----------------------------------------------------------------------

    @Test fun `pinned input has no nested statement bodies (M-DB-1 전제)`() {
        val sql = File(repoRoot, pinnedSqlPath).readText()
        val nested = statements(sql).filter {
            Regex("(?is)\\b(BEGIN|CREATE\\s+(OR\\s+REPLACE\\s+)?(FUNCTION|PROCEDURE|TRIGGER))\\b")
                .containsMatchIn(it.second)
        }
        assertTrue(nested.isEmpty(), "PL/pgSQL 본문이 있으면 ';' 분할 인벤토리가 부정확해진다: $nested")
    }

    @Test fun `L0 db probe`() {
        val sqlFile = File(repoRoot, pinnedSqlPath)
        val before = sqlFile.readBytes()
        val beforeHash = sha256(before)
        val beforeModified = sqlFile.lastModified()
        val sql = before.toString(Charsets.UTF_8)

        val pinned = pinnedSource("db:legacy-sample")
        val probe = mapper.createObjectNode()
        probe.put("probeVersion", "l0-db-probe/v1")
        probe.put("layer", "L0")
        probe.put("track", "db")
        probe.put("projectId", "lodestar")
        probe.put("sourceRevision", manifest()["sourceRevision"].asText())
        probe.put("goldSetId", manifest()["goldSetId"].asText())
        probe.put("fixtureHash", manifest()["fixtureHash"].asText())

        probe.putObject("collector").apply {
            put("impl", "DdlParser + DdlSource (DDL 텍스트 경로) · SampleLegacyDb + MetadataService (샘플 적재 경로)")
            put("declaredVersion", "none")
            put("citedVersion", "DdlParser@3c27259")
            put("note", "수집기 자체가 버전을 선언하지 않는다 — 보고서의 collector 버전은 revision 으로 대신 고정한다")
        }

        probe.putObject("input").apply {
            put("sourceId", "db:legacy-sample")
            put("path", pinnedSqlPath)
            put("contentHash", beforeHash)
            put("pinnedContentHash", pinned["contentHash"].asText())
            put("hashMatchesPinned", beforeHash == pinned["contentHash"].asText())
            put("lines", sql.count { it == '\n' } + if (sql.endsWith("\n")) 0 else 1)
            put("pinnedLines", pinned["lines"].asInt())
        }

        // 1) 문장 인벤토리와 수집 결과 대조
        val inv = statements(sql)
        val parsed = DdlParser().parse(sql)
        val acquiredNames = parsed.tables.map { it.name }.toSet()

        val byKind = linkedMapOf<String, Int>()
        val exclusions = linkedMapOf<String, MutableList<String>>()
        var acquired = 0
        var missing = mutableListOf<String>()
        for ((line, body) in inv) {
            val kind = kindOf(body)
            byKind[kind] = (byKind[kind] ?: 0) + 1
            val target = targetOf(kind, body)
            val locator = "$pinnedSqlPath#L$line"
            when (kind) {
                "CREATE_TABLE" ->
                    if (target in acquiredNames) acquired++ else missing.add("$locator ($target)")
                "CREATE_VIEW" -> exclusions
                    .getOrPut("UNSUPPORTED_STATEMENT: CREATE VIEW 는 수집기가 처리하지 않는다 (DdlParser 는 CREATE TABLE 만 본다)") { mutableListOf() }
                    .add("$locator ($target)")
                "INSERT" -> exclusions
                    .getOrPut("OUT_OF_SCOPE_BY_DESIGN: 행 데이터는 L0 최소저장 범위 밖이다 (구조·메타데이터만 보관)") { mutableListOf() }
                    .add("$locator ($target)")
                else -> exclusions
                    .getOrPut("OTHER: 인벤토리 규칙이 분류하지 못한 문장") { mutableListOf() }
                    .add("$locator ($target)")
            }
        }

        probe.putObject("statementInventory").apply {
            put("rule", "M-DB-1")
            put("total", inv.size)
            putObject("byKind").also { n -> byKind.forEach { (k, v) -> n.put(k, v) } }
        }
        probe.putObject("acquisition").apply {
            put("acquired", acquired)
            put("failed", 0)
            put("excluded", exclusions.values.sumOf { it.size })
            putArray("missing").also { a -> missing.forEach { a.add(it) } }
            putArray("exclusions").also { arr ->
                exclusions.forEach { (reason, examples) ->
                    val e = mapper.createObjectNode()
                    e.put("reason", reason); e.put("count", examples.size)
                    e.putArray("examples").also { a -> examples.forEach { x -> a.add(x) } }
                    arr.add(e)
                }
            }
        }

        // 2) 결정성 — 3회 실행 (M-DB-4)
        val hashes = (1..3).map { sha256(canonical(DdlParser().parse(sql)).toByteArray()) }
        val largestGroup = hashes.groupingBy { it }.eachCount().values.max()
        probe.putObject("determinism").apply {
            put("runs", 3)
            putArray("artifactHashes").also { a -> hashes.forEach { a.add(it) } }
            put("largestIdenticalGroup", largestGroup)
            put("rate", largestGroup.toDouble() / 3.0)
        }

        // 3) provenance 필수 식별 필드 — 산출물 타입에 자리가 있는가 (리플렉션)
        val memberNames = listOf(
            SchemaModel::class, TableInfo::class, ColumnInfo::class, ForeignKeyInfo::class
        ).flatMap { k -> k.members.map { it.name } }.map { it.lowercase() }.toSet()
        val present = requiredProvenanceFields.filter { f -> memberNames.any { it.contains(f.lowercase()) } }
        probe.putObject("provenance").apply {
            put("probe", "kotlin-reflect — SchemaModel/TableInfo/ColumnInfo/ForeignKeyInfo 의 선언 멤버 이름")
            putArray("required").also { a -> requiredProvenanceFields.forEach { a.add(it) } }
            putArray("present").also { a -> present.forEach { a.add(it) } }
            put("rate", present.size.toDouble() / requiredProvenanceFields.size)
        }

        // 4) 오류·제외 보고 채널이 산출물에 존재하는가
        val channels = reportingChannelNames.filter { c -> memberNames.any { it.contains(c) } }
        probe.putObject("reporting").apply {
            put("probe", "산출물 타입에 실패·제외를 담을 멤버가 있는가")
            putArray("channelsFound").also { a -> channels.forEach { a.add(it) } }
            put("channelExists", channels.isNotEmpty())
            put("note", "DdlParser.parse 의 반환형은 SchemaModel 뿐이다 — 제외·실패를 실을 자리가 없으므로 " +
                "제외 사유 보고율은 구조적으로 0 이다(I1 §4.1 오류 가시성)")
        }

        // 5) 실패 재현 픽스처 (I2 gold failures.json 의 DB 3건)
        val goldFailures = mapper.readTree(File(goldDir, "failures.json"))
        val fixArr = probe.putArray("failureFixtures")
        for (f in goldFailures["fixtures"]) {
            val path = f["path"].asText()
            if (!path.endsWith(".sql")) continue
            val file = File(repoRoot, path)
            val bytes = file.readBytes()
            val fixSql = bytes.toString(Charsets.UTF_8)
            val out = DdlParser().parse(fixSql)
            val expectedReported = f["reported"].size()
            val expectedNames = f["extracted"].filter { it["type"].asText() == "TABLE" }
                .map { it["name"].asText() }.sorted()
            val actualNames = out.tables.map { it.name }.sorted()
            val n = mapper.createObjectNode()
            n.put("id", f["id"].asText())
            n.put("kind", f["kind"].asText())
            n.put("path", path)
            n.put("contentHash", sha256(bytes))
            n.put("hashMatchesPinned", sha256(bytes) == f["contentHash"].asText())
            n.putArray("expectedExtracted").also { a -> expectedNames.forEach { a.add(it) } }
            n.putArray("actualExtracted").also { a -> actualNames.forEach { a.add(it) } }
            n.putArray("unexpectedExtracted").also { a ->
                for (x in actualNames - expectedNames.toSet()) {
                    val t = out.tables.first { it.name == x }
                    a.add("$x(columns=${t.columns.joinToString("|") { it.name }})")
                }
            }
            n.putArray("missingExtracted")
                .also { a -> (expectedNames - actualNames.toSet()).forEach { x -> a.add(x) } }
            n.put("expectedReported", expectedReported)
            n.put("actualReported", 0)
            n.put("silentSkipIsFailure", f["silentSkipIsFailure"].asBoolean())
            n.put("verdict", when {
                expectedReported > 0 && actualNames != expectedNames -> "UNREPORTED+SILENT_PARTIAL_RECOVERY"
                expectedReported > 0 -> "UNREPORTED"
                actualNames != expectedNames -> "EXTRACTION_MISMATCH"
                else -> "OK"
            })
            fixArr.add(n)
        }

        // 6) PII·시크릿 — 수집 산출물 표면에 gold 양성이 원문으로 남는가
        val piiGold = mapper.readTree(File(goldDir, "pii.json"))
        val corpusPath = "docs/superpowers/specs/gold/fixtures/pii/corpus.sql"
        val corpusSql = File(repoRoot, corpusPath).readText()
        val corpusArtifact = canonical(DdlParser().parse(corpusSql))
        val unmasked = mutableListOf<String>()
        val notCollected = mutableListOf<String>()
        var positives = 0
        for (item in piiGold["items"]) {
            if (item["ref"]["sourceId"].asText() != "pii:corpus.sql") continue
            if (item["expect"].asText() != "MASKED") continue
            positives++
            val text = item["value"]["text"].asText()
            if (corpusArtifact.contains(text)) unmasked.add(item["id"].asText())
            else notCollected.add(item["id"].asText())
        }
        probe.putObject("pii").apply {
            put("corpus", "pii:corpus.sql")
            put("corpusPath", corpusPath)
            put("positives", positives)
            put("masked", 0)
            putArray("unmaskedInArtifact").also { a -> unmasked.forEach { a.add(it) } }
            putArray("notCollected").also { a -> notCollected.forEach { a.add(it) } }
            put("note", "'미마스킹 0건' 이 곧 마스킹 성공이 아니다 — 양성이 산출물 표면에 도달하지 못한 " +
                "(not_collected) 결과이며 마스킹 단계는 존재하지 않는다")
        }

        // 7) 샘플 적재 경로 — 행 데이터가 저장소에 원문으로 들어가는가
        val ingest = probe.putObject("ingestStore")
        SampleLegacyDb().open().use { conn ->
            ingest.put("probe", "SampleLegacyDb.open() 후 저장소 질의")
            ingest.put("statementsExecuted", inv.size)
            val rowProbes = ingest.putArray("piiShapedColumns")
            for ((table, cols) in listOf(
                "TB_CUST_MST" to listOf("CUST_NM" to "ORG_NAME", "RPRS_NM" to "NAME", "TEL_NO" to "TEL", "BIZ_NO" to "BIZ_NO"),
                "TB_EMP_MST" to listOf("EMP_NM" to "NAME"),
            )) {
                for ((col, cls) in cols) {
                    conn.createStatement().use { st ->
                        st.executeQuery("SELECT COUNT($col) FROM $table WHERE $col IS NOT NULL").use { rs ->
                            rs.next()
                            val n = mapper.createObjectNode()
                            n.put("table", table); n.put("column", col); n.put("class", cls)
                            n.put("retrievableValues", rs.getInt(1))
                            n.put("masked", false)
                            n.put("locator", "$pinnedSqlPath#L229-L262")
                            rowProbes.add(n)
                        }
                    }
                }
            }
            ingest.put("note", "적재는 CREATE 뿐 아니라 INSERT 까지 전 문장을 실행한다(SampleLegacyDb.kt#L20-L28). " +
                "행 데이터가 마스킹 없이 저장소에 남으므로, 값에 PII 가 있는 소스는 그대로 노출된다. " +
                "값은 여기 적지 않고 좌표만 남긴다.")
        }

        // 8) 원본 read-only 확인
        val after = sqlFile.readBytes()
        probe.putObject("readOnly").apply {
            put("contentHashBefore", beforeHash)
            put("contentHashAfter", sha256(after))
            put("lastModifiedUnchanged", beforeModified == sqlFile.lastModified())
            put("unchanged", beforeHash == sha256(after))
        }

        // ---- 산출물 기록 + 표류 검사 ----------------------------------------------------
        val json = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(probe) + "\n"
        val outFile = File(File(repoRoot, "backend/build/l0"), "probe-db.json")
        outFile.parentFile.mkdirs()
        outFile.writeText(json)

        val committed = File(runDir, "probe-db.json")
        if (committed.exists()) {
            assertEquals(committed.readText(), json,
                "커밋된 프로브 산출물과 이번 실행 결과가 다르다 — 보고서의 근거가 표류했다. " +
                    "새 실측이면 새 runId 로 남긴다(I3 §5.5). 생성물: ${outFile.path}")
        }

        // ---- 측정된 사실에 대한 단언 -----------------------------------------------------
        assertTrue(probe["input"]["hashMatchesPinned"].asBoolean(),
            "작업 트리 입력이 고정 revision 의 해시와 다르다 — 이 실행은 baseline 이 아니다")
        assertTrue(probe["readOnly"]["unchanged"].asBoolean(), "수집이 원본을 변경했다")
        assertEquals(
            inv.size,
            probe["acquisition"]["acquired"].asInt() + probe["acquisition"]["failed"].asInt() +
                probe["acquisition"]["excluded"].asInt(),
            "input = acquired + failed + excluded 가 성립해야 한다(I3 R2)")
        assertTrue(missing.isEmpty(), "CREATE TABLE 인데 산출물에 없는 대상: $missing")
        assertFalse(probe["reporting"]["channelExists"].asBoolean(),
            "산출물에 실패·제외 보고 채널이 생겼다면 이 프로브의 게이트 산식을 갱신해야 한다")
        assertTrue(probe["failureFixtures"].size() == 3, "DB 실패 픽스처 3건을 모두 돌려야 한다")
        assertTrue(probe["failureFixtures"].all { it["hashMatchesPinned"].asBoolean() },
            "실패 픽스처 해시가 gold 고정값과 다르다")
    }
}
