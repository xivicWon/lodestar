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

class RelationJudgeTest {
    private val base = "http://ex#"

    /** 프롬프트를 캡처하고 지정된 응답을 돌려주는 페이크 어드바이저. */
    private class CapturingAdvisor(private val response: String) : AiAdvisor {
        var lastPrompt: String? = null
        override fun ask(prompt: String): String { lastPrompt = prompt; return response }
    }

    /** 호출되면 실패시키는 페이크(후보 0개일 때 AI 미호출 검증). */
    private class ThrowingAdvisor : AiAdvisor {
        override fun ask(prompt: String): String = throw AssertionError("AI must not be called")
    }

    private fun holderOf(schema: SchemaModel): OntologyHolder {
        val ont = SchemaToOwlMapper().build(schema, base)
        val holder = OntologyHolder()
        holder.replace(ont, base)
        return holder
    }

    // tbl_a(A_ID 자기 PK + CUST_NO·DEPT_CD 참조) → E2가 tbl_cust, tbl_dept 로 후보 2개를 낸다.
    private fun sampleSchema() = SchemaModel.of(sourceId = "db:test:relationjudgetest", tables = listOf(
        TableInfo("tbl_a",
            listOf(ColumnInfo("A_ID", "varchar(20)", false),
                   ColumnInfo("CUST_NO", "varchar(20)", true),
                   ColumnInfo("DEPT_CD", "varchar(20)", true)),
            listOf("A_ID"), emptyList()),
        TableInfo("tbl_cust",
            listOf(ColumnInfo("CUST_NO", "varchar(20)", false),
                   ColumnInfo("CUST_NM", "varchar(100)", true)),
            listOf("CUST_NO"), emptyList()),
        TableInfo("tbl_dept",
            listOf(ColumnInfo("DEPT_CD", "varchar(20)", false),
                   ColumnInfo("DEPT_NM", "varchar(100)", true)),
            listOf("DEPT_CD"), emptyList())
    ))

    @Test fun `judges candidates by index and keeps keep-first ordering`() {
        val holder = holderOf(sampleSchema())
        val service = RelationService(holder, OntologyMapper(holder))
        val candidates = service.suggest()
        assertTrue(candidates.isNotEmpty(), "expected E2 candidates, got $candidates")

        // 인덱스 0 만 keep=true, 나머지 인덱스는 응답에서 누락시켜 keep=false / 판정 없음 검증.
        val advisor = CapturingAdvisor("""[{"i":0,"keep":true,"reason":"ok"}]""")
        val judge = RelationJudge(advisor, holder, OntologyMapper(holder))
        val judged = judge.judge(candidates)

        assertEquals(candidates.size, judged.size, "judged length == candidates length")
        // keep 우선 정렬이므로 첫 항목이 keep=true.
        assertTrue(judged.first().keep, "keep=true 항목이 먼저 와야 함")
        assertEquals("ok", judged.first().reason)

        // 응답에 없던 후보들은 keep=false, reason="판정 없음".
        val dropped = judged.filter { !it.keep }
        assertTrue(dropped.isNotEmpty(), "누락 인덱스가 keep=false 로 있어야 함")
        assertTrue(dropped.all { it.reason == "판정 없음" }, "누락 인덱스 reason 은 '판정 없음'")

        // 프롬프트에 테이블 short-name 과 컬럼명이 포함.
        val prompt = advisor.lastPrompt!!
        assertTrue(prompt.contains("tbl_a"), "프롬프트에 tbl_a 포함: $prompt")
        assertTrue(prompt.contains("CUST_NO"), "프롬프트에 컬럼명 CUST_NO 포함: $prompt")
    }

    @Test fun `empty candidate list returns empty without calling advisor`() {
        val holder = holderOf(SchemaModel.of(emptyList(), "db:test:relationjudgetest"))
        val judge = RelationJudge(ThrowingAdvisor(), holder, OntologyMapper(holder))
        val judged = judge.judge(emptyList())
        assertTrue(judged.isEmpty())
    }

    @Test fun `keep-first ordering places all kept before dropped`() {
        val holder = holderOf(sampleSchema())
        val service = RelationService(holder, OntologyMapper(holder))
        val candidates = service.suggest()
        val advisor = CapturingAdvisor("""[{"i":0,"keep":false,"reason":"no"}]""")
        val judge = RelationJudge(advisor, holder, OntologyMapper(holder))
        val judged = judge.judge(candidates)
        // keep=false 전부여도 순서상 keep 이 있으면 앞에 온다(여기선 없음 → 모두 drop).
        val firstDropIdx = judged.indexOfFirst { !it.keep }
        val lastKeepIdx = judged.indexOfLast { it.keep }
        assertTrue(lastKeepIdx < firstDropIdx || lastKeepIdx == -1, "keep 이 drop 보다 앞")
        assertFalse(judged.first().keep)
    }
}
