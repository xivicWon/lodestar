plugins {
    kotlin("jvm") version "2.1.20"
    kotlin("plugin.spring") version "2.1.20"
    id("org.springframework.boot") version "3.4.4"
    id("io.spring.dependency-management") version "1.1.7"
}

group = "com.ontostudio"
version = "0.1.0"

repositories { mavenCentral() }

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.jetbrains.kotlin:kotlin-reflect")
    implementation("net.sourceforge.owlapi:owlapi-distribution:5.5.0")
    implementation("net.sourceforge.owlapi:org.semanticweb.hermit:1.4.5.519") {
        exclude(group = "net.sourceforge.owlapi")
    }
    implementation("com.github.jsqlparser:jsqlparser:4.9")
    implementation("org.postgresql:postgresql:42.7.4")
    implementation("com.mysql:mysql-connector-j:9.1.0")
    implementation("com.h2database:h2:2.3.232")
    implementation("org.xerial:sqlite-jdbc:3.45.3.0")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation(kotlin("test"))
}

// 수집기 버전을 손으로 적지 않게 한다 — 손으로 옮긴 버전은 올려도 티가 나지 않고, 그러면
// collectorVersion 이 재현 대상을 잘못 가리킨다(#112 가 codegraph 에서 고친 것과 같은 결함).
// 대상 파일만 지정한다: 전체 expand 는 legacy-sample.sql 같은 리소스의 ${...} 를 망가뜨린다.
tasks.processResources {
    filesMatching("lodestar-build.properties") { expand("version" to project.version) }
}

tasks.test {
    useJUnitPlatform()
    // L0 프로브(#88)는 리포에 커밋된 증거와 대조한다. 그 파일을 입력으로 선언하지 않으면
    // 증거가 바뀌거나 사라져도 gradle 이 UP-TO-DATE 로 판단해 검사를 조용히 건너뛴다.
    inputs.files(fileTree(File(rootDir.parentFile, "docs/superpowers/specs/bench/l0/runs")))
        .withPropertyName("l0BenchEvidence")
        .optional()
    inputs.files(fileTree(File(rootDir.parentFile, "docs/superpowers/specs/bench/l0/metadata")))
        .withPropertyName("l0MetadataEvidence")
        .optional()
    // 부트스트랩 스위치는 gradle JVM 이 아니라 **테스트 JVM** 이 읽어야 한다.
    // 전달하지 않으면 문서에 적힌 `-DL0_PROBE_BOOTSTRAP=true` 가 조용히 무시된다.
    // 리포 루트를 **명시적으로** 넘긴다. 테스트가 .git 을 찾아 올라가면 .git 이 없는 소스 아카이브에서
    // 환경 때문에 붉어진다(worktree 는 .git 이 파일이라 exists() 로 잘 찾지만, 아카이브는 아예 없다).
    systemProperty("lodestar.repo.root", rootDir.parentFile.absolutePath)
    // providers.systemProperty 로 읽는다 — System.getProperty 를 구성 단계에서 직접 읽으면
    // configuration cache 가 추적하지 못하는 입력이 된다.
    for (key in listOf("L0_PROBE_BOOTSTRAP", "L0_METADATA_BOOTSTRAP", "L0_METADATA_FORCE")) {
        providers.systemProperty(key).orNull?.let { systemProperty(key, it) }
    }
}
kotlin { jvmToolchain(21) }
