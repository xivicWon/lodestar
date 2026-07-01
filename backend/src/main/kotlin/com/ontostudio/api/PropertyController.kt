package com.ontostudio.api

import com.ontostudio.dto.DataPropertyDto
import com.ontostudio.dto.ObjectPropertyDto
import com.ontostudio.ontology.PropertyService
import org.springframework.web.bind.annotation.*

data class CreateObjectPropRequest(
    val label: String,
    val domains: List<String> = emptyList(),
    val ranges: List<String> = emptyList()
)

data class CreateDataPropRequest(
    val label: String,
    val domains: List<String> = emptyList(),
    val range: String? = null
)

data class CharacteristicsRequest(val characteristics: List<String>)

data class LabelRequest(val label: String)

@RestController
@RequestMapping("/api/properties")
class PropertyController(private val service: PropertyService) {

    @GetMapping("/object")
    fun listObject(): List<ObjectPropertyDto> = service.listObject()

    @GetMapping("/data")
    fun listData(): List<DataPropertyDto> = service.listData()

    @PostMapping("/object")
    fun createObject(@RequestBody r: CreateObjectPropRequest): ObjectPropertyDto =
        service.createObject(r.label, r.domains, r.ranges)

    @PostMapping("/data")
    fun createData(@RequestBody r: CreateDataPropRequest): DataPropertyDto =
        service.createData(r.label, r.domains, r.range)

    @PatchMapping("/object/by-iri")
    fun setChars(@RequestParam iri: String, @RequestBody r: CharacteristicsRequest): ObjectPropertyDto =
        service.setObjectCharacteristics(iri, r.characteristics)

    @PatchMapping("/object/label")
    fun setObjectLabel(@RequestParam iri: String, @RequestBody r: LabelRequest): ObjectPropertyDto =
        service.setObjectLabel(iri, r.label)

    @DeleteMapping("/by-iri")
    fun delete(
        @RequestParam type: String,
        @RequestParam iri: String,
        @RequestParam(defaultValue = "false") cascade: Boolean
    ) = service.delete(type, iri, cascade)
}
