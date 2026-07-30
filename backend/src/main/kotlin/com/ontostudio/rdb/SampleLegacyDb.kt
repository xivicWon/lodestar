package com.ontostudio.rdb

import com.ontostudio.dto.ApiException
import com.ontostudio.security.MaskLedger
import com.ontostudio.security.SqlTextMasker
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Component
import java.sql.Connection
import java.sql.DriverManager

/**
 * 적재 정책 (#115 · #85 데이터 최소화).
 *
 * - [maskRowData] `true`(기본): 모든 문장이 **적재 전에** 마스킹 단계를 통과한다. 저장·로그보다
 *   마스킹이 먼저다(#85). 길이를 보존하므로 컬럼 길이·좌표가 깨지지 않는다.
 * - [minimizeRowData] `true`: DML(INSERT/UPDATE/DELETE/MERGE)을 아예 실행하지 않는다 — "구조·
 *   메타데이터만 수집" 이라는 #85 의 기본 원칙에 가장 가까운 형태다. 기본값이 `false` 인 이유는
 *   #88 baseline 계측기(`L0DbSourceProbeTest`)가 적재된 행을 관측 대상으로 고정해 두었기 때문이며,
 *   기본값 전환은 L0 재측정(gold revision 재고정 + 승인)을 필요로 한다 — 문서 §후속 이슈 참조.
 */
data class IngestPolicy(
    val maskRowData: Boolean = true,
    val minimizeRowData: Boolean = false,
)

/**
 * E1-2: 번들된 지저분한 레거시 샘플 DDL을 임베디드 H2에 적재하고 Connection을 돌려준다.
 * 기본 H2 모드(미인용 식별자 대문자 유지)로 TB_CUST_MST 같은 원형 이름을 보존한다.
 */
@Component
class SampleLegacyDb(private val masker: SqlTextMasker = SqlTextMasker()) {

    @Volatile
    private var maskingSummary: Map<String, Any> = emptyMap()

    @Volatile
    private var skippedDml: Int = 0

    /** 이 적재 실행에서 무엇을 몇 건 가렸는지(원문 없음). 마지막 [open] 호출의 집계다. */
    val lastMasking: Map<String, Any> get() = maskingSummary

    /** 마지막 [open] 호출이 최소화 정책으로 건너뛴 DML 문장 수. */
    val lastSkippedDml: Int get() = skippedDml

    fun open(policy: IngestPolicy = IngestPolicy()): Connection {
        val sql = javaClass.getResource("/com/ontostudio/rdb/legacy-sample.sql")?.readText()
            ?: throw ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "sample_missing",
                "샘플 스크립트를 찾을 수 없습니다", null)
        val conn = DriverManager.getConnection("jdbc:h2:mem:legacy_${System.nanoTime()};DB_CLOSE_DELAY=-1")
        val ledger = MaskLedger()
        var skipped = 0
        conn.createStatement().use { st ->
            for (chunk in sql.split(";")) {
                // 주석 라인(--) 제거 후 실행
                val stmt = chunk.lineSequence()
                    .filterNot { it.trim().startsWith("--") }
                    .joinToString("\n").trim()
                if (stmt.isEmpty()) continue
                if (policy.minimizeRowData && isDml(stmt)) { skipped++; continue }
                // #115: 저장보다 마스킹이 먼저다.
                st.execute(if (policy.maskRowData) masker.mask(stmt, ledger) else stmt)
            }
        }
        maskingSummary = ledger.summary()
        skippedDml = skipped
        return conn
    }

    private fun isDml(stmt: String): Boolean {
        val head = stmt.trimStart().uppercase()
        return head.startsWith("INSERT") || head.startsWith("UPDATE") ||
            head.startsWith("DELETE") || head.startsWith("MERGE")
    }
}
