package kr.nova.shared

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.request.HttpRequestBuilder
import io.ktor.client.request.bearerAuth
import io.ktor.client.request.delete
import io.ktor.client.request.get
import io.ktor.client.request.parameter
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.http.isSuccess
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonPrimitive

/** 게이트웨이 오류 — message 는 서버가 준 사람 말(UX H9). 화면은 이것을 그대로 보여 준다. */
class ApiException(val status: Int, val code: String, message: String, val perm: String? = null) : Exception(message) {
    /** 잠시 뒤 다시 시도하면 풀릴 수 있는 오류인가 — 상태 코드가 아니라 오류 코드로 판단한다 */
    val retryable: Boolean get() = code == RBAC_UNAVAILABLE
}

/** 권한 원천(rbac) 일시 장애 오류 코드 — 게이트웨이가 403 → 503 으로 바꾸는 중이라(ADR-012 P10) 상태 코드로 가르지 않는다 */
const val RBAC_UNAVAILABLE = "rbac_unavailable"

/** 권한 원천 일시 장애의 사람 말 — '권한 없음'으로 읽히지 않게, 상태 코드와 무관하게 이 문구로 고정한다 */
const val RBAC_UNAVAILABLE_MESSAGE = "권한 정보를 잠시 확인할 수 없습니다. 잠시 후 다시 시도하세요"

val NovaJson = Json { ignoreUnknownKeys = true; explicitNulls = false; encodeDefaults = true }

/**
 * 게이트웨이(/v1) 전용 클라이언트 — 앱은 서비스를 직접 부르지 않는다.
 * 공통(로그인 · 메뉴)은 여기, 업무 API 는 확장 함수(SampleApi.kt 처럼)로 나눠 붙인다.
 */
class ApiClient(private val baseUrl: String, engine: HttpClient? = null) {
    var token: String? = null
    val http: HttpClient = (engine ?: HttpClient()).config {
        install(ContentNegotiation) { json(NovaJson) }
        expectSuccess = false
        defaultRequest { url(baseUrl.trimEnd('/') + "/") }
    }

    fun HttpRequestBuilder.auth() { token?.let { bearerAuth(it) } }

    suspend inline fun <reified T> HttpResponse.ok(): T {
        if (status.isSuccess()) return body()
        throw toError()
    }

    suspend fun HttpResponse.toError(): ApiException {
        val text = bodyAsText()
        val err = runCatching { NovaJson.decodeFromString(ApiErrorBody.serializer(), text).error }.getOrNull()
        val code = err?.get("code")?.jsonPrimitive?.content ?: "error"
        return ApiException(
            status.value,
            code,
            // 오류 코드가 정한 문구가 먼저 — 같은 코드면 403 이든 503 이든 화면이 같다(T03-6.08 Expand)
            if (code == RBAC_UNAVAILABLE) RBAC_UNAVAILABLE_MESSAGE
            else err?.get("message")?.jsonPrimitive?.content ?: defaultMessage(status.value),
            err?.get("perm")?.jsonPrimitive?.content,
        )
    }

    suspend inline fun <reified T> get(path: String, query: Map<String, Any?> = emptyMap()): T =
        http.get(path.trimStart('/')) { auth(); query.forEach { (k, v) -> if (v != null && v != "") parameter(k, v) } }.ok()

    suspend inline fun <reified T, reified B> post(path: String, body: B): T =
        http.post(path.trimStart('/')) { auth(); contentType(ContentType.Application.Json); setBody(body) }.ok()

    suspend inline fun <reified T> post(path: String): T = http.post(path.trimStart('/')) { auth() }.ok()

    suspend fun delete(path: String) {
        val r = http.delete(path.trimStart('/')) { auth() }
        if (!r.status.isSuccess()) throw r.toError()
    }

    suspend fun login(email: String, password: String): User {
        val r: LoginResult = post("auth/login", LoginRequest(email, password))
        token = r.token
        return r.user
    }

    suspend fun menu(channel: String = "app"): Menu = get("menu", mapOf("channel" to channel))
}

/** 서버가 문구를 주지 않았을 때의 사람 말 — 웹 @nova/sdk defaultMessage 와 같다 */
fun defaultMessage(status: Int): String = when {
    status == 401 -> "로그인이 필요합니다"
    status == 403 -> "이 기능을 쓸 권한이 없습니다"
    status == 404 -> "찾는 항목이 없습니다. 이미 삭제되었을 수 있습니다"
    status == 409 -> "다른 변경과 충돌했습니다. 새로고침 후 다시 시도하세요"
    status == 429 -> "요청이 너무 많습니다. 잠시 후 다시 시도하세요"
    status >= 500 -> "서버에 문제가 생겼습니다. 잠시 후 다시 시도하세요"
    else -> "요청을 처리하지 못했습니다"
}
