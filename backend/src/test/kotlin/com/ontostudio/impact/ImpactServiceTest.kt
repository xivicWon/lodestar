package com.ontostudio.impact

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.rdb.ColumnInfo
import com.ontostudio.rdb.ForeignKeyInfo
import com.ontostudio.rdb.SchemaModel
import com.ontostudio.rdb.SchemaToOwlMapper
import com.ontostudio.rdb.TableInfo
import kotlin.test.Test
import kotlin.test.assertTrue

class ImpactServiceTest {
    private val base = "http://ex#"

    private fun holderOf(schema: SchemaModel): OntologyHolder {
        val ont = SchemaToOwlMapper().build(schema, base)
        val holder = OntologyHolder()
        holder.replace(ont, base)
        return holder
    }

    private fun service(holder: OntologyHolder) =
        ImpactService(holder, OntologyMapper(holder))

    @Test fun `impact of B has downstream C and upstream A via A to B to C object properties`() {
        // A --FK--> B --FK--> C  (each FK becomes an ObjectProperty domain→range)
        val schema = SchemaModel.of(sourceId = "db:test:impactservicetest", tables = listOf(
            TableInfo("A",
                listOf(ColumnInfo("ID", "int", false),
                       ColumnInfo("B_ID", "int", true)),
                listOf("ID"),
                listOf(ForeignKeyInfo(listOf("B_ID"), "B", listOf("ID")))),
            TableInfo("B",
                listOf(ColumnInfo("ID", "int", false),
                       ColumnInfo("C_ID", "int", true)),
                listOf("ID"),
                listOf(ForeignKeyInfo(listOf("C_ID"), "C", listOf("ID")))),
            TableInfo("C",
                listOf(ColumnInfo("ID", "int", false)),
                listOf("ID"), emptyList())
        ))
        val holder = holderOf(schema)
        val impact = service(holder).impact(base + "B")

        assertTrue(impact.downstream.contains(base + "C"),
            "expected downstream to contain C, got ${impact.downstream}")
        assertTrue(impact.upstream.contains(base + "A"),
            "expected upstream to contain A, got ${impact.upstream}")
    }
}
