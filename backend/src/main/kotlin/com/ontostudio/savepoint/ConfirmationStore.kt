package com.ontostudio.savepoint

import com.fasterxml.jackson.core.type.TypeReference
import com.fasterxml.jackson.databind.ObjectMapper
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths

/** 운영자가 승인해 고정된 사실(세이브포인트). 온톨로지와 분리된 별도 저장소에 영속(E8). */
data class ConfirmedFact(val iri: String, val label: String, val kind: String)

/**
 * 확정 사실을 IRI로 키잉한 맵. 파일(JSON)로 영속되어 재임포트/재로드에도 살아남는다(E8 D1).
 * Jackson으로 `List<Map>` 형태 직렬화(코틀린 모듈 불필요, [SemanticEnricher.parse]와 동일 방식).
 * 스레드 안전(모든 연산 synchronized).
 */
@Component
class ConfirmationStore(
    @Value("\${lodestar.confirmations.file:./data/confirmations.json}") private val filePath: String,
) {
    private val path: Path = Paths.get(filePath)
    private val json = ObjectMapper()
    private val lock = Any()
    private val map = LinkedHashMap<String, ConfirmedFact>()

    init {
        synchronized(lock) { load() }
    }

    private fun load() {
        if (!Files.exists(path)) return
        val rows: List<Map<String, String>> = try {
            json.readValue(Files.readAllBytes(path), object : TypeReference<List<Map<String, String>>>() {})
        } catch (e: Exception) {
            return // 손상된 파일은 빈 상태로 시작(다음 mutation에서 재작성)
        }
        for (r in rows) {
            val iri = r["iri"] ?: continue
            map[iri] = ConfirmedFact(iri, r["label"].orEmpty(), r["kind"].orEmpty())
        }
    }

    private fun persist() {
        path.parent?.let { if (!Files.exists(it)) Files.createDirectories(it) }
        val rows = map.values.map { mapOf("iri" to it.iri, "label" to it.label, "kind" to it.kind) }
        Files.write(path, json.writeValueAsBytes(rows))
    }

    fun confirm(fact: ConfirmedFact) = synchronized(lock) {
        map[fact.iri] = fact
        persist()
    }

    fun all(): List<ConfirmedFact> = synchronized(lock) { map.values.toList() }

    fun isConfirmed(iri: String): Boolean = synchronized(lock) { map.containsKey(iri) }

    fun remove(iri: String) = synchronized(lock) {
        if (map.remove(iri) != null) persist()
    }
}
