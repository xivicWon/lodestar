package com.ontostudio.rdb

import kotlin.test.Test
import kotlin.test.assertEquals

class SchemaModelTest {
    @Test fun `schema model holds tables columns and fks`() {
        val schema = SchemaModel(listOf(
            TableInfo(
                name = "orders",
                columns = listOf(ColumnInfo("id", "integer", false), ColumnInfo("total", "numeric", true)),
                primaryKey = listOf("id"),
                foreignKeys = listOf(ForeignKeyInfo(listOf("customer_id"), "customers", listOf("id")))
            )
        ))
        assertEquals(1, schema.tables.size)
        assertEquals("orders", schema.tables[0].name)
        assertEquals("customers", schema.tables[0].foreignKeys[0].refTable)
    }
}
