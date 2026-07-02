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
     */
    private fun ingest(source: SchemaSource): ImportResult {
        val baseIri = "http://lodestar/rdb/${schemaMapper.slug(source.name)}#"
        holder.replace(schemaMapper.build(source.extract(), baseIri), baseIri)
        val merge = merger.merge()
        return ImportResult(ontologyMapper.meta(), merge)
    }

    @PostMapping("/import/ddl")
    fun importDdl(@RequestBody req: DdlImportRequest): ImportResult =
        ingest(DdlSource(req.sql, req.schemaName, ddlParser))

    @PostMapping("/import/connection")
    fun importConnection(@RequestBody info: ConnectionInfo): ImportResult =
        ingest(LiveJdbcSource(info, dbConnector, metadataService))

    /** E1-2: 번들 샘플 레거시를 H2에 적재 → 라이브 경로로 임포트. 데모/검증용 원클릭. */
    @PostMapping("/import/sample")
    fun importSample(): ImportResult =
        ingest(SampleSource(sampleLegacyDb, metadataService))
}
