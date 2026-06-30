package com.ontostudio.api

import com.ontostudio.dto.ApiError
import com.ontostudio.dto.ApiException
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.RestControllerAdvice
import org.springframework.web.servlet.resource.NoResourceFoundException

@RestControllerAdvice
class ApiExceptionHandler {
    @ExceptionHandler(ApiException::class)
    fun handle(e: ApiException): ResponseEntity<ApiError> =
        ResponseEntity.status(e.status).body(ApiError(e.error, e.message, e.targetIri))

    /** Unknown route / missing static resource → proper 404 (not a 500 "internal"). */
    @ExceptionHandler(NoResourceFoundException::class)
    fun handleNotFound(e: NoResourceFoundException): ResponseEntity<ApiError> =
        ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(ApiError("not_found", "요청한 경로를 찾을 수 없습니다: ${e.resourcePath}", null))

    @ExceptionHandler(Exception::class)
    fun handleGeneric(e: Exception): ResponseEntity<ApiError> =
        ResponseEntity.status(500).body(ApiError("internal", e.message ?: "internal error", null))
}
