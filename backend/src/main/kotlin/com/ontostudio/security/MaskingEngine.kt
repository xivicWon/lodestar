package com.ontostudio.security

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import org.springframework.stereotype.Component

/**
 * PII·시크릿 마스킹 단계 (#115 · L0-fix-5 · 요구 통합 #85).
 *
 * 규칙은 이 코드가 아니라 **리포 단일 원본**이 정한다:
 * `docs/superpowers/specs/security/masking-rules.v0.json`.
 * 클래스패스 사본이 원본과 다르면 [MaskingRuleSpecParityTest] 가 붉어진다 — 두 엔진(Kotlin ·
 * Python `lodestar_codegraph.mask`)이 다른 규칙으로 가리면 "같은 정책" 이라는 말이 성립하지 않는다.
 *
 * 기록 원칙(#85): 건수·규칙 id·클래스·좌표만 남기고 **원문은 어디에도 남기지 않는다.**
 */
data class MaskRule(
    val id: String,
    val cls: String,
    val regex: Regex,
    val valueGroup: Int = 0,
    val luhn: Boolean = false,
    /** 대안 그룹 — 목록 순서대로 보고 처음 참여한 그룹을 가린다(따옴표 있는 값 / 없는 값 등). */
    val valueGroups: List<Int> = emptyList(),
)

/** 마스킹 정책. 기본값이 곧 수집 경로의 기본 동작이다. */
data class MaskPolicy(
    val disabledClasses: Set<String> = emptySet(),
    /** null = 규칙 스펙의 기본값(true) */
    val allowlistEnabled: Boolean? = null,
    /** SQL 리터럴처럼 길이·좌표 제약이 있는 자리는 원문 길이만큼 '*' 로 바꾼다 */
    val lengthPreserving: Boolean = false,
)

data class MaskSpan(val start: Int, val end: Int, val ruleId: String, val cls: String)

data class MaskResult(val text: String, val spans: List<MaskSpan>) {
    val masked: Int get() = spans.size
    val byRule: Map<String, Int> get() = spans.groupingBy { it.ruleId }.eachCount().toSortedMap()
    val byClass: Map<String, Int> get() = spans.groupingBy { it.cls }.eachCount().toSortedMap()
}

/** 한 수집 실행의 마스킹 집계 — 무엇을(클래스·규칙) 몇 건 가렸는지. 원문은 담지 않는다. */
class MaskLedger {
    private val rules = linkedMapOf<String, Int>()
    private val classes = linkedMapOf<String, Int>()
    var fields: Int = 0
        private set

    fun add(result: MaskResult) {
        if (result.spans.isNotEmpty()) fields++
        result.byRule.forEach { (k, v) -> rules[k] = (rules[k] ?: 0) + v }
        result.byClass.forEach { (k, v) -> classes[k] = (classes[k] ?: 0) + v }
    }

    val total: Int get() = rules.values.sum()

    fun summary(): Map<String, Any> = linkedMapOf(
        "specVersion" to MaskingRules.load().specVersion,
        "maskedTotal" to total,
        "maskedFields" to fields,
        "byClass" to classes.toSortedMap(),
        "byRule" to rules.toSortedMap(),
    )
}

/** 규칙 스펙 — 클래스패스 사본에서 읽는다. */
class MaskingRules private constructor(
    val specVersion: String,
    val template: String,
    val fillChar: String,
    val allowlistDefault: Boolean,
    val allow: List<MaskRule>,
    val detect: List<MaskRule>,
) {
    companion object {
        const val RESOURCE = "/com/ontostudio/security/masking-rules.v0.json"

        @Volatile
        private var cached: MaskingRules? = null

        fun load(): MaskingRules = cached ?: synchronized(this) {
            cached ?: parse(
                MaskingRules::class.java.getResource(RESOURCE)?.readText()
                    ?: error("마스킹 규칙 스펙이 클래스패스에 없다: $RESOURCE")
            ).also { cached = it }
        }

        fun parse(json: String): MaskingRules {
            val root = ObjectMapper().readTree(json)
            fun rule(n: JsonNode) = MaskRule(
                id = n["id"].asText(),
                cls = n["class"].asText(),
                regex = Regex(n["regex"].asText()),
                valueGroup = n["valueGroup"]?.asInt() ?: 0,
                luhn = n["luhn"]?.asBoolean() ?: false,
                valueGroups = n["valueGroups"]?.map { it.asInt() } ?: emptyList(),
            )
            return MaskingRules(
                specVersion = root["specVersion"].asText(),
                template = root["maskToken"]["template"].asText(),
                fillChar = root["maskToken"]["lengthPreservingChar"].asText(),
                allowlistDefault = root["policy"]["allowlistEnabled"].asBoolean(),
                allow = root["allow"].map { rule(it) },
                detect = root["detect"].map { rule(it) },
            )
        }
    }
}

