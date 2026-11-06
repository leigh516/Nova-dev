package kr.nova.shared

import io.ktor.client.call.NoTransformationFoundException
import io.ktor.serialization.ContentConvertException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.SerializationException

/** 연결 실패(인터넷 끊김 · 서버 꺼짐 · 시간 초과)일 때의 사람 말 */
const val NETWORK_MESSAGE = "서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요"

/** 서버 응답을 앱이 해석하지 못했을 때(앱 · 서버 버전 불일치 등)의 사람 말 */
const val CLIENT_MESSAGE = "서버 응답을 처리하지 못했습니다. 앱을 최신 버전으로 업데이트한 뒤 다시 시도하세요"

/**
 * 어떤 예외든 화면에 보일 ApiException 으로 바꾼다 — 화면은 이것 하나만 다룬다(UX H9).
 *  - ApiException: 서버가 준 오류 그대로
 *  - 직렬화 · 변환 실패: code="client" (앱 쪽 문제 — 연결 문제로 오해하지 않게 다른 문구)
 *  - 그 밖(Ktor IO · 시간 초과 · 주소 해석 실패 등): code="network"
 *  - CancellationException: 바꾸지 않고 다시 던진다(코루틴 취소가 오류 알림이 되면 안 된다)
 */
fun Throwable.toApiException(): ApiException = when (this) {
    is CancellationException -> throw this
    is ApiException -> this
    is SerializationException, is ContentConvertException, is NoTransformationFoundException -> ApiException(0, "client", CLIENT_MESSAGE)
    else -> ApiException(0, "network", NETWORK_MESSAGE)
}

/** 화면 상태 3종(로딩 · 데이터 · 오류)을 하나로 — 웹 useApi 와 같은 모양. 실패해도 이전 데이터는 남긴다. */
data class Loadable<T>(val data: T? = null, val loading: Boolean = false, val error: ApiException? = null)

fun <T> CoroutineScope.load(flow: MutableStateFlow<Loadable<T>>, block: suspend () -> T): Job = launch {
    flow.value = flow.value.copy(loading = true, error = null)
    flow.value = try {
        Loadable(block(), loading = false)
    } catch (e: CancellationException) {
        flow.value = flow.value.copy(loading = false) // 취소되면 '불러오는 중'에 멈추지 않게 표시만 풀고 다시 던진다
        throw e
    } catch (e: Exception) {
        flow.value.copy(loading = false, error = e.toApiException()) // 취소는 toApiException 이 다시 던진다
    }
}

/**
 * 앱 상태 저장소 — 세션 · 메뉴(공통) + 샘플 항목. 화면은 StateFlow 를 구독만 한다.
 * 새 업무는 같은 모양(MutableStateFlow<Loadable<…>> + load)으로 추가한다.
 */
class AppStore(val api: ApiClient, private val scope: CoroutineScope) {
    private val _user = MutableStateFlow<User?>(null)
    val user: StateFlow<User?> = _user.asStateFlow()
    val menu = MutableStateFlow(Loadable<Menu>())
    val items = MutableStateFlow(Loadable<Page<Item>>())
    val detail = MutableStateFlow(Loadable<Item>())

    /** 로그인 — 서버 오류뿐 아니라 연결 실패도 onError 로 넘긴다(버튼이 '확인 중'에 멈추거나 앱이 죽지 않게) */
    fun login(email: String, password: String, onError: (ApiException) -> Unit = {}): Job = scope.launch {
        try {
            _user.value = api.login(email, password)
        } catch (e: Exception) {
            onError(e.toApiException()) // 취소는 다시 던진다
            return@launch
        }
        refreshMenu()
    }

    fun logout() {
        api.token = null
        _user.value = null
        refreshMenu()
    }

    fun refreshMenu(): Job = scope.load(menu) { api.menu("app") }
    fun loadItems(q: String? = null, page: Int = 1): Job = scope.load(items) { api.items(q = q, page = page) }
    fun loadItem(id: String): Job = scope.load(detail) { api.item(id) }
}
