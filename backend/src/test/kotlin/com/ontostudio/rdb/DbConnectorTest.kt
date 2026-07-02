package com.ontostudio.rdb

import kotlin.test.Test
import kotlin.test.assertTrue
import kotlin.test.assertEquals

class DbConnectorTest {
    private val c = DbConnector()

    @Test fun `postgres url (default vendor)`() {
        val url = c.jdbcUrl(ConnectionInfo("h", 5432, "shop", "u", "p"))
        assertEquals("jdbc:postgresql://h:5432/shop", url)
    }

    @Test fun `mysql url with params`() {
        val url = c.jdbcUrl(ConnectionInfo("h", 23306, "shop", "u", "p", vendor = "mysql"))
        assertTrue(url.startsWith("jdbc:mysql://h:23306/shop?"), url)
        assertTrue(url.contains("useSSL=false"))
        assertTrue(url.contains("allowPublicKeyRetrieval=true"))
    }

    @Test fun `mysql url without database (catalog enumeration)`() {
        val url = c.jdbcUrl(ConnectionInfo("h", 23306, "", "u", "p", vendor = "mysql"))
        assertTrue(url.startsWith("jdbc:mysql://h:23306/?"), url)
    }
}
