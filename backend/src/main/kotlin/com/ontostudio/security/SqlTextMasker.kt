package com.ontostudio.security

import org.springframework.stereotype.Component

/**
 * SQL 텍스트 마스킹 — **문자열 리터럴과 주석 안만** 가린다.
 *
 * 왜 텍스트 전체에 엔진을 돌리지 않는가: 테이블·컬럼 이름이나 숫자 리터럴이 규칙에 걸리면 마스킹이
 * 스키마를 망가뜨린다. 마스킹이 수집을 깨뜨리면 마스킹의 실패다(#85 "마스킹 후에도 구조 정보 유지").
 *
 * 왜 길이를 보존하는가: ① 적재 시 컬럼 길이를 넘기면 INSERT 가 실패한다. ② 좌표가 밀리면
 * `path#Lnn` 형태의 근거 좌표(I1 §1.3 · #113/#114)가 원본에서 조회되지 않는다. 마스킹은 바이트
 * 오프셋을 바꾸지 않는다.
 *
 * 주석의 NAME 클래스는 기본 비활성이다: 한국 성 + 2음절 휴리스틱은 산문에서 오탐이 잦고(‘추정용’·
 * ‘괄호가’), 주석은 AI 의미 추정의 주요 신호다. 값(리터럴)에서는 활성이다 — PII 는 값에 있다.
 * 주석 속 인명은 잔여 위험으로 기록한다(문서 §잔여 위험).
 */
@Component
class SqlTextMasker(
    private val engine: MaskingEngine = MaskingEngine(),
    private val literalPolicy: MaskPolicy = MaskPolicy(lengthPreserving = true),
    private val commentPolicy: MaskPolicy = MaskPolicy(
        lengthPreserving = true,
        disabledClasses = setOf("NAME"),
    ),
) {
    /** 리터럴/주석 구간 — kind 는 "LITERAL" | "COMMENT" */
    private data class Segment(val start: Int, val end: Int, val kind: String)

    fun mask(sql: String, ledger: MaskLedger? = null): String {
        val sb = StringBuilder(sql)
        for (seg in segments(sql).asReversed()) {
            val body = sql.substring(seg.start, seg.end)
            if (body.isEmpty()) continue
            val r = engine.mask(body, if (seg.kind == "LITERAL") literalPolicy else commentPolicy)
            ledger?.add(r)
            sb.replace(seg.start, seg.end, r.text)
        }
        return sb.toString()
    }

    /** 문자열 리터럴('' 이스케이프 인식) · 라인 주석(--) · 블록 주석(/* */) 의 본문 구간. */
    private fun segments(sql: String): List<Segment> {
        val out = mutableListOf<Segment>()
        var i = 0
        while (i < sql.length) {
            when {
                sql[i] == '\'' -> {
                    var j = i + 1
                    while (j < sql.length) {
                        if (sql[j] == '\'') {
                            if (j + 1 < sql.length && sql[j + 1] == '\'') j += 2 else break
                        } else j++
                    }
                    out.add(Segment(i + 1, minOf(j, sql.length), "LITERAL"))
                    i = minOf(j + 1, sql.length)
                }
                sql.startsWith("--", i) -> {
                    val nl = sql.indexOf('\n', i).let { if (it < 0) sql.length else it }
                    out.add(Segment(i + 2, nl, "COMMENT"))
                    i = nl
                }
                sql.startsWith("/*", i) -> {
                    val close = sql.indexOf("*/", i + 2).let { if (it < 0) sql.length else it }
                    out.add(Segment(i + 2, close, "COMMENT"))
                    i = minOf(close + 2, sql.length)
                }
                else -> i++
            }
        }
        return out
    }
}
