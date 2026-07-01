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
            val schema = MetadataService().extract(conn)
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
            val live = MetadataService().extract(conn).tables.first { it.name.equals("customers", true) }
            val ddl = DdlParser().parse(liveSql).tables.first { it.name == "customers" }
            assertEquals(ddl.primaryKey.map { it.lowercase() }, live.primaryKey.map { it.lowercase() })
            assertEquals(ddl.columns.map { it.name.lowercase() }.toSet(),
                         live.columns.map { it.name.lowercase() }.toSet())
        }
    }
}