@Component
class MaskingEngine(private val rules: MaskingRules = MaskingRules.load()) {

    /** 탐지만 한다(치환 없음). allow 스팬과 겹치는 탐지는 버리고, 겹치는 탐지끼리는 스펙 순서가 이긴다. */
    fun detect(text: String, policy: MaskPolicy = MaskPolicy()): List<MaskSpan> {
        val allowOn = policy.allowlistEnabled ?: rules.allowlistDefault
        val allowed = if (!allowOn) emptyList() else rules.allow.flatMap { r ->
            r.regex.findAll(text).map { it.range.first to it.range.last + 1 }.toList()
        }

        val kept = mutableListOf<MaskSpan>()
        for (rule in rules.detect) {
            if (rule.cls in policy.disabledClasses) continue
            for (m in rule.regex.findAll(text)) {
                // 대안 그룹은 목록 순서대로 보고 처음 참여한 것을 쓴다(규칙 스펙 `maskToken.valueGroupsNote`).
                val group = rule.valueGroups.firstOrNull { m.groups[it] != null } ?: rule.valueGroup
                val g = m.groups[group] ?: continue
                val start = g.range.first
                val end = g.range.last + 1
                if (end <= start) continue
                if (rule.luhn && !luhn(text.substring(start, end))) continue
                if (allowed.any { (a, b) -> a < end && start < b }) continue
                if (kept.any { it.start < end && start < it.end }) continue
                kept.add(MaskSpan(start, end, rule.id, rule.cls))
            }
        }
        return kept.sortedWith(compareBy({ it.start }, { it.end }, { it.ruleId }))
    }

    fun mask(text: String, policy: MaskPolicy = MaskPolicy()): MaskResult {
        val spans = detect(text, policy)
        val sb = StringBuilder(text)
        for (s in spans.asReversed()) {
            sb.replace(s.start, s.end, token(s.cls, text.substring(s.start, s.end), policy.lengthPreserving))
        }
        return MaskResult(sb.toString(), spans)
    }

    /** 산출물·로그·저장에 실리는 텍스트 필드 하나를 마스킹한다. 수집 경로가 쓰는 진입점. */
    fun maskField(value: String?, ledger: MaskLedger? = null, policy: MaskPolicy = MaskPolicy()): String? {
        if (value.isNullOrEmpty()) return value
        val r = mask(value, policy)
        ledger?.add(r)
        return r.text
    }

    private fun token(cls: String, original: String, lengthPreserving: Boolean): String {
        if (!lengthPreserving) return rules.template.replace("{class}", cls)
        if (original.isEmpty()) return rules.fillChar
        // 개행은 보존한다 — 여러 줄 값(PEM 개인 키 등)을 통째로 덮으면 뒤따르는 `path#Lnn` 좌표가 밀린다.
        return original.map { if (it == '\n') "\n" else rules.fillChar }.joinToString("")
    }

    private fun luhn(digits: String): Boolean {
        var sum = 0
        var alt = false
        for (ch in digits.reversed()) {
            if (!ch.isDigit()) return false
            var d = ch - '0'
            if (alt) { d *= 2; if (d > 9) d -= 9 }
            sum += d
            alt = !alt
        }
        return sum % 10 == 0
    }
}
