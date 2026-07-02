package com.ontostudio.ai

import com.ontostudio.dto.ApiException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class ClaudeCliAdvisorTest {

    /** 실제 CLI 대신 /bin/echo 로 subprocess 실행·인자 전달·stdout 캡처를 검증. */
    @Test fun `ask spawns command and captures stdout`() {
        val advisor = ClaudeCliAdvisor(command = "/bin/echo", timeoutSec = 10)
        val out = advisor.ask("HELLO_PROMPT")
        assertTrue(out.contains("HELLO_PROMPT"), "stdout should echo the prompt, got=$out")
    }

    @Test fun `missing command yields ai_unavailable`() {
        val advisor = ClaudeCliAdvisor(command = "definitely_not_a_real_binary_xyz", timeoutSec = 5)
        val e = assertFailsWith<ApiException> { advisor.ask("x") }
        assertEquals("ai_unavailable", e.error)
    }
}
