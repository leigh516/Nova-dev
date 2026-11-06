package kr.nova.shared

import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame

class StoreTest {
    private val json = headersOf(HttpHeaders.ContentType, "application/json")

    /** 연결 실패 흉내 — 엔진이 응답 대신 예외를 던진다(Ktor IO 예외와 같은 자리) */
    private fun failing(e: Throwable) = ApiClient("http://gw/v1", HttpClient(MockEngine { throw e }))

    @Test
    fun loginNetworkFailureReachesOnError() = runTest {
        val store = AppStore(failing(RuntimeException("Connection refused")), this)
        var got: ApiException? = null
        store.login("a@b", "pw") { got = it }.join()
        assertEquals("network", got?.code)
        assertEquals(NETWORK_MESSAGE, got?.message)
        assertNull(store.user.value)
    }

    @Test
    fun loginServerErrorKeepsServerMessage() = runTest {
        val api = ApiClient("http://gw/v1", HttpClient(MockEngine {
            respond("""{"error":{"code":"bad_credentials","message":"이메일 또는 비밀번호가 맞지 않습니다"}}""", HttpStatusCode.Unauthorized, json)
        }))
        var got: ApiException? = null
        AppStore(api, this).login("a@b", "pw") { got = it }.join()
        assertEquals("bad_credentials", got?.code)
        assertEquals("이메일 또는 비밀번호가 맞지 않습니다", got?.message)
    }

    @Test
    fun loginBadBodyIsClientErrorNotNetwork() = runTest {
        val api = ApiClient("http://gw/v1", HttpClient(MockEngine { respond("""{"unexpected":true}""", HttpStatusCode.OK, json) }))
        var got: ApiException? = null
        AppStore(api, this).login("a@b", "pw") { got = it }.join()
        assertEquals("client", got?.code)
        assertEquals(CLIENT_MESSAGE, got?.message)
    }

    @Test
    fun loadNetworkFailureBecomesErrorState() = runTest {
        val store = AppStore(failing(RuntimeException("timeout")), this)
        store.loadItems().join()
        assertEquals("network", store.items.value.error?.code)
        assertEquals(false, store.items.value.loading)
    }

    @Test
    fun toApiExceptionMapping() {
        val api = ApiException(403, "forbidden", "권한 없음")
        assertSame(api, api.toApiException())
        assertEquals("client", kotlinx.serialization.SerializationException("x").toApiException().code)
        assertEquals("network", IllegalStateException("x").toApiException().code)
        assertFailsWith<CancellationException> { CancellationException("취소").toApiException() }
    }
}
