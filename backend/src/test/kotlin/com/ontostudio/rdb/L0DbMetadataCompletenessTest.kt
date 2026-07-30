package com.ontostudio.rdb

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.node.ObjectNode
import java.io.File
import java.sql.DriverManager
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * #113 L0-fix — `gate-l0-metadata-completeness` 재측정 (DB 트랙).
 *
 * #88 프로브와 **같은 산식**으로 다시 잰다: 산출물 타입에서 필수 5필드가 조회되는가.
 * 다른 점은 두 가지다 —
 *  1) 리플렉션이 산출물 타입 **그래프**(중첩 [CollectionMetadata] 포함)를 본다. #88 의 프로브는
 *     평면 4타입만 봤고, 그 시점의 산출물에는 중첩 신원 타입 자체가 없었다.
 *  2) 타입에 자리가 있는 것으로 끝내지 않고 **실제 수집 경로 3종의 산출물 값**을 함께 센다.
 *     자리만 있고 비어 있으면 완전성은 여전히 0 이다.
 *
 * #88 의 baseline 산출물(`run-l0-db-3c27259-001`)은 손대지 않는다 — 그것은 revision 3c27259
 * 시점의 증거다(I3 §5.5). 이 측정은 별도 좌표에 남는다.
 *
 * 계약: docs/superpowers/specs/2026-07-30-m0-l0-collection-metadata-contract.md
 */
class L0DbMetadataCompletenessTest {

    private val mapper = ObjectMapper()

    private val repoRoot: File by lazy {
        RepoRoot.path
    }
    private val committed get() =
        File(repoRoot, "docs/superpowers/specs/bench/l0/metadata/completeness-db.json")

    /** 산출물 타입 그래프의 선언 멤버 이름 — #88 프로브의 리플렉션을 중첩까지 넓힌 것. */
    private val artifactTypes = listOf(
        SchemaModel::class, TableInfo::class, ColumnInfo::class, ForeignKeyInfo::class,
        CollectionMetadata::class,
    )

    private fun fieldsOf(m: CollectionMetadata) = mapOf(
        "projectId" to m.projectId, "sourceId" to m.sourceId, "revision" to m.revision,
        "contentHash" to m.contentHash, "collectorVersion" to m.collectorVersion)

    private fun pathNode(label: String, m: CollectionMetadata): ObjectNode {
        val values = fieldsOf(m)
        val present = CollectionMetadata.REQUIRED_FIELDS.filter { values[it]?.isNotBlank() == true }
        return mapper.createObjectNode().apply {
            put("path", label)
            put("sourceId", m.sourceId)
            putArray("present").also { a -> present.forEach { a.add(it) } }
            putArray("absent").also { a ->
                CollectionMetadata.REQUIRED_FIELDS.filterNot { it in present }.forEach { a.add(it) }
            }
            put("rate", present.size.toDouble() / CollectionMetadata.REQUIRED_FIELDS.size)
        }
    }

