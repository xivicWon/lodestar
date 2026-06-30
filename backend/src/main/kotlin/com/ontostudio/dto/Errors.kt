package com.ontostudio.dto

import org.springframework.http.HttpStatus

data class ApiError(val error: String, val message: String, val targetIri: String? = null)

class ApiException(
    val status: HttpStatus, val error: String,
    override val message: String, val targetIri: String? = null
) : RuntimeException(message)
