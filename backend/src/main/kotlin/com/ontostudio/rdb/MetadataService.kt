package com.ontostudio.rdb

import org.springframework.stereotype.Service
import java.sql.Connection

/** JDBC Connection → SchemaModel. DatabaseMetaData 표준 API만 사용(드라이버 무관). */
@Service
class MetadataService {
    // PostgreSQL/MySQL 시스템 스키마·카탈로그(MySQL은 DB=카탈로그) 모두 제외.
    private val systemNames = setOf(
        "information_schema", "pg_catalog", "pg_toast",
        "mysql", "performance_schema", "sys"
    )

    /**
     * [revisionScheme] 는 이 카탈로그가 어디서 왔는지를 드러낸다 — 라이브 DB 는 `live`,
     * 리포에 번들된 샘플을 적재한 것이면 `bundle`. 둘 다 git 커밋이 아니므로 sha 를 지어내지 않는다(#113).
     */
    fun extract(
        conn: Connection,
        sourceId: String = "db:jdbc",
        projectId: String = CollectionMetadata.DEFAULT_PROJECT_ID,
        revisionScheme: String = "live",
    ): SchemaModel {
        val md = conn.metaData
        val tables = mutableListOf<TableInfo>()

        // (catalog, schema, table) 목록 수집 — 행별 cat/schem을 이후 조회에 그대로 사용(벤더 무관).
        val ids = mutableListOf<Triple<String?, String?, String>>()
        md.getTables(conn.catalog, null, "%", arrayOf("TABLE")).use { rs ->
            while (rs.next()) {
                val cat = rs.getString("TABLE_CAT")
                val schem = rs.getString("TABLE_SCHEM")
                if (cat != null && cat.lowercase() in systemNames) continue
                if (schem != null && schem.lowercase() in systemNames) continue
                ids.add(Triple(cat, schem, rs.getString("TABLE_NAME")))
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
            val fkBuild = linkedMapOf<String, Triple<String, java.util.TreeMap<Int, String>, java.util.TreeMap<Int, String>>>()
            md.getImportedKeys(catalog, schem, name).use { rs ->
                while (rs.next()) {
                    val fkName = rs.getString("FK_NAME") ?: "${name}_${rs.getString("FKCOLUMN_NAME")}"
                    val entry = fkBuild.getOrPut(fkName) {
                        Triple(rs.getString("PKTABLE_NAME"), java.util.TreeMap(), java.util.TreeMap())
                    }
                    val seq = rs.getInt("KEY_SEQ")
                    entry.second[seq] = rs.getString("FKCOLUMN_NAME")
                    entry.third[seq] = rs.getString("PKCOLUMN_NAME")
                }
            }
            val foreignKeys = fkBuild.values.map {
                ForeignKeyInfo(it.second.values.toList(), it.first, it.third.values.toList())
            }

            tables.add(TableInfo(name, columns, pk.values.toList(), foreignKeys))
        }
        // JDBC 경로에는 '읽은 원본 바이트' 가 없다 — 수집기가 실제로 본 카탈로그의 정규화 표현을 해싱한다.
        return SchemaModel(
            tables,
            CollectionMetadata.fromContent(sourceId, SchemaCanonical.bytes(tables), revisionScheme, projectId),
        )
    }
}
