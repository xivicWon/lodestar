package com.ontostudio.io

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.ApiException
import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.formats.RDFXMLDocumentFormat
import org.semanticweb.owlapi.formats.TurtleDocumentFormat
import org.semanticweb.owlapi.model.OWLDocumentFormat
import org.semanticweb.owlapi.model.OWLOntologyCreationException
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

@Service
class IoService(private val holder: OntologyHolder) {
    fun load(bytes: ByteArray, baseIri: String) = synchronized(holder.lock) {
        val mgr = OWLManager.createOWLOntologyManager()
        val ont = try {
            mgr.loadOntologyFromOntologyDocument(ByteArrayInputStream(bytes))
        } catch (e: OWLOntologyCreationException) {
            throw ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "load_failed",
                "온톨로지 파일을 읽을 수 없습니다: ${e.message}", null)
        }
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
