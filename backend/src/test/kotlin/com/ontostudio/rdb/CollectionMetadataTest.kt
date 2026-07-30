package com.ontostudio.rdb

import java.sql.DriverManager
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/**
 * #113 L0-fix — 수집 식별 메타데이터 계약 v0 (DB 트랙).
 *
 * 계약: docs/superpowers/specs/2026-07-30-m0-l0-collection-metadata-contract.md
 *
 * 여기서 거는 단언은 두 종류다.
 * 1) 계약이 **거절해야 하는 것**을 거절하는가 — 빈 값·플레이스홀더로 게이트를 통과시키는 길을 막는다.
 * 2) **모든 수집 경로**가 다섯 필드를 채우는가 — 경로 하나라도 비면 추적성은 그 경로에서 끊긴다.
 */
class CollectionMetadataTest {

    private fun valid() = CollectionMetadata(
        projectId = "lodestar",
        sourceId = "db:ddl:schema",
        // 비-VCS revision 은 자기 contentHash 에서 파생돼야 한다 — 픽스처도 그 불변식을 지킨다.
        revision = "inline:" + "a".repeat(12),
        contentHash = "sha256:" + "a".repeat(64),
        collectorVersion = "lodestar-rdb-collector@0.1.0",
    )

    // ---- 1) 계약이 거절하는 것 --------------------------------------------------------

    @Test fun `blank fields are rejected`() {
        for (mutate in listOf<(CollectionMetadata) -> CollectionMetadata>(
            { it.copy(projectId = "") },
            { it.copy(sourceId = " ") },
            { it.copy(revision = "") },
            { it.copy(contentHash = "") },
            { it.copy(collectorVersion = "") },
        )) {
            assertFailsWith<IllegalArgumentException> { mutate(valid()) }
        }
    }

    @Test fun `placeholder identities are rejected`() {
        // "모르는 값을 unknown 으로 채워 통과" 는 은폐다 — 계약이 직접 막는다.
        for (bad in listOf("unknown", "UNKNOWN", "n/a", "null", "none", "todo", "-")) {
            assertFailsWith<IllegalArgumentException> { valid().copy(sourceId = bad) }
            assertFailsWith<IllegalArgumentException> { valid().copy(projectId = bad) }
        }
    }

    @Test fun `malformed content hash is rejected`() {
        for (bad in listOf("abc", "sha256:xyz", "sha256:" + "a".repeat(63), "md5:" + "a".repeat(32))) {
            assertFailsWith<IllegalArgumentException> { valid().copy(contentHash = bad) }
        }
    }

    @Test fun `revision must be a commit sha or a declared non-vcs scheme`() {
        // 커밋이 아닌 것을 커밋처럼 보이게 하는 값을 막는다.
        for (bad in listOf("HEAD", "main", "2026-07-30T00:00:00Z", "snapshot:abc", "inline:zz")) {
            assertFailsWith<IllegalArgumentException> { valid().copy(revision = bad) }
        }
        // valid() 의 contentHash 는 "a" * 64 이므로 비-VCS revision 의 접미사도 그것이어야 한다.
        val a12 = "a".repeat(12)
        for (ok in listOf("3c27259", "a".repeat(40)) +
            CollectionMetadata.REVISION_SCHEMES.map { "$it:$a12" }) {
            assertEquals(ok, valid().copy(revision = ok).revision)
        }
    }

    @Test fun `non-vcs revision must be derived from this artifact's content hash`() {
        // 형식만 보면 다른 스냅샷의 해시를 붙여도 통과한다 — 그러면 revision 이 신원을 가리키지 않는다.
        for (scheme in CollectionMetadata.REVISION_SCHEMES) {
            assertFailsWith<IllegalArgumentException> {
                valid().copy(revision = "$scheme:0123456789ab")
            }
        }
        // 커밋 sha 는 내용 파생이 아니다 — 그 자체가 외부 좌표이므로 이 불변식의 대상이 아니다.
        assertEquals("3c27259", valid().copy(revision = "3c27259").revision)
    }

    @Test fun `collector version must carry name and semver`() {
        for (bad in listOf("lodestar-codegraph v1", "0.1.0", "collector@1", "collector@1.0")) {
            assertFailsWith<IllegalArgumentException> { valid().copy(collectorVersion = bad) }
        }
        assertEquals("c@1.2.3+3c27259", valid().copy(collectorVersion = "c@1.2.3+3c27259").collectorVersion)
    }

