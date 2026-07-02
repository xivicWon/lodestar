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
    override fun extract(): SchemaModel = parser.parse(sql)
}

/** 라이브 JDBC 소스 (벤더 무관 — DatabaseMetaData 기반). 벤더 확장은 DbConnector/DbDialect에서 흡수. */
class LiveJdbcSource(
    private val info: ConnectionInfo,
    private val connector: DbConnector,
    private val metadata: MetadataService,
) : SchemaSource {
    override val name: String = info.database
    override fun extract(): SchemaModel =
        connector.open(info).use { conn: Connection -> metadata.extract(conn) }
}

/** 번들 샘플 레거시 소스 */
class SampleSource(
    private val sampleDb: SampleLegacyDb,
    private val metadata: MetadataService,
) : SchemaSource {
    override val name: String = "legacy"
    override fun extract(): SchemaModel =
        sampleDb.open().use { conn: Connection -> metadata.extract(conn) }
}
