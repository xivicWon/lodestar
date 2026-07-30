package com.ontostudio.rdb

import com.ontostudio.security.MaskingEngine
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * #115 — DB 수집 경로의 마스킹 단계 (#88 F7 이 지적한 노출 지점).
 *
 * F7 은 두 지점을 구분해 기록했다: 수집 **산출물**(행 값이 실리지 않음)과 **적재된 저장소**
 * (전 36문장 실행으로 행 데이터가 원문으로 남음). 여기서 고치는 것은 후자이며, 산출물 구조는
 * 그대로여야 한다 — 마스킹이 스키마를 바꾸면 마스킹의 실패다.
 */
class DbIngestMaskingTest {

    private val repoRoot: File by lazy {
        var d = File("").absoluteFile
        while (!File(d, ".git").exists()) d = d.parentFile ?: error("리포 루트를 찾지 못했다")
        d
    }
    private val pinnedSql get() =
        File(repoRoot, "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql").readText()

    /**
     * #88 F7 이 좌표와 함께 고정한 "PII 형태 값 14건" 의 컬럼 — 값은 여기 적지 않고 원본에서 읽어 대조한다.
     *
     * `CUST_NM`(상호)만 클래스가 `ORG_NAME` 이며 **정책상 마스킹 대상이 아니다**: 법인명은 개인정보가
     * 아니고, 가리면 이 샘플이 존재하는 이유(값에서 의미가 드러나는 신호)를 잃는다. 정책 판단이므로
     * 숨기지 않고 증거·보고서에 미마스킹 3건으로 남긴다 — 14 = 마스킹 11 + 정책상 제외 3.
     */
    private val piiShapedColumns = listOf(
        Triple("TB_CUST_MST", "CUST_NM", "ORG_NAME"),
        Triple("TB_CUST_MST", "RPRS_NM", "NAME"),
        Triple("TB_CUST_MST", "TEL_NO", "PHONE"),
        Triple("TB_CUST_MST", "BIZ_NO", "KR_BIZ_NO"),
        Triple("TB_EMP_MST", "EMP_NM", "NAME"),
    )

    /** 마스킹 대상 클래스(= 위 목록에서 정책상 제외를 뺀 것). */
    private val maskedColumns get() = piiShapedColumns.filterNot { it.third == "ORG_NAME" }

    private fun storedValues(conn: java.sql.Connection, table: String, col: String): List<String> {
        val out = mutableListOf<String>()
        conn.createStatement().use { st ->
            st.executeQuery("SELECT $col FROM $table WHERE $col IS NOT NULL").use { rs ->
                while (rs.next()) out.add(rs.getString(1))
            }
        }
        return out
    }

    @Test fun `ingested row data carries no unmasked PII`() {
        SampleLegacyDb().open().use { conn ->
            for ((table, col, cls) in maskedColumns) {
                val values = storedValues(conn, table, col)
                assertTrue(values.isNotEmpty(), "$table.$col 이 비어 있으면 이 검사는 아무것도 보지 않는다")
                for (v in values) {
                    assertTrue(v.isBlank() || v.all { it == '*' },
                        "$table.$col 에 마스킹되지 않은 값이 남았다 (class=$cls)")
                }
            }
        }
    }

    @Test fun `org name is kept by policy and that decision is visible`() {
        // 정책상 제외는 '조용한 미마스킹' 과 구별돼야 한다 — 테스트가 결정을 명시하고, 증거에 건수로 남는다.
        // '별표가 아니다' 로는 부족하다: 부분 변조도 통과한다(리뷰 LOD-062). 원문과 정확히 대조한다.
        val expected = Regex("(?is)INSERT INTO TB_CUST_MST[^;]*;").find(pinnedSql)!!.value
            .let { Regex("\\('([^']*)',\\s*'([^']*)'").findAll(it).map { m -> m.groupValues[2] }.toList() }
        assertEquals(3, expected.size, "원본에서 상호 3건을 찾지 못했다")
        SampleLegacyDb().open().use { conn ->
            assertEquals(expected.sorted(), storedValues(conn, "TB_CUST_MST", "CUST_NM").sorted(),
                "법인명은 개인정보가 아니므로 원문 그대로 남는다 — 정책을 바꾸려면 규칙 스펙에 클래스를 추가한다")
        }
    }