    @Test fun `collector version reports name and semver of the db collector`() {
        assertTrue(DbCollector.version().startsWith("lodestar-rdb-collector@"),
            "수집기 신원은 산출물만 보고 특정할 수 있어야 한다: ${DbCollector.version()}")
        // 형식 검증은 계약이 한다 — 여기서 만들어 통과하는지 본다.
        valid().copy(collectorVersion = DbCollector.version())
    }

    @Test fun `build revision falls through to the next candidate when one is unusable`() {
        // `?:` 로 이으면 비어 있거나 형식에 맞지 않는 속성 하나가 유효한 환경변수를 가려,
        // 산출물에서 커밋 식별자가 통째로 사라진다.
        val sha = "3c27259"
        for (unusable in listOf(null, "", "   ", "HEAD", "not-a-sha", "zzzzzzz")) {
            assertEquals("lodestar-rdb-collector@${DbCollector.VERSION}+$sha",
                DbCollector.version(unusable, sha),
                "쓸 수 없는 후보 '$unusable' 가 유효한 다음 후보를 가렸다")
        }
        // 앞 후보가 유효하면 그것을 쓴다(우선순위는 유지된다).
        assertEquals("lodestar-rdb-collector@${DbCollector.VERSION}+abc1234",
            DbCollector.version("ABC1234", sha))
        // 유효한 후보가 하나도 없으면 커밋 없이 이름·semver 만 남는다 — 지어내지 않는다.
        assertEquals("lodestar-rdb-collector@${DbCollector.VERSION}", DbCollector.version(null, ""))
    }

    // ---- 2) 모든 수집 경로가 다섯 필드를 채우는가 ----------------------------------------

    private fun assertComplete(m: CollectionMetadata) {
        // 계약이 init 에서 이미 검증하지만, 다섯 필드가 **다 있는지**는 여기서 필드 이름으로 센다.
        val values = mapOf(
            "projectId" to m.projectId, "sourceId" to m.sourceId, "revision" to m.revision,
            "contentHash" to m.contentHash, "collectorVersion" to m.collectorVersion)
        assertEquals(CollectionMetadata.REQUIRED_FIELDS.toSet(), values.keys)
        assertTrue(values.values.none { it.isBlank() }, "빈 필드가 있다: $values")
    }

    @Test fun `ddl path records identity derived from the input bytes`() {
        val sql = "CREATE TABLE t (id INTEGER PRIMARY KEY)"
        val m = DdlSource(sql, "sales", DdlParser()).extract().metadata
        assertComplete(m)
        assertEquals("lodestar", m.projectId)
        assertEquals("db:ddl:sales", m.sourceId)
        assertEquals(CollectionMetadata.sha256(sql.toByteArray()), m.contentHash)
        assertEquals("inline:" + m.contentHash.removePrefix("sha256:").take(12), m.revision)
        assertEquals(DbCollector.version(), m.collectorVersion)
    }

    @Test fun `ddl content hash changes when the input changes`() {
        val a = DdlSource("CREATE TABLE t (id INTEGER)", "s", DdlParser()).extract().metadata
        val b = DdlSource("CREATE TABLE t (id BIGINT)", "s", DdlParser()).extract().metadata
        assertNotEquals(a.contentHash, b.contentHash)
        assertNotEquals(a.revision, b.revision)
    }

    @Test fun `sample path records the gold pinned source id`() {
        val m = SampleSource(SampleLegacyDb(), MetadataService()).extract().metadata
        assertComplete(m)
        // gold manifest 가 고정한 id 와 같아야 증거가 이어진다(I2 §6.1).
        assertEquals(SampleSource.SOURCE_ID, m.sourceId)
        assertTrue(m.revision.startsWith("bundle:"), "번들 리소스는 커밋 sha 를 지어내지 않는다: ${m.revision}")
        // 접두어만 보면 revision 이 고정값으로 굳거나 다른 스냅샷에서 계산돼도 통과한다.
        assertEquals("bundle:" + m.contentHash.removePrefix("sha256:").take(12), m.revision)
        assertEquals(
            CollectionMetadata.sha256(
                SchemaCanonical.bytes(SampleSource(SampleLegacyDb(), MetadataService()).extract().tables)),
            m.contentHash,
            "번들 경로의 contentHash 가 수집한 카탈로그의 정규화 스냅샷에서 나오지 않았다")
    }

