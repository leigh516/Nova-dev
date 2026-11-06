package kr.nova.app

import androidx.compose.ui.ImageComposeScene
import androidx.compose.ui.unit.Density
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kr.nova.shared.ApiClient
import kr.nova.shared.AppStore
import kr.nova.shared.createItem
import org.jetbrains.skia.EncodedImageFormat
import java.io.File

/**
 * 화면 스냅샷(헤드리스) — 실제 게이트웨이 데이터로 각 화면을 오프스크린 렌더링해 PNG 로 저장.
 *   gradle :composeApp:snapshots -Papi=http://127.0.0.1:8080/v1 -Pout=../../../docs/screenshots
 */
fun main(args: Array<String>): Unit = runBlocking {
    val base = args.getOrNull(0) ?: "http://127.0.0.1:8080/v1"
    val out = File(args.getOrNull(1) ?: "build/snapshots").apply { mkdirs() }
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    fun shot(name: String, store: AppStore?, screen: Screen, dark: Boolean = false) = runBlocking {
        // 390×844dp 휴대폰 화면(밀도 2 → 780×1688 픽셀)
        val scene = ImageComposeScene(780, 1688, Density(2f)) { App(base, screen, store, dark) }
        var t = 0L
        repeat(40) { scene.render(t); t += 50_000_000; delay(50) }
        val img = scene.render(t)
        File(out, "kmp-$name.png").writeBytes(img.encodeToData(EncodedImageFormat.PNG)!!.bytes)
        scene.close()
        println("✓ kmp-$name.png")
    }

    // 부품 갤러리 — 서버 데이터가 필요 없어 로그인 전에 찍는다. 렌더만으로 onApprove 가 불리면 실패(AI 확인 카드 계약)
    fun gallery(name: String, dark: Boolean) = runBlocking {
        var approveCalls = 0
        val scene = ImageComposeScene(780, 3000, Density(2f)) { UikitGallery(dark) { approveCalls++ } }
        var t = 0L
        repeat(20) { scene.render(t); t += 50_000_000; delay(50) }
        val img = scene.render(t)
        scene.close()
        check(approveCalls == 0) { "AI 확인 카드가 렌더만으로 onApprove 를 ${approveCalls}번 불렀습니다" }
        File(out, "kmp-$name.png").writeBytes(img.encodeToData(EncodedImageFormat.PNG)!!.bytes)
        println("✓ kmp-$name.png (렌더만으로 승인 호출 0회)")
    }
    gallery("gallery", dark = false)
    gallery("gallery-dark", dark = true)

    // 템플릿 상태 갤러리 — 상태 3종을 서버 없이 라이트 · 다크로(T07-3.03)
    fun templates(name: String, dark: Boolean) = runBlocking {
        val scene = ImageComposeScene(780, 2600, Density(2f)) { TemplateGallery(dark) }
        var t = 0L
        repeat(20) { scene.render(t); t += 50_000_000; delay(50) }
        val img = scene.render(t)
        scene.close()
        File(out, "kmp-$name.png").writeBytes(img.encodeToData(EncodedImageFormat.PNG)!!.bytes)
        println("✓ kmp-$name.png")
    }
    templates("templates", dark = false)
    templates("templates-dark", dark = true)

    val store = AppStore(ApiClient(base), scope)
    store.login("user@nova.dev", "nova1234").join()
    val item = store.api.createItem("모바일에서 본 항목", "KMP 스냅샷")
    delay(1500) // 이벤트 소비(활동 기록) 기다림

    shot("login", null, Screen.Login)
    shot("items", store, Screen.Items)
    shot("item-detail", store, Screen.ItemDetail(item.id))
    shot("help", store, Screen.Help)
    shot("items-dark", store, Screen.Items, dark = true)
    scope.cancel()
    println("KMP SNAPSHOTS OK → ${out.absolutePath}")
}
