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
        fun sourceId(info: ConnectionInfo): String =
            "db:jdbc:${info.vendor}://${info.host}:${info.port}/${info.database}"
    }
}

/** 번들 샘플 레거시 소스 */
class SampleSource(
    private val sampleDb: SampleLegacyDb,
    private val metadata: MetadataService,
) : SchemaSource {
    override val name: String = "legacy"

    /** gold manifest 가 고정한 sourceId 와 같은 값을 쓴다 — 증거가 이어지려면 같은 이름이어야 한다(I2 §6.1). */
    override fun extract(): SchemaModel =
        sampleDb.open().use { conn: Connection ->
            metadata.extract(conn, sourceId = "db:legacy-sample", revisionScheme = "bundle")
        }
}
