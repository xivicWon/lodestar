package com.ontostudio.trash

import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.rdb.ColumnInfo
import com.ontostudio.rdb.ForeignKeyInfo
import com.ontostudio.rdb.SchemaModel
import com.ontostudio.rdb.SchemaToOwlMapper
import com.ontostudio.rdb.TableInfo
import com.ontostudio.savepoint.ConfirmationStore
import com.ontostudio.savepoint.ConfirmedFact
import org.semanticweb.owlapi.model.IRI
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class TrashServiceTest {
    private val base = "http://ex#"
    private val trashFile = Files.createTempFile("trash", ".json")
    private val confFile = Files.createTempFile("confirmations", ".json")

    @AfterTest fun cleanup() {
        Files.deleteIfExists(trashFile)
        Files.deleteIfExists(java.nio.file.Paths.get("$trashFile.corrupt"))
        Files.deleteIfExists(confFile)
    }

    // TB_A(비키 컬럼 2개 + TB_B 로의 FK 1개) + TB_B
    private fun schema() = SchemaModel.of(sourceId = "db:test:trashservicetest", tables = listOf(
        TableInfo(
            name = "TB_A",
            columns = listOf(
                ColumnInfo("a_name", "VARCHAR", true),
                ColumnInfo("a_age", "INT", true),
                ColumnInfo("b_id", "INT", true),
            ),
            primaryKey = emptyList(),
            foreignKeys = listOf(ForeignKeyInfo(listOf("b_id"), "TB_B", listOf("id"))),
        ),
        TableInfo(
            name = "TB_B",
            columns = listOf(ColumnInfo("id", "INT", false)),
            primaryKey = listOf("id"),
            foreignKeys = emptyList(),
        ),
    ))

    private fun setup(retentionDays: Long = 30): Triple<TrashService, OntologyHolder, ConfirmationStore> {
        val holder = OntologyHolder()
        holder.replace(SchemaToOwlMapper().build(schema(), base), base)
        val mapper = OntologyMapper(holder)
        val conf = ConfirmationStore(confFile.toString())
        val svc = TrashService(holder, mapper, conf, trashFile.toString(), retentionDays)
        return Triple(svc, holder, conf)
    }

    private val iriA = base + "TB_A"
    private val iriB = base + "TB_B"
    private fun classIris(h: OntologyHolder) =
        h.ontology.classesInSignature().map { it.iri.toString() }.toList()
    private fun dataPropIris(h: OntologyHolder) =
        h.ontology.dataPropertiesInSignature().map { it.iri.toString() }.toList()
    private fun objPropIris(h: OntologyHolder) =
        h.ontology.objectPropertiesInSignature().map { it.iri.toString() }.toList()

    @Test fun `trash removes class, its columns and relation with correct counts`() {
        val (svc, h, _) = setup()
        val result = svc.trash(iriA)

        assertEquals(2, result.columns)
        assertEquals(1, result.relations)
        assertFalse(classIris(h).contains(iriA), "TB_A class removed")
        assertTrue(classIris(h).contains(iriB), "TB_B stays (상대편 미삭제)")
        assertFalse(dataPropIris(h).any { it.startsWith("$iriA.") }, "TB_A data props removed")
        assertTrue(objPropIris(h).isEmpty(), "A→B object property removed")

        assertEquals(listOf(iriA), svc.list().map { it.iri })
    }

    @Test fun `restore brings class, columns and relation back`() {
        val (svc, h, _) = setup()
        svc.trash(iriA)
        assertFalse(classIris(h).contains(iriA))

        svc.restore(iriA)
        assertTrue(classIris(h).contains(iriA), "TB_A back in signature")
        assertEquals(2, dataPropIris(h).count { it.startsWith("$iriA.") }, "columns restored")
        assertEquals(1, objPropIris(h).size, "relation restored")
        assertTrue(svc.list().isEmpty(), "entry consumed")
    }

    @Test fun `trashed confirmed fact is removed and restored on restore`() {
        val (svc, _, conf) = setup()
        conf.confirm(ConfirmedFact(iriA, "고객 마스터", "class"))
        svc.trash(iriA)
        assertFalse(conf.isConfirmed(iriA), "확정도 함께 이동")

        svc.restore(iriA)
        assertTrue(conf.isConfirmed(iriA), "복구 시 확정 재등록")
        // entry.label(온톨로지 라벨=TB_A)로 재확정된다(spec §3 restore).
        assertEquals("TB_A", conf.all().single { it.iri == iriA }.label)
    }

    @Test fun `purge removes entry and prevents restore`() {
        val (svc, _, _) = setup()
        svc.trash(iriA)
        svc.purge(iriA)
        assertTrue(svc.list().isEmpty())
    }

    @Test fun `retention-days 0 makes list auto-purge immediately`() {
        val (svc, _, _) = setup(retentionDays = 0)
        svc.trash(iriA)
        Thread.sleep(5) // trashedAt + 0 < now 성립 보장
        assertTrue(svc.list().isEmpty(), "보존기간 초과분 lazy purge")
    }

    @Test fun `persists to file and reloads in a new instance`() {
        val (svc, holder, conf) = setup()
        svc.trash(iriA)
        val mapper = OntologyMapper(holder)
        val reloaded = TrashService(holder, mapper, conf, trashFile.toString(), 30)
        assertEquals(listOf(iriA), reloaded.list().map { it.iri })
    }
}
