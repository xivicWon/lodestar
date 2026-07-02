package com.ontostudio.savepoint

import com.fasterxml.jackson.core.type.TypeReference
import com.fasterxml.jackson.databind.ObjectMapper
import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.nio.file.StandardCopyOption

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
    private val log = LoggerFactory.getLogger(ConfirmationStore::class.java)
    private val path: Path = Paths.get(filePath)
    private val json = ObjectMapper()
    private val lock = Any()
    private val map = LinkedHashMap<String, ConfirmedFact>()

    init {
        synchronized(lock) { load() }
    }

    private fun load() {
        if (!Files.exists(path)) return
        val bytes = Files.readAllBytes(path)
        if (bytes.isEmpty()) return // 빈 파일 = 데이터 없음(손상 아님)
        val rows: List<Map<String, String>> = try {
            json.readValue(bytes, object : TypeReference<List<Map<String, String>>>() {})
        } catch (e: Exception) {
            // 손상 파일은 조용히 버리지 않는다: .corrupt 로 백업하고 경고를 남긴 뒤 빈 상태로 시작.
            val backup = Paths.get("$filePath.corrupt")
            runCatching { Files.move(path, backup, StandardCopyOption.REPLACE_EXISTING) }
                .onFailure { log.error("확정 저장소 손상 파일 백업 실패: {}", path, it) }
            log.error("확정 저장소 파싱 실패 — {} 로 백업 후 빈 상태로 시작(세이브포인트 검토 필요)", backup, e)
            return
        }
        for (r in rows) {
            val iri = r["iri"] ?: continue
            map[iri] = ConfirmedFact(iri, r["label"].orEmpty(), r["kind"].orEmpty())
        }
    }

    /** 원자적 저장: 같은 디렉터리 임시파일에 쓴 뒤 ATOMIC_MOVE 로 교체 → 부분/잘린 파일이 남지 않는다. */
    private fun persist() {
        val dir = path.parent ?: Paths.get(".")
        if (!Files.exists(dir)) Files.createDirectories(dir)
        val rows = map.values.map { mapOf("iri" to it.iri, "label" to it.label, "kind" to it.kind) }
        val bytes = json.writeValueAsBytes(rows)
        val tmp = Files.createTempFile(dir, ".confirmations", ".tmp")
        try {
            Files.write(tmp, bytes)
            try {
                Files.move(tmp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            } catch (e: AtomicMoveNotSupportedException) {
                Files.move(tmp, path, StandardCopyOption.REPLACE_EXISTING)
            }
        } finally {
            Files.deleteIfExists(tmp)
        }
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
