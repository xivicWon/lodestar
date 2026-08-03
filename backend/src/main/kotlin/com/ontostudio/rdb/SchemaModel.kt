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
 * [metadata] 는 **기본값이 없다**. 기본값을 두면 신원 없는 산출물이 계속 만들어지고,
 * 그게 #88 에서 `gate-l0-metadata-completeness` 가 0/5 였던 이유다(#113).
 *
 * @param issues   **문장·객체 단위** 제외·실패·부분수집. 세는 단위는 입력 문장 또는 객체다(gold R-F-4) —
 *                 전처리 분할로 한 문장이 여러 조각이 되어도 1건이다. 신원(metadata)과 보고(issues)는
 *                 다른 축이다: 무엇을 봤는가와 무엇을 못 했는가를 한 자리에 섞지 않는다(#114).
 * @param partials **입력 단위** 부분 성공 요약. `issues` 와 분모가 달라 섞으면 집계가 깨지므로 분리한다.
 */
data class SchemaModel(
    val tables: List<TableInfo>,
    val metadata: CollectionMetadata,
    val issues: List<CollectionIssue> = emptyList(),
    val partials: List<CollectionIssue> = emptyList(),
) {
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

/**
 * 수집된 테이블 하나.
 *
 * [schema] 는 이 테이블의 **소속**이다(#126). 소속이 없으면 `sales.orders` 와 `archive.orders` 가
 * 모델 단계에서 이미 한 항목으로 접히고, 테이블이 스키마 사이를 옮겨도 스냅샷 신원이 그대로다 —
 * "수집기가 실제로 본 것을 가리킨다" 는 계약(§5.1)이 그 지점에서 약해진다.
 *
 * `null` 은 **소속을 모른다**는 뜻이다(비한정 DDL 의 `CREATE TABLE orders`). 빈 문자열(이름이 빈
 * 스키마)과 다른 값이며, 정규화 바이트도 둘을 구분한다.
 *
 * **catalog 는 담지 않는다.** [MetadataService] 의 수집은 `conn.catalog` 하나로 한정되므로
 * 카탈로그는 한 스냅샷 안에서 상수이고, 그 신원은 이미 `sourceId`(vendor·host·port·database)가
 * 담는다. 넣으면 번들 샘플의 H2 카탈로그(`LEGACY_<nanoTime>`)가 해시에 섞여 같은 스냅샷이 매 실행
 * 다른 신원을 갖게 된다 — 소속을 담으려다 결정성을 잃는 교환이다.
 */
data class TableInfo(
    val name: String,
    val columns: List<ColumnInfo>,
    val primaryKey: List<String>,
    val foreignKeys: List<ForeignKeyInfo>,
    val schema: String? = null,
) {
    /** 소속을 포함한 표시용 이름. 소속을 모르면 이름 그대로다. 신원 계산에는 쓰지 않는다(§ [SchemaCanonical]). */
    val qualifiedName: String get() = if (schema == null) name else "$schema.$name"
}

data class ColumnInfo(val name: String, val sqlType: String, val nullable: Boolean)

/**
 * fkColumns(이 테이블의 컬럼) → refTable.refColumns 를 가리키는 외래키. 복합키는 리스트가 다중.
 *
 * [refSchema] 는 대상 테이블의 소속이다(#126). 없으면 동명 테이블이 여럿일 때 어느 쪽을 가리키는지
 * 알 수 없어, 하류(매퍼)가 임의로 하나를 고르게 된다. `null` 은 원본이 한정하지 않았다는 뜻이며,
 * 그때의 해석은 SQL 과 같은 방향으로 — 참조하는 쪽의 스키마 안을 먼저 본다([SchemaToOwlMapper]).
 */
data class ForeignKeyInfo(
    val fkColumns: List<String>,
    val refTable: String,
    val refColumns: List<String>,
    val refSchema: String? = null,
)

/**
 * 테이블 목록의 결정적 직렬화 — 라이브 JDBC 처럼 "읽은 원본 바이트" 가 없는 경로의 `contentHash` 입력이다.
 * 수집 순서에 흔들리지 않도록 이름으로 정렬한다. 시각·실행 식별자는 절대 넣지 않는다.
 */
object SchemaCanonical {

    /**
     * 식별자를 구분자와 겹치지 않게 만든다. **이 이스케이프가 없으면 직렬화가 단사가 아니다** —
     * 이름에 탭·개행이 들어가면 필드·레코드 경계가 밀려 구조가 다른 스키마가 같은 바이트가 되고,
     * 쉼표가 들어가면 `["a,b"]` 와 `["a","b"]` 가 구별되지 않는다. 그러면 contentHash 가 신원이 아니다.
     * 식별자는 DDL 요청 본문에서 그대로 올 수 있으므로(`/api/rdb/import/ddl`) 입력으로 취급한다.
     */
    private fun esc(s: String): String = s
        .replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
        .replace(",", "\\c")

    /**
     * 개수를 앞에 적는다. 그러지 않으면 `emptyList()` 와 `listOf("")` 가 **둘 다 빈 문자열**이 되어
     * 구별되지 않는다 — 키가 없는 테이블과 이름이 빈 키를 가진 테이블이 같은 신원을 갖게 된다.
     */
    private fun escList(items: List<String>): String =
        items.size.toString() + ":" + items.joinToString(",") { esc(it) }

    /**
     * 소속처럼 **없을 수 있는** 필드. 없으면 필드 자체를 적지 않는다 — 그래야 소속을 모르는 입력
     * (비한정 DDL)의 바이트가 이 변경 전과 같고, 이 이슈와 무관한 입력의 revision 이 갈리지 않는다.
     * 있으면 탭으로 구분된 필드 하나가 늘어난다. `null`(모른다)과 `""`(이름이 빈 스키마)는
     * 필드의 유무로 구분되므로 서로 다른 신원이다.
     */
    private fun optField(s: String?): String = if (s == null) "" else "\t" + esc(s)

    fun bytes(tables: List<TableInfo>): ByteArray = buildString {
        // 소속이 정렬 키에 없으면 동명 테이블의 상대 순서가 입력 순서(JDBC 반환 순서)에 맡겨진다.
        for (t in tables.sortedWith(
            compareBy<TableInfo, String?>(nullsFirst(naturalOrder())) { it.schema }.thenBy { it.name })) {
            append("T\t").append(esc(t.name)).append(optField(t.schema)).append('\n')
            // 컬럼은 정렬하지 않는다 — 순서 자체가 스키마의 일부이고, 두 수집 경로 모두
            // 순서가 결정적이다(DDL 은 선언 순, JDBC 는 ORDINAL_POSITION 순).
            for (c in t.columns) {
                append("C\t").append(esc(c.name)).append('\t').append(esc(c.sqlType)).append('\t')
                    .append(c.nullable).append('\n')
            }
            append("P\t").append(escList(t.primaryKey)).append('\n')
            // 정렬 키에 refColumns 까지 넣는다 — 빼면 같은 테이블·같은 FK 컬럼을 다른 대상 컬럼으로
            // 가리키는 두 FK 의 순서가 해시를 흔든다. 키를 잇는 구분자는 **esc 가 이스케이프하는 문자**여야
            // 한다 — 공백처럼 이스케이프되지 않는 문자로 이으면 이름에 든 공백이 키 경계를 밀어
            // 서로 다른 FK 가 같은 키가 되고(fk=["a b"]/ref="r" 와 fk=["b"]/ref="r a"),
            // 그러면 정렬이 입력 순서를 그대로 두어 JDBC 반환 순서에 따라 해시가 갈린다.
            for (f in t.foreignKeys.sortedBy {
                esc(it.refTable) + "\t" + escList(it.fkColumns) + "\t" + escList(it.refColumns) +
                    optField(it.refSchema)
            }) {
                append("F\t").append(escList(f.fkColumns)).append('\t')
                    .append(esc(f.refTable)).append('\t').append(escList(f.refColumns))
                    .append(optField(f.refSchema)).append('\n')
            }
        }
    }.toByteArray()
}
