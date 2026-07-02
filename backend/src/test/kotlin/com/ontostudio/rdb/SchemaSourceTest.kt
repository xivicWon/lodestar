package com.ontostudio.rdb

import kotlin.test.Test
import kotlin.test.assertEquals

class SchemaSourceTest {
    @Test fun `ddl source extracts schema model and exposes name`() {
        val src = DdlSource("CREATE TABLE t (id INTEGER PRIMARY KEY);", "shop", DdlParser())
        assertEquals("shop", src.name)
        assertEquals(listOf("t"), src.extract().tables.map { it.name })
    }

    @Test fun `ddl source falls back to default name when blank`() {
        assertEquals("schema", DdlSource("", null, DdlParser()).name)
        assertEquals("schema", DdlSource("", "  ", DdlParser()).name)
    }
}
