package com.ontostudio.api

import com.ontostudio.ontology.SearchHit
import com.ontostudio.ontology.SearchService
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api")
class SearchController(private val service: SearchService) {
    @GetMapping("/search") fun search(@RequestParam q: String): List<SearchHit> = service.search(q)
    @GetMapping("/usage") fun usage(@RequestParam iri: String): List<String> = service.usage(iri)
}
