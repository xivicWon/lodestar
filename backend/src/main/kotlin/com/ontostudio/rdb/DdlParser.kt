package com.ontostudio.rdb

import net.sf.jsqlparser.parser.CCJSqlParserUtil
import net.sf.jsqlparser.statement.create.table.CreateTable
import net.sf.jsqlparser.statement.create.table.ForeignKeyIndex
import net.sf.jsqlparser.statement.insert.Insert
import org.springframework.stereotype.Component

/**
 * DDL 텍스트 → SchemaModel. CREATE TABLE 만 사실로 산출하고, **처리하지 못한 문장은 좌표·사유와 함께
 * 반환형에 남긴다**(#114). 조용히 건너뛰는 경로는 없다 — 제외·실패·부분수집이 모두 [SchemaModel.issues] 에
 * 들어가므로 `tables + issues` 가 입력 문장 수를 설명한다(I3 R2).
 */
@Component
class DdlParser {

    /** 문장 하나. [startLine]~[endLine] 은 1-base 이며 종결 ';' 행을 포함한다. */
    private data class RawStatement(val startLine: Int, val endLine: Int, val text: String)

    /**
     * @param sourcePath 좌표에 붙일 원본 경로. 없으면 좌표는 `#L11-L14` 형태로만 남는다.
     */
    fun parse(sql: String, sourcePath: String? = null): SchemaModel {
        val tables = mutableListOf<TableInfo>()
        val issues = mutableListOf<CollectionIssue>()

        for (stmt in split(sql)) {
            val locator = locator(sourcePath, stmt)
            val target = target(stmt.text)
            val head = head(stmt.text)

            val parsed = try {
                CCJSqlParserUtil.parse(stmt.text)
            } catch (e: Exception) {
                // 미지원 문법(트리거·함수·프로시저 본문)과 진짜 깨진 문장을 구분한다 —
                // 둘을 한 통에 넣으면 '고칠 것' 과 '지원 범위' 가 섞인다.
                issues.add(
                    if (unsupportedByDesign(head)) CollectionIssue(
                        IssueKind.SKIPPED, CollectionReason.UNSUPPORTED_STATEMENT,
                        "수집기가 처리하지 않는 구문이다 — DdlParser 는 CREATE TABLE 만 사실로 산출한다",
                        locator, target)
                    else CollectionIssue(
                        IssueKind.FAILED, CollectionReason.PARSE_ERROR,
                        "SQL 파싱 실패: ${message(e)}", locator, target)
                )
                continue
            }

            when {
                parsed is CreateTable -> {
                    val swallowed = swallowedColumns(parsed)
                    if (swallowed.isNotEmpty()) {
                        // 파서가 뒤 컬럼을 앞 컬럼의 제약으로 삼켜 '컬럼 1개짜리 테이블' 을 만든 경우다.
                        // 그 부분 복구를 산출하면 부분 성공이 완전 성공으로 위장된다 — 버리고 보고한다.
                        issues.add(CollectionIssue(
                            IssueKind.FAILED, CollectionReason.PARSE_ERROR,
                            "컬럼 정의가 앞 컬럼의 제약으로 흡수됐다(쉼표 누락 등) — 부분 복구 결과를 버리고 " +
                                "실패로 보고한다. 흡수된 것으로 보이는 이름: ${swallowed.joinToString(", ")}",
                            locator, target))
                    } else {
                        tables.add(toTableInfo(parsed))
                    }
                }

                parsed is Insert -> issues.add(CollectionIssue(
                    IssueKind.SKIPPED, CollectionReason.OUT_OF_SCOPE_BY_DESIGN,
                    "행 데이터는 L0 최소저장 범위 밖이다(구조·메타데이터만 보관) — 정당한 제외이지만 분모에 남긴다",
                    locator, target))

                else -> issues.add(CollectionIssue(
                    IssueKind.SKIPPED, CollectionReason.UNSUPPORTED_STATEMENT,
                    "수집기가 처리하지 않는 구문이다 — DdlParser 는 CREATE TABLE 만 사실로 산출한다",
                    locator, target))
            }
        }

        val failed = issues.count { it.kind == IssueKind.FAILED }
        val partials = if (tables.isNotEmpty() && failed > 0) listOf(
            CollectionIssue(
                IssueKind.PARTIAL, CollectionReason.PARTIAL_COLLECTION,
                "부분 성공: 테이블 ${tables.size}건 산출 · 실패 ${failed}건 · 제외 " +
                    "${issues.size - failed}건 (입력 문장 ${tables.size + issues.size}건)",
                sourcePath?.let { "$it#L1" } ?: "#L1",
                sourcePath ?: "(ddl-text)")
        ) else emptyList()

        return SchemaModel(tables, issues, partials)
    }

    // ---- 문장 분리 -------------------------------------------------------------------------

