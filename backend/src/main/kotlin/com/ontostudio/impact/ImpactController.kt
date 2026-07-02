package com.ontostudio.impact

import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api")
class ImpactController(private val service: ImpactService) {
    @GetMapping("/impact")
    fun impact(@RequestParam iri: String): ImpactResult = service.impact(iri)
}
