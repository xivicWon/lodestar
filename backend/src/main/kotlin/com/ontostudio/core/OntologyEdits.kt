package com.ontostudio.core

import org.semanticweb.owlapi.model.OWLAnnotationAssertionAxiom
import org.semanticweb.owlapi.model.OWLAxiom
import org.semanticweb.owlapi.model.OWLDeclarationAxiom
import org.semanticweb.owlapi.model.OWLEntity
import org.semanticweb.owlapi.model.OWLOntology

/** Referencing axioms that are NOT the entity's own declaration or self-addressed annotation assertions. */
fun externalReferencingAxioms(ont: OWLOntology, entity: OWLEntity): List<OWLAxiom> =
    ont.referencingAxioms(entity).toList().filter {
        it !is OWLDeclarationAxiom &&
        !(it is OWLAnnotationAssertionAxiom && it.subject == entity.iri)
    }
