package com.ontostudio.rdb

import java.sql.Connection

/**
 * 스키마 입력 소스의 공통 계약 — 모든 입력(DDL/라이브 JDBC/샘플)이 SchemaModel로 수렴한다.
 * 새 DB 벤더나 입력 방식 추가 = 이 인터페이스 구현 하나 추가(하류: 매퍼·온톨로지·UI 무변경).
 */
interface SchemaSource {
    /** baseIri·표시에 쓰는 논리 이름 */
    val name: String
    fun extract(): SchemaModel
}

/** DDL 텍스트 소스 */
class DdlSource(
    private val sql: String,
    schemaName: String?,
    private val parser: DdlParser,
) : SchemaSource {
    override val name: String = schemaName?.takeIf { it.isNotBlank() } ?: "schema"
    override fun extract(): SchemaModel = parser.parse(sql, sourceId = "db:ddl:$name")
}

/** 라이브 JDBC 소스 (벤더 무관 — DatabaseMetaData 기반). 벤더 확장은 DbConnector/DbDialect에서 흡수. */
class LiveJdbcSource(
    private val info: ConnectionInfo,
    private val connector: DbConnector,
    private val metadata: MetadataService,
) : SchemaSource {
    override val name: String = info.database

    /**
     * sourceId 에 host·port 가 들어간다 — 빼면 서로 다른 서버의 같은 이름 DB(운영/스테이징)가
     * **같은 소스**로 기록되어 추적성이 그 지점에서 끊긴다. 자격증명은 넣지 않는다.
     */
    override fun extract(): SchemaModel =
        connector.open(info).use { conn: Connection ->
            metadata.extract(conn, sourceId = LiveJdbcSource.sourceId(info))
        }

    companion object {
        /**
         * vendor·database 를 **JDBC URL 과 같은 규칙**으로 정규화한다(DbConnector.jdbcUrl).
         * 그러지 않으면 같은 연결을 가리키는 `Postgresql` / `postgresql ` 같은 입력이 서로 다른
         * sourceId 를 만들어, 한 소스가 여러 신원으로 갈린다.
         */
        fun sourceId(info: ConnectionInfo): String {
            val vendor = info.vendor.trim().lowercase()
            val host = info.host.trim().lowercase()   // DNS 는 대소문자를 구분하지 않는다
            val database = info.database.trim()
            return "db:jdbc:$vendor://$host:${info.port}/$database"
        }
    }
}

/** 번들 샘플 레거시 소스 */
class SampleSource(
    private val sampleDb: SampleLegacyDb,
    private val metadata: MetadataService,
) : SchemaSource {
    override val name: String = "legacy"

    override fun extract(): SchemaModel =
        sampleDb.open().use { conn: Connection ->
            metadata.extract(conn, sourceId = SOURCE_ID, revisionScheme = REVISION_SCHEME)
        }

    companion object {
        /**
         * gold manifest 가 고정한 sourceId — 증거가 이어지려면 같은 이름이어야 한다(I2 §6.1).
         * 번들 샘플을 읽는 곳은 **전부 이 상수**를 쓴다. 문자열을 각자 적으면 한쪽만 바뀌어도
         * 같은 소스가 두 신원으로 갈리고, 그건 호출부에서 보이지 않는다.
         */
        const val SOURCE_ID = "db:legacy-sample"

        /** 리포에 번들된 리소스다 — 커밋 sha 를 지어내지 않는다. */
        const val REVISION_SCHEME = "bundle"
    }
}
