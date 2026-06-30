package com.ontostudio.api

import com.ontostudio.dto.IndividualDto
import com.ontostudio.ontology.IndividualService
import org.springframework.web.bind.annotation.*

data class CreateIndividualRequest(val label: String, val types: List<String> = emptyList())
data class AssertionRequest(val property: String, val value: String, val isLiteral: Boolean)

@RestController
@RequestMapping("/api/individuals")
class IndividualController(private val service: IndividualService) {
    @GetMapping fun list(@RequestParam(required = false) type: String?): List<IndividualDto> = service.list(type)
    @PostMapping fun create(@RequestBody r: CreateIndividualRequest): IndividualDto = service.create(r.label, r.types)

    @PostMapping("/{iri}/assertions")
    fun addAssertion(@PathVariable iri: String, @RequestBody r: AssertionRequest): IndividualDto =
        if (r.isLiteral) service.addDataAssertion(iri, r.property, r.value)
        else service.addObjectAssertion(iri, r.property, r.value)

    @DeleteMapping("/{iri}")
    fun delete(
        @PathVariable iri: String,
        @RequestParam(defaultValue = "false") cascade: Boolean
    ) = service.delete(iri, cascade)
}
