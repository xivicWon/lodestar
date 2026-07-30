package com.ontostudio.security

import com.fasterxml.jackson.databind.ObjectMapper
import java.io.File
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * #115 — 교차 엔진 패리티 증거 (Kotlin 쪽).
 *
 * gold 코퍼스는 이번에 신설·수정된 분기를 지나가지 않는다: 따옴표로 묶인 키드 시크릿(대안 그룹),
 * `@` 가 든 URL 비밀번호, 여러 줄 PEM, 잘린 PEM, BMP 밖 문자(스팬 좌표 단위), 길이 보존 모드의 개행
 * 보존. **그 분기에서 두 엔진이 갈려도 gold 증거만으로는 조용히 통과한다.** 그 구멍을 닫는 증거다.
 *
 * 이 픽스처에는 **정답이 없다** — 확정하는 것은 "두 엔진이 갈리지 않는다" 하나이고, 정확성 판정은
 * gold(#99)가 한다. 두 증거의 일치는 `verify_masking.py` M2 가 대조한다.
 *
 * 좌표·문자 수의 단위는 **UTF-16 코드 단위**다(규칙 스펙 `spanContract`). Kotlin 의 `String` 인덱스가
 * 그 단위이므로 여기서는 변환이 없고, Python 쪽이 코드포인트에서 변환해 맞춘다.
 */
class MaskingParityTest {

    private val mapper = ObjectMapper()
    private val engine = MaskingEngine()

    private val repoRoot: File by lazy {
        var d = File("").absoluteFile
        while (!File(d, ".git").exists()) d = d.parentFile ?: error("리포 루트를 찾지 못했다")
        d
    }
    private val fixtureFile get() =
        File(repoRoot, "docs/superpowers/specs/bench/masking/fixtures/parity-cases.json")
    private val runDir get() =
        File(repoRoot, "docs/superpowers/specs/bench/masking/runs/run-mask-parity-001")

    private fun sha256(bytes: ByteArray) =
        "sha256:" + MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private val policies = listOf(
        "default" to MaskPolicy(),
        "lengthPreserving" to MaskPolicy(lengthPreserving = true),
    )

    @Test fun `parity evidence is recorded and does not drift`() {
        val fixture = mapper.readTree(fixtureFile)
        assertTrue(fixture["cases"].size() >= 15, "패리티 픽스처가 비었거나 너무 작다")

        val out = mapper.createObjectNode()
        out.put("evidenceVersion", "mask-parity-evidence/v1")
        out.put("engine", "kotlin:com.ontostudio.security.MaskingEngine")
        out.put("specVersion", MaskingRules.load().specVersion)
        out.put("fixtureVersion", fixture["fixtureVersion"].asText())
        out.put("fixtureHash", sha256(fixtureFile.readBytes()))
        out.putArray("policies").also { a -> fixture["policies"].forEach { a.add(it.asText()) } }

        val cases = out.putArray("cases")
        for (case in fixture["cases"]) {
            val text = case["text"].asText()
            val node = mapper.createObjectNode()
            node.put("id", case["id"].asText())
            node.put("inputHash", sha256(text.toByteArray()))
            node.put("inputChars", text.length)
            node.put("inputLines", text.count { it == '\n' } + 1)
            for ((name, policy) in policies) {
                val result = engine.mask(text, policy)
                node.putObject(name).apply {
                    // 원문·마스킹 텍스트는 적지 않는다 — 해시와 좌표만 남긴다(#85).
                    put("maskedTextHash", sha256(result.text.toByteArray()))
                    put("maskedChars", result.text.length)
                    put("maskedLines", result.text.count { it == '\n' } + 1)
                    putArray("spans").also { arr ->
                        for (s in result.spans) {
                            arr.add(mapper.createObjectNode().apply {
                                put("start", s.start); put("end", s.end)
                                put("ruleId", s.ruleId); put("class", s.cls)
                            })
                        }
                    }
                    putObject("byRule").also { o -> result.byRule.forEach { (k, v) -> o.put(k, v) } }
                }
            }
            cases.add(node)
        }

        val json = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(out) + "\n"
        val generated = File(File(repoRoot, "backend/build/masking"), "parity-kotlin.json")
        generated.parentFile.mkdirs()
        generated.writeText(json)

        val committed = File(runDir, "engine-kotlin.json")
        val bootstrap = System.getProperty("MASK_EVIDENCE_BOOTSTRAP") == "true"
        assertTrue(committed.exists() || bootstrap,
            "커밋된 패리티 증거가 없다: ${committed.path} — 최초 생성이면 " +
                "-DMASK_EVIDENCE_BOOTSTRAP=true 로 실행하고 ${generated.path} 를 커밋한다")
        if (!committed.exists()) return
        assertEquals(committed.readText(), json,
            "커밋된 패리티 증거와 이번 실행이 다르다 — 규칙·엔진이 바뀌었으면 두 증거를 갱신하고 " +
                "verify_masking.py 로 두 엔진 일치를 다시 확인한다")
    }

    /** 픽스처가 실제로 새 분기를 지나가는지 — 지나가지 않으면 이 증거는 아무것도 막지 못한다. */
    @Test fun `fixture actually exercises the branches it claims`() {
        val fixture = mapper.readTree(fixtureFile)
        val rules = mutableSetOf<String>()
        var astral = false
        var multiline = false
        for (case in fixture["cases"]) {
            val text = case["text"].asText()
            engine.detect(text).forEach { rules.add(it.ruleId) }
            if (text.codePoints().anyMatch { it > 0xFFFF }) astral = true
            if (text.contains("\n")) multiline = true
        }
        assertTrue("SECRET.KEYED_VALUE" in rules, "키드 시크릿(대안 그룹) 분기를 지나가지 않는다")
        assertTrue("SECRET.URL_CREDENTIAL" in rules, "URL 자격증명 분기를 지나가지 않는다")
        assertTrue("SECRET.PRIVATE_KEY_BLOCK" in rules, "PEM 블록 분기를 지나가지 않는다")
        assertTrue(astral, "BMP 밖 문자가 없으면 좌표 단위 계약이 검증되지 않는다")
        assertTrue(multiline, "여러 줄 입력이 없으면 개행 보존 계약이 검증되지 않는다")
    }

    /** 길이 보존 모드는 UTF-16 문자 수와 행 수를 유지한다 — 두 엔진이 같은 결과를 내야 하는 계약이다. */
    @Test fun `length preserving keeps chars and lines for every case`() {
        for (case in mapper.readTree(fixtureFile)["cases"]) {
            val text = case["text"].asText()
            val masked = engine.mask(text, MaskPolicy(lengthPreserving = true)).text
            assertEquals(text.length, masked.length, case["id"].asText())
            assertEquals(text.count { it == '\n' }, masked.count { it == '\n' }, case["id"].asText())
        }
    }
}
