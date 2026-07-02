package com.ontostudio.ai

import com.ontostudio.dto.ApiException
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Component
import java.util.concurrent.TimeUnit

/** AI 어드바이저의 교체 가능한 계약. 테스트는 페이크로 주입, 운영은 로컬 claude CLI. */
interface AiAdvisor {
    /** 프롬프트를 AI에 보내고 원문 응답 텍스트를 받는다. */
    fun ask(prompt: String): String
}

/**
 * 로컬 `claude -p <prompt>` CLI를 subprocess로 호출하는 구현. Anthropic API 키 불필요.
 * command/timeout은 프로퍼티로 오버라이드 가능(테스트는 생성자 직접 사용).
 */
@Component
class ClaudeCliAdvisor(
    @Value("\${lodestar.ai.command:claude}") private val command: String = "claude",
    @Value("\${lodestar.ai.timeout-sec:90}") private val timeoutSec: Long = 90,
) : AiAdvisor {
    override fun ask(prompt: String): String {
        val proc = try {
            ProcessBuilder(command, "-p", prompt).redirectErrorStream(false).start()
        } catch (e: Exception) {
            throw ApiException(HttpStatus.SERVICE_UNAVAILABLE, "ai_unavailable",
                "claude CLI 실행 실패(설치/PATH 확인): ${e.message}", null)
        }
        val finished = proc.waitFor(timeoutSec, TimeUnit.SECONDS)
        if (!finished) {
            proc.destroyForcibly()
            throw ApiException(HttpStatus.GATEWAY_TIMEOUT, "ai_timeout", "AI 응답 시간 초과", null)
        }
        val out = proc.inputStream.bufferedReader().readText().trim()
        if (proc.exitValue() != 0) {
            throw ApiException(HttpStatus.BAD_GATEWAY, "ai_failed",
                "claude CLI 오류(exit ${proc.exitValue()})", null)
        }
        return out
    }
}
