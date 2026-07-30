package com.ontostudio.security

import com.fasterxml.jackson.databind.ObjectMapper
import java.io.File
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * #115 마스킹 게이트 — #99 gold PII 코퍼스 전수 검증 (Kotlin 엔진).
 *
 * 게이트: 양성 28건 **미마스킹 0건**(I1 §4.1 · H2). 오탐(음성이 가려짐)은 게이트가 아니라 기록
 * 대상이지만, gold 선언대로 GIT_SHA·CONTENT_HASH 오탐은 revision·fixture 추적을 끊으므로 여기서
 * 붉어진다.
 *
 * 이 테스트는 **교차 언어 증거**도 남긴다: `bench/masking/runs/run-mask-gold-001/engine-kotlin.json`.
 * Python 엔진이 같은 스팬·같은 마스킹 결과 해시를 내는지는 `verify_masking.py` 가 대조한다. 커밋된
 * 증거와 이번 실행이 다르면 실패한다 — 규칙을 바꾸고 증거를 갱신하지 않는 상태를 막는다
 * (최초 생성만 `-DMASK_EVIDENCE_BOOTSTRAP=true`).
 */
class MaskingGoldGateTest {

    private val mapper = ObjectMapper()
    private val engine = MaskingEngine()

    private val repoRoot: File by lazy {
        var d = File("").absoluteFile
        while (!File(d, ".git").exists()) d = d.parentFile ?: error("리포 루트를 찾지 못했다")
        d
    }
    private val goldFile get() = File(repoRoot, "docs/superpowers/specs/gold/pii.json")
    private val runDir get() = File(repoRoot, "docs/superpowers/specs/bench/masking/runs/run-mask-gold-001")

    private fun sha256(bytes: ByteArray) =
        "sha256:" + MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private fun gold() = mapper.readTree(goldFile)

    private fun corpus(): Map<String, String> = gold()["scope"]["files"].associate {
        it["sourceId"].asText() to File(repoRoot, it["path"].asText()).readText()
    }

    private fun masked(): Map<String, String> = corpus().mapValues { engine.mask(it.value).text }

    @Test fun `gold corpus files match pinned hashes`() {
        for (f in gold()["scope"]["files"]) {
            val got = sha256(File(repoRoot, f["path"].asText()).readBytes())
            assertEquals(f["contentHash"].asText(), got, f["path"].asText())
        }
    }

    @Test fun `no positive survives unmasked`() {
        val masked = masked()
        val survivors = gold()["items"]
            .filter { it["expect"].asText() == "MASKED" }
            .filter { masked.getValue(it["ref"]["sourceId"].asText()).contains(it["value"]["text"].asText()) }
            .map { it["id"].asText() }
        assertTrue(survivors.isEmpty(), "미마스킹 양성: $survivors")
    }

    @Test fun `negatives are preserved`() {
        val masked = masked()
        val lost = gold()["items"]
            .filter { it["expect"].asText() == "NOT_MASKED" }
            .filterNot { masked.getValue(it["ref"]["sourceId"].asText()).contains(it["value"]["text"].asText()) }
            .map { it["id"].asText() }
        assertTrue(lost.isEmpty(), "오탐(음성이 가려짐): $lost")
    }

    @Test fun `masking is deterministic and idempotent`() {
        val once = masked()
        assertEquals(once, masked())
        assertEquals(once, once.mapValues { engine.mask(it.value).text })
    }

    @Test fun `cross-engine evidence is recorded and does not drift`() {
        val out = mapper.createObjectNode()
        out.put("evidenceVersion", "mask-engine-evidence/v1")
        out.put("engine", "kotlin:com.ontostudio.security.MaskingEngine")
        out.put("specVersion", MaskingRules.load().specVersion)
        out.put("goldSetVersion", gold()["goldSetVersion"].asText())
        val files = out.putArray("files")
        for (f in gold()["scope"]["files"]) {
            val sourceId = f["sourceId"].asText()
            val raw = File(repoRoot, f["path"].asText()).readText()
            val result = engine.mask(raw)
            val n = mapper.createObjectNode()
            n.put("sourceId", sourceId)
            n.put("contentHash", sha256(raw.toByteArray()))
            // 마스킹 결과는 해시로만 남긴다 — 원문·마스킹 텍스트를 증거에 적지 않는다(#85).
            n.put("maskedTextHash", sha256(result.text.toByteArray()))
            n.put("maskedSpans", result.spans.size)
            val spans = n.putArray("spans")
            for (s in result.spans) {
                spans.add(mapper.createObjectNode().apply {
                    put("start", s.start); put("end", s.end)
                    put("ruleId", s.ruleId); put("class", s.cls)
                    put("line", 1 + raw.substring(0, s.start).count { it == '\n' })
                })
            }
            n.putObject("byClass").also { o -> result.byClass.forEach { (k, v) -> o.put(k, v) } }
            n.putObject("byRule").also { o -> result.byRule.forEach { (k, v) -> o.put(k, v) } }
            files.add(n)
        }
        val json = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(out) + "\n"
        val generated = File(File(repoRoot, "backend/build/masking"), "engine-kotlin.json")
        generated.parentFile.mkdirs()
        generated.writeText(json)

        // 증거는 실재해야 한다 — 없을 때 조용히 통과하면 증거를 지우는 것이 검사를 지우는 것이 된다.
        val committed = File(runDir, "engine-kotlin.json")
        val bootstrap = System.getProperty("MASK_EVIDENCE_BOOTSTRAP") == "true"
        assertTrue(committed.exists() || bootstrap,
            "커밋된 교차 언어 증거가 없다: ${committed.path} — 최초 생성이면 " +
                "-DMASK_EVIDENCE_BOOTSTRAP=true 로 실행하고 ${generated.path} 를 커밋한다")
        if (!committed.exists()) return
        assertEquals(committed.readText(), json,
            "커밋된 마스킹 증거와 이번 실행이 다르다 — 규칙이 바뀌었으면 증거를 갱신하고 " +
                "verify_masking.py 로 두 엔진 일치를 다시 확인한다")
    }
}