    @Test fun `bundled sample identity matches the pinned gold manifest`() {
        // 번들 샘플을 읽는 곳(SampleSource · SemanticEnricher)이 같은 상수를 쓰고, 그 상수가
        // gold 가 고정한 sourceId 와 같아야 증거가 이어진다(I2 §6.1). 문자열을 각자 적으면
        // 한쪽만 바뀌어도 같은 소스가 두 신원으로 갈리고, 그건 호출부에서 보이지 않는다.
        var dir = java.io.File("").absoluteFile
        while (!java.io.File(dir, ".git").exists()) dir = dir.parentFile ?: error("리포 루트를 찾지 못했다")
        val manifest = com.fasterxml.jackson.databind.ObjectMapper()
            .readTree(java.io.File(dir, "docs/superpowers/specs/gold/manifest.json"))
        val pinned = manifest["pinnedSources"].map { it["sourceId"].asText() }
        assertTrue(SampleSource.SOURCE_ID in pinned,
            "gold 가 고정한 sourceId 중에 없다: ${SampleSource.SOURCE_ID} (gold=$pinned)")
        assertEquals("bundle", SampleSource.REVISION_SCHEME)
    }

    @Test fun `canonical bytes are injective against delimiter injection`() {
        // 이스케이프가 없으면 이름 안의 탭·개행이 필드·레코드 경계를 밀어, 구조가 다른 스키마가
        // 같은 바이트가 된다. 식별자는 DDL 요청 본문에서 그대로 올 수 있다(/api/rdb/import/ddl).
        fun h(tables: List<TableInfo>) = CollectionMetadata.sha256(SchemaCanonical.bytes(tables))

        val real = listOf(TableInfo("t", listOf(
            ColumnInfo("x", "int", true), ColumnInfo("evil", "varchar", false)), emptyList(), emptyList()))
        val forged = listOf(TableInfo("t", listOf(
            ColumnInfo("x\tint\ttrue\nC\tevil", "varchar", false)), emptyList(), emptyList()))
        assertNotEquals(h(real), h(forged), "컬럼 이름에 넣은 구분자가 다른 스키마를 같은 신원으로 만든다")

        // 리스트 필드도 같다 — ["a,b"] 와 ["a","b"] 는 다른 키다.
        val base = TableInfo("t", listOf(ColumnInfo("c", "int", true)), emptyList(), emptyList())
        assertNotEquals(
            h(listOf(base.copy(primaryKey = listOf("a,b")))),
            h(listOf(base.copy(primaryKey = listOf("a", "b")))),
            "복합키 ['a','b'] 와 단일키 ['a,b'] 가 같은 신원이다")
        assertNotEquals(
            h(listOf(base.copy(foreignKeys = listOf(ForeignKeyInfo(listOf("a,b"), "r", listOf("p")))))),
            h(listOf(base.copy(foreignKeys = listOf(ForeignKeyInfo(listOf("a", "b"), "r", listOf("p")))))),
            "FK 컬럼 목록에서 같은 충돌이 난다")

        // 테이블 이름으로 레코드를 위조하지 못한다.
        assertNotEquals(
            h(listOf(TableInfo("x\nC\tfake\tint\ttrue", emptyList(), emptyList(), emptyList()))),
            h(listOf(TableInfo("x", listOf(ColumnInfo("fake", "int", true)), emptyList(), emptyList()))),
            "테이블 이름에 넣은 개행이 컬럼 레코드를 위조한다")
    }

    @Test fun `fk ordering does not depend on input order when names contain the sort separator`() {
        // 정렬 키를 공백으로 이으면, 이름에 든 공백이 키 경계를 밀어 **서로 다른 FK 가 같은 키**가 된다.
        // 같은 키의 정렬은 입력 순서를 그대로 두므로(stable), JDBC 반환 순서에 따라 해시가 갈린다.
        fun h(fks: List<ForeignKeyInfo>) = CollectionMetadata.sha256(
            SchemaCanonical.bytes(listOf(
                TableInfo("t", listOf(ColumnInfo("c", "int", true)), emptyList(), fks))))

        val a = ForeignKeyInfo(listOf("a b"), "r", listOf("c"))   // 컬럼 이름에 공백
        val b = ForeignKeyInfo(listOf("b"), "r a", listOf("c"))   // 테이블 이름에 공백
        assertEquals(h(listOf(a, b)), h(listOf(b, a)),
            "이름에 공백이 있으면 FK 정렬이 입력 순서에 따라 달라진다 — 같은 카탈로그가 다른 신원을 낸다")

        // 두 FK 는 실제로 다르므로, 집합이 다르면 신원도 달라야 한다.
        assertNotEquals(h(listOf(a)), h(listOf(b)))
    }

