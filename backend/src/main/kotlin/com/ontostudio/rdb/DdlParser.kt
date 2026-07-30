package com.ontostudio.rdb

import com.ontostudio.security.MaskLedger
import com.ontostudio.security.SqlTextMasker
import net.sf.jsqlparser.parser.CCJSqlParserUtil
import net.sf.jsqlparser.statement.create.table.CreateTable
import net.sf.jsqlparser.statement.create.table.ForeignKeyIndex
import org.springframework.stereotype.Component

/** 파싱 결과 + 그 실행에서 무엇을 몇 건 가렸는지(원문 없음 · #115). */
data class MaskedSchema(val schema: SchemaModel, val masking: Map<String, Any>)

/**
 * DDL 텍스트 → SchemaModel. CREATE TABLE 만 처리하고, 파싱 실패 구문은 조용히 건너뛴다
 * (조용한 스킵은 #114 의 몫이다).
 *
 * #115: 파싱 **전에** PII·시크릿 마스킹 단계를 통과한다. DDL 의 노출면은 주석과 DEFAULT 리터럴이며,
 * 마스킹은 리터럴·주석 안에서만 길이를 보존해 일어나므로 스키마 구조와 좌표는 그대로다.
 */
@Component
class DdlParser(private val masker: SqlTextMasker = SqlTextMasker()) {

    /**
     * [sourceId]·[projectId] 는 산출물의 수집 신원이 된다(#113 계약 v0).
     * DDL 텍스트는 커밋된 적 없는 입력이므로 revision 은 입력 바이트에서 파생한 `inline:` 이다.
     */
    fun parse(
        sql: String,
        sourceId: String = "db:ddl:schema",
        projectId: String = CollectionMetadata.DEFAULT_PROJECT_ID,
    ): SchemaModel = parseMasked(sql, sourceId, projectId).schema

    fun parseMasked(
        sql: String,
        sourceId: String = "db:ddl:schema",
        projectId: String = CollectionMetadata.DEFAULT_PROJECT_ID,
    ): MaskedSchema {
        val ledger = MaskLedger()
        val masked = masker.mask(sql, ledger)
        // 파싱은 마스킹된 텍스트로, 신원은 **원문 바이트**로 만든다(#113). 마스킹된 바이트로 신원을
        // 잡으면 PII 만 다른 두 입력이 같은 revision 으로 접혀 서로 다른 수집이 구분되지 않는다.
        // 해시는 단방향이라 원문이 산출물에 남지 않는다.
        return MaskedSchema(parseInternal(masked, sql, sourceId, projectId), ledger.summary())
    }

    private fun parseInternal(
        sql: String,
        identityBytes: String,
        sourceId: String,
        projectId: String,
    ): SchemaModel {
        val tables = mutableListOf<TableInfo>()
        // ';' 기준으로 개별 문장 분리 후 하나씩 파싱 → 트리거/함수 등 미지원 구문은 건너뛴다.
        for (raw in sql.split(";")) {
            val stmt = raw.trim()
            if (stmt.isEmpty()) continue
            val parsed = try { CCJSqlParserUtil.parse(stmt) } catch (e: Exception) { null } ?: continue
            if (parsed is CreateTable) tables.add(toTableInfo(parsed))
        }
        // 신원은 수집기가 **실제로 읽은 바이트**(입력 SQL)에서 나온다 — 파싱 결과가 아니라.
        return SchemaModel(
            tables,
            CollectionMetadata.fromContent(sourceId, identityBytes.toByteArray(), "inline", projectId),
        )
    }

    private fun unquote(s: String): String = s.trim().trim('"', '`', '[', ']')

    private fun toTableInfo(ct: CreateTable): TableInfo {
        val tableName = unquote(ct.table.name)
        val columns = (ct.columnDefinitions ?: emptyList()).map { cd ->
            val specs = (cd.columnSpecs ?: emptyList()).joinToString(" ").uppercase()
            ColumnInfo(unquote(cd.columnName), cd.colDataType.dataType, nullable = !specs.contains("NOT NULL"))
        }

        val pk = mutableListOf<String>()
        val fks = mutableListOf<ForeignKeyInfo>()

        // 1) 컬럼 인라인 제약: "PRIMARY KEY", "REFERENCES table(col)"
        for (cd in ct.columnDefinitions ?: emptyList()) {
            val specs = (cd.columnSpecs ?: emptyList()).joinToString(" ")
            val up = specs.uppercase()
            if (up.contains("PRIMARY KEY")) pk.add(unquote(cd.columnName))
            val m = Regex("REFERENCES\\s+([\\w\"`.]+)\\s*\\(\\s*([\\w\"`]+)\\s*\\)", RegexOption.IGNORE_CASE).find(specs)
            if (m != null) {
                fks.add(ForeignKeyInfo(
                    listOf(unquote(cd.columnName)),
                    unquote(m.groupValues[1].substringAfterLast('.')),
                    listOf(unquote(m.groupValues[2]))))
            }
        }

        // 2) 테이블-레벨 제약: getIndexes() 에 PRIMARY KEY / ForeignKeyIndex 로 등장
        for (idx in ct.indexes ?: emptyList()) {
            if (idx is ForeignKeyIndex) {
                fks.add(ForeignKeyInfo(
                    idx.columnsNames.map { unquote(it) },
                    unquote(idx.table.name),
                    (idx.referencedColumnNames ?: emptyList()).map { unquote(it) }))
            } else if (idx.type?.uppercase()?.contains("PRIMARY KEY") == true) {
                idx.columnsNames.forEach { pk.add(unquote(it)) }
            }
        }

        return TableInfo(tableName, columns, pk.distinct(), fks)
    }
}
