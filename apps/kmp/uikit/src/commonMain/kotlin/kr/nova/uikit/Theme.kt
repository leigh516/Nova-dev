package kr.nova.uikit

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf

/** 현재 모드의 의미 색 토큰 — 컴포넌트는 Tokens.current 만 쓴다(직접 색 금지) */
val LocalTokens = staticCompositionLocalOf { LightColors }

object Tokens {
    val current: ColorTokens @Composable get() = LocalTokens.current
}

/**
 * 앱 테마 — 생성 토큰(LightColors · DarkColors)을 Material3 색 구성에도 연결한다(웹 tokens.css 와 같은 값).
 *
 * Material 은 primary · error 를 '버튼 배경'뿐 아니라 '배경 위 글자 · 테두리'(입력란 포커스 테두리 · 라벨 · 진행 표시 ·
 * 기본 TextButton · 오류 문구)로도 쓴다. 그래서 primary · error 에는 각 모드에서 글자 대비를 통과한 글자용 토큰
 * (text.brand · status.danger.fg)을 넣는다. 다크에서 action.primary(#4F5BD5)를 글자로 쓰면 표면 위 2.98:1 로 미달이다.
 * 버튼 배경(action.primary · action.danger)은 NovaButton 이 직접 지정한다.
 * surface · surfaceContainer* 를 비워 두면 Material 기본 보라 계열이 대화상자 · 하단 탭 · 메뉴에 섞이므로 모두 bg 토큰으로 채운다.
 */
@Composable
fun NovaTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val t = if (dark) DarkColors else LightColors
    val scheme = colorSchemeOf(t, dark)
    CompositionLocalProvider(LocalTokens provides t) {
        MaterialTheme(colorScheme = scheme, content = content)
    }
}

/** 토큰 → Material3 색 구성(라이트 · 다크 같은 규칙). 대비 수치는 다크 기준 bgSurface(#1A1F29) 위 값 */
internal fun colorSchemeOf(t: ColorTokens, dark: Boolean): ColorScheme {
    // 스낵바(inverseSurface) — 다크의 bg.inverse 는 캔버스와 거의 같아 구분이 안 되므로 한 단계 밝은 bg.inverse2
    val inverseSurface = if (dark) t.bgInverse2 else t.bgInverse
    // 스낵바 '실행 취소' 글자 — 어두운 반전 표면 위이므로 다크 모드의 글자용 브랜드색(두 모드 모두)
    val inversePrimary = DarkColors.textBrand
    // 기본 구성에서 출발해 모든 색 역할을 토큰으로 덮는다(빈 역할이 Material 기본 보라로 남지 않게)
    return (if (dark) darkColorScheme() else lightColorScheme()).copy(
        primary = t.textBrand, onPrimary = t.bgCanvas,                       // 다크 7.65:1 · onPrimary 8.82:1
        primaryContainer = t.statusInfoBg, onPrimaryContainer = t.statusInfoFg,
        secondary = t.textBrand, onSecondary = t.bgCanvas,
        secondaryContainer = t.statusInfoBg, onSecondaryContainer = t.statusInfoFg, // 하단 탭 선택 표시 6.61:1
        tertiary = t.textBrand, onTertiary = t.bgCanvas,
        tertiaryContainer = t.statusInfoBg, onTertiaryContainer = t.statusInfoFg,
        background = t.bgCanvas, onBackground = t.textPrimary,
        surface = t.bgSurface, onSurface = t.textPrimary,                    // 15.54:1
        surfaceVariant = t.bgSubtle, onSurfaceVariant = t.textMuted,         // 6.43:1 (입력 라벨 · 안 고른 탭)
        surfaceTint = t.bgSurface,                                           // 높이에 따른 보라 덧칠 없앰
        inverseSurface = inverseSurface, inverseOnSurface = t.textInverse,   // 13.18:1
        inversePrimary = inversePrimary,                                     // 다크 6.48:1 · 라이트 8.23:1
        error = t.statusDangerFg, onError = t.bgCanvas,                      // 다크 6.85:1 · onError 7.90:1
        errorContainer = t.statusDangerBg, onErrorContainer = t.statusDangerFg,
        outline = t.borderControl, outlineVariant = t.borderSubtle,          // 테두리(비글자) 다크 3.92:1
        scrim = t.bgInverse,
        surfaceBright = t.bgSurface, surfaceDim = t.bgCanvas,
        surfaceContainerLowest = t.bgCanvas, surfaceContainerLow = t.bgSurface, surfaceContainer = t.bgSurface,
        surfaceContainerHigh = t.bgSurface, surfaceContainerHighest = t.bgSubtle,
    )
}
