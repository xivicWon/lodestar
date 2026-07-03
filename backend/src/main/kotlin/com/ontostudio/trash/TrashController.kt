package com.ontostudio.trash

import org.springframework.web.bind.annotation.*

data class TrashRequest(val iri: String? = null)

@RestController
@RequestMapping("/api/trash")
class TrashController(private val service: TrashService) {

    @PostMapping
    fun trash(
        @RequestBody(required = false) body: TrashRequest?,
        @RequestParam(required = false) iri: String?,
    ): TrashResult {
        val target = body?.iri ?: iri
            ?: throw com.ontostudio.dto.ApiException(
                org.springframework.http.HttpStatus.BAD_REQUEST, "bad_request", "iri 필요", null)
        return service.trash(target)
    }

    @GetMapping
    fun list(): List<TrashEntryDto> =
        service.list().map { TrashEntryDto(it.iri, it.label, it.trashedAt) }

    @PostMapping("/restore")
    fun restore(@RequestParam iri: String) = service.restore(iri)

    @DeleteMapping
    fun purge(@RequestParam iri: String) = service.purge(iri)
}
