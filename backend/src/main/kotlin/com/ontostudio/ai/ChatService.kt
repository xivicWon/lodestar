package com.ontostudio.ai

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import org.springframework.stereotype.Service

/** AI 챗 요청/응답 (E6). */
data class ChatQuestion(val question: String)
data class ChatAnswer(val answer: String)

/**
 * 현재 온톨로지 구조를 컨텍스트로 삼아 사용자의 질문에 답하는 AI 챗 (E6).
 * 기존 [AiAdvisor] 계약(로컬 claude CLI / 테스트 페이크)을 재사용한다.
 */
@Service
class ChatService(
    private val advisor: AiAdvisor,
    private val holder: OntologyHolder,
    private val mapper: OntologyMapper,
) {
    fun ask(question: String): ChatAnswer = ChatAnswer(advisor.ask(buildPrompt(question)))

    private fun shortName(iri: String): String {
        val frag = iri.substringAfterLast('#', "")
        return if (frag.isNotEmpty()) frag else iri.substringAfterLast('/')
    }

    /** 현재 온톨로지의 클래스/객체속성을 사람이 읽기 쉬운 컨텍스트로 직렬화한다. */
    internal fun buildContext(): String = synchronized(holder.lock) {
        val ont = holder.ontology
        val sb = StringBuilder()
        sb.appendLine("## 클래스 (짧은이름 · 라벨)")
        val classes = ont.classesInSignature()
            .filter { !it.isOWLThing && !it.isOWLNothing }
            .toList().sortedBy { it.iri.toString() }
        if (classes.isEmpty()) sb.appendLine("- (없음)")
        for (c in classes) {
            val label = mapper.labelOf(c.iri)
            sb.appendLine("- ${shortName(c.iri.toString())}" + if (label != null) " · $label" else "")
        }
        sb.appendLine("## 객체 속성 (도메인 → 레인지 : 라벨)")
        val props = ont.objectPropertiesInSignature().toList().map { mapper.objectPropertyDto(it) }
        if (props.isEmpty()) sb.appendLine("- (없음)")
        for (p in props) {
            val d = p.domains.joinToString(", ") { shortName(it) }.ifEmpty { "?" }
            val r = p.ranges.joinToString(", ") { shortName(it) }.ifEmpty { "?" }
            val label = p.label ?: shortName(p.iri)
            sb.appendLine("- $d → $r : $label")
        }
        sb.toString()
    }

    /** 컨텍스트 + 질문 + 지시문으로 한국어 프롬프트를 구성한다. */
    internal fun buildPrompt(question: String): String = buildString {
        appendLine("당신은 아래 온톨로지에 대해서만 답하는 도우미다. 다음은 현재 온톨로지의 구조다:")
        appendLine()
        append(buildContext())
        appendLine()
        appendLine("질문: $question")
        appendLine()
        appendLine("위에 주어진 온톨로지에 근거해서만 한국어로 간결하게 답하라. 온톨로지에 없는 내용은 지어내지 말고 모른다고 답하라.")
    }
}
