package kr.nova.app

import androidx.compose.ui.window.ComposeUIViewController

/** iOS: Xcode SwiftUI 앱에서 UIViewControllerRepresentable 로 감싸 호스팅 (게이트웨이 주소는 앱 설정으로) */
fun MainViewController(apiBase: String = "http://127.0.0.1:8080/v1") = ComposeUIViewController { App(apiBase) }