    @Test fun `original plaintext values are not retrievable from the store`() {
        // 원본 스크립트의 PII 형태 리터럴이 저장소에서 그대로 회수되지 않아야 한다.
        val engine = MaskingEngine()
        val plaintexts = Regex("'([^']*)'").findAll(pinnedSql)
            .map { it.groupValues[1] }
            .filter { engine.detect(it).isNotEmpty() }
            .toSet()
        assertTrue(plaintexts.size >= 8, "PII 형태 리터럴을 못 찾았다면 이 검사는 무의미하다: ${plaintexts.size}")
        SampleLegacyDb().open().use { conn ->
            for ((table, col, _) in maskedColumns) {
                val stored = storedValues(conn, table, col).toSet()
                assertTrue(stored.intersect(plaintexts).isEmpty(),
                    "$table.$col 에서 원문이 회수됐다")
            }
        }
    }

    @Test fun `masking does not change the collected schema`() {
        // 이름·건수만 비교하면 특정 컬럼·FK 유실을 놓친다(리뷰 LOD-068). 마스킹 유무로 **구조 전체**를 대조한다.
        fun structure(policy: IngestPolicy): List<TableInfo> =
            SampleLegacyDb().open(policy).use { conn ->
                MetadataService().extract(conn, SampleSource.SOURCE_ID).tables.sortedBy { it.name }
                    .map { t -> t.copy(columns = t.columns.sortedBy { it.name },
                        foreignKeys = t.foreignKeys.sortedBy { it.refTable + it.fkColumns.joinToString() }) }
            }
        val masked = structure(IngestPolicy())
        val unmasked = structure(IngestPolicy(maskRowData = false))
        assertEquals(unmasked, masked, "마스킹이 수집 구조를 바꿨다")
        assertEquals(DdlParser().parse(pinnedSql).tables.map { it.name }.sorted(),
            masked.map { it.name }.sorted())
        assertTrue(masked.sumOf { it.foreignKeys.size } > 0 && masked.all { it.columns.isNotEmpty() })
    }

    @Test fun `masking ledger records counts without plaintext`() {
        val db = SampleLegacyDb()
        db.open().close()
        val summary = db.lastMasking
        assertTrue((summary["maskedTotal"] as Int) >= 11,
            "#88 F7 이 센 PII 형태 값(이름 5 · 전화 3 · 사업자번호 3)은 최소한 가려져야 한다: $summary")
        @Suppress("UNCHECKED_CAST")
        val byClass = summary["byClass"] as Map<String, Int>
        assertEquals(5, byClass["NAME"])
        assertEquals(3, byClass["PHONE"])
        assertEquals(3, byClass["KR_BIZ_NO"])
        assertTrue(!summary.toString().contains("김한빛"))
    }

    @Test fun `minimize policy stores no row data at all`() {
        val db = SampleLegacyDb()
        db.open(IngestPolicy(minimizeRowData = true)).use { conn ->
            // 등록된 컬럼만 보면 다른 테이블에 남은 행을 놓친다(리뷰 LOD-075) — 전 테이블을 센다.
            val tables = MetadataService().extract(conn, SampleSource.SOURCE_ID).tables.map { it.name }
            assertTrue(tables.size >= 27, "수집 테이블이 줄었다: ${tables.size}")
            for (t in tables) {
                conn.createStatement().use { st ->
                    st.executeQuery("SELECT COUNT(*) FROM \"$t\"").use { rs ->
                        rs.next()
                        assertEquals(0, rs.getInt(1), "$t 에 행이 남았다")
                    }
                }
            }
            // 구조는 유지된다 — 최소화는 '수집을 줄이는 것' 이 아니라 '행 데이터를 두지 않는 것' 이다.
            assertEquals(
                DdlParser().parse(pinnedSql).tables.map { it.name }.sorted(),
                MetadataService().extract(conn, SampleSource.SOURCE_ID).tables.map { it.name }.sorted(),
            )
        }
        assertEquals(8, db.lastSkippedDml, "legacy-sample 의 INSERT 8문장을 건너뛰어야 한다")
    }

