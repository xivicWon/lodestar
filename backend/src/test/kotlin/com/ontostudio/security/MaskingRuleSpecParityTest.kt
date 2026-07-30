package com.ontostudio.security

import java.io.File
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
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
            assertTrue(!p.contains("(?P<"), "${r.id}: 이름있는 그룹 문법이 언어마다 다르다")
        }
        assertTrue(rules.allow.isNotEmpty() && rules.detect.size >= 10)
    }
}
