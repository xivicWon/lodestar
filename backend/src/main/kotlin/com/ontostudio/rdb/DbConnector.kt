package com.ontostudio.rdb

import com.ontostudio.dto.ApiException
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Component
import java.sql.Connection
import java.sql.DriverManager

/**
 * DB 접속정보. [vendor] 로 다형화(기본 postgresql). database 는 선택
 * (비우면 DB 미지정으로 접속 — 카탈로그 열거 용도).
 */
data class ConnectionInfo(
    val host: String,
    val port: Int,
    val database: String = "",
    val user: String,
    val password: String,
    val vendor: String = "postgresql",
)

/** ConnectionInfo → JDBC Connection. 벤더별 URL을 만든다(DatabaseMetaData는 벤더 무관). */
@Component
class DbConnector {

    /** 벤더별 JDBC URL. (순수·테스트 가능) */
    internal fun jdbcUrl(info: ConnectionInfo): String {
        val db = info.database.trim()
        return when (info.vendor.lowercase()) {
            "mysql", "mariadb" -> buildString {
                append("jdbc:mysql://").append(info.host).append(':').append(info.port).append('/')
                if (db.isNotEmpty()) append(db)
                append("?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC&connectTimeout=8000")
            }
            else -> "jdbc:postgresql://${info.host}:${info.port}/$db"
        }
    }

    fun open(info: ConnectionInfo): Connection {
        return try {
            DriverManager.getConnection(jdbcUrl(info), info.user, info.password)
        } catch (e: Exception) {
            throw ApiException(HttpStatus.BAD_REQUEST, "connect_failed",
                "DB 연결 실패(${info.vendor}): ${e.message}", null)
        }
    }
}
