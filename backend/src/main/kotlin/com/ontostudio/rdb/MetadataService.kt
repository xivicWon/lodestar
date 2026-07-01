package com.ontostudio.rdb

import org.springframework.stereotype.Service
import java.sql.Connection

/** JDBC Connection → SchemaModel. DatabaseMetaData 표준 API만 사용(드라이버 무관). */
@Service
class MetadataService {
    private val systemSchemas = setOf("information_schema", "pg_catalog", "pg_toast")

    fun extract(conn: Connection): SchemaModel {
        val md = conn.metaData
        val catalog = conn.catalog
        val tables = mutableListOf<TableInfo>()

        // (schema, table) 목록 수집
        val ids = mutableListOf<Pair<String?, String>>()
        md.getTables(catalog, null, "%", arrayOf("TABLE")).use { rs ->
            while (rs.next()) {
                val schem = rs.getString("TABLE_SCHEM")
                if (schem != null && schem.lowercase() in systemSchemas) continue
                ids.add(schem to rs.getString("TABLE_NAME"))
            }
        }

        for ((schem, name) in ids) {
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
        return SchemaModel(tables)
    }
}
