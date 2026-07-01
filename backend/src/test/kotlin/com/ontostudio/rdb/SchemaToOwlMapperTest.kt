package com.ontostudio.rdb

import org.semanticweb.owlapi.model.IRI
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SchemaToOwlMapperTest {
    private val base = "http://lodestar/rdb/shop#"
    private val mapper = SchemaToOwlMapper()

    private fun sampleTwoTables() = SchemaModel(listOf(
        TableInfo("customers",
            listOf(ColumnInfo("id", "integer", false), ColumnInfo("name", "varchar(100)", true)),
            listOf("id"), emptyList()),
        TableInfo("orders",
            listOf(ColumnInfo("id", "integer", false), ColumnInfo("total", "numeric(10,2)", true),
                   ColumnInfo("customer_id", "integer", true)),
            listOf("id"),
            listOf(ForeignKeyInfo(listOf("customer_id"), "customers", listOf("id"))))
    ))

    @Test fun `each table becomes a class`() {
        val ont = mapper.build(sampleTwoTables(), base)
        val classIris = ont.classesInSignature().map { it.iri.toString() }.toList()
        assertTrue(classIris.contains(base + "customers"))
        assertTrue(classIris.contains(base + "orders"))
        assertEquals(2, classIris.size)
    }

    @Test fun `non-fk column becomes data property with domain and xsd range`() {
        val ont = mapper.build(sampleTwoTables(), base)
        val df = ont.owlOntologyManager.owlDataFactory
        val name = df.getOWLDataProperty(IRI.create(base + "customers.name"))
        assertTrue(ont.containsDataPropertyInSignature(name.iri))
        val domains = ont.dataPropertyDomainAxioms(name).map { it.domain.asOWLClass().iri.toString() }.toList()
        assertEquals(listOf(base + "customers"), domains)
        val ranges = ont.dataPropertyRangeAxioms(name).map { it.range.asOWLDatatype().iri.toString() }.toList()
        assertEquals(listOf("http://www.w3.org/2001/XMLSchema#string"), ranges)
    }

    @Test fun `table gets rdfs label of original name`() {
        val ont = mapper.build(sampleTwoTables(), base)
        val df = ont.owlOntologyManager.owlDataFactory
        val labels = ont.annotationAssertionAxioms(IRI.create(base + "orders"))
            .filter { it.property.iri == df.rdfsLabel.iri }
            .map { it.value.asLiteral().get().literal }.toList()
        assertEquals(listOf("orders"), labels)
    }
}
