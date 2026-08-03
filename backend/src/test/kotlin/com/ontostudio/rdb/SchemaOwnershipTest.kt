package com.ontostudio.rdb

import java.sql.DriverManager
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * #126 L0-fix — 수집 모델이 테이블의 **소속(schema)** 을 담는다.
 *
 * #113 리뷰의 지적: 라이브 스냅샷의 `contentHash` 는 `SchemaCanonical.bytes` 에서 나오는데
 * 그 스냅샷에 소속이 없어 `sales.orders` 와 `archive.orders` 가 한 신원으로 접혔고,
 * 테이블이 스키마 사이를 옮겨도 `contentHash` 가 그대로였다.
 *
 * **catalog 는 모델에 넣지 않는다.** 수집은 `conn.catalog` 하나로 한정되므로(MetadataService)
 * 카탈로그는 한 스냅샷 안에서 상수이고, 그 신원은 이미 `sourceId`(vendor·host·port·database)가
 * 담는다. 넣으면 번들 샘플의 H2 카탈로그(`LEGACY_<nanoTime>`)가 해시에 들어가 신원이 매 실행
 * 달라진다 — 소속을 담으려다 결정성을 잃는다.
 */
class SchemaOwnershipTest {

    private fun h(tables: List<TableInfo>) = CollectionMetadata.sha256(SchemaCanonical.bytes(tables))

    private fun t(name: String, schema: String?, vararg fks: ForeignKeyInfo) = TableInfo(
        name, listOf(ColumnInfo("id", "integer", false)), listOf("id"), fks.toList(), schema = schema)

    // ---- 신원 (SchemaCanonical) -------------------------------------------------------------

    @Test fun `동명 테이블은 스키마가 다르면 다른 신원이다`() {
        assertNotEquals(
            h(listOf(t("orders", "sales"))),
            h(listOf(t("orders", "archive"))),
            "sales.orders 와 archive.orders 가 같은 신원으로 접힌다")
    }

    @Test fun `한 스냅샷 안의 동명 테이블 둘이 서로를 지우지 않는다`() {
        // 소속이 없으면 두 레코드가 같은 바이트가 되어, 카탈로그가 실제로 두 개인 사실이 사라진다.
        assertNotEquals(
            h(listOf(t("orders", "sales"), t("orders", "archive"))),
            h(listOf(t("orders", "sales"), t("orders", "sales"))))
    }

    @Test fun `테이블이 스키마 사이를 옮기면 contentHash 가 바뀐다`() {
        val before = listOf(t("orders", "sales"), t("customers", "sales"))
        val after = listOf(t("orders", "archive"), t("customers", "sales"))
        assertNotEquals(h(before), h(after), "카탈로그가 달라졌는데 스냅샷 신원이 그대로다")
    }

    @Test fun `소속을 모르는 것과 빈 이름의 스키마는 다른 신원이다`() {
        // null(소속 정보 없음)을 빈 문자열로 접으면 '모른다' 와 '이름이 빈 스키마' 가 구별되지 않는다.
        assertNotEquals(h(listOf(t("orders", null))), h(listOf(t("orders", ""))))
    }

    @Test fun `소속 필드를 이름에 심어 위조하지 못한다`() {
        // T 레코드는 `T\t<이름>[\t<소속>]` 이다. 그래서 **이름에 탭을 심은 무소속 테이블**과
        // **소속을 가진 테이블**이 진짜 충돌 쌍이다 — 이스케이프가 없으면 둘의 바이트가 같아진다.
        //
        // 위조 입력과 비교 대상의 **레코드 구조가 같아야** 이 테스트에 검증력이 있다. 테이블 수가
        // 다른 쌍을 비교하면 블록 개수만으로 바이트가 갈려, 이스케이프를 지워도 통과한다(리뷰 LOD-174).
        val withSchema = t("orders", "s")
        val tabInName = TableInfo("orders\ts", withSchema.columns, withSchema.primaryKey, emptyList())
        assertEquals(withSchema.columns, tabInName.columns, "두 입력의 나머지 레코드는 같아야 한다")
        assertNotEquals(h(listOf(withSchema)), h(listOf(tabInName)),
            "이름에 심은 탭이 소속 필드로 읽혀 두 스키마가 같은 신원이 된다")
    }