    /**
     * 문장 분리. 문자열 리터럴·`--`·블록 주석·달러 인용(`$$`, `$tag$`) 안의 ';' 는 경계가 아니다.
     * 본문 안의 ';' 로 한 문장이 여러 조각이 되면 실패 건수가 부풀어 실행 간 비교가 불가능해진다(gold R-F-4).
     */
    private fun split(sql: String): List<RawStatement> {
        val out = mutableListOf<RawStatement>()
        var i = 0
        var line = 1
        var startIdx = 0
        var startLine = 1

        fun flush(endIdx: Int, endLine: Int) {
            statementOf(sql.substring(startIdx, endIdx), startLine, endLine)?.let { out.add(it) }
        }

        while (i < sql.length) {
            val c = sql[i]
            when {
                c == '\n' -> { line++; i++ }

                c == '-' && sql.startsWith("--", i) -> {
                    while (i < sql.length && sql[i] != '\n') i++
                }

                c == '/' && sql.startsWith("/*", i) -> {
                    i += 2
                    while (i < sql.length && !sql.startsWith("*/", i)) { if (sql[i] == '\n') line++; i++ }
                    i = minOf(sql.length, i + 2)
                }

                c == '\'' -> {
                    i++
                    while (i < sql.length) {
                        if (sql[i] == '\n') line++
                        if (sql[i] == '\'') {
                            if (i + 1 < sql.length && sql[i + 1] == '\'') { i += 2; continue }
                            i++
                            break
                        }
                        i++
                    }
                }

                c == '$' -> {
                    val tag = dollarTag(sql, i)
                    if (tag == null) i++
                    else {
                        i += tag.length
                        while (i < sql.length && !sql.startsWith(tag, i)) { if (sql[i] == '\n') line++; i++ }
                        i = minOf(sql.length, i + tag.length)
                    }
                }

                c == ';' -> {
                    flush(i + 1, line)
                    i++
                    startIdx = i
                    startLine = line
                }

                else -> i++
            }
        }
        if (startIdx < sql.length) flush(sql.length, line)
        return out
    }

    /** `$$` 또는 `$tag$` 여는 표시. 아니면 null(파라미터·문자 `$`). */
    private fun dollarTag(sql: String, at: Int): String? =
        Regex("^\\$[A-Za-z_][A-Za-z0-9_]*\\$|^\\$\\$").find(sql.substring(at))?.value

    /**
     * 주석·빈 줄만 남은 조각은 문장이 아니다. 좌표는 **첫 실제 코드 행**부터 센다.
     *
     * 주석 판정은 행 단위 근사다(행 주석 · 블록 주석 시작 · 이어지는 별표). 근사여도 방향이 정해져
     * 있다: 주석만 있는 조각을 문장으로 세면 없는 실패가 보고되므로, 그 방향으로 틀리지 않게 걷어낸다.
     */
    private fun statementOf(text: String, startLine: Int, endLine: Int): RawStatement? {
        fun isComment(line: String): Boolean {
            val t = line.trim()
            return t.startsWith("--") || t.startsWith("/*") || t.startsWith("*")
        }

        var first = -1
        var lineNo = startLine
        for (l in text.split("\n")) {
            if (l.isNotBlank() && !isComment(l)) { first = lineNo; break }
            lineNo++
        }
        if (first < 0) return null
        val body = text.lineSequence().filterNot { isComment(it) }.joinToString("\n").trim()
        if (body.isEmpty() || body == ";") return null
        return RawStatement(first, endLine, text)
    }

    private fun locator(sourcePath: String?, s: RawStatement): String {
        val span = if (s.startLine == s.endLine) "#L${s.startLine}" else "#L${s.startLine}-L${s.endLine}"
        return (sourcePath ?: "") + span
    }

    // ---- 문장 분류 -------------------------------------------------------------------------

    private val objectHead = Regex(
        "(?is)(CREATE\\s+(?:OR\\s+REPLACE\\s+)?(?:GLOBAL\\s+|LOCAL\\s+|TEMPORARY\\s+|TEMP\\s+|UNIQUE\\s+)*" +
            "(?:TABLE|MATERIALIZED\\s+VIEW|VIEW|INDEX|TRIGGER|FUNCTION|PROCEDURE|SEQUENCE|TYPE)" +
            "(?:\\s+IF\\s+NOT\\s+EXISTS)?\\s+[\\w\"`.\\[\\]]+" +
            "|INSERT\\s+INTO\\s+[\\w\"`.\\[\\]]+" +
            "|(?:ALTER|DROP|COMMENT|GRANT|SET|MERGE|UPDATE|DELETE|SELECT)\\s+[^\\n]*)")

    /** 문장 전체의 정규화된 머리 — 분류에만 쓴다(좌표 대상 문자열은 [target] 이 원문에서 만든다). */
    private fun head(text: String): String =
        text.lineSequence().filterNot { it.trim().startsWith("--") }
            .joinToString(" ").replace(Regex("\\s+"), " ").trim().uppercase()

    private fun unsupportedByDesign(head: String): Boolean =
        Regex("^CREATE (OR REPLACE )?(TRIGGER|FUNCTION|PROCEDURE)\\b").containsMatchIn(head)

