package com.ontostudio.rdb

import com.ontostudio.security.MaskLedger
import com.ontostudio.security.SqlTextMasker
import net.sf.jsqlparser.parser.CCJSqlParserUtil
import net.sf.jsqlparser.statement.create.table.CreateTable
import net.sf.jsqlparser.statement.create.table.ForeignKeyIndex
import net.sf.jsqlparser.statement.insert.Insert
import org.springframework.stereotype.Component

/** 파싱 결과 + 그 실행에서 무엇을 몇 건 가렸는지(원문 없음 · #115). */
data class MaskedSchema(val schema: SchemaModel, val masking: Map<String, Any>)

/**
 * DDL 텍스트 → SchemaModel. CREATE TABLE 만 사실로 산출하고, **처리하지 못한 문장은 좌표·사유와 함께
 * 반환형에 남긴다**(#114). 조용히 건너뛰는 경로는 없다 — 제외·실패·부분수집이 모두 [SchemaModel.issues] 에
 * 들어가므로 `tables + issues` 가 입력 문장 수를 설명한다(I3 R2).
 *
 * #115: 파싱 **전에** PII·시크릿 마스킹 단계를 통과한다. DDL 의 노출면은 주석과 DEFAULT 리터럴이며,
 * 마스킹은 리터럴·주석 안에서만 길이를 보존해 일어나므로 스키마 구조와 좌표는 그대로다. 보고 좌표가
 * 마스킹 후 텍스트에서 계산된다는 뜻이기도 하다 — 길이 보존이 곧 #114 좌표의 정확성 조건이다.
 */
@Component
class DdlParser(private val masker: SqlTextMasker = SqlTextMasker()) {

    /** 문장 하나. [startLine]~[endLine] 은 1-base 이며 종결 ';' 행을 포함한다. */
    private data class RawStatement(val startLine: Int, val endLine: Int, val text: String)

    /**
     * [sourceId]·[projectId] 는 산출물의 **수집 신원**이 된다(#113 계약 v0). DDL 텍스트는 커밋된 적 없는
     * 입력이므로 revision 은 입력 바이트에서 파생한 `inline:` 이다.
     *
     * [sourcePath] 는 **보고 좌표**에 붙일 원본 경로다(#114). 신원과 좌표는 다른 축이라 따로 받는다 —
     * 신원은 "무엇을 읽었나", 좌표는 "그 안 어디서 못 했나" 이고, 경로를 모르는 호출(요청 본문의 DDL)에서도
     * 신원은 여전히 성립해야 한다. 경로를 모르면 좌표는 `#L11-L14` 형태로만 남는다.
     */
    fun parse(
        sql: String,
        sourcePath: String? = null,
        sourceId: String = "db:ddl:schema",
        projectId: String = CollectionMetadata.DEFAULT_PROJECT_ID,
    ): SchemaModel = parseMasked(sql, sourcePath, sourceId, projectId).schema

    fun parseMasked(
        sql: String,
        sourcePath: String? = null,
        sourceId: String = "db:ddl:schema",
        projectId: String = CollectionMetadata.DEFAULT_PROJECT_ID,
    ): MaskedSchema {
        val ledger = MaskLedger()
        val masked = masker.mask(sql, ledger)
        // 파싱은 마스킹된 텍스트로, 신원은 **원문 바이트**로 만든다(#113). 마스킹된 바이트로 신원을
        // 잡으면 PII 만 다른 두 입력이 같은 revision 으로 접혀 서로 다른 수집이 구분되지 않는다.
        // 해시는 단방향이라 원문이 산출물에 남지 않는다.
        return MaskedSchema(parseInternal(masked, sql, sourcePath, sourceId, projectId), ledger.summary())
    }

