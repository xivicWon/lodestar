package com.ontostudio.rdb

/**
 * 수집 보고 항목의 **전송 표현**. [CollectionIssue] 와 같은 넷을 그대로 싣는다
 * (종류 · 사유코드+사유문 · 좌표 · 대상). enum 을 그대로 직렬화하지 않고 문자열로 고정하는 이유는
 * 이 값이 gold(#99) `failures.json` 의 어휘와 대조되는 **계약 문자열**이기 때문이다 —
 * Kotlin enum 의 이름이 바뀌면 계약이 조용히 바뀌는 자리를 만들지 않는다.
 */
data class CollectionIssueDto(
    val kind: String,
    val reasonCode: String,
    val reason: String,
    val locator: String,
    val target: String,
) {
    companion object {
        fun of(i: CollectionIssue) =
            CollectionIssueDto(i.kind.name, i.reasonCode, i.reason, i.locator, i.target)
    }
}

/**
 * 임포트 응답에 실리는 수집 보고(#129). 수집기가 반환형에 실은 제외·실패·부분수집(#114)을
 * **전달 경로에서 버리지 않기 위한** 자리다.
 *
 * 집계만 싣지 않는다 — 사유 없는 건수는 gold R-F-2 기준으로 미보고다. 건수는 화면의 요약용이고,
 * 계약을 만족시키는 것은 [issues]·[partials] 의 항목들이다.
 *
 * @param sourceKind 어느 입력 경로가 만든 보고인가(`ddl`·`jdbc`·`sample`). 좌표 규약이 경로마다
 *                   다르므로 소비자는 이 값 없이 좌표를 해석할 수 없다.
 * @param locatorScheme 좌표 규약. `line` = `path#L11-L14`(경로를 모르면 `#L11-L14`),
 *                   `jdbc` = `jdbc://<catalog>/<schema>/<object>`. 문서: L0-fix 문서 §8.
 * @param collected 산출된 테이블 수 — 보고의 **분모**다. 건수만 있는 성공 표시를 막는다.
 * @param issues   문장·객체 단위 제외·실패(gold R-F-4).
 * @param partials 입력 단위 부분 성공 요약. [issues] 와 분모가 달라 섞지 않는다.
 */
data class CollectionReport(
    val sourceKind: String,
    val locatorScheme: String,
    val collected: Int,
    val skipped: Int,
    val failed: Int,
    val partial: Int,
    val issues: List<CollectionIssueDto>,
    val partials: List<CollectionIssueDto>,
) {
    /**
     * 완전 수집인가. **정당한 제외(SKIPPED)는 불완전이 아니다** — 행 데이터처럼 설계상 범위 밖인
     * 대상까지 불완전으로 세면 모든 임포트가 항상 경고를 달아 경고가 신호이기를 그친다.
     * 반대로 실패·부분수집이 하나라도 있으면 완전 성공으로 **표시하지 않는다**(#88 조용한 skip).
     */
    val complete: Boolean get() = failed == 0 && partial == 0

    companion object {
        /** 좌표 규약은 입력 경로가 정한다 — DDL 은 행 번호, JDBC 계열은 객체 좌표다. */
        fun locatorScheme(sourceKind: String): String =
            if (sourceKind == SchemaSource.KIND_DDL) "line" else "jdbc"

        fun of(sourceKind: String, schema: SchemaModel): CollectionReport = CollectionReport(
            sourceKind = sourceKind,
            locatorScheme = locatorScheme(sourceKind),
            collected = schema.tables.size,
            skipped = schema.issues.count { it.kind == IssueKind.SKIPPED },
            failed = schema.issues.count { it.kind == IssueKind.FAILED },
            partial = schema.partials.size + schema.issues.count { it.kind == IssueKind.PARTIAL },
            issues = schema.issues.map { CollectionIssueDto.of(it) },
            partials = schema.partials.map { CollectionIssueDto.of(it) },
        )
    }
}
