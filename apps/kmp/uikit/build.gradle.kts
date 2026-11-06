// uikit — 디자인 토큰(DesignTokens.kt 는 scripts/gen_tokens.py 생성물) + 공통 컴포넌트. 웹 @nova/ui 와 같은 이름 · 같은 규칙.
buildscript {
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
if (withAndroid) apply(plugin = "com.android.library")

kotlin {
    jvmToolchain(21)
    if (withAndroid) androidTarget()
    jvm("desktop")
    iosX64(); iosArm64(); iosSimulatorArm64()
    sourceSets {
        commonMain.dependencies {
            api(project(":shared"))
            api(compose.runtime)
            api(compose.foundation)
            api(compose.material3)
            api(compose.ui)
        }
    }
}

if (withAndroid) {
    extensions.getByName("android").withGroovyBuilder {
        "setNamespace"("kr.nova.uikit")
        "setCompileSdk"(34)
        "defaultConfig" { "setMinSdk"(26) }
    }
}