    private fun parseInternal(
        sql: String,
        identityBytes: String,
        sourcePath: String?,
        sourceId: String,
        projectId: String,
    ): SchemaModel {
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

        // 신원은 수집기가 **실제로 읽은 바이트**(입력 SQL)에서 나온다 — 파싱 결과가 아니라.
        return SchemaModel(
            tables,
            CollectionMetadata.fromContent(sourceId, identityBytes.toByteArray(), "inline", projectId),
            issues,
            partials,
        )
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
                        // 마스커와 **같은 규칙**으로 백슬래시 이스케이프를 인정한다(리뷰 LOD-123).
                        // 두 스캐너가 리터럴 경계를 다르게 보면 마스킹된 구간과 문장 분리가 어긋난다.
                        if (sql[i] == '\\') { i += 2; continue }
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

    /**
     * 한정 이름을 **인용부호를 존중해** 조각으로 나눈다: `catalog.schema.table`.
     *
     * 단순 `split('.')` 은 인용부호 **안의** 점에서도 자른다 — `"my.schema"."t"` 가 세 조각이 되어
     * 소속이 `schema` 로 잘리고, 소속 없는 `"a.b"` 는 스키마 `a` 의 테이블 `b` 로 읽힌다. 같은 대상을
     * 인라인 `REFERENCES` 로 적을 때와 테이블-레벨 제약으로 적을 때(이쪽은 JSqlParser 가 읽는다)
     * 결과가 갈리면, 같은 스키마가 두 값으로 기록되어 신원(`contentHash`)이 표기 방식에 따라 달라진다.
     *
     * 조각은 인용부호를 **붙인 채로** 돌려준다 — 벗기는 일은 [unquote] 한 곳에서만 한다.
     * 표준 이스케이프(`"a""b"`)는 닫는 인용부호로 세지 않는다.
     */
    private fun splitQualified(qualified: String): List<String> {
        val parts = mutableListOf<String>()
        val sb = StringBuilder()
        var closing: Char? = null
        var i = 0
        val s = qualified.trim()
        while (i < s.length) {
            val c = s[i]
            when {
                closing != null -> {
                    // 겹친 인용부호는 이름 안의 문자다: `"a""b"` 는 조각 하나(`a"b`)다.
                    if (c == closing && i + 1 < s.length && s[i + 1] == c) { sb.append(c).append(c); i++ }
                    else { if (c == closing) closing = null; sb.append(c) }
                }
                c == '"' || c == '`' -> { closing = c; sb.append(c) }
                c == '[' -> { closing = ']'; sb.append(c) }
                c == '.' -> { parts.add(sb.toString()); sb.clear() }
                else -> sb.append(c)
            }
            i++
        }
        parts.add(sb.toString())
        return parts
    }

    /**
     * `schema.table` · `catalog.schema.table` 에서 **소속**(마지막 이름 바로 앞 부분)만 취한다(#126).
     * 카탈로그는 모델이 담지 않는다([TableInfo] 참조) — JDBC 경로와 같은 축만 남겨야 두 경로의
     * 산출물이 같은 것을 뜻한다.
     */
    private fun schemaOf(qualified: String): String? =
        splitQualified(qualified).dropLast(1).lastOrNull()?.let { unquote(it) }?.takeIf { it.isNotEmpty() }

    /** 한정 이름의 대상 이름. 인용부호 안의 점은 이름의 일부다(`"a.b"` 는 테이블 `a.b`). */
    private fun nameOf(qualified: String): String = unquote(splitQualified(qualified).last())

    private fun toTableInfo(ct: CreateTable): TableInfo {
        val tableName = unquote(ct.table.name)
        val tableSchema = ct.table.schemaName?.let { unquote(it) }?.takeIf { it.isNotEmpty() }
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
                    nameOf(m.groupValues[1]),
                    listOf(unquote(m.groupValues[2])),
                    refSchema = schemaOf(m.groupValues[1])))
            }
        }

        // 2) 테이블-레벨 제약: getIndexes() 에 PRIMARY KEY / ForeignKeyIndex 로 등장
        for (idx in ct.indexes ?: emptyList()) {
            if (idx is ForeignKeyIndex) {
                fks.add(ForeignKeyInfo(
                    idx.columnsNames.map { unquote(it) },
                    unquote(idx.table.name),
                    (idx.referencedColumnNames ?: emptyList()).map { unquote(it) },
                    refSchema = idx.table.schemaName?.let { unquote(it) }?.takeIf { it.isNotEmpty() }))
            } else if (idx.type?.uppercase()?.contains("PRIMARY KEY") == true) {
                idx.columnsNames.forEach { pk.add(unquote(it)) }
            }
        }

        return TableInfo(tableName, columns, pk.distinct(), fks, schema = tableSchema)
    }
}
