package com.ontostudio.align

import com.ontostudio.dto.AlignmentDto
import com.ontostudio.dto.AlignmentRequest
import com.ontostudio.dto.MatchType
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api/alignments")
class AlignmentController(private val service: AlignmentService) {

    @PostMapping
    fun create(@RequestBody req: AlignmentRequest): AlignmentDto = service.create(req)

    @GetMapping
    fun list(): List<AlignmentDto> = service.list()

    @DeleteMapping
    fun delete(
        @RequestParam sourceIri: String,
        @RequestParam targetIri: String,
        @RequestParam matchType: MatchType,
    ) = service.delete(sourceIri, targetIri, matchType)
}
