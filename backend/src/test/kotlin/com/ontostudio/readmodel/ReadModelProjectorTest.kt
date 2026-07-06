package com.ontostudio.readmodel

import com.ontostudio.align.AlignmentService
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.ClassService
import com.ontostudio.ontology.PropertyService
import com.ontostudio.provenance.Provenance
import com.ontostudio.provenance.ProvenanceDto
import com.ontostudio.provenance.RelationKind
import com.ontostudio.reference.ReferenceHolder
import com.ontostudio.reference.ReferenceService
import com.ontostudio.savepoint.ConfirmationStore
import com.ontostudio.savepoint.ConfirmedFact
import org.semanticweb.owlapi.model.IRI
import java.nio.file.Files
import java.sql.DriverManager
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ReadModelProjectorTest {
    private val db = Files.createTempFile("readmodel", ".db")
    private val confFile = Files.createTempFile("conf", ".json")
    @AfterTest fun cleanup() { Files.deleteIfExists(db); Files.deleteIfExists(confFile) }

    private fun projector(): ReadModelProjector {
        val holder = OntologyHolder()
        val df = holder.dataFactory
        listOf("http://ex#a", "http://ex#b").forEach {
            holder.manager.addAxiom(holder.ontology, df.getOWLDeclarationAxiom(df.getOWLClass(IRI.create(it))))
            holder.manager.addAxiom(holder.ontology, df.getOWLAnnotationAssertionAxiom(
                IRI.create(it), df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(it.substringAfter('#')))))
        }
        val mapper = OntologyMapper(holder)
        val props = PropertyService(holder, mapper)
        props.createObject("placedBy", listOf("http://ex#a"), listOf("http://ex#b"),
            ProvenanceDto(RelationKind.NAMEPATTERN, Provenance.INFERRED, 0.6))
        val conf = ConfirmationStore(confFile.toString()).also { it.confirm(ConfirmedFact("http://ex#a", "a", "class")) }
        val ref = ReferenceService(ReferenceHolder())
        val align = AlignmentService(holder, ref)
        return ReadModelProjector(holder, mapper, ClassService(holder, mapper), props, align, conf)
    }

    @Test fun `project creates schema tables`() {
        projector().project(db.toString())
        DriverManager.getConnection("jdbc:sqlite:${db}").use { c ->
            val names = mutableSetOf<String>()
            c.createStatement().executeQuery("SELECT name FROM sqlite_master WHERE type='table'").use { rs ->
                while (rs.next()) names.add(rs.getString(1))
            }
            assertTrue(names.containsAll(setOf("class", "relation", "evidence", "alignment", "domain", "meta")), "tables: $names")
        }
    }

    @Test fun `project writes class relation and alignment rows`() {
        projector().project(db.toString())
        DriverManager.getConnection("jdbc:sqlite:${db}").use { c ->
            fun count(t: String): Int = c.createStatement().executeQuery("SELECT COUNT(*) FROM $t").use { it.next(); it.getInt(1) }
            assertEquals(2, count("class"))
            assertEquals(1, count("relation"))
            // relation provenance round-trip
            c.createStatement().executeQuery("SELECT from_iri,to_iri,name,kind,provenance,confidence FROM relation").use { rs ->
                assertTrue(rs.next())
                assertEquals("http://ex#a", rs.getString("from_iri"))
                assertEquals("http://ex#b", rs.getString("to_iri"))
                assertEquals("placedBy", rs.getString("name"))
                assertEquals("NAMEPATTERN", rs.getString("kind"))
                assertEquals("INFERRED", rs.getString("provenance"))
                assertEquals(0.6, rs.getDouble("confidence"), 1e-9)
            }
            // confirmed flag from ConfirmationStore
            c.createStatement().executeQuery("SELECT confirmed FROM class WHERE iri='http://ex#a'").use { rs ->
                assertTrue(rs.next()); assertEquals(1, rs.getInt("confirmed"))
            }
            // degree: a has 1 relation
            c.createStatement().executeQuery("SELECT degree FROM class WHERE iri='http://ex#a'").use { rs ->
                assertTrue(rs.next()); assertEquals(1, rs.getInt("degree"))
            }
        }
    }
}
