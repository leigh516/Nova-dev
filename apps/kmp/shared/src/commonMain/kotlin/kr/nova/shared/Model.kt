package kr.nova.shared

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/* ------------------------------------------------------------------ 공통 */
@Serializable data class User(val id: String, val name: String, val role: String, val tenant: String? = null, val email: String? = null)
@Serializable data class LoginRequest(val email: String, val password: String)
@Serializable data class LoginResult(val token: String, val user: User)
@Serializable data class MenuItem(val key: String, val label: String, val icon: String? = null, val path: String)
@Serializable data class Maintenance(val key: String, val label: String, val message: String)
@Serializable data class Menu(val channel: String, val items: List<MenuItem>, val maintenance: List<Maintenance> = emptyList(), val features: Map<String, Boolean> = emptyMap())
/** 목록 API 계약(docs/conventions/ui.md §4) */
@Serializable data class Page<T>(val items: List<T>, val total: Int, val page: Int, val size: Int)
@Serializable data class ApiErrorBody(val error: JsonObject)

/* ------------------------------------------------------------------ 샘플 업무(sample 서비스) — 새 업무 DTO 는 이렇게 파일을 나눠 추가 */
/** 활동 한 건 — 서버 키 recorded_at(T04-2.05, 웹 Item 타입과 같은 이름) */
@Serializable data class Activity(val kind: String, @SerialName("recorded_at") val recordedAt: String)
@Serializable data class Item(
    val id: String,
    val name: String,
    val memo: String? = null,
    val status: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    val activity: List<Activity> = emptyList(),
    /** 활동이 상한(최근 50건)을 넘어 잘렸는가 — 없으면 false(T04-6.04) */
    @SerialName("activity_truncated") val activityTruncated: Boolean = false,
)
@Serializable data class ItemIn(val name: String, val memo: String? = null)
