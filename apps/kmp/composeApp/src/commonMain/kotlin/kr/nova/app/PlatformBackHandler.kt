package kr.nova.app

import androidx.compose.runtime.Composable

/**
 * 시스템 뒤로 가기(T04-7.04) — enabled 일 때만 onBack 으로 받고, 아니면 시스템 기본 동작에 맡긴다.
 * Android 는 androidx.activity.compose.BackHandler, 데스크톱 · iOS 는 시스템 뒤로 가기가 없어 빈 구현.
 */
@Composable
expect fun PlatformBackHandler(enabled: Boolean, onBack: () -> Unit)
