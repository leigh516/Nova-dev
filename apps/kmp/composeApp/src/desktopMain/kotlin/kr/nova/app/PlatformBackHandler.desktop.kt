package kr.nova.app

import androidx.compose.runtime.Composable

/** 데스크톱은 시스템 뒤로 가기가 없다 — 화면의 '← 항목' 버튼으로 돌아간다 */
@Composable
actual fun PlatformBackHandler(enabled: Boolean, onBack: () -> Unit) = Unit
