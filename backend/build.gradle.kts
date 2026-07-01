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
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation(kotlin("test"))
}

tasks.test { useJUnitPlatform() }
kotlin { jvmToolchain(21) }
