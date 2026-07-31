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

    /** 파일별 탐지 스팬 — 좌표 대조의 기준이다. */
    private fun spans(): Map<String, List<MaskSpan>> = corpus().mapValues { engine.detect(it.value) }

    @Test fun `gold corpus files match pinned hashes`() {
        for (f in gold()["scope"]["files"]) {
            val got = sha256(File(repoRoot, f["path"].asText()).readBytes())
            assertEquals(f["contentHash"].asText(), got, f["path"].asText())
        }
    }

    /**
     * gold 양성 ↔ 탐지 스팬을 **정확히 1:1로** 대조한다.
     *
     * '원문 전체가 남았는가' 만 보면 스팬이 값의 일부만 덮어도, 좌표가 밀려도, gold 에 없는 자리를
     * 덮어도 통과한다(리뷰 LOD-130). Python 확인기의 M4 와 **같은 판정**을 Kotlin 쪽에도 둔다 —
     * 두 관문이 다른 강도로 재면 한쪽만 통과하는 결함이 남는다.
     */
    @Test fun `every positive maps to exactly one span with exact coordinates`() {
        val rules = MaskingRules.load()
        val ruleClass = (rules.allow + rules.detect).associate { it.id to it.cls }
        val used = mutableMapOf<String, MutableSet<Int>>()
        var checked = 0

        for (item in gold()["items"].filter { it["expect"].asText() == "MASKED" }) {
            val src = item["ref"]["sourceId"].asText()
            val corpus = corpus().getValue(src)
            val lineNo = item["ref"]["locator"].asText().substringAfterLast("#L").toInt()
            val lines = corpus.split("\n")
            val line = lines[lineNo - 1]
            val needle = item["value"]["text"].asText()
            assertTrue(needle in line, "${item["id"].asText()}: 좌표가 원본에서 조회되지 않는다")

            val lineStart = lines.take(lineNo - 1).sumOf { it.length + 1 }
            val wanted = generateSequence(line.indexOf(needle)) { prev ->
                line.indexOf(needle, prev + 1).takeIf { it >= 0 }
            }.map { lineStart + it to lineStart + it + needle.length }.toSet()

            val spans = spans().getValue(src)
            val seen = used.getOrPut(src) { mutableSetOf() }
            val hit = spans.withIndex().firstOrNull { (k, sp) ->
                (sp.start to sp.end) in wanted && k !in seen
            }
            assertTrue(hit != null,
                "${item["id"].asText()}: gold 좌표 $wanted 와 정확히 일치하는 스팬이 없다 — " +
                    "그 줄의 스팬: ${spans.filter { it.start >= lineStart && it.start < lineStart + line.length }}")
            val (idx, span) = hit!!
            assertEquals(item["value"]["class"].asText(), span.cls, item["id"].asText())
            assertEquals(span.cls, ruleClass[span.ruleId],
                "${item["id"].asText()}: ruleId ${span.ruleId} 가 산출하는 클래스와 스팬 클래스가 다르다")
            seen.add(idx)
            checked++
        }

        assertTrue(checked > 0, "양성이 없다")
        for ((src, spans) in spans()) {
            val extra = spans.indices.filter { it !in (used[src] ?: emptySet<Int>()) }
            assertTrue(extra.isEmpty(),
                "$src: 어느 양성에도 귀속되지 않은 스팬 ${extra.size}건: ${extra.take(3).map { spans[it] }}")
        }
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
