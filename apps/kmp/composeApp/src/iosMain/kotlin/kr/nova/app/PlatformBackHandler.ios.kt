package kr.nova.app

import androidx.compose.runtime.Composable

/** iOS 는 시스템 뒤로 가기 버튼이 없다(밀어서 뒤로 가기는 내비게이션 라이브러리 몫) — 화면 버튼으로 돌아간다 */
@Composable
actual fun PlatformBackHandler(enabled: Boolean, onBack: () -> Unit) = Unit
