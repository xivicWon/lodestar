package com.ontostudio.rdb

import java.security.MessageDigest

/**
 * L0 수집 식별 메타데이터 — DB·CODE 공통 계약 v0 의 DB 트랙 구현.
 *
 * 계약: `docs/superpowers/specs/2026-07-30-m0-l0-collection-metadata-contract.md`
 *
 * 다섯 필드는 **산출물만 보고** "무엇을, 어느 스냅샷을, 어떤 수집기로 만들었는가" 에 답한다.
 * 검증을 [init] 에 두는 이유: 빈 값이나 `"unknown"` 같은 플레이스홀더로 완전성 게이트를 통과시키는
 * 길을 타입 단계에서 막기 위해서다. 모르는 신원은 지어내지 않고 [revision] 의 스킴 접두어로 드러낸다.
 */
data class CollectionMetadata(
    val projectId: String,
    val sourceId: String,
    val revision: String,
    val contentHash: String,
    val collectorVersion: String,
) {
    init {
        requireIdentity("projectId", projectId)
        requireIdentity("sourceId", sourceId)
        require(REVISION.matches(revision)) {
            "revision 은 커밋 sha(7~40 hex) 또는 선언된 비-VCS 스킴이어야 한다: '$revision'"
        }
        require(CONTENT_HASH.matches(contentHash)) {
            "contentHash 는 'sha256:<64 hex>' 여야 한다: '$contentHash'"
        }
        require(COLLECTOR_VERSION.matches(collectorVersion)) {
            "collectorVersion 은 '<이름>@<semver>[+<commit>]' 여야 한다: '$collectorVersion'"
        }
        // 비-VCS revision 은 **이 산출물의 내용**에서 나온 것이어야 한다. 형식만 보면
        // 다른 스냅샷의 해시를 붙여도 통과하고, 그러면 revision 이 신원을 가리키지 않는다.
        val scheme = revision.substringBefore(':', missingDelimiterValue = "")
        if (scheme in REVISION_SCHEMES) {
            val expected = revisionOf(scheme, contentHash)
            require(revision == expected) {
                "revision 이 contentHash 에서 파생되지 않았다: '$revision' (기대: '$expected')"
            }
        }
    }

    companion object {
        /** 완전성(completeness) 산식의 분모. #88 프로브가 센 것과 같은 다섯 필드다. */
        val REQUIRED_FIELDS = listOf("projectId", "sourceId", "revision", "contentHash", "collectorVersion")

        const val DEFAULT_PROJECT_ID = "lodestar"

        /** VCS 가 정본이 아닌 소스가 쓰는 revision 접두어 — "이건 커밋이 아니다" 를 드러낸다. */
        val REVISION_SCHEMES = listOf("inline", "bundle", "live", "dirty", "nogit")

        private val REVISION =
            Regex("^(?:[0-9a-f]{7,40}|(?:${REVISION_SCHEMES.joinToString("|")}):[0-9a-f]{12})$")
        private val CONTENT_HASH = Regex("^sha256:[0-9a-f]{64}$")
        private val COLLECTOR_VERSION = Regex("^[a-z0-9][a-z0-9-]*@\\d+\\.\\d+\\.\\d+(?:\\+[0-9a-f]{7,40})?$")

        /** 신원 자리를 채운 척하는 값들 — 이걸 허용하면 게이트가 통과를 뜻하지 않게 된다. */
        private val PLACEHOLDERS = setOf("unknown", "n/a", "na", "null", "none", "todo", "tbd", "-", "?")

        private fun requireIdentity(field: String, value: String) {
            require(value.isNotBlank()) { "$field 는 비어있을 수 없다" }
            require(value.trim().lowercase() !in PLACEHOLDERS) {
                "$field 에 플레이스홀더를 쓸 수 없다: '$value' — 모르는 신원은 지어내지 않는다"
            }
        }

        fun sha256(bytes: ByteArray): String =
            "sha256:" + MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }

        /**
         * 내용에서 파생한 스냅샷 식별자. 시각을 쓰지 않는 것이 요점이다 —
         * 같은 입력의 두 실행이 달라지면 결정성 측정(I1 H1)이 오염된다.
         */
        fun revisionOf(scheme: String, contentHash: String): String {
            require(scheme in REVISION_SCHEMES) { "선언되지 않은 revision 스킴: '$scheme'" }
            return "$scheme:" + contentHash.removePrefix("sha256:").take(12)
        }

        /** 수집기가 실제로 읽은 바이트에서 신원을 만든다. */
        fun fromContent(
            sourceId: String,
            bytes: ByteArray,
            scheme: String,
            projectId: String = DEFAULT_PROJECT_ID,
            collectorVersion: String = DbCollector.version(),
        ): CollectionMetadata {
            val hash = sha256(bytes)
            return CollectionMetadata(projectId, sourceId, revisionOf(scheme, hash), hash, collectorVersion)
        }
    }
}

/** DB 수집기(DdlParser · MetadataService)의 신원. */
object DbCollector {
    const val NAME = "lodestar-rdb-collector"

    /**
     * backend 모듈 버전 — **빌드가 넣어준다**(`processResources` 가 `lodestar-build.properties` 를
     * 채운다). 손으로 적으면 gradle 버전을 올려도 티가 나지 않고, 그러면 `collectorVersion` 이
     * 재현 대상을 잘못 가리킨다. 못 읽으면 지어내지 않고 실패한다(codegraph 쪽과 같은 규칙).
     */
    val VERSION: String by lazy {
        val props = java.util.Properties()
        DbCollector::class.java.getResourceAsStream("/lodestar-build.properties")?.use(props::load)
            ?: error("빌드 버전 리소스가 없다 — processResources 가 lodestar-build.properties 를 만들지 않았다")
        props.getProperty("version")?.trim()?.takeIf { it.isNotEmpty() && !it.contains("\${") }
            ?: error("빌드 버전이 채워지지 않았다: ${props.getProperty("version")}")
    }

    private val COMMIT = Regex("^[0-9a-f]{7,40}$")

    /**
     * 빌드가 커밋을 알면 `+<sha>` 를 붙인다 — 산출물만으로 재현 대상을 특정할 수 있게 하는 부분이다.
     * (`-Dlodestar.build.revision=<sha>` 또는 환경변수 `LODESTAR_BUILD_REVISION`)
     */
    fun version(): String = version(
        System.getProperty("lodestar.build.revision"), System.getenv("LODESTAR_BUILD_REVISION"))

    /**
     * 후보를 순서대로 보되 **유효한 첫 값**을 쓴다. `?:` 로 이으면 비어 있거나 형식에 맞지 않는
     * 속성 하나가 유효한 환경변수를 가려, 산출물에서 커밋 식별자가 통째로 사라진다.
     */
    internal fun version(vararg commitCandidates: String?): String {
        val commit = commitCandidates.filterNotNull()
            .firstNotNullOfOrNull { it.trim().lowercase().takeIf(COMMIT::matches) }
        return if (commit != null) "$NAME@$VERSION+$commit" else "$NAME@$VERSION"
    }
}
