package com.ontostudio.savepoint

import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ConfirmationStoreTest {

    private val tmp = Files.createTempFile("confirmations", ".json")

    @AfterTest fun cleanup() {
        Files.deleteIfExists(tmp)
        Files.deleteIfExists(java.nio.file.Paths.get("$tmp.corrupt"))
    }

    private fun store() = ConfirmationStore(tmp.toString())

    @Test fun `confirm makes iri confirmed and appears in all`() {
        val s = store()
        s.confirm(ConfirmedFact("iri#A", "고객 마스터", "class"))
        assertTrue(s.isConfirmed("iri#A"))
        assertFalse(s.isConfirmed("iri#B"))
        assertEquals(listOf(ConfirmedFact("iri#A", "고객 마스터", "class")), s.all())
    }

    @Test fun `persists to file and reloads in a new instance`() {
        store().confirm(ConfirmedFact("iri#A", "고객 마스터", "class"))
        // 새 인스턴스가 같은 파일에서 재로드하는지 = 재임포트/재기동 생존
        val reloaded = store()
        assertTrue(reloaded.isConfirmed("iri#A"))
        assertEquals("고객 마스터", reloaded.all().single().label)
    }

    @Test fun `corrupt file is backed up and store starts empty (no silent data loss)`() {
        Files.write(tmp, "{{ this is not valid json".toByteArray())
        val s = store() // 예외 없이 시작해야 함
        assertTrue(s.all().isEmpty())
        // 손상 파일은 조용히 삭제되지 않고 .corrupt 로 보존되어야 함
        assertTrue(Files.exists(java.nio.file.Paths.get("$tmp.corrupt")))
    }

    @Test fun `remove deletes and persists`() {
        val s = store()
        s.confirm(ConfirmedFact("iri#A", "고객 마스터", "class"))
        s.remove("iri#A")
        assertFalse(s.isConfirmed("iri#A"))
        // 파일에도 반영되어 새 인스턴스에서 없어야 함
        assertFalse(store().isConfirmed("iri#A"))
    }
}
