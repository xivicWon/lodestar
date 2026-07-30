package com.ontostudio.security

import java.io.File
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * #115 — 규칙 스펙의 단일 원본 보장.
 *
 * 두 수집 경로(Kotlin · Python)가 같은 정책으로 가린다는 주장은 **같은 규칙 파일**을 쓴다는 사실에
 * 기댄다. 사본이 표류하면 그 주장이 조용히 거짓이 되므로 해시로 못박는다.
 */
class MaskingRuleSpecParityTest {

    private val repoRoot: File by lazy {
        var d = File("").absoluteFile
        while (!File(d, ".git").exists()) d = d.parentFile ?: error("리포 루트를 찾지 못했다")
        d
    }

    private fun sha256(f: File) =
        MessageDigest.getInstance("SHA-256").digest(f.readBytes()).joinToString("") { "%02x".format(it) }

    @Test fun `copies match the canonical spec`() {
        val canonical = File(repoRoot, "docs/superpowers/specs/security/masking-rules.v0.json")
        assertTrue(canonical.exists(), "규칙 단일 원본이 없다: ${canonical.path}")
        val copies = listOf(
            File(repoRoot, "backend/src/main/resources/com/ontostudio/security/masking-rules.v0.json"),
            File(repoRoot, "codegraph/src/lodestar_codegraph/masking-rules.v0.json"),
        )
        for (c in copies) assertEquals(sha256(canonical), sha256(c), "규칙 사본 표류: ${c.path}")
    }

    @Test fun `patterns keep cross-engine portability constraints`() {
        val rules = MaskingRules.load()
        for (r in rules.allow + rules.detect) {
            val p = r.regex.pattern
            assertTrue(!p.contains("\\d") && !p.contains("\\w"),
                "${r.id}: \\d·\\w 는 Python 에서 유니코드까지 먹어 두 엔진 결과가 갈린다")
            assertTrue(!p.contains("(?P<"), "${r.id}: Python 형식 이름있는 그룹")
            // Java/Kotlin 형식도 거부한다 — Kotlin 에서는 컴파일되지만 Python 에서는 실패한다(리뷰 LOD-053).
            // 역참조 lookbehind `(?<!`·`(?<=` 는 허용해야 하므로 '<' 뒤에 문자가 오는 경우만 잡는다.
            assertFalse(Regex("\\(\\?<[A-Za-z]").containsMatchIn(p),
                "${r.id}: Java 형식 이름있는 그룹은 Python re 에서 컴파일되지 않는다")
        }
    }

    /**
     * 사본 3종을 **똑같이** 잘못 바꾸면 해시 검사는 통과한다(리뷰 LOD-054). 규칙 구성 자체를 못박는다.
     * 이 목록과 Python 쪽 같은 목록(`test_rule_set_is_exactly_the_contracted_one`)은 서로 독립적인
     * 두 자리이며, 규칙을 늘리거나 줄이려면 두 곳을 의도적으로 고쳐야 한다.
     */
    @Test fun `rule set is exactly the contracted one`() {
        val rules = MaskingRules.load()
        assertEquals(
            listOf("ALLOW.MASK_TOKEN", "ALLOW.GIT_SHA", "ALLOW.CONTENT_HASH", "ALLOW.UUID",
                "ALLOW.JDBC_URL", "ALLOW.TIMESTAMP", "ALLOW.INTERNAL_ID"),
            rules.allow.map { it.id })
        assertEquals(
            listOf("SECRET.AWS_ACCESS_KEY_ID", "SECRET.GITHUB_TOKEN", "SECRET.SLACK_TOKEN",
                "SECRET.JWT", "SECRET.PRIVATE_KEY_BLOCK", "SECRET.URL_CREDENTIAL",
                "SECRET.KEYED_VALUE", "PII.KR_RRN", "PII.EMAIL", "PII.KR_PHONE",
                "PII.CARD_NO_DELIMITED", "PII.CARD_NO_PLAIN", "PII.KR_BANK_ACCOUNT",
                "PII.KR_BIZ_NO", "PII.IP_ADDRESS", "PII.KR_ADDRESS", "PII.KR_NAME"),
            rules.detect.map { it.id })
    }
}
