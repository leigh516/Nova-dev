package kr.nova.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kr.nova.shared.ApiClient
import kr.nova.shared.AppStore
import kr.nova.shared.BackStack
import kr.nova.shared.toApiException
import kr.nova.uikit.Dimens
import kr.nova.uikit.Notice
import kr.nova.uikit.NovaTheme
import kr.nova.uikit.Tokens

/** 화면 — 내비게이션 라이브러리 없이 sealed class 하나로(작은 앱의 기본값). 스택은 shared BackStack */
sealed class Screen {
    data object Login : Screen()
    data object Items : Screen()
    data class ItemDetail(val id: String) : Screen()
    data object Help : Screen()
}

/** 서버 메뉴 키 → 화면(탭은 게이트웨이 /v1/menu?channel=app 이 권한으로 거른 것) */
val TAB_SCREENS: Map<String, Screen> = mapOf("items" to Screen.Items)

/** 서버 메뉴 아이콘 키 → 그림(탭마다 다르게 — UX H6 알아보기 쉽게) */
val ICONS = mapOf("home" to "🏠", "list" to "📋", "palette" to "🎨", "activity" to "📈", "help" to "❓")

@Composable
fun App(apiBase: String, start: Screen? = null, injected: AppStore? = null, dark: Boolean? = null) {
    val scope = rememberCoroutineScope()
    val store = remember { injected ?: AppStore(ApiClient(apiBase), scope) }
    val user by store.user.collectAsState()
    var stack by remember { mutableStateOf(BackStack(start ?: Screen.Login)) }
    val snackbar = remember { SnackbarHostState() }
    val notify: (Notice) -> Unit = { n ->
        scope.launch {
            val r = snackbar.showSnackbar(n.message, actionLabel = if (n.undo != null) "실행 취소" else null,
                duration = if (n.undo != null) SnackbarDuration.Long else SnackbarDuration.Short)
            val undo = n.undo
            if (r == SnackbarResult.ActionPerformed && undo != null) {
                // 실행 취소 실패가 처리되지 않으면 앱이 죽는다 — 오류 알림으로 바꾼다(rememberAction 의 undo 는 스스로 알리지만 안전망)
                try {
                    undo()
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    snackbar.showSnackbar("실행 취소하지 못했습니다 — ${e.toApiException().message}")
                }
            }
        }
    }
    fun go(s: Screen) { stack = stack.push(s) }
    fun back() { stack = stack.pop() }
    LaunchedEffect(Unit) { store.refreshMenu() }
    LaunchedEffect(user) { if (user != null && stack.current == Screen.Login) stack = stack.reset(Screen.Items) }

    NovaTheme(dark = dark ?: androidx.compose.foundation.isSystemInDarkTheme()) {
        val menu by store.menu.collectAsState()
        val current = stack.current
        // 시스템 뒤로 가기 — 쌓인 화면이 있을 때만 앱이 받는다. 첫 화면이면 시스템 기본(Android: 앱 닫힘)
        PlatformBackHandler(enabled = stack.canPop, onBack = ::back)
        Scaffold(
            snackbarHost = { SnackbarHost(snackbar) },
            bottomBar = {
                val tabs = menu.data?.items.orEmpty().filter { it.key in TAB_SCREENS }
                if (user != null && tabs.isNotEmpty() && current !is Screen.Login) {
                    NavigationBar {
                        tabs.forEach { m ->
                            NavigationBarItem(selected = TAB_SCREENS[m.key] == current, onClick = { stack = stack.reset(TAB_SCREENS.getValue(m.key)) },
                                icon = { Text(ICONS[m.icon] ?: "•") }, label = { Text(m.label) })
                        }
                        NavigationBarItem(selected = current == Screen.Help, onClick = { stack = stack.reset(Screen.Help) }, icon = { Text(ICONS.getValue("help")) }, label = { Text("도움말") })
                    }
                }
            },
        ) { pad ->
            Column(Modifier.fillMaxSize().background(Tokens.current.bgCanvas).padding(pad).padding(Dimens.space4)) {
                when (current) {
                    Screen.Login -> SignInScreen(store)
                    Screen.Items -> ItemsScreen(store, notify, onOpen = { go(Screen.ItemDetail(it)) }, onLogout = { store.logout(); stack = stack.reset(Screen.Login) })
                    is Screen.ItemDetail -> ItemDetailScreen(store, current.id, notify, onBack = ::back)
                    Screen.Help -> HelpScreen()
                }
            }
        }
    }
}
