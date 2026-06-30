package com.ontostudio.core

import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.model.*
import org.springframework.stereotype.Component

@Component
class OntologyHolder {
    val lock = Any()

    private var _manager: OWLOntologyManager = OWLManager.createOWLOntologyManager()
    val manager: OWLOntologyManager get() = _manager

    val dataFactory: OWLDataFactory get() = _manager.owlDataFactory

    private lateinit var _ontology: OWLOntology
    val ontology: OWLOntology get() = _ontology

    private var _baseIri: String = "http://onto-studio/ex#"
    val baseIri: String get() = _baseIri

    init { newOntology(null, _baseIri) }

    fun newOntology(ontologyIri: String?, baseIri: String) = synchronized(lock) {
        _manager = OWLManager.createOWLOntologyManager()
        _ontology = if (ontologyIri != null)
            _manager.createOntology(IRI.create(ontologyIri))
        else _manager.createOntology()
        _baseIri = baseIri
    }

    fun replace(ont: OWLOntology, baseIri: String) = synchronized(lock) {
        _manager = ont.owlOntologyManager
        _ontology = ont
        _baseIri = baseIri
    }
}
