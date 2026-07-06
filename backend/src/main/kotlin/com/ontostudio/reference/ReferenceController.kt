package com.ontostudio.reference

import com.ontostudio.dto.ClassDto
import com.ontostudio.dto.ReferenceMetaDto
import org.springframework.web.bind.annotation.*
import org.springframework.web.multipart.MultipartFile

@RestController
@RequestMapping("/api/reference")
class ReferenceController(private val service: ReferenceService) {

    @PostMapping("/load")
    fun load(@RequestParam file: MultipartFile): ReferenceMetaDto =
        service.load(file.bytes, file.originalFilename)

    @GetMapping("/meta")
    fun meta(): ReferenceMetaDto = service.meta()

    @GetMapping("/classes")
    fun classes(): List<ClassDto> = service.classes()

    @DeleteMapping
    fun clear() = service.clear()
}