    @Test fun `소속의 구분자는 리터럴로 이스케이프된다`() {
        // 위 테스트는 '두 입력이 갈린다' 만 본다. 무엇으로 갈렸는지는 바이트가 말해야 한다 —
        // 그래야 esc() 가 치환을 멈추는 회귀를 이 자리에서 바로 읽을 수 있다.
        val bytes = SchemaCanonical.bytes(listOf(TableInfo(
            "orders", listOf(ColumnInfo("id", "int", false)), emptyList(), emptyList(),
            schema = "a\tb\nc"))).decodeToString()
        assertEquals("T\torders\ta\\tb\\nc\nC\tid\tint\tfalse\nP\t0:\n", bytes)
    }

    @Test fun `FK 의 대상 스키마도 신원의 일부다`() {
        val toSales = ForeignKeyInfo(listOf("oid"), "orders", listOf("id"), refSchema = "sales")
        val toArchive = ForeignKeyInfo(listOf("oid"), "orders", listOf("id"), refSchema = "archive")
        assertNotEquals(h(listOf(t("lines", "sales", toSales))), h(listOf(t("lines", "sales", toArchive))))
    }

    @Test fun `FK 대상 소속도 모르는 것과 빈 이름을 구분한다`() {
        // 테이블 소속과 같은 규칙이 FK 쪽에도 서야 한다 — 한쪽만 구분하면 같은 이유의 충돌이
        // 반대쪽에 남는다.
        fun withRef(rs: String?) = h(listOf(t("lines", "sales",
            ForeignKeyInfo(listOf("oid"), "orders", listOf("id"), refSchema = rs))))
        assertNotEquals(withRef(null), withRef(""))
    }

    @Test fun `정렬은 스키마까지 보되 입력 순서에는 흔들리지 않는다`() {
        val a = t("orders", "sales")
        val b = t("orders", "archive")
        assertEquals(h(listOf(a, b)), h(listOf(b, a)), "같은 카탈로그의 입력 순서가 신원을 흔든다")
    }

    @Test fun `소속을 모르는 스키마의 정규화 바이트는 예전 그대로다`() {
        // 비한정 DDL 처럼 소속을 모르는 입력의 신원까지 흔들면, 이 이슈와 무관한 입력의 revision 이
        // 전부 갈린다. 소속이 없을 때의 바이트를 그대로 고정한다.
        val tables = listOf(TableInfo(
            "t", listOf(ColumnInfo("c", "int", true)), emptyList(),
            listOf(ForeignKeyInfo(listOf("x"), "r", listOf("p")))))
        assertEquals(
            "T\tt\nC\tc\tint\ttrue\nP\t0:\nF\t1:x\tr\t1:p\n",
            SchemaCanonical.bytes(tables).decodeToString())
    }

    // ---- 수집 경로 -----------------------------------------------------------------------

    @Test fun `JDBC 수집이 테이블의 스키마 소속을 담는다`() {
        val url = "jdbc:h2:mem:ownership_jdbc;DB_CLOSE_DELAY=-1"
        DriverManager.getConnection(url, "sa", "").use { conn ->
            conn.createStatement().use { st ->
                st.execute("DROP ALL OBJECTS")
                st.execute("CREATE SCHEMA SALES")
                st.execute("CREATE SCHEMA ARCHIVE")
                st.execute("CREATE TABLE SALES.ORDERS (ID INTEGER PRIMARY KEY)")
                st.execute("CREATE TABLE ARCHIVE.ORDERS (ID INTEGER PRIMARY KEY)")
                st.execute("CREATE TABLE SALES.ORDER_LINES (ID INTEGER PRIMARY KEY, OID INTEGER, " +
                    "CONSTRAINT FK_O FOREIGN KEY (OID) REFERENCES SALES.ORDERS(ID))")
            }
            val schema = MetadataService().extract(conn, "db:test:ownership")
            assertEquals(setOf("SALES.ORDERS", "ARCHIVE.ORDERS", "SALES.ORDER_LINES"),
                schema.tables.map { it.qualifiedName }.toSet())
            val lines = schema.tables.first { it.name == "ORDER_LINES" }
            assertEquals("SALES", lines.schema)
            assertEquals("SALES", lines.foreignKeys.single().refSchema,
                "FK 대상의 소속을 담지 않으면 동명 테이블 중 어느 쪽을 가리키는지 알 수 없다")
        }
    }

