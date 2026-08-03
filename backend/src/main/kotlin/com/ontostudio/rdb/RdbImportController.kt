package com.ontostudio.rdb

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.savepoint.ConfirmationMerger
import com.ontostudio.savepoint.ImportResult
import org.springframework.web.bind.annotation.*

data class DdlImportRequest(val sql: String, val schemaName: String? = null)

@RestController
@RequestMapping("/api/rdb")
class RdbImportController(
    private val dbConnector: DbConnector,
    private val metadataService: MetadataService,
    private val ddlParser: DdlParser,
    private val schemaMapper: SchemaToOwlMapper,
    private val holder: OntologyHolder,
    private val ontologyMapper: OntologyMapper,
    private val sampleLegacyDb: SampleLegacyDb,
    private val merger: ConfirmationMerger
) {
    /**
     * 모든 입력 경로의 공통 종착: 소스 → SchemaModel → 온톨로지 주입.
     * 주입 직후 확정 저장소를 새 온톨로지에 병합해 확정 라벨을 자동 복원한다(E9).
     *
     * #129: 수집 결과를 **매퍼에 넘기기 전에 붙잡아** 응답에 싣는다. 이전에는 `source.extract()` 가
     * 인자 자리에서 소비돼 `tables` 만 하류로 가고 `issues`·`partials` 는 여기서 사라졌다 —
     * 수집기는 말하는데 전달 경로가 삼키는 구조였다. 세 입력 경로가 이 한 자리로 수렴하므로
     * 보고 모양도 여기서 하나로 정해진다.
     */
    private fun ingest(source: SchemaSource): ImportResult {
        val baseIri = "http://lodestar/rdb/${schemaMapper.slug(source.name)}#"
        val schema = source.extract()
        holder.replace(schemaMapper.build(schema, baseIri), baseIri)
        val merge = merger.merge()
        return ImportResult(ontologyMapper.meta(), merge, CollectionReport.of(source.kind, schema))
    }

    @PostMapping("/import/ddl")
    fun importDdl(@RequestBody req: DdlImportRequest): ImportResult =
        ingest(DdlSource(req.sql, req.schemaName, ddlParser))

    @PostMapping("/import/connection")
    fun importConnection(@RequestBody info: ConnectionInfo): ImportResult =
        ingest(LiveJdbcSource(info, dbConnector, metadataService))

    /** 접속 검증 + DB(카탈로그) 목록. database 없이 접속해 스캔할 DB를 고르는 용도. */
    @PostMapping("/databases")
    fun listDatabases(@RequestBody info: ConnectionInfo): List<String> =
        dbConnector.open(info).use { conn ->
            val out = mutableListOf<String>()
            conn.metaData.catalogs.use { rs -> while (rs.next()) out.add(rs.getString(1)) }
            out.filter { it.lowercase() !in setOf("information_schema", "mysql", "performance_schema", "sys") }
        }

    /** E1-2: 번들 샘플 레거시를 H2에 적재 → 라이브 경로로 임포트. 데모/검증용 원클릭. */
    @PostMapping("/import/sample")
    fun importSample(): ImportResult =
        ingest(SampleSource(sampleLegacyDb, metadataService))
}
