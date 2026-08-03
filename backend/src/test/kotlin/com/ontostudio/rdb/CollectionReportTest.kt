package com.ontostudio.rdb

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/** #129 — 응답 보고를 만드는 순수 로직. 세 경로의 좌표 규약과 `complete` 의 뜻을 고정한다. */
class CollectionReportTest {

    private fun schema(issues: List<CollectionIssue> = emptyList(), partials: List<CollectionIssue> = emptyList()) =
        SchemaModel(
            listOf(TableInfo("T", emptyList(), emptyList(), emptyList())),
            CollectionMetadata.fromContent("db:test", ByteArray(0), "inline"),
            issues, partials)

    private fun issue(kind: IssueKind) = CollectionIssue(kind, "CODE", "사유", "#L1", "T")

    @Test fun `locator scheme follows the input path`() {
        assertEquals("line", CollectionReport.locatorScheme(SchemaSource.KIND_DDL))
        assertEquals("jdbc", CollectionReport.locatorScheme(SchemaSource.KIND_JDBC))
        assertEquals("jdbc", CollectionReport.locatorScheme(SchemaSource.KIND_SAMPLE))
    }

    /**
     * 등록되지 않은 입력 경로는 **조용히 jdbc 로 취급되지 않는다**. 포괄 기본값을 두면 새 경로가
     * 행 기반 좌표를 내면서 jdbc 로 광고되고, 소비자는 그 좌표를 잘못 읽는다.
     */
    @Test fun `an unregistered source kind fails instead of guessing a scheme`() {
        val e = assertFailsWith<IllegalStateException> { CollectionReport.locatorScheme("csv") }
        assertTrue(e.message!!.contains("csv"), e.message!!)
    }

    /** 정당한 제외만 있으면 완전 수집이다 — 그래도 항목은 사유와 함께 남는다(I3 R20). */
    @Test fun `skipped alone does not break completeness but is still reported`() {
        val r = CollectionReport.of(SchemaSource.KIND_DDL, schema(issues = listOf(issue(IssueKind.SKIPPED))))
        assertTrue(r.complete)
        assertEquals(1, r.skipped)
        assertEquals(1, r.issues.size)
        assertEquals("사유", r.issues[0].reason)
    }

    @Test fun `failed or partial makes the import incomplete`() {
        assertTrue(!CollectionReport.of(SchemaSource.KIND_DDL, schema(issues = listOf(issue(IssueKind.FAILED)))).complete)
        assertTrue(!CollectionReport.of(SchemaSource.KIND_DDL, schema(partials = listOf(issue(IssueKind.PARTIAL)))).complete)
    }

    /** 분모가 다른 두 리스트를 섞지 않는다 — partial 건수는 양쪽 모두를 센다. */
    @Test fun `partial counts both the issue level and the input level entries`() {
        val r = CollectionReport.of(
            SchemaSource.KIND_JDBC,
            schema(issues = listOf(issue(IssueKind.PARTIAL)), partials = listOf(issue(IssueKind.PARTIAL))))
        assertEquals(2, r.partial)
        assertEquals(1, r.issues.size)
        assertEquals(1, r.partials.size)
    }
}
