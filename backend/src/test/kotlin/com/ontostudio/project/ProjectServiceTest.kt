package com.ontostudio.project

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.io.IoService
import java.nio.file.Files
import kotlin.test.*

class ProjectServiceTest {

    private fun sampleBytes() = this::class.java
        .getResourceAsStream("/com/ontostudio/fixtures/mini-ontology.ttl")!!.readBytes()

    @Test fun `save then list then load roundtrips classes`() {
        val dir = Files.createTempDirectory("proj-test").toString()
        val holder = OntologyHolder()
        val io = IoService(holder)
        val mapper = OntologyMapper(holder)
        val service = ProjectService(io, mapper, dir)

        io.load(sampleBytes(), "http://ex#")
        assertEquals(2, mapper.meta().counts["classes"])

        val names = service.save("t")
        assertTrue(names.contains("t"))
        assertTrue(service.list().contains("t"))

        // clear ontology, then load back
        holder.newOntology(null, "http://ex#")
        assertEquals(0, mapper.meta().counts["classes"])

        val meta = service.load("t")
        assertEquals(2, meta.counts["classes"])
    }

    @Test fun `name is sanitized`() {
        val dir = Files.createTempDirectory("proj-test").toString()
        val holder = OntologyHolder()
        val io = IoService(holder)
        val service = ProjectService(io, OntologyMapper(holder), dir)

        io.load(sampleBytes(), "http://ex#")
        service.save("my proj!/../x")
        assertTrue(service.list().any { it == "myprojx" || it.matches(Regex("[A-Za-z0-9_-]+")) })
    }
}