    @Test fun `드라이버가 빈 소속을 주면 모름으로 접는다`() {
        // JDBC 명세는 해당 없을 때 TABLE_SCHEM 을 null 로 주라고 하지만 **빈 문자열을 주는 드라이버가
        // 있다.** 그대로 담으면 같은 카탈로그가 드라이버에 따라 다른 신원을 갖고(null vs ""),
        // IRI 는 slug 의 빈 문자열 대체(`x`)로 접혀 `x` 라는 이름의 스키마와 충돌한다(리뷰 Q3).
        // 빈 이름은 이름이 아니므로 '모름' 으로 접는다.
        val blank = t("orders", MetadataService.ownerOf(""))
        assertNull(blank.schema)
        assertNull(MetadataService.ownerOf("   "))
        assertNull(MetadataService.ownerOf(null))
        assertEquals("sales", MetadataService.ownerOf("sales"))
        // 정규화가 소속을 뭉개지는 않는다.
        assertEquals(h(listOf(t("orders", null))), h(listOf(blank)))
    }

    @Test fun `DDL 의 스키마 한정 이름이 소속으로 들어간다`() {
        val schema = DdlParser().parse(
            """
            CREATE TABLE sales.orders (id INTEGER PRIMARY KEY);
            CREATE TABLE archive.orders (id INTEGER PRIMARY KEY);
            CREATE TABLE sales.order_lines (
              id INTEGER PRIMARY KEY,
              oid INTEGER REFERENCES sales.orders(id));
            """.trimIndent())
        assertEquals(setOf("sales.orders", "archive.orders", "sales.order_lines"),
            schema.tables.map { it.qualifiedName }.toSet())
        val lines = schema.tables.first { it.name == "order_lines" }
        assertEquals("sales", lines.schema)
        assertEquals("sales", lines.foreignKeys.single().refSchema,
            "DDL 이 적어 준 대상 스키마를 버리면 동명 테이블 사이에서 대상을 고를 수 없다")
    }

    @Test fun `DDL 의 테이블-레벨 FK 제약도 대상 스키마를 담는다`() {
        val schema = DdlParser().parse(
            """
            CREATE TABLE sales.order_lines (
              id INTEGER PRIMARY KEY,
              oid INTEGER,
              CONSTRAINT fk_o FOREIGN KEY (oid) REFERENCES archive.orders(id));
            """.trimIndent())
        assertEquals("archive", schema.tables.single().foreignKeys.single().refSchema)
        assertEquals("orders", schema.tables.single().foreignKeys.single().refTable)
    }

    @Test fun `인용부호 안의 점을 두 FK 표기가 같게 읽는다`() {
        // 같은 대상을 인라인 REFERENCES 로 적든 테이블-레벨 제약으로 적든 소속은 하나여야 한다.
        // 갈리면 같은 스키마가 두 값으로 기록되어 신원(contentHash)이 표기 방식에 따라 달라지고,
        // 잘린 소속은 대상 해석에도 실패한다.
        fun fkOf(ddl: String) = DdlParser().parse(ddl).tables.single().foreignKeys.single()

        val inline = fkOf("""CREATE TABLE t (id INTEGER PRIMARY KEY, cid INTEGER
              REFERENCES "my.schema"."customers"(id))""")
        val tableLevel = fkOf("""CREATE TABLE t (id INTEGER PRIMARY KEY, cid INTEGER,
              CONSTRAINT fk FOREIGN KEY (cid) REFERENCES "my.schema"."customers"(id))""")

        assertEquals("my.schema", tableLevel.refSchema)
        assertEquals(tableLevel.refSchema, inline.refSchema, "같은 대상을 두 표기가 다르게 읽는다")
        assertEquals(tableLevel.refTable, inline.refTable)
    }

