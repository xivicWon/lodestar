package com.ontostudio.api

import com.ontostudio.dto.ClassDto
import com.ontostudio.ontology.ClassService
import org.springframework.web.bind.annotation.*

data class CreateClassRequest(val label: String, val superClass: String? = null)
data class PatchClassRequest(val label: String? = null, val superClasses: List<String>? = null)

@RestController
@RequestMapping("/api/classes")
class ClassController(private val service: ClassService) {
    @GetMapping fun list(): List<ClassDto> = service.list()
    @GetMapping("/{iri}") fun get(@PathVariable iri: String): ClassDto = service.get(iri)
    @PostMapping fun create(@RequestBody r: CreateClassRequest): ClassDto = service.create(r.label, r.superClass)

    @PatchMapping("/{iri}")
    fun patch(@PathVariable iri: String, @RequestBody r: PatchClassRequest): ClassDto {
        var dto: ClassDto? = null
        r.label?.let { dto = service.setLabel(iri, it) }
        r.superClasses?.let { dto = service.setSuperClasses(iri, it) }
        return dto ?: service.get(iri)
    }

    @DeleteMapping("/{iri}")
    fun delete(@PathVariable iri: String, @RequestParam(defaultValue = "false") cascade: Boolean) =
        service.delete(iri, cascade)
}
