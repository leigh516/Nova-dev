package kr.nova.shared

import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ApiClientTest {
    private val json = headersOf(HttpHeaders.ContentType, "application/json")

    private fun client(handler: (path: String, auth: String?) -> Pair<HttpStatusCode, String>): ApiClient =
        ApiClient("http://gw/v1", HttpClient(MockEngine { req ->
            val (status, body) = handler(req.url.encodedPath, req.headers[HttpHeaders.Authorization])
            respond(body, status, json)
        }))

    @Test
    fun loginStoresTokenAndSendsBearer() = runTest {
        var seen: String? = null
        val api = client { path, auth ->
            if (path.endsWith("/auth/login")) HttpStatusCode.OK to """{"token":"T1","user":{"id":"u","name":"홍","role":"user"}}"""
            else { seen = auth; HttpStatusCode.OK to """{"items":[],"total":0,"page":1,"size":20}""" }
        }
        assertEquals("user", api.login("a@b", "pw").role)
        assertEquals(0, api.items().total)
        assertEquals("Bearer T1", seen)
    }

    @Test
    fun errorEnvelopeBecomesHumanMessage() = runTest {
        val api = client { _, _ -> HttpStatusCode.Forbidden to """{"error":{"code":"forbidden_perm","message":"이 기능을 쓸 권한이 없습니다 (sample.delete)","perm":"sample.delete"}}""" }
        val e = assertFailsWith<ApiException> { api.deleteItem("x") }
        assertEquals(403, e.status)
        assertEquals("forbidden_perm", e.code)
        assertEquals("sample.delete", e.perm)
    }

    @Test
    fun rbacUnavailableIsSameRegardlessOfStatus() = runTest {
        // 게이트웨이가 403 → 503 으로 바꾸는 사이(T03-6.08 → 6.09)에도 앱은 오류 코드로 판단해 같은 결과를 낸다
        val results = listOf(HttpStatusCode.Forbidden, HttpStatusCode.ServiceUnavailable).map { st ->
            val api = client { _, _ -> st to """{"error":{"code":"rbac_unavailable","message":"서버 문구 $st","perm":"sample.read"}}""" }
            assertFailsWith<ApiException> { api.items() }
        }
        results.forEach { e ->
            assertEquals("rbac_unavailable", e.code)
            assertEquals(RBAC_UNAVAILABLE_MESSAGE, e.message)
            assertTrue(e.retryable)
            assertEquals("sample.read", e.perm)
        }
        assertEquals(results[0].message, results[1].message)
    }

    @Test
    fun missingMessageFallsBackToDefault() = runTest {
        val api = client { _, _ -> HttpStatusCode.NotFound to "not json" }
        val e = assertFailsWith<ApiException> { api.item("x") }
        assertEquals("찾는 항목이 없습니다. 이미 삭제되었을 수 있습니다", e.message)
    }

    @Test
    fun pageAndItemDecode() = runTest {
        val api = client { _, _ ->
            HttpStatusCode.OK to """{"items":[{"id":"01a1","name":"가","status":"active","created_at":"2026-11-03T00:00:00Z","updated_at":"2026-11-03T00:00:00Z","extra":1}],"total":1,"page":1,"size":20}"""
        }
        val p = api.items(q = "가")
        assertEquals("가", p.items.single().name)
        assertNull(p.items.single().memo)
    }
}
