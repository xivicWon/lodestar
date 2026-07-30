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

tasks.test {
    useJUnitPlatform()
    // L0 프로브(#88)는 리포에 커밋된 증거와 대조한다. 그 파일을 입력으로 선언하지 않으면
    // 증거가 바뀌거나 사라져도 gradle 이 UP-TO-DATE 로 판단해 검사를 조용히 건너뛴다.
    inputs.files(fileTree(File(rootDir.parentFile, "docs/superpowers/specs/bench/l0/runs")))
        .withPropertyName("l0BenchEvidence")
        .optional()
    // 새 runId 를 처음 만들 때만 쓰는 1회 우회. 테스트 JVM 은 데몬의 -D 를 물려받지 않으므로
    // 여기서 명시적으로 넘긴다 — 넘기지 않으면 부트스트랩 플래그가 조용히 무시된다.
    System.getProperty("L0_PROBE_BOOTSTRAP")?.let { systemProperty("L0_PROBE_BOOTSTRAP", it) }
}
kotlin { jvmToolchain(21) }
