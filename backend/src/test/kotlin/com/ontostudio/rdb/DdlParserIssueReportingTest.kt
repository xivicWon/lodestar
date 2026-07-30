package com.ontostudio.rdb

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * #114 — 수집 제외·실패·부분복구가 **반환형에** 남는가.
 *
 * 기준은 gold(#99) `failures.json` 의 `reported` 다. 여기서 재는 것은 정확도가 아니라 정직성이다:
 * 못 한 것을 못 했다고 좌표·사유와 함께 말하는가, 부분 복구를 조용히 성공으로 위장하지 않는가.
 */
class DdlParserIssueReportingTest {

    private val repoRoot: File by lazy {
        var d = File("").absoluteFile
        while (!File(d, ".git").exists()) d = d.parentFile ?: error("리포 루트를 찾지 못했다")
        d
    }

    private fun fixture(name: String) =
        File(repoRoot, "docs/superpowers/specs/gold/fixtures/failure/$name").readText()

    private fun parse(name: String) = DdlParser().parse(fixture(name))

    @Test fun `파싱 실패는 좌표·사유와 함께 보고된다 (F_DB_BROKEN_SYNTAX)`() {
        val out = parse("db-broken-syntax.sql")
        assertEquals(emptyList(), out.tables.map { it.name }, "깨진 문장에서 테이블이 나오면 안 된다")
        assertEquals(1, out.issues.size, "실패 1건이 보고돼야 한다: ${out.issues}")
        val i = out.issues.single()
        assertEquals(IssueKind.FAILED, i.kind)
        assertEquals(CollectionReason.PARSE_ERROR, i.reasonCode)
        assertEquals("#L3-L7", i.locator)
        assertTrue(i.target.contains("TB_BROKEN"), "대상: ${i.target}")
        assertTrue(i.reason.isNotBlank(), "사유 없는 보고는 미보고다(R-F-2)")
    }

    @Test fun `미지원 문장은 조각이 아니라 문장 단위로 보고된다 (F_DB_UNSUPPORTED_TRIGGER)`() {
        val out = parse("db-unsupported-trigger.sql")
        assertEquals(emptyList(), out.tables.map { it.name })
        // R-F-4: PL/pgSQL 본문의 ';' 로 부풀지 않고 2건이다.
        assertEquals(
            listOf("#L6-L9", "#L11-L17"), out.issues.map { it.locator },
            "본문 안 ';' 로 실패 건수가 부풀면 실행 간 비교가 불가능해진다(R-F-4): ${out.issues}")
        assertTrue(out.issues.all { it.kind == IssueKind.SKIPPED })
        assertTrue(out.issues.all { it.reasonCode == CollectionReason.UNSUPPORTED_STATEMENT })
        assertTrue(out.issues[0].target.contains("TRG_ORD_AUDIT"), out.issues[0].target)
        assertTrue(out.issues[1].target.contains("FN_ORD_AUDIT"), out.issues[1].target)
    }

    @Test fun `조용한 부분복구는 없다 — 실패한 테이블은 산출하지 않고 보고한다 (F_DB_PARTIAL_EXTRACT)`() {
        val out = parse("db-partial-extract.sql")
        assertEquals(listOf("TB_OK_ONE", "TB_OK_TWO"), out.tables.map { it.name }.sorted())
        assertTrue(out.tables.none { it.name == "TB_BAD_MIDDLE" },
            "쉼표 누락으로 컬럼 하나만 살아난 테이블을 산출하면 조용한 부분복구다")

        val failed = out.issues.filter { it.kind == IssueKind.FAILED }
        assertEquals(1, failed.size, "실패 1건: ${out.issues}")
        assertEquals(CollectionReason.PARSE_ERROR, failed[0].reasonCode)
        assertEquals("#L11-L14", failed[0].locator)
        assertTrue(failed[0].target.contains("TB_BAD_MIDDLE"))
        assertTrue(failed[0].reason.contains("부분"), "부분복구를 버렸다는 사실이 사유에 남아야 한다: ${failed[0].reason}")

        val skipped = out.issues.filter { it.kind == IssueKind.SKIPPED }
        assertEquals(1, skipped.size)
        assertEquals(CollectionReason.UNSUPPORTED_STATEMENT, skipped[0].reasonCode)
        assertEquals("#L16", skipped[0].locator)
        assertTrue(skipped[0].target.contains("IX_OK_ONE_NM"))
    }

    @Test fun `부분 성공 입력은 partial 로 명시된다`() {
        val out = parse("db-partial-extract.sql")
        assertEquals(1, out.partials.size, "성공과 실패가 섞인 입력은 partial 이다: ${out.partials}")
        val p = out.partials.single()
        assertEquals(IssueKind.PARTIAL, p.kind)
        assertEquals(CollectionReason.PARTIAL_COLLECTION, p.reasonCode)
        assertTrue(p.reason.contains("2"), "산출 대 실패의 분모가 사유에 남아야 한다: ${p.reason}")

        // 전량 성공 입력은 partial 이 아니다.
        assertTrue(DdlParser().parse("CREATE TABLE T (ID INT PRIMARY KEY);").partials.isEmpty())
    }

    @Test fun `정당한 제외도 사유와 분모로 보고된다 (legacy-sample INSERT·VIEW)`() {
        val sqlPath = "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql"
        val out = DdlParser().parse(File(repoRoot, sqlPath).readText(), sqlPath)

        assertEquals(27, out.tables.size, "고정 입력의 테이블 27건은 그대로 수집돼야 한다")
        assertTrue(out.issues.none { it.kind == IssueKind.FAILED }, "실패: ${out.issues.filter { it.kind == IssueKind.FAILED }}")

        val outOfScope = out.issues.filter { it.reasonCode == CollectionReason.OUT_OF_SCOPE_BY_DESIGN }
        assertEquals(8, outOfScope.size, "행 데이터 8건은 정당한 제외이지만 사유와 함께 보고한다(I3 R20)")
        val unsupported = out.issues.filter { it.reasonCode == CollectionReason.UNSUPPORTED_STATEMENT }
        assertEquals(1, unsupported.size, "CREATE VIEW 1건")
        assertTrue(unsupported[0].target.contains("VW_ORD_SUMMARY"))

        // 좌표는 경로를 포함하고, 그 행에서 대상이 실제로 조회된다(#88 V5 와 같은 검사).
        val lines = File(repoRoot, sqlPath).readLines()
        for (i in out.issues) {
            val m = Regex("^([^#]+)#L(\\d+)").find(i.locator) ?: error("좌표 형식 아님: ${i.locator}")
            assertEquals(sqlPath, m.groupValues[1])
            val line = lines[m.groupValues[2].toInt() - 1]
            assertTrue(line.contains(i.target), "좌표가 가리키는 행에 대상이 없다: ${i.locator} → $line")
        }

        // I3 R2 — 입력 = 산출 + 실패 + 제외. 문장 36건이 남는 자리 없이 설명된다.
        assertEquals(36, out.tables.size + out.issues.size)
    }
}
