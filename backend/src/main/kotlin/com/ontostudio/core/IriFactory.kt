package com.ontostudio.core

import org.semanticweb.owlapi.model.IRI

class IriFactory(private val baseIri: String) {
    fun forLabel(label: String, existing: Set<IRI>): IRI {
        val slug = label.trim().replace(Regex("\\s+"), "_").replace(Regex("[^\\p{L}\\p{N}_]"), "")
            .ifBlank { "Entity" }
        var candidate = IRI.create(baseIri + slug)
        var n = 2
        while (existing.contains(candidate)) {
            candidate = IRI.create(baseIri + slug + "_" + n); n++
        }
        return candidate
    }
}
