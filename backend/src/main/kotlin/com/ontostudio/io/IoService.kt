package com.ontostudio.io

import com.ontostudio.core.OntologyHolder
import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.formats.RDFXMLDocumentFormat
import org.semanticweb.owlapi.formats.TurtleDocumentFormat
import org.semanticweb.owlapi.model.OWLDocumentFormat
import org.springframework.stereotype.Service
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

@Service
class IoService(private val holder: OntologyHolder) {
    fun load(bytes: ByteArray, baseIri: String) = synchronized(holder.lock) {
        val mgr = OWLManager.createOWLOntologyManager()
        val ont = mgr.loadOntologyFromOntologyDocument(ByteArrayInputStream(bytes))
        holder.replace(ont, baseIri)
    }

    fun export(format: String): ByteArray = synchronized(holder.lock) {
        val docFormat: OWLDocumentFormat = when (format.lowercase()) {
            "rdfxml" -> RDFXMLDocumentFormat()
            else -> TurtleDocumentFormat()
        }
        val out = ByteArrayOutputStream()
        holder.manager.saveOntology(holder.ontology, docFormat, out)
        out.toByteArray()
    }
}
