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
        val schema = SchemaModel.of(sourceId = "db:test:relationservicetest", tables = listOf(
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

    @Test fun `does not propose a relation from a class own PK column (false positive)`() {
        // TB_ORD_HD.ORD_NO 는 자기 PK. TB_ORD_DTL 이 있어도 ORD_NO 로 관계를 만들면 안 된다.
        val schema = SchemaModel.of(sourceId = "db:test:relationservicetest", tables = listOf(
            TableInfo("TB_ORD_HD",
                listOf(ColumnInfo("ORD_NO", "varchar(20)", false),
                       ColumnInfo("CUST_NO", "varchar(20)", true)),
                listOf("ORD_NO"), emptyList()),
            TableInfo("TB_ORD_DTL",
                listOf(ColumnInfo("ORD_NO", "varchar(20)", false),
                       ColumnInfo("ORD_SEQ", "integer", false)),
                listOf("ORD_NO", "ORD_SEQ"), emptyList()),
            TableInfo("TB_CUST_MST",
                listOf(ColumnInfo("CUST_NO", "varchar(20)", false)),
                listOf("CUST_NO"), emptyList())
        ))
        val candidates = service(holderOf(schema)).suggest()

        // ORD_NO 를 통한 관계는 하나도 없어야 한다 (자기 식별자)
        assertTrue(candidates.none { it.viaColumn == "ORD_NO" },
            "ORD_NO(자기 PK)로 만든 관계가 있으면 안 됨: $candidates")
        // 정상 관계(CUST_NO→TB_CUST_MST)는 여전히 나와야 한다
        assertTrue(candidates.any { it.viaColumn == "CUST_NO" && it.toIri == base + "TB_CUST_MST" })
    }

    @Test fun `exact core-name match yields high confidence`() {
        val schema = SchemaModel.of(sourceId = "db:test:relationservicetest", tables = listOf(
            TableInfo("TB_EMP",
                listOf(ColumnInfo("EMP_NO", "varchar(10)", false),
                       ColumnInfo("DEPT_CD", "varchar(5)", true)),
                listOf("EMP_NO"), emptyList()),
            TableInfo("TB_DEPT",
                listOf(ColumnInfo("DEPT_CD", "varchar(5)", false),
                       ColumnInfo("DEPT_NM", "varchar(80)", true)),
                listOf("DEPT_CD"), emptyList())
        ))
        val candidates = service(holderOf(schema)).suggest()
        val hit = candidates.firstOrNull {
            it.fromIri == base + "TB_EMP" && it.toIri == base + "TB_DEPT" && it.viaColumn == "DEPT_CD"
        }
        assertTrue(hit != null, "expected TB_EMP→TB_DEPT via DEPT_CD, got $candidates")
        assertEquals(0.9, hit.confidence)
    }

    @Test fun `empty ontology yields no candidates`() {
        val candidates = service(holderOf(SchemaModel.of(emptyList(), "db:test:relationservicetest"))).suggest()
        assertTrue(candidates.isEmpty())
    }
}
