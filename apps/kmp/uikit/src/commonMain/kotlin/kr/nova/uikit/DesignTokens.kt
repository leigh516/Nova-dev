// 생성 파일 — scripts/gen_tokens.py (원천: design/tokens/brand.tokens.json). 직접 고치지 않는다.
package kr.nova.uikit

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** 의미 색 토큰(라이트 · 다크) — 웹 tokens.css 의 --color-* 와 같은 이름 · 값. */
@Immutable
data class ColorTokens(
    val bgCanvas: Color,
    val bgSurface: Color,
    val bgSubtle: Color,
    val bgInverse: Color,
    val bgInverse2: Color,
    val bgNav: Color,
    val bgNavActive: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val textMuted: Color,
    val textInverse: Color,
    val textInverseMuted: Color,
    val textBrand: Color,
    val textOnNav: Color,
    val textOnNavMuted: Color,
    val textOnNavActive: Color,
    val borderSubtle: Color,
    val borderControl: Color,
    val borderFocus: Color,
    val borderFocusOnNav: Color,
    val actionPrimary: Color,
    val actionOnPrimary: Color,
    val actionAccent: Color,
    val actionOnAccent: Color,
    val actionDanger: Color,
    val actionOnDanger: Color,
    val statusInfoFg: Color,
    val statusInfoBg: Color,
    val statusSuccessFg: Color,
    val statusSuccessBg: Color,
    val statusWarningFg: Color,
    val statusWarningBg: Color,
    val statusDangerFg: Color,
    val statusDangerBg: Color,
    val statusLinkFg: Color,
    val statusLinkBg: Color,
    val statusNeutralFg: Color,
    val statusNeutralBg: Color,
    val statusSuccessSolid: Color,
    val statusWarningSolid: Color,
    val statusDangerSolid: Color,
    val statusInfoSolid: Color,
    val statusNeutralSolid: Color,
    val statusOnSolid: Color,
    val statusOnWarningSolid: Color,
    val aiFg: Color,
    val aiBg: Color,
    val aiBorder: Color,
    val domain1Mark: Color,
    val domain1Text: Color,
    val domain2Mark: Color,
    val domain2Text: Color,
    val domain3Mark: Color,
    val domain3Text: Color,
    val domain4Mark: Color,
    val domain4Text: Color,
    val domain5Mark: Color,
    val domain5Text: Color,
    val domain6Mark: Color,
    val domain6Text: Color,
    val chart1: Color,
    val chart2: Color,
    val chart3: Color,
    val chart4: Color,
    val chart5: Color,
    val chart6: Color,
    val overlayScrim: Color,
)

val LightColors = ColorTokens(
    bgCanvas = Color(0xFFF7F8FA),
    bgSurface = Color(0xFFFFFFFF),
    bgSubtle = Color(0xFFEEF0F4),
    bgInverse = Color(0xFF141821),
    bgInverse2 = Color(0xFF262C38),
    bgNav = Color(0xFF1E2366),
    bgNavActive = Color(0xFFA3ABF7),
    textPrimary = Color(0xFF141821),
    textSecondary = Color(0xFF3D4553),
    textMuted = Color(0xFF586172),
    textInverse = Color(0xFFF7F8FA),
    textInverseMuted = Color(0xFF9AA2B1),
    textBrand = Color(0xFF4F5BD5),
    textOnNav = Color(0xFFF7F8FA),
    textOnNavMuted = Color(0xFF9AA2B1),
    textOnNavActive = Color(0xFF141821),
    borderSubtle = Color(0xFFE1E4EA),
    borderControl = Color(0xFF737C8C),
    borderFocus = Color(0xFF4F5BD5),
    borderFocusOnNav = Color(0xFFA3ABF7),
    actionPrimary = Color(0xFF4F5BD5),
    actionOnPrimary = Color(0xFFFFFFFF),
    actionAccent = Color(0xFFF5B83D),
    actionOnAccent = Color(0xFF141821),
    actionDanger = Color(0xFFB42F2F),
    actionOnDanger = Color(0xFFFFFFFF),
    statusInfoFg = Color(0xFF4F5BD5),
    statusInfoBg = Color(0xFFECEEFE),
    statusSuccessFg = Color(0xFF0E7A57),
    statusSuccessBg = Color(0xFFE3F3EC),
    statusWarningFg = Color(0xFF7A4F00),
    statusWarningBg = Color(0xFFFDF1D6),
    statusDangerFg = Color(0xFFB42F2F),
    statusDangerBg = Color(0xFFFBE5E5),
    statusLinkFg = Color(0xFF2459C4),
    statusLinkBg = Color(0xFFE5EEFC),
    statusNeutralFg = Color(0xFF3D4553),
    statusNeutralBg = Color(0xFFE1E4EA),
    statusSuccessSolid = Color(0xFF0E7A57),
    statusWarningSolid = Color(0xFFF5B83D),
    statusDangerSolid = Color(0xFFB42F2F),
    statusInfoSolid = Color(0xFF4F5BD5),
    statusNeutralSolid = Color(0xFF586172),
    statusOnSolid = Color(0xFFFFFFFF),
    statusOnWarningSolid = Color(0xFF141821),
    aiFg = Color(0xFF6D28D9),
    aiBg = Color(0xFFEDE9FE),
    aiBorder = Color(0xFF6D28D9),
    domain1Mark = Color(0xFF2A64D0),
    domain1Text = Color(0xFF2A64D0),
    domain2Mark = Color(0xFF4D7C0F),
    domain2Text = Color(0xFF4D7C0F),
    domain3Mark = Color(0xFFC2307A),
    domain3Text = Color(0xFFC2307A),
    domain4Mark = Color(0xFF0E7490),
    domain4Text = Color(0xFF0E7490),
    domain5Mark = Color(0xFF7C4DDB),
    domain5Text = Color(0xFF7C4DDB),
    domain6Mark = Color(0xFFA21CAF),
    domain6Text = Color(0xFFA21CAF),
    chart1 = Color(0xFF2A64D0),
    chart2 = Color(0xFF0D7D72),
    chart3 = Color(0xFFA35A09),
    chart4 = Color(0xFFC2410C),
    chart5 = Color(0xFF7C4DDB),
    chart6 = Color(0xFFC2307A),
    overlayScrim = Color(0x730D1016),
)

