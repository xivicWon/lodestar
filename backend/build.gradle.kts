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
    // #115 마스킹 교차언어 증거도 같은 이유로 입력이다. 규칙 스펙 단일 원본도 함께 — 원본이 바뀌면
    // 사본 해시 검사와 gold 게이트를 다시 돌려야 한다.
    inputs.files(fileTree(File(rootDir.parentFile, "docs/superpowers/specs/bench/masking/runs")))
        .withPropertyName("maskingBenchEvidence")
        .optional()
    inputs.files(File(rootDir.parentFile, "docs/superpowers/specs/security/masking-rules.v0.json"))
        .withPropertyName("maskingRuleSpec")
        .optional()
    // 증거 최초 생성 우회 플래그는 테스트 JVM 으로 전달돼야 의미가 있다.
    for (flag in listOf("L0_PROBE_BOOTSTRAP", "MASK_EVIDENCE_BOOTSTRAP")) {
        System.getProperty(flag)?.let { systemProperty(flag, it) }
    }
}
kotlin { jvmToolchain(21) }