    /**
     * 좌표가 가리키는 행에서 **실제로 조회되는** 대상 문자열. 원문 조각을 그대로 쓰되, 여러 행에 걸치면
     * 한 행에서 조회되지 않으므로 객체 이름만 남긴다.
     */
    private fun target(text: String): String {
        val body = text.lineSequence().filterNot { it.trim().startsWith("--") }.joinToString("\n")
        val m = objectHead.find(body)
            ?: return body.trim().lineSequence().firstOrNull()?.trim()?.take(80) ?: "?"
        val v = m.groupValues[1].trim()
        return if (v.contains("\n")) v.split(Regex("\\s+")).last() else v
    }

    private fun message(e: Exception): String =
        (e.message ?: e.javaClass.simpleName).lineSequence().first().trim().take(200)

    // ---- 부분 복구 탐지 ---------------------------------------------------------------------

    private val sqlTypeWords = setOf(
        "CHAR", "CHARACTER", "VARCHAR", "VARCHAR2", "NCHAR", "NVARCHAR", "TEXT", "CLOB", "BLOB", "BYTEA",
        "INT", "INTEGER", "SMALLINT", "TINYINT", "BIGINT", "NUMBER", "NUMERIC", "DECIMAL", "DEC",
        "FLOAT", "REAL", "DOUBLE", "MONEY", "BOOL", "BOOLEAN", "DATE", "TIME", "TIMESTAMP", "DATETIME",
        "SERIAL", "BIGSERIAL", "UUID", "JSON", "JSONB", "XML", "BINARY", "VARBINARY")

    /**
     * 컬럼 제약(columnSpecs) 안에 **다른 컬럼의 타입 선언**이 들어앉았는지 본다. 쉼표가 빠지면 파서는
     * 예외 없이 뒤 컬럼을 앞 컬럼의 제약으로 흡수하므로, 예외만 보면 이 실패는 조용히 통과한다.
     * 반환값은 흡수된 것으로 보이는 이름들.
     */
    private fun swallowedColumns(ct: CreateTable): List<String> {
        val out = mutableListOf<String>()
        for (cd in ct.columnDefinitions ?: emptyList()) {
            val specs = (cd.columnSpecs ?: emptyList()).joinToString(" ")
            // 값 표현식(DEFAULT · CHECK · REFERENCES · COMMENT)은 타입 낱말을 정당하게 품을 수 있다.
            val cleaned = specs
                .replace(Regex("(?is)\\bDEFAULT\\b\\s*('(?:[^']|'')*'|[\\w.$]+(\\s*\\([^)]*\\))?)"), " ")
                .replace(Regex("(?is)\\b(CHECK|COMMENT|COLLATE|REFERENCES|CONSTRAINT|USING|ON)\\b[^,]*"), " ")
                .replace(Regex("\\([^)]*\\)"), " ")
            val tokens = cleaned.split(Regex("[^\\w$]+")).filter { it.isNotBlank() }
            val idx = tokens.indexOfFirst { it.uppercase() in sqlTypeWords }
            if (idx >= 0) out.add(if (idx > 0) tokens[idx - 1] else tokens[idx])
        }
        return out
    }

    private fun unquote(s: String): String = s.trim().trim('"', '`', '[', ']')

    private fun toTableInfo(ct: CreateTable): TableInfo {
        val tableName = unquote(ct.table.name)
        val columns = (ct.columnDefinitions ?: emptyList()).map { cd ->
            val specs = (cd.columnSpecs ?: emptyList()).joinToString(" ").uppercase()
            ColumnInfo(unquote(cd.columnName), cd.colDataType.dataType, nullable = !specs.contains("NOT NULL"))
        }

        val pk = mutableListOf<String>()
        val fks = mutableListOf<ForeignKeyInfo>()

        // 1) 컬럼 인라인 제약: "PRIMARY KEY", "REFERENCES table(col)"
        for (cd in ct.columnDefinitions ?: emptyList()) {
            val specs = (cd.columnSpecs ?: emptyList()).joinToString(" ")
            val up = specs.uppercase()
            if (up.contains("PRIMARY KEY")) pk.add(unquote(cd.columnName))
            val m = Regex("REFERENCES\\s+([\\w\"`.]+)\\s*\\(\\s*([\\w\"`]+)\\s*\\)", RegexOption.IGNORE_CASE).find(specs)
            if (m != null) {
                fks.add(ForeignKeyInfo(
                    listOf(unquote(cd.columnName)),
                    unquote(m.groupValues[1].substringAfterLast('.')),
                    listOf(unquote(m.groupValues[2]))))
            }
        }

        // 2) 테이블-레벨 제약: getIndexes() 에 PRIMARY KEY / ForeignKeyIndex 로 등장
        for (idx in ct.indexes ?: emptyList()) {
            if (idx is ForeignKeyIndex) {
                fks.add(ForeignKeyInfo(
                    idx.columnsNames.map { unquote(it) },
                    unquote(idx.table.name),
                    (idx.referencedColumnNames ?: emptyList()).map { unquote(it) }))
            } else if (idx.type?.uppercase()?.contains("PRIMARY KEY") == true) {
                idx.columnsNames.forEach { pk.add(unquote(it)) }
            }
        }

        return TableInfo(tableName, columns, pk.distinct(), fks)
    }
}
