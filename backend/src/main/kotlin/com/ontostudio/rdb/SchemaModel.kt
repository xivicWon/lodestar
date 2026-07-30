package com.ontostudio.rdb

/**
 * 수집 결과 한 항목의 처리 종류.
 *
 * - [SKIPPED]  수집 범위 밖이거나 수집기가 처리하지 않는 대상 — 정당한 제외도 여기다(사유는 필수).
 * - [FAILED]   처리하려 했으나 실패한 대상 — 산출물에 사실을 싣지 않는다.
 * - [PARTIAL]  일부만 수집된 대상 — 부분 성공을 완전 성공으로 위장하지 않기 위한 표시다.
 */
enum class IssueKind { SKIPPED, FAILED, PARTIAL }

/** 사유 코드. gold(#99) `failures.json` 의 `reported[].kind` 어휘와 같은 값을 쓴다 — 대조가 가능해야 한다. */
object CollectionReason {
    const val PARSE_ERROR = "PARSE_ERROR"
    const val UNSUPPORTED_STATEMENT = "UNSUPPORTED_STATEMENT"

    /** 수집기가 다루지 않는 객체 타입(JDBC 메타데이터의 VIEW·SYNONYM 등) */
    const val UNSUPPORTED_OBJECT_TYPE = "UNSUPPORTED_OBJECT_TYPE"

    /** 설계상 정당한 제외(행 데이터 등). 정당하더라도 사유·분모는 보고한다(I3 R20). */
    const val OUT_OF_SCOPE_BY_DESIGN = "OUT_OF_SCOPE_BY_DESIGN"

    /** 입력 단위 부분 성공 요약 */
    const val PARTIAL_COLLECTION = "PARTIAL_COLLECTION"
}

/**
 * 수집기가 **하지 못한 일**을 담는 항목. 조용한 skip 을 구조적으로 불가능하게 만드는 자리다.
 *
 * @param locator 원본 좌표. 경로를 아는 경우 `path#L11-L14`, 모르는 경우 `#L11-L14`.
 *                한 행이면 `#L16` 으로 적는다.
 * @param target  좌표가 가리키는 대상. **원본 그 행에서 조회되는 문자열**이어야 한다
 *                (그럴듯하지만 조회되지 않는 좌표를 막는 #88 V5 와 같은 요구).
 */
data class CollectionIssue(
    val kind: IssueKind,
    val reasonCode: String,
    val reason: String,
    val locator: String,
    val target: String,
)

/**
 * DB에서 추출한 날것의 스키마. OWL 지식 없음, 순수 데이터. 두 입력 경로가 이 타입으로 수렴한다.
 *
 * @param issues   **문장·객체 단위** 제외·실패·부분수집. 세는 단위는 입력 문장 또는 객체다(gold R-F-4) —
 *                 전처리 분할로 한 문장이 여러 조각이 되어도 1건이다.
 * @param partials **입력 단위** 부분 성공 요약. `issues` 와 분모가 달라 섞으면 집계가 깨지므로 분리한다.
 */
data class SchemaModel(
    val tables: List<TableInfo>,
    val issues: List<CollectionIssue> = emptyList(),
    val partials: List<CollectionIssue> = emptyList(),
)

data class TableInfo(
    val name: String,
    val columns: List<ColumnInfo>,
    val primaryKey: List<String>,
    val foreignKeys: List<ForeignKeyInfo>
)

data class ColumnInfo(val name: String, val sqlType: String, val nullable: Boolean)

/** fkColumns(이 테이블의 컬럼) → refTable.refColumns 를 가리키는 외래키. 복합키는 리스트가 다중. */
data class ForeignKeyInfo(
    val fkColumns: List<String>,
    val refTable: String,
    val refColumns: List<String>
)
