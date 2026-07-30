package com.ontostudio.security

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * #115 — SQL 마스킹은 값·주석만 건드리고 구조와 좌표를 보존한다.
 * 마스킹이 스키마를 바꾸거나 좌표를 밀면 수집을 망가뜨린 것이다(#85 수용조건).
 */
class SqlTextMaskerTest {

    private val masker = SqlTextMasker()

    @Test fun `masks literal values only`() {
        val sql = "INSERT INTO TB_CUST (NM, TEL) VALUES ('홍길동', '010-1234-5678');"
        val out = masker.mask(sql)
        assertFalse(out.contains("홍길동"))
        assertFalse(out.contains("010-1234-5678"))
        assertTrue(out.contains("INSERT INTO TB_CUST (NM, TEL) VALUES ("))
        assertEquals("INSERT INTO TB_CUST (NM, TEL) VALUES ('***', '*************');", out)
    }

    /**
     * 좌표 보존의 단위는 **문자와 행**이다(규칙 스펙 `maskToken.note`). 다중 바이트 문자를 ASCII '*'
     * 로 바꾸므로 UTF-8 바이트 오프셋은 보존되지 않으며(리뷰 LOD-055), 근거 좌표는 `path#Lnn` 즉
     * 행 기준이므로 검사할 불변식은 **행 번호 안정성**이다.
     */
    @Test fun `preserves char offsets and line numbers so locators stay valid`() {
        val sql = "-- 담당 hong@example.com\nCREATE TABLE T (ID CHAR(10));"
        val out = masker.mask(sql)
        assertEquals(sql.length, out.length)
        assertEquals(sql.indexOf("CREATE"), out.indexOf("CREATE"))
        assertEquals(sql.lines().indexOfFirst { it.startsWith("CREATE") },
            out.lines().indexOfFirst { it.startsWith("CREATE") })
        assertFalse(out.contains("hong@example.com"))
    }

    @Test fun `multiline literal keeps line numbers`() {
        // 여러 줄 값(PEM 개인 키)을 통째로 '*' 로 덮으면 개행이 사라져 뒤따르는 행 좌표가 밀린다.
        val pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAfake0000\n-----END RSA PRIVATE KEY-----"
        val sql = "INSERT INTO T VALUES ('$pem');\n-- MARKER\nCREATE TABLE U (ID INT);"
        val out = masker.mask(sql)
        assertFalse(out.contains("MIIEowIBAAKCAQEAfake0000"), "개인 키 본문이 남았다")
        assertEquals(sql.count { it == '\n' }, out.count { it == '\n' })
        assertEquals(sql.lines().indexOfFirst { it.contains("MARKER") },
            out.lines().indexOfFirst { it.contains("MARKER") })
    }

    @Test fun `postgres escape strings do not end the literal early`() {
        // E'\'' 를 종료로 읽으면 그 뒤가 리터럴 밖으로 분류돼 민감 값이 마스킹되지 않는다.
        val sql = "INSERT INTO T VALUES (E'o\\'brien', '900101-1234567');"
        val out = masker.mask(sql)
        assertFalse(out.contains("900101-1234567"), "이스케이프 문자열 뒤의 값이 새어나갔다: $out")
    }

    @Test fun `nested block comments stay inside the comment`() {
        val sql = "/* outer /* inner */ rrn=900101-1234567 */ CREATE TABLE T (ID INT);"
        val out = masker.mask(sql)
        assertFalse(out.contains("900101-1234567"), "중첩 주석 안의 값이 새어나갔다: $out")
        assertTrue(out.endsWith("CREATE TABLE T (ID INT);"))
    }

    @Test fun `does not touch identifiers that look like rules`() {
        // 컬럼명이 규칙에 걸려 바뀌면 스키마가 망가진다 — 리터럴·주석 밖은 손대지 않는다.
        val sql = "CREATE TABLE TB_900101 (RRN_900101_1234567 CHAR(14), IP_203_0_113_47 VARCHAR(20));"
        assertEquals(sql, masker.mask(sql))
    }

    @Test fun `handles escaped quotes without running past the literal`() {
        val sql = "INSERT INTO T VALUES ('o''brien 010-1234-5678', 'ITM000000001');"
        val out = masker.mask(sql)
        assertFalse(out.contains("010-1234-5678"))
        assertTrue(out.contains("'ITM000000001'"), "내부 코드는 allowlist 로 남는다: $out")
    }

    @Test fun `block comments are masked`() {
        val sql = "/* key: ghp_${"A".repeat(36)} */ CREATE TABLE T (ID INT);"
        val out = masker.mask(sql)
        assertFalse(out.contains("ghp_"))
        assertTrue(out.endsWith("CREATE TABLE T (ID INT);"))
    }

    @Test fun `ledger counts what was masked without recording plaintext`() {
        val ledger = MaskLedger()
        masker.mask("INSERT INTO T VALUES ('900101-1234567', 'hong@example.com');", ledger)
        assertEquals(2, ledger.total)
        val summary = ledger.summary().toString()
        assertTrue(summary.contains("KR_RRN") && summary.contains("EMAIL"))
        assertFalse(summary.contains("900101-1234567"))
        assertFalse(summary.contains("hong@example.com"))
    }

    @Test fun `name heuristic is off in comments and on in values`() {
        // '추정용' 같은 3음절 업무용어를 인명으로 오탐하면 주석의 의미 신호가 깎인다.
        assertEquals("-- AI 의미 추정용 신호\n", masker.mask("-- AI 의미 추정용 신호\n"))
        assertEquals("('***')", masker.mask("('추정용')"))
    }
}
