package kr.nova.shared

import io.ktor.client.HttpClient
import io.ktor.client.engine.cio.CIO
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking

/** 실행 중인 게이트웨이 스모크 — gradle -Pnova.skipCompose=true :shared:smoke -Papi=http://127.0.0.1:8080/v1 */
fun main(args: Array<String>) = runBlocking {
    val api = ApiClient(args.getOrNull(0) ?: "http://127.0.0.1:8080/v1", HttpClient(CIO))
    val user = api.login("user@nova.dev", "nova1234")
    println("✓ 로그인 ${user.name}(${user.role})")
    val menu = api.menu("app")
    println("✓ 메뉴 ${menu.items.map { it.label }}")
    val item = api.createItem("KMP 스모크")
    println("✓ 생성 ${item.id}")
    var kinds = emptyList<String>()
    repeat(30) {
        kinds = api.item(item.id).activity.map { it.kind }
        if (kinds.isNotEmpty()) return@repeat
        delay(200)
    }
    check(kinds == listOf("created")) { "활동 기록 $kinds" }
    println("✓ 이벤트 소비 활동 기록 $kinds")
    check(api.archiveItem(item.id).status == "archived")
    println("✓ 보관")
    val denied = runCatching { api.deleteItem(item.id) }.exceptionOrNull() as? ApiException
    check(denied?.status == 403) { "user 삭제가 403 이 아님: $denied" }
    println("✓ 권한 오류: ${denied?.message}")
    println("KMP SMOKE OK")
}
