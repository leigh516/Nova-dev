rootProject.name = "nova-kmp"

pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
        google()
    }
}
dependencyResolutionManagement {
    repositories {
        mavenCentral()
        google()
    }
}

include(":shared")
// Compose UI 는 androidx(Google Maven) 의존 — 차단된 환경에서는 -Pnova.skipCompose=true 로 shared 만 검증
if (providers.gradleProperty("nova.skipCompose").orNull != "true") {
    include(":uikit")       // 디자인 토큰(생성물) + 공통 컴포넌트 — 웹 @nova/ui 와 같은 이름
    include(":composeApp")  // 샘플 앱: Desktop(JVM) · iOS 항상, Android 는 ANDROID_HOME 이 있을 때만
}
