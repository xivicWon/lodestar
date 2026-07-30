package com.ontostudio.rdb

import java.sql.DriverManager
import kotlin.test.Test
import kotlin.test.assertEquals

class MetadataServiceTest {
    private val url = "jdbc:h2:mem:meta_test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1"

    private fun openWithSchema(): java.sql.Connection {
        val conn = DriverManager.getConnection(url, "sa", "")
        conn.createStatement().use { st ->
            st.execute("DROP ALL OBJECTS")
            st.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(100))")
            st.execute("""CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                total NUMERIC(10,2),
                customer_id INTEGER,
                CONSTRAINT fk_cust FOREIGN KEY (customer_id) REFERENCES customers(id))""")
        }
        return conn
    }

    @Test fun `extract reads tables columns pk and fk`() {
        openWithSchema().use { conn ->
            val schema = MetadataService().extract(conn, "db:test:metadataservicetest")
            val names = schema.tables.map { it.name.lowercase() }.toSet()
            assertEquals(setOf("customers", "orders"), names)
            val orders = schema.tables.first { it.name.equals("orders", ignoreCase = true) }
            assertEquals(listOf("id"), orders.primaryKey.map { it.lowercase() })
            assertEquals(1, orders.foreignKeys.size)
            assertEquals("customers", orders.foreignKeys[0].refTable.lowercase())
            assertEquals(listOf("customer_id"), orders.foreignKeys[0].fkColumns.map { it.lowercase() })
        }
    }

    @Test fun `ddl path and live path yield equivalent schema`() {
        val liveSql = "CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(100))"
        openWithSchema().use { conn ->
            val live = MetadataService().extract(conn, "db:test:metadataservicetest").tables.first { it.name.equals("customers", true) }
            val ddl = DdlParser().parse(liveSql).tables.first { it.name == "customers" }
            assertEquals(ddl.primaryKey.map { it.lowercase() }, live.primaryKey.map { it.lowercase() })
            assertEquals(ddl.columns.map { it.name.lowercase() }.toSet(),
                         live.columns.map { it.name.lowercase() }.toSet())
        }
    }

    /** #114 — 타입 필터가 걸러낸 객체는 사유와 함께 반환형에 남는다. 조용한 제외 금지. */
    @Test fun `타입 필터로 걸러진 뷰가 사유와 함께 보고된다`() {
        openWithSchema().use { conn ->
            conn.createStatement().use { st ->
                st.execute("CREATE VIEW v_order_total AS SELECT id, total FROM orders")
            }
            val schema = MetadataService().extract(conn, "db:test:metadataservicetest")
            assertEquals(setOf("customers", "orders"), schema.tables.map { it.name.lowercase() }.toSet())

            // 테이블은 수집됐으므로 제외 목록에 없어야 한다 — TABLE_TYPE 문자열 비교로 판정하면
            // H2 의 "BASE TABLE" 표기에 걸려 전 테이블이 미지원으로 오보고된다.
            assertEquals(1, schema.issues.size, "제외는 뷰 1건뿐이어야 한다: ${schema.issues}")
            val view = schema.issues.single { it.target.lowercase() == "v_order_total" }
            assertEquals(IssueKind.SKIPPED, view.kind)
            assertEquals(CollectionReason.UNSUPPORTED_OBJECT_TYPE, view.reasonCode)
            kotlin.test.assertTrue(view.reason.contains("VIEW"), view.reason)
            kotlin.test.assertTrue(view.locator.startsWith("jdbc://"), view.locator)
        }
    }
}
