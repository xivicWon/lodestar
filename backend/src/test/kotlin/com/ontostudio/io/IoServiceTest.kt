package com.ontostudio.io

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import kotlin.test.*

class IoServiceTest {
    private fun fixture() = this::class.java
        .getResourceAsStream("/com/ontostudio/fixtures/mini-ontology.ttl")!!.readBytes()

    @Test fun `load reads classes and roundtrips`() {
        val holder = OntologyHolder()
        val io = IoService(holder)
        val mapper = OntologyMapper(holder)

        io.load(fixture(), "http://ex#")
        assertEquals(2, mapper.meta().counts["classes"])

        val out = io.export("turtle")
        // 재로드 후 동일 클래스 수 (라운드트립)
        io.load(out, "http://ex#")
        assertEquals(2, mapper.meta().counts["classes"])
    }
}
