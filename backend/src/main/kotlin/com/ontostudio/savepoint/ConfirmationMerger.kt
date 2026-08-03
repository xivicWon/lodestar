package com.ontostudio.savepoint

import com.ontostudio.core.OntologyHolder
import com.ontostudio.dto.OntologyMetaDto
import com.ontostudio.rdb.CollectionReport
import com.ontostudio.ontology.ClassService
import org.semanticweb.owlapi.model.IRI
import org.springframework.stereotype.Service

/** 재임포트 병합 요약(E9): 재적용된 확정 수, 미매칭(stale) 수, 미매칭 IRI 목록. */
data class MergeSummary(val reapplied: Int, val stale: Int, val staleIris: List<String>)

/**
 * 임포트 응답: 온톨로지 메타 + 확정 병합 요약 + **수집 보고**(#129).
 *
 * [collection] 에 기본값을 두지 않는다. 기본값이 있으면 새 임포트 경로가 보고를 싣지 않아도 컴파일이
 * 통과하고, 그 경로에서 제외·실패가 다시 조용히 사라진다 — 이 이슈가 고친 그 결함이다.
 */
data class ImportResult(
    val meta: OntologyMetaDto,
    val merge: MergeSummary,
    val collection: CollectionReport,
)

/**
 * E9 — 재임포트 시 확정(세이브포인트) 라벨을 새 온톨로지에 IRI로 매칭해 자동 복원한다.
 * 결정론적 IRI(baseIri+slug)가 매칭 키. 미매칭 확정은 저장소에 그대로 보존(자동 삭제 안 함, D2).
 * 대상은 클래스 라벨 확정(kind=="class")만(D3).
 */
@Service
class ConfirmationMerger(
    private val store: ConfirmationStore,
    private val classService: ClassService,
    private val holder: OntologyHolder,
) {
    /** 확정 저장소를 순회해 현재 온톨로지에 존재하는 클래스 라벨을 재적용한다. */
    fun merge(): MergeSummary {
        var reapplied = 0
        val staleIris = mutableListOf<String>()
        for (fact in store.all()) {
            if (fact.kind != "class") continue
            val exists = synchronized(holder.lock) {
                holder.ontology.containsClassInSignature(IRI.create(fact.iri))
            }
            if (exists) {
                classService.setLabel(fact.iri, fact.label)
                reapplied++
            } else {
                staleIris.add(fact.iri)
            }
        }
        return MergeSummary(reapplied, staleIris.size, staleIris)
    }
}
