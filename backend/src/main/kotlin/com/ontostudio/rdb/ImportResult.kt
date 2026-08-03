package com.ontostudio.rdb

import com.ontostudio.dto.OntologyMetaDto
import com.ontostudio.savepoint.MergeSummary

/**
 * 임포트 응답: 온톨로지 메타 + 확정 병합 요약 + **수집 보고**(#129).
 *
 * 확정 병합 모듈(`savepoint`)이 아니라 임포트 경로(`rdb`)에 산다 — 이건 `/api/rdb/import/…` 의 응답
 * 계약이고, 병합 요약은 그중 한 필드일 뿐이다. `savepoint` 에 두면 확정 병합이 수집 보고 타입을
 * 끌어들여야 해서 의존이 거꾸로 선다.
 *
 * [collection] 에 기본값을 두지 않는다. 기본값이 있으면 새 임포트 경로가 보고를 싣지 않아도 컴파일이
 * 통과하고, 그 경로에서 제외·실패가 다시 조용히 사라진다 — 이 이슈가 고친 그 결함이다.
 */
data class ImportResult(
    val meta: OntologyMetaDto,
    val merge: MergeSummary,
    val collection: CollectionReport,
)
