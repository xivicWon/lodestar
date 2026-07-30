package com.ontostudio.rdb

import java.io.File

/**
 * 리포 루트 — gradle 이 `lodestar.repo.root` 로 넘긴다(build.gradle.kts). 없으면 위로 올라가며 찾는다.
 *
 * 탐색만 쓰면 `.git` 이 없는 소스 아카이브에서 테스트가 **환경 때문에** 붉어진다. 증거 파일의 위치는
 * 빌드가 아는 사실이므로 빌드가 알려주는 것이 맞다.
 */
object RepoRoot {
    val path: File by lazy {
        System.getProperty("lodestar.repo.root")?.let(::File)?.takeIf { it.isDirectory }
            ?: search()
    }

    private fun search(): File {
        var d: File? = File("").absoluteFile
        while (d != null && !File(d, ".git").exists()) d = d.parentFile
        return d ?: error("리포 루트를 찾지 못했다 — gradle 이 -Dlodestar.repo.root 를 넘기지 않았다")
    }
}