    @Test fun `canonical bytes follow column order and fk target columns`() {
        // 정렬로 뭉개면 카탈로그가 바뀌었는데 contentHash 가 같아진다.
        val cols = listOf(ColumnInfo("a", "integer", false), ColumnInfo("b", "integer", true))
        val base = TableInfo("t", cols, listOf("a"), emptyList())
        assertNotEquals(
            CollectionMetadata.sha256(SchemaCanonical.bytes(listOf(base))),
            CollectionMetadata.sha256(SchemaCanonical.bytes(listOf(base.copy(columns = cols.reversed())))),
            "컬럼 순서가 바뀌었는데 신원이 같다")

        val fks = listOf(
            ForeignKeyInfo(listOf("x"), "ref", listOf("p")),
            ForeignKeyInfo(listOf("x"), "ref", listOf("q")),
        )
        assertEquals(
            CollectionMetadata.sha256(SchemaCanonical.bytes(listOf(base.copy(foreignKeys = fks)))),
            CollectionMetadata.sha256(SchemaCanonical.bytes(listOf(base.copy(foreignKeys = fks.reversed())))),
            "같은 FK 집합의 입력 순서가 신원을 흔든다")
    }

    @Test fun `live jdbc source id distinguishes different servers`() {
        // 같은 이름의 DB 가 운영·스테이징에 각각 있으면, host·port 가 없는 sourceId 는
        // 두 서버를 같은 소스로 기록한다 — 그 지점에서 추적성이 끊긴다.
        val prod = ConnectionInfo("db.prod", 5432, "app", "u", "p")
        val stage = ConnectionInfo("db.stage", 5432, "app", "u", "p")
        assertNotEquals(LiveJdbcSource.sourceId(prod), LiveJdbcSource.sourceId(stage))
        assertNotEquals(LiveJdbcSource.sourceId(prod), LiveJdbcSource.sourceId(prod.copy(port = 5433)))
        assertEquals("db:jdbc:postgresql://db.prod:5432/app", LiveJdbcSource.sourceId(prod))
        // 자격증명은 신원이 아니다 — 산출물에 실리면 안 된다.
        val withSecret = prod.copy(user = "svc_account", password = "s3cr3t")
        assertFalse(LiveJdbcSource.sourceId(withSecret).contains("s3cr3t"))
        assertFalse(LiveJdbcSource.sourceId(withSecret).contains("svc_account"))
    }

    @Test fun `live jdbc path records vendor and database in the source id`() {
        val url = "jdbc:h2:mem:meta_prov;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1"
        DriverManager.getConnection(url, "sa", "").use { conn ->
            conn.createStatement().use { st ->
                st.execute("DROP ALL OBJECTS")
                st.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(100))")
            }
            val m = MetadataService().extract(conn, sourceId = "db:jdbc:h2/meta_prov").metadata
            assertComplete(m)
            assertEquals("db:jdbc:h2/meta_prov", m.sourceId)
            assertTrue(m.revision.startsWith("live:"), "라이브 DB 는 VCS 신원이 없다: ${m.revision}")
            assertEquals("live:" + m.contentHash.removePrefix("sha256:").take(12), m.revision)
        }
    }

    @Test fun `live content hash is deterministic across runs and follows the catalog`() {
        val url = "jdbc:h2:mem:meta_det;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1"
        DriverManager.getConnection(url, "sa", "").use { conn ->
            conn.createStatement().use { st ->
                st.execute("DROP ALL OBJECTS")
                st.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY)")
            }
            // 시각이 아니라 내용에서 나오므로 3회 실행이 같아야 한다(H1 결정성을 오염시키지 않는다).
            val hashes = (1..3).map { MetadataService().extract(conn, "db:test:live").metadata.contentHash }
            assertEquals(1, hashes.toSet().size, "같은 카탈로그의 3회 수집이 다른 신원을 냈다: $hashes")

            conn.createStatement().use { st -> st.execute("ALTER TABLE customers ADD COLUMN note VARCHAR(10)") }
            assertNotEquals(hashes[0], MetadataService().extract(conn, "db:test:live").metadata.contentHash,
                "카탈로그가 바뀌었는데 contentHash 가 같다")
        }
    }

    @Test fun `in-memory schemas derive identity from their own content`() {
        val tables = listOf(TableInfo("t", listOf(ColumnInfo("id", "integer", false)), listOf("id"), emptyList()))
        val m = SchemaModel.of(tables, sourceId = "db:test:memory").metadata
        assertComplete(m)
        assertEquals(CollectionMetadata.sha256(SchemaCanonical.bytes(tables)), m.contentHash)
    }
}
