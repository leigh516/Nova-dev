package kr.nova.app

import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import androidx.compose.ui.window.rememberWindowState

/** 데스크톱 실행: gradle :composeApp:run  (NOVA_API 로 게이트웨이 주소 변경) */
fun main() = application {
    Window(onCloseRequest = ::exitApplication, title = "Nova 샘플 앱", state = rememberWindowState(size = DpSize(420.dp, 860.dp))) {
        App(apiBase = System.getenv("NOVA_API") ?: "http://127.0.0.1:8080/v1")
    }
}
