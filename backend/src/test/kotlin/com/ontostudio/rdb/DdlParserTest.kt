package com.ontostudio.rdb

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class DdlParserTest {
    private val parser = DdlParser()

    @Test fun `parses tables columns pk and table-level fk`() {
        val sql = """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            );
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                total NUMERIC(10,2),
                customer_id INTEGER,
                CONSTRAINT fk_cust FOREIGN KEY (customer_id) REFERENCES customers (id)
            );
        """.trimIndent()
        val schema = parser.parse(sql)
        assertEquals(setOf("customers", "orders"), schema.tables.map { it.name }.toSet())
        val orders = schema.tables.first { it.name == "orders" }
        assertEquals(listOf("id"), orders.primaryKey)
        assertEquals(1, orders.foreignKeys.size)
        assertEquals("customers", orders.foreignKeys[0].refTable)
        assertEquals(listOf("customer_id"), orders.foreignKeys[0].fkColumns)
    }

    @Test fun `parses inline column references as fk`() {
        val sql = """
            CREATE TABLE dept (id INTEGER PRIMARY KEY);
            CREATE TABLE emp (id INTEGER PRIMARY KEY, dept_id INTEGER REFERENCES dept(id));
        """.trimIndent()
        val schema = parser.parse(sql)
        val emp = schema.tables.first { it.name == "emp" }
        assertEquals(1, emp.foreignKeys.size)
        assertEquals("dept", emp.foreignKeys[0].refTable)
        assertEquals(listOf("dept_id"), emp.foreignKeys[0].fkColumns)
    }

    @Test fun `skips unparseable statements without failing`() {
        val sql = """
            CREATE TABLE t (id INTEGER PRIMARY KEY);
            CREATE TRIGGER trg BEFORE INSERT ON t FOR EACH ROW EXECUTE FUNCTION f();
        """.trimIndent()
        val schema = parser.parse(sql)
        assertTrue(schema.tables.any { it.name == "t" })
    }
}