    @Test fun `소속 없는 인용 이름의 점은 이름의 일부다`() {
        // `REFERENCES "a.b"(id)` 의 대상은 스키마 a 의 테이블 b 가 아니라 이름이 `a.b` 인 테이블이다.
        val fk = DdlParser().parse("""CREATE TABLE t (id INTEGER PRIMARY KEY, cid INTEGER REFERENCES "a.b"(id))""")
            .tables.single().foreignKeys.single()
        assertNull(fk.refSchema)
        assertEquals("a.b", fk.refTable)
    }

    @Test fun `테이블-레벨 3단 참조는 카탈로그를 버리고 소속만 담는다`() {
        // 모델이 담는 축은 소속 하나다([TableInfo]) — 카탈로그가 섞이면 JDBC 경로와 축이 어긋난다.
        val fk = DdlParser().parse(
            """CREATE TABLE t (cid INTEGER,
               CONSTRAINT fk FOREIGN KEY (cid) REFERENCES prodcat.sales.customers(id))""")
            .tables.single().foreignKeys.single()
        assertEquals("sales", fk.refSchema)
        assertEquals("customers", fk.refTable)
    }

    @Test fun `인라인 3단 참조는 파서가 못 읽지만 조용히 사라지지 않는다`() {
        // JSqlParser 4.9 는 컬럼 인라인 REFERENCES 의 3단 이름(`catalog.schema.table`)에서 두 번째
        // 점을 만나 파싱을 포기한다. 수집기의 한계이지만, 그 문장이 **사유·좌표와 함께 보고되는
        // 한**(#114) 유실이 아니다. 이 경계를 고정해 두지 않으면 나중에 "FK 가 안 나온다" 를
        // 조용한 누락과 구별할 수 없다.
        val s = DdlParser().parse("CREATE TABLE t (cid INTEGER REFERENCES prodcat.sales.customers(id))")
        assertTrue(s.tables.isEmpty(), "부분 복구를 사실로 산출하면 안 된다: ${s.tables}")
        assertEquals(listOf(CollectionReason.PARSE_ERROR), s.issues.map { it.reasonCode })
        assertEquals(IssueKind.FAILED, s.issues.single().kind)
    }

    @Test fun `인용 안의 겹인용은 이름의 한 문자다`() {
        // `"sch""ema"` 는 이름이 `sch"ema` 인 스키마다. 겹침을 접지 않고 그대로 두면 신원이
        // 원본을 가리키지 않는다 — contentHash 가 있지도 않은 이름을 지목하게 된다(리뷰 Q1).
        val t = DdlParser().parse("""CREATE TABLE "sch""ema"."ta""b" (id INTEGER)""").tables.single()
        assertEquals("sch\"ema", t.schema)
        assertEquals("ta\"b", t.name)
    }

    @Test fun `인용하지 않은 식별자의 따옴표는 건드리지 않는다`() {
        // 겹침을 접는 규칙은 **인용된 조각**에만 선다. 비인용 식별자까지 손대면 파서가 원본에 없는
        // 이름을 만든다.
        val fk = DdlParser().parse("""CREATE TABLE t (cid INTEGER REFERENCES sales.customers(id))""")
            .tables.single().foreignKeys.single()
        assertEquals("sales", fk.refSchema)
        assertEquals("customers", fk.refTable)
    }

    @Test fun `백틱 한정 이름도 소속을 담는다`() {
        val fk = DdlParser().parse(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, cid INTEGER REFERENCES `sales`.`customers`(id))")
            .tables.single().foreignKeys.single()
        assertEquals("sales", fk.refSchema)
        assertEquals("customers", fk.refTable)
    }

