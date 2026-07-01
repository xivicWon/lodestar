package com.ontostudio.rdb

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.OntologyMetaDto
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
    private val ontologyMapper: OntologyMapper
) {
    private fun ingest(schema: SchemaModel, dbName: String): OntologyMetaDto {
        val baseIri = "http://lodestar/rdb/${schemaMapper.slug(dbName)}#"
        val ont = schemaMapper.build(schema, baseIri)
        holder.replace(ont, baseIri)
        return ontologyMapper.meta()
    }

    @PostMapping("/import/ddl")
    fun importDdl(@RequestBody req: DdlImportRequest): OntologyMetaDto =
        ingest(ddlParser.parse(req.sql), req.schemaName ?: "schema")

    @PostMapping("/import/connection")
    fun importConnection(@RequestBody info: ConnectionInfo): OntologyMetaDto =
        dbConnector.open(info).use { conn -> ingest(metadataService.extract(conn), info.database) }
}
