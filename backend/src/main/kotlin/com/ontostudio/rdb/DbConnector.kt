package com.ontostudio.rdb

import com.ontostudio.dto.ApiException
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Component
import java.sql.Connection
import java.sql.DriverManager

data class ConnectionInfo(
    val host: String, val port: Int, val database: String,
    val user: String, val password: String
)

/** ConnectionInfo → PostgreSQL JDBC Connection. 실패 시 400 connect_failed. */
@Component
class DbConnector {
    fun open(info: ConnectionInfo): Connection {
        val url = "jdbc:postgresql://${info.host}:${info.port}/${info.database}"
        return try {
            DriverManager.getConnection(url, info.user, info.password)
        } catch (e: Exception) {
            throw ApiException(HttpStatus.BAD_REQUEST, "connect_failed",
                "DB 연결 실패: ${e.message}", null)
        }
    }
}
