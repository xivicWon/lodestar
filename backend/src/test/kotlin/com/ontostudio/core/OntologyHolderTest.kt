package com.ontostudio.core

import org.semanticweb.owlapi.model.IRI
import kotlin.test.*

class OntologyHolderTest {
    @Test fun `newOntology creates empty ontology with base iri`() {
        val holder = OntologyHolder()
        holder.newOntology(ontologyIri = "http://ex/onto", baseIri = "http://ex/onto#")
        assertEquals(0, holder.ontology.classesInSignature().count())
        assertEquals("http://ex/onto#", holder.baseIri)
    }

    @Test fun `iri factory slugs label and avoids collision`() {
        val f = IriFactory("http://ex#")
        val first = f.forLabel("Red Wine", emptySet())
        assertEquals("http://ex#Red_Wine", first.toString())
        val second = f.forLabel("Red Wine", setOf(first))
        assertEquals("http://ex#Red_Wine_2", second.toString())
    }

    @Test fun `iri factory keeps unicode letters in slug`() {
        val f = IriFactory("http://ex#")
        val iri = f.forLabel("동물", emptySet())
        assertEquals("http://ex#동물", iri.toString())
    }

    @Test fun `iri factory falls back to Entity for symbol-only label`() {
        val f = IriFactory("http://ex#")
        val iri = f.forLabel("***", emptySet())
        assertEquals("http://ex#Entity", iri.toString())
    }
}
