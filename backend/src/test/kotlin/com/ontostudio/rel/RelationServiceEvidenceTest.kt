package com.ontostudio.rel

import com.ontostudio.ai.AiAdvisor
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.rdb.ColumnInfo
import com.ontostudio.rdb.SchemaModel
import com.ontostudio.rdb.SchemaToOwlMapper
import com.ontostudio.rdb.TableInfo
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** E13: 관계 후보 판단 근거(evidence) 산출 검증. */
class RelationServiceEvidenceTest {
    private val base = "http://ex#"

    private fun holderOf(schema: SchemaModel): OntologyHolder {
        val ont = SchemaToOwlMapper().build(schema, base)
        val holder = OntologyHolder()
        holder.replace(ont, base)
        return holder
    }

    private fun service(holder: OntologyHolder) = RelationService(holder, OntologyMapper(holder))

    // TB_ASSET_MASTER.GROUP_CD 가 TB_GROUP(완전일치)·TB_USER_GROUP_ASSET(토큰일치) 둘 다에 매칭.
    private fun ambiguousSchema() = SchemaModel(listOf(
        TableInfo("TB_ASSET_MASTER",
            listOf(ColumnInfo("ASSET_NO", "varchar(20)", false),
                   ColumnInfo("GROUP_CD", "varchar(10)", true)),
            listOf("ASSET_NO"), emptyList()),
        TableInfo("TB_GROUP",
            listOf(ColumnInfo("GROUP_NO", "varchar(10)", false),
                   ColumnInfo("GROUP_NM", "varchar(100)", true)),
            listOf("GROUP_NO"), emptyList()),
        TableInfo("TB_USER_GROUP_ASSET",
            listOf(ColumnInfo("USER_ID", "varchar(20)", false),
                   ColumnInfo("GROUP_SEQ", "integer", true),
                   ColumnInfo("ASSET_NO", "varchar(20)", true)),
            listOf("USER_ID", "GROUP_SEQ"), emptyList())
    ))

    @Test fun `token match carries evidence with alternatives, similar keys, and columns`() {
        val cands = service(holderOf(ambiguousSchema())).suggest()

        val tok = cands.first {
            it.toIri == base + "TB_USER_GROUP_ASSET" && it.viaColumn == "GROUP_CD"
        }
        val ev = tok.evidence
        assertEquals("token", ev.matchType, "부분(토큰) 일치")
        assertEquals(0.6, tok.confidence)
        assertEquals("GROUP", ev.matchStem)
        assertFalse(ev.targetHasSameColumn, "대상에 GROUP_CD 컬럼 없음")
        assertTrue(ev.targetSimilarKeys.any { it.equals("GROUP_SEQ", ignoreCase = true) },
            "같은 스템 유사키 GROUP_SEQ 노출: ${ev.targetSimilarKeys}")
        // 더 유력한 완전일치(0.9) 대안이 모호성으로 보여야 한다.
        assertTrue(ev.alternatives.any {
            it.toIri == base + "TB_GROUP" && it.confidence == 0.9 && it.matchType == "exact"
        }, "완전일치 대안 TB_GROUP 포함: ${ev.alternatives}")
        // 양쪽 컬럼 목록이 채워진다.
        assertTrue(ev.fromColumns.any { it.equals("GROUP_CD", ignoreCase = true) })
        assertTrue(ev.toColumns.any { it.equals("GROUP_SEQ", ignoreCase = true) })
        assertTrue(ev.cardinalityReason.isNotBlank())
    }

    @Test fun `exact core-name match is labeled exact with 0_9 confidence`() {
        val cands = service(holderOf(ambiguousSchema())).suggest()
        val ex = cands.first { it.toIri == base + "TB_GROUP" && it.viaColumn == "GROUP_CD" }
        assertEquals("exact", ex.evidence.matchType)
        assertEquals(0.9, ex.confidence)
        assertEquals("N:1 추정", ex.evidence.cardinality, "대상이 그룹/코드 성격 → N:1 추정")
    }

    @Test fun `evidence propagates through AI judge`() {
        val holder = holderOf(ambiguousSchema())
        val cands = service(holder).suggest()
        val advisor = object : AiAdvisor {
            override fun ask(prompt: String) = """[{"i":0,"keep":true,"reason":"ok"}]"""
        }
        val judged = RelationJudge(advisor, holder, OntologyMapper(holder)).judge(cands)
        // 판정 결과에도 근거가 실려야 한다.
        assertTrue(judged.all { it.evidence.fromColumns.isNotEmpty() },
            "JudgedCandidate 에 evidence 전파")
        val tok = judged.first { it.toIri == base + "TB_USER_GROUP_ASSET" && it.viaColumn == "GROUP_CD" }
        assertEquals("token", tok.evidence.matchType)
    }
}
