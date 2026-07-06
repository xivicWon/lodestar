package com.ontostudio.readmodel

import org.springframework.web.bind.annotation.*

data class ProjectResult(val path: String, val ok: Boolean)

@RestController
@RequestMapping("/api/readmodel")
class ReadModelController(private val projector: ReadModelProjector) {
    @PostMapping("/project")
    fun project(@RequestParam path: String): ProjectResult {
        projector.project(path)
        return ProjectResult(path, true)
    }
}
