package com.ontostudio.rdb

import com.ontostudio.dto.ApiException
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Component
import java.sql.Connection
import java.sql.DriverManager

/**
 * E1-2: 번들된 지저분한 레거시 샘플 DDL을 임베디드 H2에 적재하고 Connection을 돌려준다.
 * 기본 H2 모드(미인용 식별자 대문자 유지)로 TB_CUST_MST 같은 원형 이름을 보존한다.
 */
@Component
class SampleLegacyDb {
    fun open(): Connection {
        val sql = javaClass.getResource("/com/ontostudio/rdb/legacy-sample.sql")?.readText()
            ?: throw ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "sample_missing",
                "샘플 스크립트를 찾을 수 없습니다", null)
        val conn = DriverManager.getConnection("jdbc:h2:mem:legacy_${System.nanoTime()};DB_CLOSE_DELAY=-1")
        conn.createStatement().use { st ->
            for (chunk in sql.split(";")) {
                // 주석 라인(--) 제거 후 실행
                val stmt = chunk.lineSequence()
                    .filterNot { it.trim().startsWith("--") }
                    .joinToString("\n").trim()
                if (stmt.isNotEmpty()) st.execute(stmt)
            }
        }
        return conn
    }
}
