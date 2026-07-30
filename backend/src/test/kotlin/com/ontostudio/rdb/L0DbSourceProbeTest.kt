package com.ontostudio.rdb

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.node.ArrayNode
import com.fasterxml.jackson.databind.node.ObjectNode
import java.io.File
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * #114 L0 Source — DB 트랙 프로브 **v2** (오류 가시성 수정 후 재측정).
 *
 * 이 테스트는 기능이 아니라 **계측기**다. 고정 revision(3c27259)의 `legacy-sample.sql` 을 입력으로
 * 실제 수집기(`DdlParser` · `SampleLegacyDb` · `MetadataService`)를 돌려 I1 §4.1 의 L0 무조건 게이트
 * 4종을 측정하고, 결과를 결정적 JSON 프로브 산출물로 남긴다. 보고서는 이 산출물에서만 만든다.
 *
 * **v1 과의 차이**: v1(run-l0-db-3c27259-001)은 `SchemaModel` 에 제외·실패를 실을 자리가 없던
 * 수집기를 쟀다. #114 로 반환형에 [CollectionIssue] 채널이 생겼으므로 v1 의 산식(보고율은 구조적으로 0)이
 * 더 이상 성립하지 않는다. v1 산출물·보고서는 비교 기준선으로 **그대로 남기고**(I3 §5.5 — 사후 수정은
 * 새 runId), 이 프로브는 새 runId 로 재측정한다. 입력은 v1 과 같은 고정 원본이므로 두 실행은 비교 가능하다.
 *
 * 측정 규칙과 판정은 docs/superpowers/specs/2026-07-30-m0-l0-source-validation.md 에 있다.
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
    // M-DB-5  보고(REPORTED) = 수집기 **반환형**에 사유(빈 문자열 아님)·좌표·대상이 함께 실린 것.
    //         gold 기대 항목과의 대조는 (사유코드 일치 ∧ 좌표 행범위 겹침) 으로 귀속한다 —
    //         건수만 맞추거나 그럴듯한 좌표를 적어 통과하는 경로를 막는다.
    private val requiredProvenanceFields =
        listOf("projectId", "sourceId", "revision", "contentHash", "collectorVersion")
    // 보고 채널로 인정하는 멤버 이름. v1 의 목록에 #114 가 도입한 어휘(issue·partial)를 더했다 —
    // 이름 목록은 선언된 휴리스틱이므로, 늘렸다는 사실 자체를 프로브 산출물에 남긴다.
    private val reportingChannelNames =
        listOf("failure", "failed", "error", "excluded", "exclusion", "skipped", "warning", "reported",
            "issue", "partial")

    private val repoRoot: File by lazy {
        var d = File("").absoluteFile
        while (!File(d, ".git").exists()) d = d.parentFile ?: error("리포 루트를 찾지 못했다")
        d
    }
    private val goldDir get() = File(repoRoot, "docs/superpowers/specs/gold")
    private val runDir get() = File(repoRoot, "docs/superpowers/specs/bench/l0/runs/run-l0-db-3c27259-002")
    private val pinnedSqlPath = "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql"

    /** 수집기 신원 — 커밋이 아직 없는 재측정에서도 재현 대상을 특정할 수 있는 값이다. */
    private val collectorSources = listOf(
        "backend/src/main/kotlin/com/ontostudio/rdb/DdlParser.kt",
        "backend/src/main/kotlin/com/ontostudio/rdb/SchemaModel.kt",
        "backend/src/main/kotlin/com/ontostudio/rdb/MetadataService.kt",
        "backend/src/main/kotlin/com/ontostudio/rdb/SampleLegacyDb.kt",
    )

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

    /**
     * 수집기 산출물의 정규화 표현 — 결정성 해시와 PII 노출 검사의 대상이다.
     *
     * 샘플 적재 경로의 H2 DB 이름(`LEGACY_<nanoTime>`)만 정규화한다. 그것은 이 실행의 접속 신원이지
     * 수집 결과가 아니다 — 정규화하지 않으면 '수집기가 비결정적' 이라고 잘못 적게 된다
     * (코드 트랙 프로브가 `meta.source_root` 를 빼는 것과 같은 이유).
     */
    private fun canonical(schema: SchemaModel): String {
        val root = mapper.createObjectNode()
        val tabs = root.putArray("tables")
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
            tabs.add(n)
        }
        // 제외·실패도 산출물의 일부다 — 결정성은 이쪽까지 포함해서 재야 의미가 있다.
        val iss = root.putArray("issues")
        for (i in (schema.issues + schema.partials).sortedWith(compareBy({ it.locator }, { it.reasonCode }))) {
            iss.add(mapper.createObjectNode().apply {
                put("kind", i.kind.name); put("reasonCode", i.reasonCode)
                put("locator", i.locator); put("target", i.target); put("reason", i.reason)
            })
        }
        return mapper.writeValueAsString(root).replace(Regex("LEGACY_\\d+"), "LEGACY_<nanoTime>")
    }

    /** 좌표에서 행 범위를 뽑는다: `path#L11-L14` · `#L16` → (11,14) · (16,16). */
    private fun lineRange(locator: String): Pair<Int, Int>? {
        val m = Regex("#L(\\d+)(?:-L(\\d+))?").find(locator) ?: return null
        val s = m.groupValues[1].toInt()
        return s to (m.groupValues[2].takeIf { it.isNotEmpty() }?.toInt() ?: s)
    }

    private fun overlaps(a: Pair<Int, Int>, b: Pair<Int, Int>) = a.first <= b.second && b.first <= a.second

    /** gold 기대 보고 항목 ↔ 수집기가 실제로 낸 항목의 귀속(M-DB-5). */
    private fun attribute(gold: JsonNode, issues: List<CollectionIssue>): ObjectNode {
        val node = mapper.createObjectNode()
        val expected = node.putArray("expected")
        val used = mutableSetOf<Int>()
        var matched = 0
        for (g in gold) {
            val want = lineRange(g["locator"].asText()) ?: (0 to 0)
            val hitIdx = issues.indices.firstOrNull { idx ->
                idx !in used &&
                    issues[idx].reasonCode == g["kind"].asText() &&
                    issues[idx].reason.isNotBlank() &&
                    lineRange(issues[idx].locator)?.let { overlaps(it, want) } == true
            }
            val e = mapper.createObjectNode()
            e.put("kind", g["kind"].asText())
            e.put("target", g["target"].asText())
            e.put("locator", g["locator"].asText())
            if (hitIdx != null) {
                used.add(hitIdx)
                matched++
                val i = issues[hitIdx]
                e.put("reported", true)
                e.put("observedKind", i.kind.name)
                e.put("observedLocator", i.locator)
                e.put("observedTarget", i.target)
                e.put("reasonPresent", i.reason.isNotBlank())
                // 대상 표기에는 자유도가 있다(경로 대 FQN) — 마지막 식별자로만 대조하고 기록에 남긴다.
                val last = g["target"].asText().split(Regex("[\\s./]+")).last()
                e.put("targetMatches", i.target.contains(last))
            } else {
                e.put("reported", false)
            }
            expected.add(e)
        }
        node.put("expectedReported", gold.size())
        node.put("actualReported", matched)
        // gold 기대에 귀속되지 않은 보고 — 과대 집계(R-F-4)를 드러낸다.
        node.putArray("unattributedReports").also { a ->
            issues.indices.filter { it !in used }
                .forEach { a.add("${issues[it].reasonCode} ${issues[it].locator}") }
        }
        return node
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
        probe.put("probeVersion", "l0-db-probe/v2")
        probe.put("layer", "L0")
        probe.put("track", "db")
        probe.put("projectId", "lodestar")
        probe.put("sourceRevision", manifest()["sourceRevision"].asText())
        probe.put("goldSetId", manifest()["goldSetId"].asText())
        probe.put("fixtureHash", manifest()["fixtureHash"].asText())

        val collectorHash = sha256(
            collectorSources.joinToString("\n") { "$it ${sha256(File(repoRoot, it).readBytes())}" }
                .toByteArray())
        probe.putObject("collector").apply {
            put("impl", "DdlParser + DdlSource (DDL 텍스트 경로) · SampleLegacyDb + MetadataService (샘플 적재 경로)")
            put("declaredVersion", "none")
            put("citedVersion", "DdlParser+SampleLegacyDb@$collectorHash")
            put("sourceHash", collectorHash)
            putArray("sourceFiles").also { a -> collectorSources.forEach { a.add(it) } }
            put("note", "수집기 자체는 여전히 버전을 선언하지 않는다(L0-fix-2 — #114 범위 밖). 재측정 시점의 " +
                "커밋이 아직 없으므로 수집기 신원은 구성 파일 해시로 고정한다 — 값은 재계산으로 검증된다")
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

        // 1) 문장 인벤토리와 수집 결과 대조 — 제외·실패는 **수집기 반환형에서** 읽는다.
        val inv = statements(sql)
        val parsed = DdlParser().parse(sql, pinnedSqlPath)
        val acquiredNames = parsed.tables.map { it.name }.toSet()

        val byKind = linkedMapOf<String, Int>()
        for ((_, body) in inv) {
            val kind = kindOf(body)
            byKind[kind] = (byKind[kind] ?: 0) + 1
        }
        val missing = inv.filter { kindOf(it.second) == "CREATE_TABLE" }
            .mapNotNull { (line, body) ->
                val name = Regex("(?is)CREATE\\s+TABLE\\s+([\\w\"`.]+)").find(body)
                    ?.groupValues?.get(1)?.trim('"', '`')
                if (name != null && name !in acquiredNames) "$pinnedSqlPath#L$line ($name)" else null
            }

        val exclusions = linkedMapOf<String, MutableList<String>>()
        for (i in parsed.issues.filter { it.kind == IssueKind.SKIPPED }) {
            exclusions.getOrPut("${i.reasonCode}: ${i.reason}") { mutableListOf() }
                .add("${i.locator.substringBefore("-L")} (${i.target})")
        }
        val failures = parsed.issues.filter { it.kind == IssueKind.FAILED }

        probe.putObject("statementInventory").apply {
            put("rule", "M-DB-1")
            put("total", inv.size)
            putObject("byKind").also { n -> byKind.forEach { (k, v) -> n.put(k, v) } }
            put("collectorAccountedTotal", parsed.tables.size + parsed.issues.size)
            put("accountingMatchesInventory", parsed.tables.size + parsed.issues.size == inv.size)
        }
        probe.putObject("acquisition").apply {
            put("acquired", parsed.tables.size)
            put("failed", failures.size)
            put("excluded", parsed.issues.count { it.kind == IssueKind.SKIPPED })
            // 사유·좌표·대상을 함께 실은 항목만 보고로 센다(M-DB-5).
            put("reported", parsed.issues.count {
                it.reason.isNotBlank() && lineRange(it.locator) != null && it.target.isNotBlank()
            })
            put("partial", parsed.partials.size)
            putArray("missing").also { a -> missing.forEach { a.add(it) } }
            putArray("exclusions").also { arr ->
                exclusions.forEach { (reason, examples) ->
                    val e = mapper.createObjectNode()
                    e.put("reason", reason); e.put("count", examples.size)
                    e.putArray("examples").also { a -> examples.forEach { x -> a.add(x) } }
                    arr.add(e)
                }
            }
            putArray("failures").also { arr ->
                failures.forEach { f ->
                    arr.add(mapper.createObjectNode().apply {
                        put("reasonCode", f.reasonCode); put("reason", f.reason)
                        put("locator", f.locator); put("target", f.target)
                    })
                }
            }
        }

        // 2) 결정성 — 3회 실행 (M-DB-4)
        val hashes = (1..3).map { sha256(canonical(DdlParser().parse(sql, pinnedSqlPath)).toByteArray()) }
        val largestGroup = hashes.groupingBy { it }.eachCount().values.max()
        probe.putObject("determinism").apply {
            put("runs", 3)
            putArray("artifactHashes").also { a -> hashes.forEach { a.add(it) } }
            put("largestIdenticalGroup", largestGroup)
            put("rate", largestGroup.toDouble() / 3.0)
        }

        // 3) provenance 필수 식별 필드 — 산출물 타입에 자리가 있는가 (리플렉션)
        val memberNames = listOf(
            SchemaModel::class, TableInfo::class, ColumnInfo::class, ForeignKeyInfo::class,
            CollectionIssue::class
        ).flatMap { k -> k.members.map { it.name } }.map { it.lowercase() }.toSet()
        val present = requiredProvenanceFields.filter { f -> memberNames.any { it.contains(f.lowercase()) } }
        probe.putObject("provenance").apply {
            put("probe", "kotlin-reflect — SchemaModel/TableInfo/ColumnInfo/ForeignKeyInfo/CollectionIssue 의 선언 멤버 이름")
            putArray("required").also { a -> requiredProvenanceFields.forEach { a.add(it) } }
            putArray("present").also { a -> present.forEach { a.add(it) } }
            put("rate", present.size.toDouble() / requiredProvenanceFields.size)
        }

        // 4) 오류·제외 보고 채널이 산출물에 존재하는가
        val channels = reportingChannelNames.filter { c -> memberNames.any { it.contains(c) } }
        probe.putObject("reporting").apply {
            put("probe", "산출물 타입에 실패·제외를 사유·좌표와 함께 실을 자리가 있는가")
            putArray("channelsFound").also { a -> channels.forEach { a.add(it) } }
            put("channelExists", channels.isNotEmpty())
            put("perItemReasons", true)
            put("channelMembers", "SchemaModel.issues · SchemaModel.partials " +
                "(CollectionIssue: kind · reasonCode · reason · locator · target)")
            put("note", "#114 로 DdlParser.parse 의 반환형에 제외·실패·부분수집 채널이 생겼다 — 보고율은 " +
                "구조가 아니라 실제 귀속으로 측정된다(M-DB-5)")
        }

        // 5) 실패 재현 픽스처 (I2 gold failures.json 의 DB 3건)
        val goldFailures = mapper.readTree(File(goldDir, "failures.json"))
        val fixArr = probe.putArray("failureFixtures")
        for (f in goldFailures["fixtures"]) {
            val path = f["path"].asText()
            if (!path.endsWith(".sql")) continue
            val file = File(repoRoot, path)
            val bytes = file.readBytes()
            val out = DdlParser().parse(bytes.toString(Charsets.UTF_8))
            val expectedNames = f["extracted"].filter { it["type"].asText() == "TABLE" }
                .map { it["name"].asText() }.sorted()
            val actualNames = out.tables.map { it.name }.sorted()
            val attribution = attribute(f["reported"], out.issues)
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
            n.put("expectedReported", attribution["expectedReported"].asInt())
            n.put("actualReported", attribution["actualReported"].asInt())
            n.set<JsonNode>("reportAttribution", attribution)
            n.put("markedAsPartial", out.partials.isNotEmpty())
            n.put("silentSkipIsFailure", f["silentSkipIsFailure"].asBoolean())
            n.put("verdict", when {
                actualNames != expectedNames -> "EXTRACTION_MISMATCH"
                attribution["actualReported"].asInt() < attribution["expectedReported"].asInt() -> "UNREPORTED"
                attribution["unattributedReports"].size() > 0 -> "OVER_REPORTED"
                else -> "OK"
            })
            fixArr.add(n)
        }

        // 6) PII·시크릿 — 수집 산출물 표면에 gold 양성이 원문으로 남는가
        val piiGold = mapper.readTree(File(goldDir, "pii.json"))
        val corpusPath = "docs/superpowers/specs/gold/fixtures/pii/corpus.sql"
        val corpusSql = File(repoRoot, corpusPath).readText()
        val corpusArtifact = canonical(DdlParser().parse(corpusSql, corpusPath))
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
                "(not_collected) 결과이며 마스킹 단계는 존재하지 않는다(L0-fix-5 — #114 범위 밖)")
        }

        // 7) 샘플 적재 경로 — (a) MetadataService 수집 산출물 (b) 저장소에 남는 행 데이터
        val ingest = probe.putObject("ingestStore")
        SampleLegacyDb().open().use { conn ->
            ingest.put("probe", "SampleLegacyDb.open() → MetadataService.extract(conn) + 저장소 질의")
            ingest.put("statementsExecuted", inv.size)

            // (a) JDBC 메타데이터 수집 경로를 실제로 돌린다 — DDL 텍스트 경로와 별개의 수집기다.
            val metadata = MetadataService()
            val jdbcHashes = (1..3).map { sha256(canonical(metadata.extract(conn)).toByteArray()) }
            val jdbcModel = metadata.extract(conn)
            val jdbcNames = jdbcModel.tables.map { it.name }.sorted()
            val jdbcArtifact = canonical(jdbcModel)
            val jdbcGroup = jdbcHashes.groupingBy { it }.eachCount().values.max()
            val jdbcMeta = ingest.putObject("metadataService").apply {
                put("probe", "MetadataService.extract(conn) — DatabaseMetaData 경로를 3회 실행")
                put("acquiredTables", jdbcNames.size)
                put("sameTableSetAsDdlPath", jdbcNames == acquiredNames.sorted())
                put("viewAcquired", jdbcNames.contains("VW_ORD_SUMMARY"))
                put("viewReported", jdbcModel.issues.any { it.target == "VW_ORD_SUMMARY" })
                putArray("reportedIssues").also { arr ->
                    jdbcModel.issues.forEach { i ->
                        arr.add(mapper.createObjectNode().apply {
                            put("kind", i.kind.name); put("reasonCode", i.reasonCode)
                            // 샘플 DB 이름은 실행마다 다르다(SampleLegacyDb 가 nanoTime 을 붙인다) —
                            // 프로브 산출물은 결정적이어야 하므로 그 부분만 정규화하고 사실을 남긴다.
                            put("locator", i.locator.replace(Regex("LEGACY_\\d+"), "LEGACY_<nanoTime>"))
                            put("target", i.target); put("reason", i.reason)
                        })
                    }
                }
                put("viewExclusionNote", "getTables(..., arrayOf(\"TABLE\")) 가 뷰를 타입 필터로 걸러낸다 — " +
                    "#114 이후 그 제외는 UNSUPPORTED_OBJECT_TYPE 사유로 반환형에 남는다")
                put("foreignKeys", jdbcModel.tables.sumOf { it.foreignKeys.size })
                put("runs", 3)
                putArray("artifactHashes").also { a -> jdbcHashes.forEach { a.add(it) } }
                put("largestIdenticalGroup", jdbcGroup)
                put("determinismRate", jdbcGroup.toDouble() / 3.0)
                put("provenanceRate", present.size.toDouble() / requiredProvenanceFields.size)
                put("note", "DDL 텍스트 경로와 같은 SchemaModel 로 수렴하므로 provenance·보고 채널 결과도 같다 " +
                    "— 두 경로의 결함도, 이번 수정도 산출물 타입에서 공유된다")
            }
            // (b) 저장소에 남는 행 데이터. 값은 산출물에 적지 않고 메모리에서만 쓴다.
            val rowProbes = ingest.putArray("piiShapedColumns")
            val storedValues = mutableListOf<String>()
            for ((table, cols) in listOf(
                "TB_CUST_MST" to listOf("CUST_NM" to "ORG_NAME", "RPRS_NM" to "NAME", "TEL_NO" to "TEL", "BIZ_NO" to "BIZ_NO"),
                "TB_EMP_MST" to listOf("EMP_NM" to "NAME"),
            )) {
                for ((col, cls) in cols) {
                    conn.createStatement().use { st ->
                        st.executeQuery("SELECT $col FROM $table WHERE $col IS NOT NULL").use { rs ->
                            var n = 0
                            while (rs.next()) { storedValues.add(rs.getString(1)); n++ }
                            val node = mapper.createObjectNode()
                            node.put("table", table); node.put("column", col); node.put("class", cls)
                            node.put("retrievableValues", n)
                            node.put("masked", false)
                            node.put("locator", "$pinnedSqlPath#L229-L262")
                            rowProbes.add(node)
                        }
                    }
                }
            }
            // 적재된 행 값이 수집 산출물 표면으로 새는가 (구조만 실리므로 0 이 기대값이다)
            jdbcMeta.put("storedRowValuesLeakedIntoArtifact",
                storedValues.count { jdbcArtifact.contains(it) })
            ingest.put("retrievableUnmaskedValues", storedValues.size)
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

        // 증거는 **실재해야** 한다. 없을 때 조용히 통과하면 증거를 지우는 것이 검사를 지우는 것이 된다.
        // 새 runId 를 처음 만들 때만 -DL0_PROBE_BOOTSTRAP=true 로 1회 우회하고, 그 흔적은 커밋 diff 에 남는다.
        val committed = File(runDir, "probe-db.json")
        val bootstrap = System.getProperty("L0_PROBE_BOOTSTRAP") == "true"
        assertTrue(committed.exists() || bootstrap,
            "커밋된 프로브 산출물이 없다: ${committed.path} — 이 보고서는 근거를 잃었다. " +
                "새 runId 최초 생성이면 -DL0_PROBE_BOOTSTRAP=true 로 실행하고 ${outFile.path} 를 커밋한다")
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
        assertTrue(probe["reporting"]["channelExists"].asBoolean(),
            "제외·실패 보고 채널이 사라졌다면 #114 가 되돌려진 것이다")
        assertEquals(
            probe["acquisition"]["excluded"].asInt() + probe["acquisition"]["failed"].asInt(),
            probe["acquisition"]["reported"].asInt(),
            "제외·실패는 전부 사유·좌표와 함께 보고돼야 한다(I1 §4.1 오류 가시성 100%)")
        assertTrue(probe["failureFixtures"].size() == 3, "DB 실패 픽스처 3건을 모두 돌려야 한다")
        assertTrue(probe["failureFixtures"].all { it["hashMatchesPinned"].asBoolean() },
            "실패 픽스처 해시가 gold 고정값과 다르다")
        assertTrue(probe["failureFixtures"].all { it["verdict"].asText() == "OK" },
            "픽스처 판정: " + probe["failureFixtures"].joinToString {
                it["id"].asText() + "=" + it["verdict"].asText()
            })
    }
}