    @Test fun `비한정 DDL 은 소속이 없다`() {
        val schema = DdlParser().parse("CREATE TABLE orders (id INTEGER PRIMARY KEY)")
        assertNull(schema.tables.single().schema)
        assertEquals("orders", schema.tables.single().qualifiedName)
    }

    // ---- 하류: IRI 생성 ---------------------------------------------------------------------

    @Test fun `동명 테이블의 클래스 IRI 가 충돌하지 않는다`() {
        val base = "http://lodestar/rdb/shop#"
        val mapper = SchemaToOwlMapper()
        val ont = mapper.build(SchemaModel.of(sourceId = "db:test:ownership", tables = listOf(
            t("orders", "sales"), t("orders", "archive"))), base)
        val iris = ont.classesInSignature().map { it.iri.toString() }.toList().toSet()
        assertEquals(setOf(base + "sales/orders", base + "archive/orders"), iris)
    }

    @Test fun `소속이 없으면 IRI 는 예전 모양 그대로다`() {
        val base = "http://lodestar/rdb/shop#"
        val ont = SchemaToOwlMapper().build(
            SchemaModel.of(sourceId = "db:test:ownership", tables = listOf(t("orders", null))), base)
        assertEquals(setOf(base + "orders"), ont.classesInSignature().map { it.iri.toString() }.toList().toSet())
    }

    @Test fun `FK 는 같은 스키마의 동명 테이블을 가리킨다`() {
        val base = "http://lodestar/rdb/shop#"
        val mapper = SchemaToOwlMapper()
        val fk = ForeignKeyInfo(listOf("oid"), "orders", listOf("id"), refSchema = "archive")
        val ont = mapper.build(SchemaModel.of(sourceId = "db:test:ownership", tables = listOf(
            t("orders", "sales"), t("orders", "archive"), t("lines", "sales", fk))), base)
        val df = ont.owlOntologyManager.owlDataFactory
        val op = df.getOWLObjectProperty(
            org.semanticweb.owlapi.model.IRI.create(base + "sales/lines_oid_ref"))
        assertEquals(listOf(base + "archive/orders"),
            ont.objectPropertyRangeAxioms(op).map { it.range.asOWLClass().iri.toString() }.toList(),
            "FK 대상 스키마를 무시하면 동명 테이블 중 아무 쪽이나 가리킨다")
    }

    @Test fun `대상 스키마를 모르는 FK 는 같은 스키마 안에서 먼저 찾는다`() {
        // DDL 이 `REFERENCES orders(id)` 로만 적으면 대상 소속을 모른다. 그때는 SQL 의 이름 해석과
        // 같은 방향으로 — 자기 스키마 안을 먼저 본다.
        val base = "http://lodestar/rdb/shop#"
        val fk = ForeignKeyInfo(listOf("oid"), "orders", listOf("id"))
        val ont = SchemaToOwlMapper().build(SchemaModel.of(sourceId = "db:test:ownership", tables = listOf(
            t("orders", "sales"), t("orders", "archive"), t("lines", "archive", fk))), base)
        val df = ont.owlOntologyManager.owlDataFactory
        val op = df.getOWLObjectProperty(
            org.semanticweb.owlapi.model.IRI.create(base + "archive/lines_oid_ref"))
        assertEquals(listOf(base + "archive/orders"),
            ont.objectPropertyRangeAxioms(op).map { it.range.asOWLClass().iri.toString() }.toList())
    }

    /** 대상 클래스 IRI 하나를 읽는다. */
    private fun rangeOf(base: String, propIri: String, tables: List<TableInfo>): List<String> {
        val ont = SchemaToOwlMapper().build(SchemaModel.of(sourceId = "db:test:ownership", tables = tables), base)
        val op = ont.owlOntologyManager.owlDataFactory
            .getOWLObjectProperty(org.semanticweb.owlapi.model.IRI.create(base + propIri))
        return ont.objectPropertyRangeAxioms(op).map { it.range.asOWLClass().iri.toString() }.toList()
    }

