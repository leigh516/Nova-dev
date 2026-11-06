plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.kotlin.serialization)
}

kotlin {
    jvmToolchain(21)
    jvm()
    iosX64(); iosArm64(); iosSimulatorArm64()
    // Android 타깃(composeApp androidTarget)은 jvm 변형을 소비한다

    sourceSets {
        commonMain.dependencies {
            api(libs.ktor.client.core)
            implementation(libs.ktor.client.content.negotiation)
            implementation(libs.ktor.serialization.json)
            api(libs.coroutines.core)
            api(libs.serialization.json)
            api(libs.datetime) // 시각 표시 fmtAt(T04-7.01) — 버전 목록에 이미 있던 것을 연결만
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
            implementation(libs.ktor.client.mock)
            implementation(libs.coroutines.test)
        }
        jvmMain.dependencies { implementation(libs.ktor.client.cio) }
        iosMain.dependencies { implementation(libs.ktor.client.darwin) }
    }
}

// 게이트웨이 실연동 스모크: gradle -Pnova.skipCompose=true :shared:smoke -Papi=http://127.0.0.1:8080/v1
tasks.register<JavaExec>("smoke") {
    group = "verification"
    description = "실행 중인 게이트웨이에 로그인 → 항목 만들기 → 목록 → 보관 확인"
    val jvm = kotlin.jvm()
    val main = jvm.compilations.getByName("main")
    dependsOn(main.compileTaskProvider)
    classpath = files(main.output.allOutputs, main.runtimeDependencyFiles)
    mainClass.set("kr.nova.shared.SmokeKt")
    jvmArgs("-Dstdout.encoding=UTF-8", "-Dfile.encoding=UTF-8")
    args(providers.gradleProperty("api").orElse("http://127.0.0.1:8080/v1").get())
}
