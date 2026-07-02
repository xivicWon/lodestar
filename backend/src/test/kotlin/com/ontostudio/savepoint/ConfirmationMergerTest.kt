package com.ontostudio.savepoint

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.ClassService
import com.ontostudio.rdb.MetadataService
import com.ontostudio.rdb.SampleLegacyDb
import com.ontostudio.rdb.SchemaToOwlMapper
import org.semanticweb.owlapi.model.IRI
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * E9 병합 단위 검증: 확정 저장소 → 재임포트로 만들어진 온톨로지에 IRI 매칭 라벨 복원.
 * 실 AI 없이 결정론적(샘플 레거시 → SchemaToOwlMapper).
 */
class ConfirmationMergerTest {

    private val tmp = Files.createTempFile("confirmations-merge", ".json").also { Files.deleteIfExists(it) }

    @AfterTest fun cleanup() {
        Files.deleteIfExists(tmp)
        Files.deleteIfExists(java.nio.file.Paths.get("$tmp.corrupt"))
    }

    private val custIri = "http://lodestar/rdb/legacy#TB_CUST_MST"

    /** 샘플 레거시를 SchemaToOwlMapper로 빌드해 holder에 주입(임포트 경로와 동일한 IRI). */
    private fun buildSampleInto(holder: OntologyHolder) {
        val schemaMapper = SchemaToOwlMapper()
        val baseIri = "http://lodestar/rdb/legacy#"
        val schema = SampleLegacyDb().open().use { conn -> MetadataService().extract(conn) }
        holder.replace(schemaMapper.build(schema, baseIri), baseIri)
    }

    @Test fun `merge reapplies confirmed label to matching class`() {
        val holder = OntologyHolder()
        buildSampleInto(holder)
        val mapper = OntologyMapper(holder)
        val classService = ClassService(holder, mapper)
        val store = ConfirmationStore(tmp.toString())
        val merger = ConfirmationMerger(store, classService, holder)

        store.confirm(ConfirmedFact(custIri, "거래처 마스터", "class"))

        val summary = merger.merge()

        assertTrue(summary.reapplied >= 1, "확정된 클래스가 재적용되어야 함")
        assertEquals("거래처 마스터", mapper.labelOf(IRI.create(custIri)))
    }

    @Test fun `merge reports stale for missing iri and preserves it in store`() {
        val holder = OntologyHolder()
        buildSampleInto(holder)
        val mapper = OntologyMapper(holder)
        val classService = ClassService(holder, mapper)
        val store = ConfirmationStore(tmp.toString())
        val merger = ConfirmationMerger(store, classService, holder)

        val bogus = "http://lodestar/rdb/legacy#NO_SUCH_TABLE"
        store.confirm(ConfirmedFact(custIri, "거래처 마스터", "class"))
        store.confirm(ConfirmedFact(bogus, "존재하지 않음", "class"))

        val summary = merger.merge()

        assertEquals(1, summary.stale)
        assertTrue(summary.staleIris.contains(bogus))
        // 미매칭 확정은 저장소에 그대로 보존(자동 삭제 안 함)
        assertTrue(store.isConfirmed(bogus))
    }
}
