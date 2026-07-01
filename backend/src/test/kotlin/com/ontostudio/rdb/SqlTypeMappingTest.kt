package com.ontostudio.rdb

import kotlin.test.Test
import kotlin.test.assertEquals

class SqlTypeMappingTest {
    private val XSD = "http://www.w3.org/2001/XMLSchema#"

    @Test fun `varchar and text map to string`() {
        assertEquals(XSD + "string", sqlTypeToXsd("varchar(255)"))
        assertEquals(XSD + "string", sqlTypeToXsd("TEXT"))
    }
    @Test fun `integer types map to integer`() {
        assertEquals(XSD + "integer", sqlTypeToXsd("integer"))
        assertEquals(XSD + "integer", sqlTypeToXsd("BIGINT"))
    }
    @Test fun `numeric maps to decimal`() {
        assertEquals(XSD + "decimal", sqlTypeToXsd("numeric(10,2)"))
    }
    @Test fun `boolean maps to boolean`() {
        assertEquals(XSD + "boolean", sqlTypeToXsd("bool"))
    }
    @Test fun `timestamp maps to dateTime`() {
        assertEquals(XSD + "dateTime", sqlTypeToXsd("timestamp without time zone"))
    }
    @Test fun `unknown type falls back to string`() {
        assertEquals(XSD + "string", sqlTypeToXsd("geometry"))
    }
}
