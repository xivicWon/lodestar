package com.ontostudio.trash

import com.fasterxml.jackson.core.type.TypeReference
import com.fasterxml.jackson.databind.ObjectMapper
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.ApiException
import com.ontostudio.savepoint.ConfirmationStore
import com.ontostudio.savepoint.ConfirmedFact
import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.formats.TurtleDocumentFormat
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLAxiom
import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.nio.file.StandardCopyOption

/** 휴지통에 보관된 폐기 클래스 1건. 제거 축을 Turtle로 직렬화해 정확 복원(E11 D5). */
data class TrashEntry(
    val iri: String,
    val label: String,
    val trashedAt: Long,
    val turtle: String,
    val confirmed: Boolean,
)

/** 이동 요약(툴바 표시용). */
data class TrashResult(val iri: String, val columns: Int, val relations: Int)

/** 목록 조회용 DTO(무거운 turtle 제외). */
data class TrashEntryDto(val iri: String, val label: String, val trashedAt: Long)

/**
 * 클래스 2단계 폐기(휴지통). 삭제=휴지통 이동(soft), 이후 복구/완전삭제(E11).
 * 파일(JSON)로 영속되며 저장은 원자적, 손상 파일은 .corrupt 로 백업(E8 ConfirmationStore 패턴 준용).
 * 스레드 안전(모든 연산 synchronized).
 */
@Service
class TrashService(
    private val holder: OntologyHolder,
    private val mapper: OntologyMapper,
    private val confirmations: ConfirmationStore,
    @Value("\${lodestar.trash.file:./data/trash.json}") private val filePath: String,
    @Value("\${lodestar.trash.retention-days:30}") private val retentionDays: Long,
) {
    private val log = LoggerFactory.getLogger(TrashService::class.java)
    private val path: Path = Paths.get(filePath)
    private val json = ObjectMapper()
    private val lock = Any()
    private val entries = LinkedHashMap<String, TrashEntry>()

    init {
        synchronized(lock) { load() }
    }

    private val retentionMs: Long get() = retentionDays * 86_400_000L

    fun trash(iri: String): TrashResult = synchronized(lock) {
        synchronized(holder.lock) {
            val df = holder.dataFactory
            val ont = holder.ontology
            val cls = df.getOWLClass(IRI.create(iri))
            if (!ont.containsClassInSignature(cls.iri))
                throw ApiException(HttpStatus.NOT_FOUND, "not_found", "클래스 없음", iri)

            // 소유 DataProperty: 도메인 집합이 정확히 {iri} 인 것.
            val ownedDataProps = ont.dataPropertiesInSignature().toList().filter { dp ->
                mapper.dataPropertyDto(dp).domains == listOf(iri)
            }
            // 관계: domain 또는 range 에 iri 를 포함하는 ObjectProperty.
            val relations = ont.objectPropertiesInSignature().toList().filter { op ->
                val dto = mapper.objectPropertyDto(op)
                dto.domains.contains(iri) || dto.ranges.contains(iri)
            }

            // 제거 축 수집(중복 제거). 변형 전에 반드시 materialize.
            val removal = LinkedHashSet<OWLAxiom>()
            removal.addAll(ont.referencingAxioms(cls).toList())
            ownedDataProps.forEach { removal.addAll(ont.referencingAxioms(it).toList()) }
            relations.forEach { removal.addAll(ont.referencingAxioms(it).toList()) }
            val axioms = removal.toList()

            // 제거 축으로 임시 온톨로지 구성 → Turtle 직렬화.
            val turtle = serialize(axioms)

            // 활성에서 제거.
            holder.manager.removeAxioms(ont, axioms.stream())

            // 확정 사실이면 함께 이동.
            val wasConfirmed = confirmations.isConfirmed(iri)
            if (wasConfirmed) confirmations.remove(iri)

            val label = mapper.labelOf(cls.iri) ?: shortName(iri)
            val entry = TrashEntry(iri, label, System.currentTimeMillis(), turtle, wasConfirmed)
            entries[iri] = entry
            persist()

            TrashResult(iri, ownedDataProps.size, relations.size)
        }
    }

    fun list(): List<TrashEntry> = synchronized(lock) {
        val now = System.currentTimeMillis()
        val expired = entries.values.filter { it.trashedAt + retentionMs < now }.map { it.iri }
        if (expired.isNotEmpty()) {
            expired.forEach { entries.remove(it) }
            persist()
        }
        entries.values.toList()
    }

    fun restore(iri: String): Unit = synchronized(lock) {
        val entry = entries[iri]
            ?: throw ApiException(HttpStatus.NOT_FOUND, "not_found", "휴지통 항목 없음", iri)
        synchronized(holder.lock) {
            val mgr = OWLManager.createOWLOntologyManager()
            val parsed = mgr.loadOntologyFromOntologyDocument(
                ByteArrayInputStream(entry.turtle.toByteArray()))
            holder.manager.addAxioms(holder.ontology, parsed.axioms())
        }
        if (entry.confirmed) confirmations.confirm(ConfirmedFact(iri, entry.label, "class"))
        entries.remove(iri)
        persist()
    }

    fun purge(iri: String): Unit = synchronized(lock) {
        if (entries.remove(iri) != null) persist()
    }

    private fun serialize(axioms: List<OWLAxiom>): String {
        val mgr = OWLManager.createOWLOntologyManager()
        val ont = mgr.createOntology()
        mgr.addAxioms(ont, axioms.stream())
        val out = ByteArrayOutputStream()
        mgr.saveOntology(ont, TurtleDocumentFormat(), out)
        return out.toString(Charsets.UTF_8.name())
    }

    private fun shortName(iri: String): String =
        iri.substringAfterLast('#').substringAfterLast('/').ifBlank { iri }

    private fun load() {
        if (!Files.exists(path)) return
        val bytes = Files.readAllBytes(path)
        if (bytes.isEmpty()) return
        val rows: List<Map<String, Any?>> = try {
            json.readValue(bytes, object : TypeReference<List<Map<String, Any?>>>() {})
        } catch (e: Exception) {
            val backup = Paths.get("$filePath.corrupt")
            runCatching { Files.move(path, backup, StandardCopyOption.REPLACE_EXISTING) }
                .onFailure { log.error("휴지통 저장소 손상 파일 백업 실패: {}", path, it) }
            log.error("휴지통 저장소 파싱 실패 — {} 로 백업 후 빈 상태로 시작", backup, e)
            return
        }
        for (r in rows) {
            val iri = r["iri"] as? String ?: continue
            entries[iri] = TrashEntry(
                iri = iri,
                label = (r["label"] as? String).orEmpty(),
                trashedAt = (r["trashedAt"] as? Number)?.toLong() ?: 0L,
                turtle = (r["turtle"] as? String).orEmpty(),
                confirmed = (r["confirmed"] as? Boolean) ?: false,
            )
        }
    }

    /** 원자적 저장: 같은 디렉터리 임시파일에 쓴 뒤 ATOMIC_MOVE 로 교체. */
    private fun persist() {
        val dir = path.parent ?: Paths.get(".")
        if (!Files.exists(dir)) Files.createDirectories(dir)
        val rows = entries.values.map {
            mapOf(
                "iri" to it.iri, "label" to it.label, "trashedAt" to it.trashedAt,
                "turtle" to it.turtle, "confirmed" to it.confirmed,
            )
        }
        val bytes = json.writeValueAsBytes(rows)
        val tmp = Files.createTempFile(dir, ".trash", ".tmp")
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
}
