package com.ontostudio.core

import org.semanticweb.owlapi.model.OWLAnnotationAssertionAxiom
import org.semanticweb.owlapi.model.OWLAxiom
import org.semanticweb.owlapi.model.OWLDataPropertyDomainAxiom
import org.semanticweb.owlapi.model.OWLDataPropertyRangeAxiom
import org.semanticweb.owlapi.model.OWLDeclarationAxiom
import org.semanticweb.owlapi.model.OWLEntity
import org.semanticweb.owlapi.model.OWLObjectPropertyDomainAxiom
import org.semanticweb.owlapi.model.OWLObjectPropertyRangeAxiom
import org.semanticweb.owlapi.model.OWLOntology

/** Referencing axioms that are NOT the entity's own declaration, self-addressed annotation assertions,
 *  or the property's own domain/range axioms. */
fun externalReferencingAxioms(ont: OWLOntology, entity: OWLEntity): List<OWLAxiom> =
    ont.referencingAxioms(entity).toList().filter {
        it !is OWLDeclarationAxiom &&
        !(it is OWLAnnotationAssertionAxiom && it.subject == entity.iri) &&
        !(it is OWLObjectPropertyDomainAxiom && it.property == entity) &&
        !(it is OWLObjectPropertyRangeAxiom && it.property == entity) &&
        !(it is OWLDataPropertyDomainAxiom && it.property == entity) &&
        !(it is OWLDataPropertyRangeAxiom && it.property == entity)
    }
