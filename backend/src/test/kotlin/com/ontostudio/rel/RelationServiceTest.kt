package com.ontostudio.rel

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.rdb.ColumnInfo
import com.ontostudio.rdb.SchemaModel
import com.ontostudio.rdb.SchemaToOwlMapper
import com.ontostudio.rdb.TableInfo
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class RelationServiceTest {
    private val base = "http://ex#"

    private fun holderOf(schema: SchemaModel): OntologyHolder {
        val ont = SchemaToOwlMapper().build(schema, base)
        val holder = OntologyHolder()
        holder.replace(ont, base)
        return holder
    }

    private fun service(holder: OntologyHolder) =
        RelationService(holder, OntologyMapper(holder))

    @Test fun `proposes implicit relation TB_ORD_HD to TB_CUST_MST via CUST_NO`() {
        // CUST_NO is a plain column (no declared FK) → becomes a DataProperty
        val schema = SchemaModel(listOf(
            TableInfo("TB_ORD_HD",
                listOf(ColumnInfo("ORD_NO", "varchar(20)", false),
                       ColumnInfo("CUST_NO", "varchar(20)", true)),
                listOf("ORD_NO"), emptyList()),
            TableInfo("TB_CUST_MST",
                listOf(ColumnInfo("CUST_NO", "varchar(20)", false),
                       ColumnInfo("CUST_NM", "varchar(100)", true)),
                listOf("CUST_NO"), emptyList())
        ))
        val holder = holderOf(schema)
        val candidates = service(holder).suggest()

        val hit = candidates.firstOrNull {
            it.fromIri == base + "TB_ORD_HD" &&
            it.toIri == base + "TB_CUST_MST" &&
            it.viaColumn == "CUST_NO"
        }
        assertTrue(hit != null,
            "expected TB_ORD_HD→TB_CUST_MST via CUST_NO, got $candidates")
        assertEquals("hasCust", hit.suggestedName)
        assertTrue(hit.confidence > 0.0)
    }
}
