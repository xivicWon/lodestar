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

    // ---- allowlist 우선순위 (리뷰 후속) ------------------------------------------------

    /**
     * allowlist 는 "가리면 추적이 끊기는 값" 의 목록이고, 그 근거는 전부 **식별성**이다
     * (ALLOW.INTERNAL_ID: "내부 코드… 그 자체로 개인을 식별하지 않는다"). 식별성 논거로
     * **명시적 시크릿 문맥**을 덮으면 안 된다 — `password=` 는 그 값이 무엇을 닮았든 비밀이다.
     */
    @Test fun `explicit secret context beats the allowlist`() {
        // ABC123456 은 ALLOW.INTERNAL_ID(`[A-Z]{1,4}[0-9]{6,15}`) 와 겹친다
        assertEquals("password=[MASKED:PASSWORD]", engine.mask("password=ABC123456").text)
        assertEquals("apikey=[MASKED:PASSWORD]", engine.mask("apikey=AB1234567890").text)
        // 문맥 없는 같은 값은 여전히 음성이다 — allowlist 를 통째로 끄는 변경이 아니다
        assertEquals("order=ORD202401000001", engine.mask("order=ORD202401000001").text)
    }

    /** 멱등성은 예외다: 이미 가려진 자리를 다시 가리면 `[MASKED:...]` 가 중첩된다(#85). */
    @Test fun `already masked token is never re-masked even in secret context`() {
        val once = engine.mask("password=ABC123456").text
        assertEquals(once, engine.mask(once).text)
    }

    // ---- 부분 마스킹 0건 (리뷰 후속) ---------------------------------------------------

    /**
     * 탐지 스팬의 **모든 문자**가 치환돼야 한다. 원문 전체 문자열의 부재만 검사하면 한 글자만
     * 남기는 구현이 통과한다(리뷰 LOD-107).
     */
    @Test fun `every detected span is fully replaced`() {
        val samples = listOf(
            "password=ABC123456",
            "aws_secret_access_key = " + "A".repeat(41),
            "contact hong@example.com now",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA1234\n",
        )
        for (text in samples) {
            val r = engine.mask(text, MaskPolicy(lengthPreserving = true))
            for (s in r.spans) {
                val replaced = r.text.substring(s.start, s.end)
                assertTrue(replaced.all { it == '*' || it == '\n' },
                    "스팬 [${s.start},${s.end}) 이 완전히 치환되지 않았다: '$replaced' (입력: $text)")
            }
        }
    }

    /** 40자 경계 뒤에 문자가 더 있으면 접미사가 평문으로 남았다(리뷰 질문 — AWS 규칙 경계). */
    @Test fun `aws secret longer than forty chars leaves no plaintext suffix`() {
        val r = engine.mask("aws_secret_access_key = " + "A".repeat(41))
        assertEquals("aws_secret_access_key = [MASKED:AWS_SECRET_ACCESS_KEY]", r.text)
    }

    /**
     * 종료 표식이 없는 개인 키. 헤더만 가리면 Base64 본문이 그대로 남는다 — 로그 절단으로 흔히
     * 생기는 형태다. 뒤를 무한정 삼키지는 않는다: **연속된 Base64 본문까지만** 가린다.
     */
    @Test fun `truncated private key masks the key body but stops at non-base64 content`() {
        val text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA1234\nabcdEFGH0123\n" +
            "무관한 뒷내용은 남는다"
        val out = engine.mask(text).text
        assertFalse(out.contains("MIIEowIBAAKCAQEA1234"), "개인 키 본문이 남았다: $out")
        assertFalse(out.contains("abcdEFGH0123"), "개인 키 본문이 남았다: $out")
        assertTrue(out.contains("무관한 뒷내용은 남는다"), "무관한 내용까지 삼켰다: $out")
    }

    // ---- 키 토큰 경계 · 값 경계 (리뷰 ctx-2ba0a4 후속) ---------------------------------

    /**
     * 비밀 키워드는 **키 안의 온전한 토큰**이어야 한다. 키워드 뒤에 아무 소문자나 붙여도 되면
     * `secret`+`ary`, `token`+`izer` 가 비밀 키로 읽혀 무관한 설정값이 가려진다.
     * 경계는 camelCase·`_`·`-`·숫자다 — `secretAccessKey` 같은 진짜 키는 그대로 살아야 한다.
     */
    @Test fun `secret keyword must be a whole token inside the key`() {
        assertEquals("secretary=Kim", engine.mask("secretary=Kim").text)
        assertEquals("tokenizer=bert", engine.mask("tokenizer=bert").text)
        // 진짜 비밀 키는 계속 가린다 — 경계를 넘은 접미사(대문자·언더스코어)는 인정한다
        assertEquals("aws.secretAccessKey=[MASKED:AWS_SECRET_ACCESS_KEY]",
            engine.mask("aws.secretAccessKey=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY").text)
        assertEquals("password_hash=[MASKED:PASSWORD]", engine.mask("password_hash=abc123").text)
        assertEquals("spring.datasource.password=[MASKED:PASSWORD]",
            engine.mask("spring.datasource.password=P@ssw0rd-not-real-123").text)
    }

    /**
     * 따옴표 값은 **그 줄 안에서** 닫혀야 한다. 개행을 넘으면 다음 줄의 닫는 따옴표까지 한 값으로
     * 읽혀 그 사이의 무관한 설정이 통째로 사라진다 — 마스킹이 데이터를 지우는 것은 마스킹의 실패다.
     */
    @Test fun `quoted secret value does not cross a line`() {
        val text = "password=\"abc\nunrelated_setting=keep-me\nother=\""
        val out = engine.mask(text).text
        assertTrue(out.contains("unrelated_setting=keep-me"), "무관한 줄이 삼켜졌다: $out")
        // 줄 넘김을 막으면서 값을 통째로 놓치면 반대편 구멍이 생긴다 — 닫는 따옴표가 없으면
        // 줄 끝까지가 값이다.
        assertEquals("password=\"[MASKED:PASSWORD]\nunrelated_setting=keep-me\nother=\"", out)
    }
}