    /**
     * **운영 진입점([LiveJdbcSource].extract)을 그대로 돌린다.** 여기서 MetadataService 에 sourceId 를
     * 직접 주입하면, LiveJdbcSource 의 신원 생성이나 전달이 깨져도 게이트가 통과한다 — 재지 않은
     * 경로를 잰 것으로 세게 된다. 커넥션 공급만 H2 로 갈아끼운다.
     */
    private fun liveMetadata(): CollectionMetadata {
        val url = "jdbc:h2:mem:meta_completeness;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1"
        val info = ConnectionInfo("db.example", 5432, "meta_completeness", "sa", "")
        val connector = object : DbConnector() {
            override fun open(info: ConnectionInfo) =
                DriverManager.getConnection(url, "sa", "").also { c ->
                    c.createStatement().use { st ->
                        st.execute("DROP ALL OBJECTS")
                        st.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(100))")
                    }
                }
        }
        return LiveJdbcSource(info, connector, MetadataService()).extract().metadata
    }

    @Test fun `db track records all five identifying fields on every collection path`() {
        val required = CollectionMetadata.REQUIRED_FIELDS

        // 1) 타입 그래프 — 산출물에 자리가 있는가
        val memberNames = artifactTypes.flatMap { k -> k.members.map { it.name } }.toSet()
        val typePresent = required.filter { f -> memberNames.any { it.equals(f, ignoreCase = true) } }

        // 2) 실제 수집 경로 3종 — 자리가 채워지는가
        val ddl = DdlSource("CREATE TABLE t (id INTEGER PRIMARY KEY)", "sales", DdlParser()).extract().metadata
        val sample = SampleSource(SampleLegacyDb(), MetadataService()).extract().metadata
        val live = liveMetadata()
        val paths = listOf("ddl" to ddl, "sample" to sample, "live-jdbc" to live)
        val minPathPresent = paths.minOf { (_, m) -> fieldsOf(m).count { it.value.isNotBlank() } }

        val measurement = mapper.createObjectNode().apply {
            put("measurementVersion", "l0-metadata-completeness/v1")
            put("issue", 113)
            put("gate", "gate-l0-metadata-completeness")
            put("track", "db")
            put("contract", "docs/superpowers/specs/2026-07-30-m0-l0-collection-metadata-contract.md")
            put("baseline", "docs/superpowers/specs/bench/l0/runs/run-l0-db-3c27259-001 (0/5, 손대지 않는다)")
            putArray("required").also { a -> required.forEach { a.add(it) } }
            putObject("typeGraph").apply {
                put("probe", "kotlin-reflect — 산출물 타입 그래프(중첩 CollectionMetadata 포함)의 선언 멤버 이름")
                putArray("types").also { a -> artifactTypes.forEach { t -> a.add(t.simpleName) } }
                putArray("present").also { a -> typePresent.forEach { a.add(it) } }
                putArray("absent").also { a -> required.filterNot { it in typePresent }.forEach { a.add(it) } }
                put("rate", typePresent.size.toDouble() / required.size)
            }
            putObject("collectionPaths").apply {
                put("probe", "각 SchemaSource 를 실제로 돌려 산출물의 metadata 값을 센다")
                putArray("paths").also { a -> paths.forEach { (l, m) -> a.add(pathNode(l, m)) } }
            }
            putObject("identity").apply {
                // 계약이 고정하는 신원이므로 표류 검사 대상이다 — volatile 에 두면 몰래 바뀌어도 못 잡는다.
                put("projectId", CollectionMetadata.DEFAULT_PROJECT_ID)
                put("collectorVersion", DbCollector.version())
            }
            putObject("completeness").apply {
                // 타입에 자리가 있는가(typeGraph)와 그 자리가 실제로 채워지는가(collectionPaths)는
                // 다른 질문이다. 게이트 수치는 **둘 중 낮은 쪽**이어야 한다 — 자리만 세면
                // 값이 비어도 5/5 로 보인다.
                put("present", minOf(typePresent.size, minPathPresent))
                put("required", required.size)
                put("rate", minOf(typePresent.size, minPathPresent).toDouble() / required.size)
                put("basis", "min(타입 그래프에 자리가 있는 필드 수, 수집 경로별로 채워진 필드 수의 최소값)")
            }
            putObject("volatile").apply {
                put("note", "입력 내용에 따라 달라지는 값만 둔다 — 표류 검사 대상이 아니다. " +
                    "projectId·collectorVersion 은 계약이 고정하는 신원이므로 identity 블록에 있다")
                put("sampleContentHash", sample.contentHash)
                put("sampleRevision", sample.revision)
                put("ddlContentHash", ddl.contentHash)
            }
        }

        val json = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(measurement) + "\n"
        val outFile = File(File(repoRoot, "backend/build/l0"), "completeness-db.json")
        outFile.parentFile.mkdirs()
        outFile.writeText(json)

        // ---- 게이트 재측정 결과 ----------------------------------------------------------
        assertEquals(required, typePresent, "산출물 타입에 자리가 없는 필드가 있다")
        for ((label, m) in paths) {
            assertEquals(required.size, fieldsOf(m).count { it.value.isNotBlank() },
                "$label 경로의 산출물에 빈 식별 필드가 있다: ${fieldsOf(m)}")
        }
        assertEquals(1.0, measurement["completeness"]["rate"].asDouble(),
            "gate-l0-metadata-completeness 는 완전성 100% 를 요구한다")

        // ---- 커밋된 측정 결과와의 표류 검사 (volatile 제외) ----------------------------------
        // 부트스트랩은 **최초 생성용**이다. 이미 있는 증거를 조용히 갈아치울 수 있으면 그 스위치는
        // "초록으로 만드는 버튼" 이 되고, 그 습관이 결국 아무도 보지 않는 baseline 을 만든다.
        val bootstrap = System.getProperty("L0_METADATA_BOOTSTRAP") == "true"
        val force = System.getProperty("L0_METADATA_FORCE") == "true"
        assertTrue(!(bootstrap && committed.exists() && !force),
            "이미 재측정 결과가 있다: ${committed.path} — 부트스트랩은 최초 생성용이다. " +
                "계약이 바뀌어 기준을 갱신하려면 -DL0_METADATA_FORCE=true 로 명시하고 git diff 로 확인한다")
        assertTrue(committed.exists() || bootstrap,
            "커밋된 재측정 결과가 없다: ${committed.path} — 최초 생성이면 " +
                "-DL0_METADATA_BOOTSTRAP=true 로 실행하고 ${outFile.path} 를 커밋한다")
        // 부트스트랩은 기준을 **새로 쓰는** 실행이므로 표류 검사의 대상이 아니다. 그 대신 위의
        // 가드가 이미 있는 기준을 말없이 갈아치우는 것을 막고, 무엇이 바뀌었는지는 git diff 에 남는다.
        if (committed.exists() && !bootstrap) {
            val a = mapper.readTree(committed.readText()) as ObjectNode
            val b = mapper.readTree(json) as ObjectNode
            a.remove("volatile"); b.remove("volatile")
            assertEquals(a, b, "커밋된 재측정 결과와 이번 실행이 다르다. 생성물: ${outFile.path}")
        }
    }
}
