import org.jetbrains.compose.desktop.application.dsl.TargetFormat

// 샘플 앱 — Compose Multiplatform 단일 UI 코드로 Desktop(JVM) · iOS · Android. Android 타깃은 ANDROID_HOME(SDK)이 있을 때만.
buildscript {
    // AGP 는 Google Maven 에만 있으므로 SDK 가 있을 때만 클래스패스에 올린다
    if (System.getenv("ANDROID_HOME") != null) {
        repositories { google(); mavenCentral() }
        dependencies { classpath("com.android.tools.build:gradle:8.5.2") }
    }
}

plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.compose)
}

val withAndroid = System.getenv("ANDROID_HOME") != null
if (withAndroid) apply(plugin = "com.android.application")

kotlin {
    jvmToolchain(21)
    if (withAndroid) androidTarget()
    jvm("desktop")
    listOf(iosX64(), iosArm64(), iosSimulatorArm64()).forEach {
        it.binaries.framework { baseName = "ComposeApp"; isStatic = true }
    }
    sourceSets {
        commonMain.dependencies {
            implementation(project(":uikit"))
            implementation(libs.coroutines.core)
        }
        val desktopMain by getting {
            dependencies {
                implementation(compose.desktop.currentOs)
                implementation(libs.coroutines.swing)
            }
        }
        if (withAndroid) {
            val androidMain by getting { dependencies { implementation(libs.androidx.activity.compose) } }
        }
    }
}

if (withAndroid) {
    // AGP 타입을 컴파일 시점에 참조하지 않도록 동적 구성(AGP 가 없을 때도 스크립트가 컴파일됨)
    extensions.getByName("android").withGroovyBuilder {
        "setNamespace"("kr.nova.app")
        "setCompileSdk"(34)
        "defaultConfig" {
            "setApplicationId"("kr.nova.app"); "setMinSdk"(26); "setTargetSdk"(34)
            "setVersionCode"(1); "setVersionName"("0.1.0")
        }
    }
}

compose.desktop {
    application {
        mainClass = "kr.nova.app.MainKt"
        nativeDistributions {
            targetFormats(TargetFormat.Dmg, TargetFormat.Msi, TargetFormat.Deb)
            packageName = "Nova"
            packageVersion = "1.0.0"
        }
    }
}

// 헤드리스 화면 스냅샷: 실행 중인 게이트웨이 데이터로 화면 PNG 생성
//   gradle :composeApp:snapshots -Papi=http://127.0.0.1:8080/v1 -Pout=../../../docs/screenshots
tasks.register<JavaExec>("snapshots") {
    group = "verification"
    val desktop = kotlin.jvm("desktop").compilations.getByName("main")
    dependsOn(desktop.compileTaskProvider)
    classpath = files(desktop.output.allOutputs, desktop.runtimeDependencyFiles)
    mainClass.set("kr.nova.app.SnapshotKt")
    jvmArgs("-Djava.awt.headless=true", "-Dstdout.encoding=UTF-8", "-Dfile.encoding=UTF-8")
    args(
        providers.gradleProperty("api").orElse("http://127.0.0.1:8080/v1").get(),
        providers.gradleProperty("out").orElse(layout.buildDirectory.dir("snapshots").get().asFile.absolutePath).get(),
    )
}
