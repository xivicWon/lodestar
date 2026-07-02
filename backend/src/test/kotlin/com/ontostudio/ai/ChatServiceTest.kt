package com.ontostudio.ai

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.ClassService
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ChatServiceTest {

    /** 프롬프트를 붙잡아두고 고정 답을 돌려주는 페이크 AI. */
    private class FakeAdvisor(val answer: String) : AiAdvisor {
        var lastPrompt: String = ""
        override fun ask(prompt: String): String { lastPrompt = prompt; return answer }
    }

    private fun fixture(answer: String): Triple<ChatService, FakeAdvisor, ClassService> {
        val holder = OntologyHolder()
        val mapper = OntologyMapper(holder)
        val fake = FakeAdvisor(answer)
        return Triple(ChatService(fake, holder, mapper), fake, ClassService(holder, mapper))
    }

    @Test fun `ask returns advisor answer`() {
        val (svc, _, _) = fixture("고객은 주문을 가진다.")
        assertEquals("고객은 주문을 가진다.", svc.ask("고객은 무엇인가?").answer)
    }

    @Test fun `prompt contains class labels and the question`() {
        val (svc, fake, classes) = fixture("ok")
        classes.create("고객", null)
        classes.create("주문", null)

        svc.ask("고객과 주문의 관계는?")

        assertTrue(fake.lastPrompt.contains("고객"), "프롬프트에 클래스 라벨(고객)이 포함돼야 함")
        assertTrue(fake.lastPrompt.contains("주문"), "프롬프트에 클래스 라벨(주문)이 포함돼야 함")
        assertTrue(fake.lastPrompt.contains("고객과 주문의 관계는?"), "프롬프트에 사용자 질문이 포함돼야 함")
    }
}