    @Test fun `db collection path evidence is recorded and does not drift`() {
        val mapper = com.fasterxml.jackson.databind.ObjectMapper()
        val engine = MaskingEngine()
        val out = mapper.createObjectNode()
        out.put("evidenceVersion", "mask-ingest-evidence/v1")
        out.put("track", "db")
        out.put("probe", "SampleLegacyDb.open() (적재 전 마스킹) + MetadataService.extract(conn)")
        out.put("input", "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql")
        out.put("specVersion", com.ontostudio.security.MaskingRules.load().specVersion)

        val db = SampleLegacyDb()
        db.open().use { conn ->
            val summary = db.lastMasking
            out.put("maskedTotal", summary["maskedTotal"] as Int)
            out.put("maskedFields", summary["maskedFields"] as Int)
            @Suppress("UNCHECKED_CAST")
            out.putObject("byClass").also { o ->
                (summary["byClass"] as Map<String, Int>).forEach { (k, v) -> o.put(k, v) }
            }
            @Suppress("UNCHECKED_CAST")
            out.putObject("byRule").also { o ->
                (summary["byRule"] as Map<String, Int>).forEach { (k, v) -> o.put(k, v) }
            }
            // #88 F7 이 좌표와 함께 고정한 컬럼별 관측 — 값은 적지 않는다.
            val cols = out.putArray("piiShapedColumns")
            var unmaskedPii = 0
            var unmaskedByPolicy = 0
            for ((table, col, cls) in piiShapedColumns) {
                val values = storedValues(conn, table, col)
                val notMasked = values.count { it.isNotBlank() && !it.all { c -> c == '*' } }
                val inScope = cls != "ORG_NAME"
                if (inScope) unmaskedPii += notMasked else unmaskedByPolicy += notMasked
                cols.add(mapper.createObjectNode().apply {
                    put("table", table); put("column", col); put("class", cls)
                    put("retrievableValues", values.size)
                    put("unmaskedValues", notMasked)
                    put("maskingClassInScope", inScope)
                    put("locator", "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql#L229-L262")
                })
            }
            out.put("retrievableUnmaskedPiiValues", unmaskedPii)
            out.put("unmaskedByPolicyValues", unmaskedByPolicy)
            out.put("policyExclusionNote", "ORG_NAME(법인명)은 개인정보가 아니므로 클래스를 도입하지 " +
                "않았다 — #88 F7 이 센 14건 = 마스킹 11 + 정책상 제외 3. 정책상 제외를 0건으로 " +
                "보이게 하려고 분모를 고르지 않는다")
            out.put("collectedTables", MetadataService().extract(conn, SampleSource.SOURCE_ID).tables.size)
        }
        // 최소화 정책(#85 기본 원칙)을 켜면 행이 아예 없다 — 정책이 실제로 동작함을 증거로 남긴다.
        val minimizing = SampleLegacyDb()
        minimizing.open(IngestPolicy(minimizeRowData = true)).use { conn ->
            out.putObject("minimizePolicy").apply {
                put("skippedDmlStatements", minimizing.lastSkippedDml)
                put("retrievableValues", piiShapedColumns.sumOf { (t, c, _) -> storedValues(conn, t, c).size })
                put("collectedTables", MetadataService().extract(conn, SampleSource.SOURCE_ID).tables.size)
                put("default", false)
                put("note", "기본값 전환은 #88 baseline 계측기의 관측 대상을 바꾸므로 L0 재측정이 필요하다")
            }
        }
        // DDL 텍스트 경로도 같은 단계를 지난다.
        out.putObject("ddlTextPath").apply {
            val masked = DdlParser().parseMasked(pinnedSql)
            put("maskedTotal", masked.masking["maskedTotal"] as Int)
            put("collectedTables", masked.schema.tables.size)
            put("plaintextLiteralsInScope", Regex("'([^']*)'").findAll(pinnedSql)
                .map { it.groupValues[1] }.count { engine.detect(it).isNotEmpty() })
        }

        val json = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(out) + "\n"
        val generated = File(File(repoRoot, "backend/build/masking"), "ingest-db.json")
        generated.parentFile.mkdirs()
        generated.writeText(json)

        val committed = File(repoRoot,
            "docs/superpowers/specs/bench/masking/runs/run-mask-ingest-001/ingest-db.json")
        val bootstrap = System.getProperty("MASK_EVIDENCE_BOOTSTRAP") == "true"
        assertTrue(committed.exists() || bootstrap,
            "커밋된 적재 경로 증거가 없다: ${committed.path} — 최초 생성이면 " +
                "-DMASK_EVIDENCE_BOOTSTRAP=true 로 실행하고 ${generated.path} 를 커밋한다")
        if (!committed.exists()) return
        assertEquals(committed.readText(), json,
            "커밋된 적재 경로 증거와 이번 실행이 다르다 — 마스킹 동작이 바뀌었으면 증거를 갱신하고 " +
                "보고서를 다시 만든다")
    }

