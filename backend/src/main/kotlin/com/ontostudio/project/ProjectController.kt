package com.ontostudio.project

import com.ontostudio.dto.OntologyMetaDto
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/projects")
class ProjectController(private val service: ProjectService) {

    @GetMapping
    fun list(): List<String> = service.list()

    @PostMapping("/save")
    fun save(@RequestParam name: String): List<String> = service.save(name)

    @PostMapping("/load")
    fun load(@RequestParam name: String): OntologyMetaDto = service.load(name)
}
