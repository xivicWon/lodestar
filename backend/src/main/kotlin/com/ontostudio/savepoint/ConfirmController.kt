package com.ontostudio.savepoint

import com.ontostudio.dto.ClassDto
import com.ontostudio.ontology.ClassService
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RestController

data class ConfirmRequest(val targetIri: String, val label: String)

/**
 * E8 세이브포인트: 운영자 승인 = 온톨로지 라벨 반영 + 확정 저장소 기록(원자적).
 * 다음 추정은 이 확정을 제외·앵커링해 그 위에서 확장한다(그라운딩).
 */
@RestController
@RequestMapping("/api")
class ConfirmController(
    private val classService: ClassService,
    private val store: ConfirmationStore,
) {
    /** 승인: ① 온톨로지 라벨 반영 → ② 확정 저장소에 기록. */
    @PostMapping("/enrich/confirm")
    fun confirm(@RequestBody req: ConfirmRequest): ClassDto {
        val dto = classService.setLabel(req.targetIri, req.label)
        store.confirm(ConfirmedFact(req.targetIri, req.label, "class"))
        return dto
    }

    @GetMapping("/confirmations")
    fun list(): List<ConfirmedFact> = store.all()

    @DeleteMapping("/confirmations")
    fun remove(@RequestParam iri: String) = store.remove(iri)
}
