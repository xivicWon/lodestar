package com.ontostudio.project

import com.ontostudio.core.OntologyMapper
import com.ontostudio.dto.ApiException
import com.ontostudio.dto.OntologyMetaDto
import com.ontostudio.io.IoService
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import kotlin.io.path.exists
import kotlin.io.path.isRegularFile
import kotlin.io.path.name
import kotlin.io.path.nameWithoutExtension

@Service
class ProjectService(
    private val io: IoService,
    private val mapper: OntologyMapper,
    @Value("\${lodestar.projects.dir:./data/projects}") private val projectsDir: String
) {
    private fun dir(): Path {
        val p = Paths.get(projectsDir)
        if (!p.exists()) Files.createDirectories(p)
        return p
    }

    private fun sanitize(name: String): String {
        val clean = name.filter { it.isLetterOrDigit() || it == '_' || it == '-' }
        if (clean.isEmpty()) throw ApiException(
            HttpStatus.BAD_REQUEST, "invalid_name",
            "프로젝트 이름이 유효하지 않습니다: $name", null
        )
        return clean
    }

    fun list(): List<String> {
        val d = dir()
        return Files.list(d).use { stream ->
            stream.filter { it.isRegularFile() && it.name.endsWith(".ttl") }
                .map { it.nameWithoutExtension }
                .sorted()
                .toList()
        }
    }

    fun save(name: String): List<String> {
        val safe = sanitize(name)
        val bytes = io.export("turtle")
        Files.write(dir().resolve("$safe.ttl"), bytes)
        return list()
    }

    fun load(name: String): OntologyMetaDto {
        val safe = sanitize(name)
        val file = dir().resolve("$safe.ttl")
        if (!file.exists()) throw ApiException(
            HttpStatus.NOT_FOUND, "not_found",
            "프로젝트를 찾을 수 없습니다: $safe", null
        )
        io.load(Files.readAllBytes(file), "http://onto-studio/ex#")
        return mapper.meta()
    }
}