val DarkColors = ColorTokens(
    bgCanvas = Color(0xFF0D1016),
    bgSurface = Color(0xFF1A1F29),
    bgSubtle = Color(0xFF141821),
    bgInverse = Color(0xFF141821),
    bgInverse2 = Color(0xFF262C38),
    bgNav = Color(0xFF1E2366),
    bgNavActive = Color(0xFFA3ABF7),
    textPrimary = Color(0xFFF7F8FA),
    textSecondary = Color(0xFFE1E4EA),
    textMuted = Color(0xFF9AA2B1),
    textInverse = Color(0xFFF7F8FA),
    textInverseMuted = Color(0xFF9AA2B1),
    textBrand = Color(0xFFA3ABF7),
    textOnNav = Color(0xFFF7F8FA),
    textOnNavMuted = Color(0xFF9AA2B1),
    textOnNavActive = Color(0xFF141821),
    borderSubtle = Color(0xFF262C38),
    borderControl = Color(0xFF737C8C),
    borderFocus = Color(0xFFA3ABF7),
    borderFocusOnNav = Color(0xFFA3ABF7),
    actionPrimary = Color(0xFF4F5BD5),
    actionOnPrimary = Color(0xFFFFFFFF),
    actionAccent = Color(0xFFF5B83D),
    actionOnAccent = Color(0xFF141821),
    actionDanger = Color(0xFFB42F2F),
    actionOnDanger = Color(0xFFFFFFFF),
    statusInfoFg = Color(0xFFA3ABF7),
    statusInfoBg = Color(0xFF22274F),
    statusSuccessFg = Color(0xFF5CC79B),
    statusSuccessBg = Color(0xFF15322A),
    statusWarningFg = Color(0xFFF9CF73),
    statusWarningBg = Color(0xFF3A2F17),
    statusDangerFg = Color(0xFFF08A8A),
    statusDangerBg = Color(0xFF3A1F1F),
    statusLinkFg = Color(0xFF86AFFF),
    statusLinkBg = Color(0xFF1D2A44),
    statusNeutralFg = Color(0xFFE1E4EA),
    statusNeutralBg = Color(0xFF262C38),
    statusSuccessSolid = Color(0xFF5CC79B),
    statusWarningSolid = Color(0xFFF9CF73),
    statusDangerSolid = Color(0xFFF08A8A),
    statusInfoSolid = Color(0xFFA3ABF7),
    statusNeutralSolid = Color(0xFF9AA2B1),
    statusOnSolid = Color(0xFF141821),
    statusOnWarningSolid = Color(0xFF141821),
    aiFg = Color(0xFFC4B5FD),
    aiBg = Color(0xFF2A2145),
    aiBorder = Color(0xFFC4B5FD),
    domain1Mark = Color(0xFF93BBFF),
    domain1Text = Color(0xFF93BBFF),
    domain2Mark = Color(0xFFA3E05A),
    domain2Text = Color(0xFFA3E05A),
    domain3Mark = Color(0xFFF59AC6),
    domain3Text = Color(0xFFF59AC6),
    domain4Mark = Color(0xFF5FD4EE),
    domain4Text = Color(0xFF5FD4EE),
    domain5Mark = Color(0xFFB9A2FF),
    domain5Text = Color(0xFFB9A2FF),
    domain6Mark = Color(0xFFF0ABFC),
    domain6Text = Color(0xFFF0ABFC),
    chart1 = Color(0xFF86AFFF),
    chart2 = Color(0xFF4FD1C1),
    chart3 = Color(0xFFF6B35C),
    chart4 = Color(0xFFFF9A6B),
    chart5 = Color(0xFFB9A2FF),
    chart6 = Color(0xFFF59AC6),
    overlayScrim = Color(0x730D1016),
)

/** 간격 · 반경 · 크기 · 글꼴 크기 · 굵기 · 시간 토큰 — 4pt 격자. */
object Dimens {
    val space0 = 0.dp
    val space1 = 4.dp
    val space2 = 8.dp
    val space3 = 12.dp
    val space4 = 16.dp
    val space5 = 20.dp
    val space6 = 24.dp
    val space8 = 32.dp
    val space10 = 40.dp
    val space12 = 48.dp
    val radiusSm = 6.dp
    val radiusMd = 10.dp
    val radiusLg = 14.dp
    val radiusXl = 20.dp
    val radiusPill = 999.dp
    val sizeTargetWeb = 24.dp
    val sizeTargetTouch = 44.dp
    val sizeControlSm = 32.dp
    val sizeControlMd = 40.dp
    val sizeControlLg = 48.dp
    val sizeContentNarrow = 860.dp
    val sizeContentDefault = 1120.dp
    val sizeContentWide = 1360.dp
    val fontXs = 12.sp
    val fontSm = 13.sp
    val fontMd = 15.sp
    val fontLg = 17.sp
    val fontXl = 20.sp
    val font2xl = 24.sp
    val font3xl = 32.sp
    val weightRegular = FontWeight(400)
    val weightMedium = FontWeight(500)
    val weightSemibold = FontWeight(600)
    val weightBold = FontWeight(700)
    const val durationFastMs = 120
    const val durationBaseMs = 200
    const val durationSlowMs = 320
}