    @Test fun `ddl parse result is unchanged by the masking stage`() {
        // 고정 입력의 수집 결과가 마스킹 전후로 같아야 한다(#88 baseline 이 이 산출물을 비교 기준으로 쓴다).
        // 대조군은 '모든 클래스를 비활성화한 정책' 으로 만든다 — 설정이 실제로 동작을 바꾼다는 증거도 된다.
        val allClasses = com.ontostudio.security.MaskingRules.load().detect.map { it.cls }.toSet()
        val off = com.ontostudio.security.MaskPolicy(disabledClasses = allClasses, lengthPreserving = true)
        val control = com.ontostudio.security.SqlTextMasker(literalPolicy = off, commentPolicy = off)
        assertEquals(pinnedSql, control.mask(pinnedSql), "대조군이 아무것도 가리지 않아야 한다")

        val masked = DdlParser().parseMasked(pinnedSql)
        assertEquals(DdlParser(control).parse(pinnedSql), masked.schema)
        assertTrue((masked.masking["maskedTotal"] as Int) >= 11)
    }
}

/**
 * #115 — 최소화 정책의 DML 판정. `open()` 은 고정 리소스를 읽으므로 분류 자체를 직접 본다.
 * 첫 키워드만 보면 `WITH … INSERT` 형태의 CTE DML 이 행을 쓰면서도 통과한다(PR 리뷰 질문).
 */
class SampleLegacyDbDmlClassificationTest {

    private val db = SampleLegacyDb()

    @Test fun `plain dml is classified as row writing`() {
        for (stmt in listOf(
            "INSERT INTO T VALUES (1)",
            "  update T set a=1",
            "DELETE FROM T",
            "MERGE INTO T USING S ON (T.ID=S.ID) WHEN MATCHED THEN UPDATE SET T.A=S.A",
        )) assertTrue(db.isDml(stmt), stmt)
    }

    @Test fun `cte wrapped dml is classified as row writing`() {
        for (stmt in listOf(
            "WITH src AS (SELECT 1 AS ID) INSERT INTO T SELECT ID FROM src",
            "with src as (select 1) update T set a = 1 from src",
            "WITH d AS (SELECT 1) DELETE FROM T WHERE ID IN (SELECT * FROM d)",
        )) assertTrue(db.isDml(stmt), "CTE 로 감싼 DML 이 최소화 정책을 통과한다: $stmt")
    }

    @Test fun `ddl and read only statements are not dml`() {
        for (stmt in listOf(
            "CREATE TABLE T (ID INT)",
            "CREATE VIEW V AS SELECT 1",
            "SELECT * FROM T",
            "WITH src AS (SELECT 1) SELECT * FROM src",
            "COMMENT ON TABLE T IS 'inserted by hand'",
        )) assertFalse(db.isDml(stmt), "DML 이 아닌데 최소화 정책이 건너뛴다: $stmt")
    }
}
