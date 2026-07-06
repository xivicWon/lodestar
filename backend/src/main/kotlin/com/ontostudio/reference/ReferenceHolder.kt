package com.ontostudio.reference

import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.model.OWLDataFactory
import org.semanticweb.owlapi.model.OWLOntology
import org.semanticweb.owlapi.model.OWLOntologyManager
import org.springframework.stereotype.Component

/** 참조(외부) 온톨로지를 소스와 완전히 분리해 보관한다. 없을 수 있다(null). */
@Component
final class ReferenceHolder {
    val lock = Any()
    private var _manager: OWLOntologyManager = OWLManager.createOWLOntologyManager()
    private var _ontology: OWLOntology? = null
    var source: String? = null
        private set

    val manager: OWLOntologyManager get() = _manager
    val dataFactory: OWLDataFactory get() = _manager.owlDataFactory
    val ontology: OWLOntology? get() = _ontology

    fun set(mgr: OWLOntologyManager, ont: OWLOntology, source: String?) = synchronized(lock) {
        _manager = mgr; _ontology = ont; this.source = source
    }

    fun clear() = synchronized(lock) { _ontology = null; source = null }
}
