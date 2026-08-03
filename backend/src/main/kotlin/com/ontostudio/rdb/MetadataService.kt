package com.ontostudio.rdb

import org.springframework.stereotype.Service
import java.sql.Connection

/** JDBC Connection → SchemaModel. DatabaseMetaData 표준 API만 사용(드라이버 무관). */
@Service
class MetadataService {

    /** FK 한 건을 KEY_SEQ 순서로 모으는 자리. 대상의 소속(refSchema)까지 함께 든다(#126). */
    private class FkBuild(
        val refTable: String,
        val refSchema: String?,
        val fkColumns: java.util.TreeMap<Int, String> = java.util.TreeMap(),
        val refColumns: java.util.TreeMap<Int, String> = java.util.TreeMap(),
    )

    // PostgreSQL/MySQL 시스템 스키마·카탈로그(MySQL은 DB=카탈로그) 모두 제외.
    private val systemNames = setOf(
        "information_schema", "pg_catalog", "pg_toast",
        "mysql", "performance_schema", "sys"
    )

    /** 수집 대상 객체 타입. 이 밖의 타입은 조용히 사라지지 않고 사유와 함께 보고된다(#114). */
    private val collectedTypes = arrayOf("TABLE")

    /**
     * [sourceId] 에 **기본값을 두지 않는다.** 기본값이 있으면 서로 다른 서버의 카탈로그가 같은 신원으로
     * 기록될 수 있고, 그것을 호출부에서 알아채지 못한다. 라이브 경로의 값은
     * [LiveJdbcSource.sourceId] 가 만든다(vendor·host·port·database).
     *
     * [revisionScheme] 는 이 카탈로그가 어디서 왔는지를 드러낸다 — 라이브 DB 는 `live`,
     * 리포에 번들된 샘플을 적재한 것이면 `bundle`. 둘 다 git 커밋이 아니므로 sha 를 지어내지 않는다(#113).
     */
    fun extract(
        conn: Connection,
        sourceId: String,
        projectId: String = CollectionMetadata.DEFAULT_PROJECT_ID,
        revisionScheme: String = "live",
    ): SchemaModel {
        val md = conn.metaData
        val tables = mutableListOf<TableInfo>()
        val issues = mutableListOf<CollectionIssue>()

        // (catalog, schema, table) 목록 수집 — 행별 cat/schem을 이후 조회에 그대로 사용(벤더 무관).
        val ids = mutableListOf<Triple<String?, String?, String>>()
        md.getTables(conn.catalog, null, "%", collectedTypes).use { rs ->
            while (rs.next()) {
                val cat = rs.getString("TABLE_CAT")
                val schem = rs.getString("TABLE_SCHEM")
                if (cat != null && cat.lowercase() in systemNames) continue
                if (schem != null && schem.lowercase() in systemNames) continue
                ids.add(Triple(cat, schem, rs.getString("TABLE_NAME")))
            }
        }

        // 타입 필터가 걸러낸 객체(VIEW·SYNONYM 등)를 사유와 함께 남긴다. 이 목록이 없으면
        // '수집 범위 밖' 과 '수집했는데 없음' 이 L0 에서 이미 구분되지 않는다(EVL §2.5).
        //
        // 제외 판정은 **신원**으로 한다 — TABLE_TYPE 문자열로 비교하면 벤더 표기 차이에 걸린다
        // (H2 는 테이블을 "BASE TABLE" 로 보고하므로 전 테이블이 미지원으로 오보고된다).
        val collected = ids.toSet()
        md.getTables(conn.catalog, null, "%", null).use { rs ->
            while (rs.next()) {
                val type = rs.getString("TABLE_TYPE") ?: "UNKNOWN"
                val cat = rs.getString("TABLE_CAT")
                val schem = rs.getString("TABLE_SCHEM")
                if (cat != null && cat.lowercase() in systemNames) continue
                if (schem != null && schem.lowercase() in systemNames) continue
                val name = rs.getString("TABLE_NAME")
                if (Triple(cat, schem, name) in collected) continue
                issues.add(CollectionIssue(
                    IssueKind.SKIPPED, CollectionReason.UNSUPPORTED_OBJECT_TYPE,
                    "getTables 의 타입 필터가 ${collectedTypes.joinToString("·")} 만 수집한다 — " +
                        "$type 은 수집기가 다루지 않는 객체 타입이다",
                    "jdbc://${cat ?: ""}/${schem ?: ""}/$name", name))
            }
        }

        for ((catalog, schem, name) in ids) {
            val columns = mutableListOf<ColumnInfo>()
            md.getColumns(catalog, schem, name, "%").use { rs ->
                while (rs.next()) {
                    columns.add(ColumnInfo(
                        rs.getString("COLUMN_NAME"),
                        rs.getString("TYPE_NAME"),
                        rs.getInt("NULLABLE") == java.sql.DatabaseMetaData.columnNullable))
                }
            }

            val pk = sortedMapOf<Int, String>()
            md.getPrimaryKeys(catalog, schem, name).use { rs ->
                while (rs.next()) pk[rs.getInt("KEY_SEQ")] = rs.getString("COLUMN_NAME")
            }

            // FK: FK_NAME 별로 묶고 KEY_SEQ 순서 유지
            val fkBuild = linkedMapOf<String, FkBuild>()
            md.getImportedKeys(catalog, schem, name).use { rs ->
                while (rs.next()) {
                    val fkName = rs.getString("FK_NAME") ?: "${name}_${rs.getString("FKCOLUMN_NAME")}"
                    val entry = fkBuild.getOrPut(fkName) {
                        FkBuild(rs.getString("PKTABLE_NAME"), rs.getString("PKTABLE_SCHEM"))
                    }
                    val seq = rs.getInt("KEY_SEQ")
                    entry.fkColumns[seq] = rs.getString("FKCOLUMN_NAME")
                    entry.refColumns[seq] = rs.getString("PKCOLUMN_NAME")
                }
            }
            val foreignKeys = fkBuild.values.map {
                ForeignKeyInfo(
                    it.fkColumns.values.toList(), it.refTable, it.refColumns.values.toList(),
                    refSchema = it.refSchema)
            }

            // schem 이 이 테이블의 소속이다(#126). 카탈로그는 담지 않는다 — 이 수집은 conn.catalog
            // 하나로 한정되므로 스냅샷 안에서 상수이고, 그 신원은 sourceId 가 이미 담는다.
            tables.add(TableInfo(name, columns, pk.values.toList(), foreignKeys, schema = schem))
        }
        // JDBC 경로에는 '읽은 원본 바이트' 가 없다 — 수집기가 실제로 본 카탈로그의 정규화 표현을 해싱한다.
        return SchemaModel(
            tables,
            CollectionMetadata.fromContent(sourceId, SchemaCanonical.bytes(tables), revisionScheme, projectId),
            issues.sortedBy { it.locator },
        )    }
}
