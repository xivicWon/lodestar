package com.ontostudio.rdb

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * E1-1: 지저분한 레거시 샘플이 실제로 대규모·레거시 특성을 갖고, 스캔 시 온톨로지로 뜨는지 검증.
 * 토이(2~3테이블)가 아니라 진짜에 가까운 조건에서 파이프라인이 버티는지 본다.
 */
class LegacySampleFixtureTest {

    private fun sampleSql(): String =
        javaClass.getResource("/com/ontostudio/rdb/legacy-sample.sql")!!.readText()

    @Test fun `legacy sample parses into many tables`() {
        val schema = DdlParser().parse(sampleSql())
        assertTrue(schema.tables.size >= 25, "대규모여야 함, got=${schema.tables.size}")
        assertTrue(schema.tables.any { it.name == "TB_CUST_MST" }, "암호명 테이블 존재")
    }

    @Test fun `legacy sample has almost no explicit FKs (messy legacy)`() {
        val schema = DdlParser().parse(sampleSql())
        val fkCount = schema.tables.sumOf { it.foreignKeys.size }
        assertEquals(1, fkCount, "레거시 특성: 명시 FK는 거의 없음(예외 1개만)")
    }

    @Test fun `legacy sample has several composite-key tables`() {
        val schema = DdlParser().parse(sampleSql())
        val composite = schema.tables.count { it.primaryKey.size >= 2 }
        assertTrue(composite >= 5, "복합키 테이블 다수, got=$composite")
    }

    @Test fun `mapping produces one class per table`() {
        val schema = DdlParser().parse(sampleSql())
        val ont = SchemaToOwlMapper().build(schema, "http://lodestar/rdb/legacy#")
        assertEquals(schema.tables.size, ont.classesInSignature().count().toInt())
    }
}
