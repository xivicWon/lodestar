package com.ontostudio.rdb

/**
 * DB에서 추출한 날것의 스키마. OWL 지식 없음, 순수 데이터. 두 입력 경로가 이 타입으로 수렴한다.
 *
 * [metadata] 는 **기본값이 없다**. 기본값을 두면 신원 없는 산출물이 계속 만들어지고,
 * 그게 #88 에서 `gate-l0-metadata-completeness` 가 0/5 였던 이유다(#113).
 */
data class SchemaModel(val tables: List<TableInfo>, val metadata: CollectionMetadata) {
    companion object {
        /**
         * 메모리에서 합성된 스키마의 신원 — 자기 내용에서 파생한다.
         * 값을 지어내지 않기 위한 것이지, 수집 경로가 쓰라고 있는 것이 아니다
         * (수집 경로는 자기가 **실제로 읽은 바이트**로 신원을 만든다).
         */
        fun of(
            tables: List<TableInfo>,
            sourceId: String,
            projectId: String = CollectionMetadata.DEFAULT_PROJECT_ID,
        ): SchemaModel = SchemaModel(
            tables,
            CollectionMetadata.fromContent(sourceId, SchemaCanonical.bytes(tables), "inline", projectId),
        )
    }
}

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

/**
 * 테이블 목록의 결정적 직렬화 — 라이브 JDBC 처럼 "읽은 원본 바이트" 가 없는 경로의 `contentHash` 입력이다.
 * 수집 순서에 흔들리지 않도록 이름으로 정렬한다. 시각·실행 식별자는 절대 넣지 않는다.
 */
object SchemaCanonical {
    fun bytes(tables: List<TableInfo>): ByteArray = buildString {
        for (t in tables.sortedBy { it.name }) {
            append("T\t").append(t.name).append('\n')
            // 컬럼은 정렬하지 않는다 — 순서 자체가 스키마의 일부이고, 두 수집 경로 모두
            // 순서가 결정적이다(DDL 은 선언 순, JDBC 는 ORDINAL_POSITION 순).
            for (c in t.columns) {
                append("C\t").append(c.name).append('\t').append(c.sqlType).append('\t')
                    .append(c.nullable).append('\n')
            }
            append("P\t").append(t.primaryKey.joinToString(",")).append('\n')
            // 정렬 키에 refColumns 까지 넣는다 — 빼면 같은 테이블·같은 FK 컬럼을 다른 대상 컬럼으로
            // 가리키는 두 FK 의 순서가 해시를 흔든다.
            for (f in t.foreignKeys.sortedBy {
                it.refTable + " " + it.fkColumns.joinToString(",") + " " + it.refColumns.joinToString(",")
            }) {
                append("F\t").append(f.fkColumns.joinToString(",")).append('\t')
                    .append(f.refTable).append('\t').append(f.refColumns.joinToString(",")).append('\n')
            }
        }
    }.toByteArray()
}