    @Test fun `수집 범위 밖을 가리키는 FK 도 대상 소속을 잃지 않는다`() {
        // 대상 테이블이 스냅샷에 없다고 해서(다른 스키마가 수집 범위 밖) 소속을 버리면,
        // sales.orders 와 archive.orders 를 가리키는 두 FK 가 같은 클래스로 수렴한다 —
        // 이 이슈가 없앤 충돌이 '해석 실패' 분기에 그대로 남는 자리다.
        val base = "http://lodestar/rdb/shop#"
        val toSales = ForeignKeyInfo(listOf("oid"), "orders", listOf("id"), refSchema = "sales")
        val toArchive = ForeignKeyInfo(listOf("oid"), "orders", listOf("id"), refSchema = "archive")
        assertEquals(listOf(base + "sales/orders"),
            rangeOf(base, "s/lines_oid_ref", listOf(t("lines", "s", toSales))))
        assertEquals(listOf(base + "archive/orders"),
            rangeOf(base, "s/lines_oid_ref", listOf(t("lines", "s", toArchive))))
    }

    @Test fun `소속을 명시한 FK 는 소속이 다른 테이블로 폴백하지 않는다`() {
        // `REFERENCES sales.orders` 인데 스냅샷에는 소속을 모르는 orders 만 있다. 이름이 같다는
        // 이유로 그 클래스에 묶으면 **원본에 없는 관계**를 EXTRACTED·confidence 1.0 으로 산출하게 된다.
        val base = "http://lodestar/rdb/shop#"
        val toSales = ForeignKeyInfo(listOf("oid"), "orders", listOf("id"), refSchema = "sales")
        val unqualified = TableInfo("orders", listOf(ColumnInfo("id", "integer", false)), listOf("id"), emptyList())
        assertEquals(listOf(base + "sales/orders"),
            rangeOf(base, "s/lines_oid_ref", listOf(t("lines", "s", toSales), unqualified)),
            "소속이 다른 동명 테이블에 FK 가 잘못 묶였다")
    }

    @Test fun `동명 테이블의 데이터 프로퍼티도 충돌하지 않는다`() {
        val base = "http://lodestar/rdb/shop#"
        val cols = listOf(ColumnInfo("id", "integer", false), ColumnInfo("memo", "varchar", true))
        val ont = SchemaToOwlMapper().build(SchemaModel.of(sourceId = "db:test:ownership", tables = listOf(
            TableInfo("orders", cols, listOf("id"), emptyList(), schema = "sales"),
            TableInfo("orders", cols, listOf("id"), emptyList(), schema = "archive"))), base)
        val iris = ont.dataPropertiesInSignature().map { it.iri.toString() }.toList().toSet()
        assertTrue(base + "sales/orders.memo" in iris, iris.toString())
        assertTrue(base + "archive/orders.memo" in iris, iris.toString())
    }

    @Test fun `라벨은 원본 이름 그대로이고 소속은 주석으로 드러난다`() {
        // 라벨에 소속을 섞으면 라벨이 "수집기가 본 이름" 이 아니게 되고, 라벨을 이름으로 쓰는
        // 경로(UI 표시·AI 그라운딩)가 함께 흔들린다. 동명 테이블을 가르는 것은 IRI 의 몫이다.
        val base = "http://lodestar/rdb/shop#"
        val ont = SchemaToOwlMapper().build(
            SchemaModel.of(sourceId = "db:test:ownership", tables = listOf(t("orders", "sales"))), base)
        val df = ont.owlOntologyManager.owlDataFactory
        val annos = ont.annotationAssertionAxioms(org.semanticweb.owlapi.model.IRI.create(base + "sales/orders"))
            .toList()
        assertEquals(listOf("orders"),
            annos.filter { it.property.iri == df.rdfsLabel.iri }.map { it.value.asLiteral().get().literal })
        assertTrue(annos.any {
            it.property.iri == df.rdfsComment.iri && it.value.asLiteral().get().literal == "schema: sales"
        }, "소속을 어디에서도 볼 수 없다: $annos")
    }
}
