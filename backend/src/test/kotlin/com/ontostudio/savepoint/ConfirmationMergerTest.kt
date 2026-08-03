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

    private val custIri = "http://lodestar/rdb/legacy#PUBLIC/TB_CUST_MST"

    /** 샘플 레거시를 SchemaToOwlMapper로 빌드해 holder에 주입(임포트 경로와 동일한 IRI). */
    private fun buildSampleInto(holder: OntologyHolder) {
        val schemaMapper = SchemaToOwlMapper()
        val baseIri = "http://lodestar/rdb/legacy#"
        val schema = SampleLegacyDb().open().use { conn -> MetadataService().extract(conn, "db:legacy-sample", revisionScheme = "bundle") }
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

    /**
     * #126 의 파급을 사실로 고정한다. 소속을 IRI 에 넣으면서 **#126 이전에 저장된 확정의 IRI**
     * (소속 없는 `…#TB_CUST_MST`)는 더 이상 어떤 클래스도 가리키지 않는다.
     *
     * 요점은 그 확정이 **조용히 사라지거나 엉뚱한 클래스에 붙지 않는다**는 것이다 — E9 는 미매칭을
     * stale 로 보고하고 저장소에 그대로 둔다(D2). 사용자는 목록에서 그것을 보고 다시 확정할 수 있다.
     */
    @Test fun `소속 없이 저장된 예전 확정은 조용히 사라지지 않고 stale 로 보고된다`() {
        val holder = OntologyHolder()
        buildSampleInto(holder)
        val mapper = OntologyMapper(holder)
        val store = ConfirmationStore(tmp.toString())
        val merger = ConfirmationMerger(store, ClassService(holder, mapper), holder)

        val preIssue126 = "http://lodestar/rdb/legacy#TB_CUST_MST"   // 소속 없는 예전 IRI
        store.confirm(ConfirmedFact(preIssue126, "거래처 마스터", "class"))

        val summary = merger.merge()

        assertEquals(0, summary.reapplied)
        assertTrue(summary.staleIris.contains(preIssue126), "예전 확정이 stale 로 보고되지 않았다")
        assertTrue(store.isConfirmed(preIssue126), "미매칭 확정을 자동 삭제하면 안 된다(D2)")
        // 엉뚱한 클래스에 붙지 않았는가 — 같은 이름의 새 IRI 는 원래 라벨 그대로여야 한다.
        assertEquals("TB_CUST_MST", mapper.labelOf(IRI.create(custIri)))
    }
}
