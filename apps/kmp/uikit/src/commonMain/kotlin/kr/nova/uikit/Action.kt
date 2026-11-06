package kr.nova.uikit

import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import kr.nova.shared.ApiException
import kr.nova.shared.toApiException

/** 결과 알림 — 앱이 스낵바 등으로 보여 준다(실행 취소 버튼 포함) */
data class Notice(val message: String, val error: Boolean = false, val undo: (suspend () -> Unit)? = null)

internal class ActionConfig<R>(
    val notify: (Notice) -> Unit,
    val success: String?,
    val undo: (suspend (R) -> Unit)?,
    val then: (suspend (R) -> Unit)?,
    val block: suspend () -> R,
)

/** 서버 호출 버튼 상태 — 웹 useAction 대응. running 동안 NovaButton(loading)은 포커스를 지킨 채 누름을 무시한다 */
class ActionState<R> internal constructor(private val scope: CoroutineScope, private val cfg: State<ActionConfig<R>>) {
    var running by mutableStateOf(false)
        private set
    var error by mutableStateOf<ApiException?>(null)
        private set

    fun run() {
        if (running) return // 중복 제출 방지(UX H5)
        val c = cfg.value
        running = true
        error = null
        scope.launch {
            try {
                val r = c.block()
                if (c.success != null) c.notify(Notice(c.success, undo = c.undo?.let { u -> { undo(c, u, r) } }))
                c.then?.invoke(r)
            } catch (e: CancellationException) {
                throw e // 화면을 떠나 취소된 것은 오류가 아니다 — 알림 없이 끝낸다
            } catch (e: Exception) {
                // 서버 오류는 서버 문구, 연결 실패 · 응답 해석 실패는 각각 다른 문구(toApiException)
                val err = e.toApiException()
                error = err
                c.notify(Notice(err.message ?: "요청을 처리하지 못했습니다", error = true))
            } finally {
                running = false
            }
        }
    }

    /** 실행 취소 — 실패하면 조용히 넘기지 않고 오류 알림으로 알린다(되돌려졌다고 오해하지 않게 · UX H9) */
    private suspend fun undo(c: ActionConfig<R>, u: suspend (R) -> Unit, r: R) {
        try {
            u(r)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            val err = e.toApiException()
            error = err
            c.notify(Notice("실행 취소하지 못했습니다 — ${err.message ?: "요청을 처리하지 못했습니다"}", error = true))
            return
        }
        try {
            c.then?.invoke(r)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            c.notify(Notice("되돌렸지만 화면을 새로 고치지 못했습니다 — ${e.toApiException().message}", error = true))
        }
    }
}

/**
 * 서버 호출 버튼의 유일한 방식(ui.md 규칙 4) — 진행 중 누름 무시(중복 방지 · 포커스 유지) · 성공/오류 알림 · 실행 취소 · 후속.
 *   val archive = rememberAction(notify, success = "보관했습니다", undo = { api.restoreItem(id) }, then = { store.loadItems() }) { api.archiveItem(id) }
 *   NovaButton("보관", archive::run, loading = archive.running)
 * 되돌릴 수 없는 액션은 ConfirmDialog 로 먼저 묻고 run() 한다.
 */
@Composable
fun <R> rememberAction(
    notify: (Notice) -> Unit,
    success: String? = null,
    undo: (suspend (R) -> Unit)? = null,
    then: (suspend (R) -> Unit)? = null,
    block: suspend () -> R,
): ActionState<R> {
    val scope = rememberCoroutineScope()
    val cfg = rememberUpdatedState(ActionConfig(notify, success, undo, then, block)) // 리컴포지션마다 최신 람다
    return remember { ActionState(scope, cfg) }
}
