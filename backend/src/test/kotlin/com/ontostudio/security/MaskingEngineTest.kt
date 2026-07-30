package com.ontostudio.security

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * #115 — Kotlin 엔진의 **계약**을 직접 고정한다.
 *
 * 이 파일이 생기기 전까지 Kotlin 엔진의 동작은 증거 파일이 Python 증거와 같은지로만 관측됐다.
 * 그 방식은 "두 엔진이 같다" 는 말할 수 있어도 "각 엔진이 무엇을 보장하는가" 는 말하지 못한다 —
 * 증거를 다시 만들면 새 동작이 그대로 새 기준이 되고, 두 엔진이 **같은 방향으로** 틀리면 아무것도
 * 붉어지지 않는다. 그래서 Python `tests/test_mask.py` 가 고정한 것과 **같은 계약**을 여기서도
 * 독립적으로 단언한다(같은 규칙 원본을 쓰지만 단언은 서로 베끼지 않는다).
 */
class MaskingEngineTest {

    private val engine = MaskingEngine()

    // ---- 기본 동작 --------------------------------------------------------------------

    @Test fun `masks email and reports rule id`() {
        val r = engine.mask("contact hong@example.com now")
        assertEquals("contact [MASKED:EMAIL] now", r.text)
        assertEquals(mapOf("PII.EMAIL" to 1), r.byRule)
        assertEquals(listOf("PII.EMAIL" to "EMAIL"), r.spans.map { it.ruleId to it.cls })
    }

    @Test fun `records no plaintext`() {
        val r = engine.mask("password=P@ssw0rd-not-real-123")
        val record = r.byRule.toString() + r.spans.map { listOf(it.start, it.end, it.ruleId, it.cls) }
        assertFalse(record.contains("P@ssw0rd"))
    }

    @Test fun `is deterministic in text counts and spans`() {
        val text = "rrn=900101-1234567 mail=a.b@c.co.kr ip=203.0.113.47"
        val a = engine.mask(text)
        val b = engine.mask(text)
        assertEquals(a.text, b.text)
        assertEquals(a.byRule, b.byRule)
        assertEquals(a.spans, b.spans)
    }

    @Test fun `is idempotent`() {
        val once = engine.mask("owner=홍길동 rrn=900101-1234567").text
        assertEquals(once, engine.mask(once).text)
    }

    // ---- 정책 ------------------------------------------------------------------------

    @Test fun `allowlist beats detection and can be turned off`() {
        val sha = "3c27259fe6c979e00912c5e3686c611a28cb977e"
        assertEquals("build=$sha", engine.mask("build=$sha").text)
        // allowlist 를 끄면 같은 값이 가려진다 — 설정이 실제로 판정을 바꾼다는 증거
        assertTrue(engine.mask("token=$sha", MaskPolicy(allowlistEnabled = false)).text != "token=$sha")
    }

    @Test fun `disabled class is not masked`() {
        assertEquals("owner=홍길동",
            engine.mask("owner=홍길동", MaskPolicy(disabledClasses = setOf("NAME"))).text)
        assertEquals("owner=[MASKED:NAME]", engine.mask("owner=홍길동").text)
    }

    @Test fun `length preserving keeps width and newlines`() {
        val r = engine.mask("'900101-1234567'", MaskPolicy(lengthPreserving = true))
        assertEquals("'" + "*".repeat("900101-1234567".length) + "'", r.text)

        val pem = "-----BEGIN RSA PRIVATE KEY-----\nAAAAfakebody0000\n-----END RSA PRIVATE KEY-----"
        val text = "a\n$pem\nMARKER"
        val masked = engine.mask(text, MaskPolicy(lengthPreserving = true)).text
        assertEquals(text.length, masked.length)
        assertEquals(text.count { it == '\n' }, masked.count { it == '\n' })
        assertEquals(text.lines().indexOf("MARKER"), masked.lines().indexOf("MARKER"))
        assertFalse(masked.contains("AAAAfakebody0000"))
    }

    // ---- 규칙별 계약 ------------------------------------------------------------------

    @Test fun `luhn guards the undelimited card rule`() {
        assertEquals("no=[MASKED:CARD_NO]", engine.mask("no=4111111111111111").text)
        assertEquals("qty=1234567812345678", engine.mask("qty=1234567812345678").text)
    }

