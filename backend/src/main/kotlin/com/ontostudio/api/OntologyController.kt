package com.ontostudio.api

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.OntologyMetaDto
import com.ontostudio.io.IoService
import org.springframework.http.HttpHeaders
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import org.springframework.web.multipart.MultipartFile

data class NewOntologyRequest(val ontologyIri: String?, val baseIri: String)

@RestController
@RequestMapping("/api/ontology")
class OntologyController(
    private val holder: OntologyHolder,
    private val io: IoService,
    private val mapper: OntologyMapper
) {
    @PostMapping("/new")
    fun new(@RequestBody req: NewOntologyRequest): OntologyMetaDto {
        holder.newOntology(req.ontologyIri, req.baseIri)
        return mapper.meta()
    }

    @PostMapping("/load")
    fun load(
        @RequestParam file: MultipartFile,
        @RequestParam(defaultValue = "http://onto-studio/ex#") baseIri: String
    ): OntologyMetaDto {
        io.load(file.bytes, baseIri)
        return mapper.meta()
    }

    @GetMapping("/meta")
    fun meta(): OntologyMetaDto = mapper.meta()

    @GetMapping("/export")
    fun export(@RequestParam(defaultValue = "turtle") format: String): ResponseEntity<ByteArray> {
        val bytes = io.export(format)
        val ext = if (format.lowercase() == "rdfxml") "owl" else "ttl"
        return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=ontology.$ext")
            .body(bytes)
    }
}