    @Test fun `spec order resolves overlapping detections`() {
        assertEquals(mapOf("SECRET.AWS_ACCESS_KEY_ID" to 1),
            engine.mask("aws.accessKeyId=AKIAIOSFODNN7EXAMPLE").byRule)
    }

    @Test fun `aws secret access key is attributed to its own class`() {
        // 일반 키드 시크릿 규칙도 이 값을 가리지만, 보고서가 클래스별 건수를 주장하므로 귀속이 맞아야 한다.
        val r = engine.mask("aws.secretAccessKey=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        assertEquals(mapOf("SECRET.AWS_SECRET_ACCESS_KEY" to 1), r.byRule)
        assertEquals(mapOf("AWS_SECRET_ACCESS_KEY" to 1), r.byClass)
    }

    @Test fun `github tokens of both generations are masked`() {
        val classic = "ghp_" + "A".repeat(36)
        val fineGrained = "github_pat_" + "1".repeat(22) + "_" + "a".repeat(59)
        for (token in listOf(classic, fineGrained)) {
            val out = engine.mask("github.token=$token").text
            assertFalse(out.contains(token), token.take(11))
            assertEquals("github.token=[MASKED:GITHUB_TOKEN]", out)
        }
    }

    @Test fun `private key block is masked whole and truncated block keeps the tail`() {
        val pem = "-----BEGIN EC PRIVATE KEY-----\nBBBBfakebody1111\n-----END EC PRIVATE KEY-----"
        val out = engine.mask("key='$pem'").text
        assertFalse(out.contains("BBBBfakebody1111"))
        assertFalse(out.contains("-----END EC PRIVATE KEY-----"))

        val truncated = engine.mask("-----BEGIN PRIVATE KEY-----\nTAIL_MARKER").text
        assertFalse(truncated.contains("BEGIN PRIVATE KEY"))
        assertTrue(truncated.contains("TAIL_MARKER"), "END 없는 입력에서 뒤를 끝까지 삼켰다")
    }

    @Test fun `url credential with at sign or colon is fully masked`() {
        val r = engine.mask("postgres://user:p@ssw0rd-x@host:5432/db")
        assertEquals("postgres://user:[MASKED:URL_CREDENTIAL]@host:5432/db", r.text)
        assertFalse(engine.mask("mysql://admin:my:pass@host/db").text.contains("my:pass"))
        // 자격증명이 없는 URL 은 건드리지 않는다
        assertEquals("jdbc:postgresql://localhost:5432/lodestar",
            engine.mask("jdbc:postgresql://localhost:5432/lodestar").text)
    }

    @Test fun `quoted secret with spaces is masked to the closing quote`() {
        // 대안 그룹 세 갈래를 각각 지나간다: 큰따옴표 · 홑따옴표 · 따옴표 없음
        assertEquals("password = \"[MASKED:PASSWORD]\" other=keep",
            engine.mask("password = \"pw with spaces\" other=keep").text)
        assertEquals("app.secret = '[MASKED:PASSWORD]' tail=keep",
            engine.mask("app.secret = 'multi word secret' tail=keep").text)
        assertEquals("password=[MASKED:PASSWORD], next=keep",
            engine.mask("password=Pw-9zzz-not-real, next=keep").text)
    }

    @Test fun `scheme prefixes stay and only the token is masked`() {
        val jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJmYWtlIn0.c2ln"
        val out = engine.mask("authorization=Bearer $jwt").text
        assertEquals("authorization=Bearer [MASKED:JWT]", out)
    }

    @Test fun `zero width value produces no span`() {
        assertEquals("secret=\"\"", engine.mask("secret=\"\"").text)
        assertEquals("token=''", engine.mask("token=''").text)
    }

    @Test fun `name heuristic needs field delimiters`() {
        assertEquals("owner=[MASKED:NAME]", engine.mask("owner=홍길동").text)
        // 산문 한가운데의 3음절 낱말은 성으로 시작해도 인명이 아니다
        assertEquals("각 줄의 정답(마스킹 대상 여부)", engine.mask("각 줄의 정답(마스킹 대상 여부)").text)
    }
}
