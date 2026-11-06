package kr.nova.uikit

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.error
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/*
 * 공통 컴포넌트 — 웹 @nova/ui 와 같은 이름 · 같은 규칙(ui.md 규칙 9).
 * 웹 DataTable ↔ 모바일 DataList, PageHeader ↔ ScreenHeader, Button ↔ NovaButton.
 * 색 · 간격은 Tokens · Dimens(생성물)만.
 */

enum class Variant { Primary, Secondary, Ghost, Danger }
enum class Tone { Neutral, Info, Success, Warning, Danger, Link }

/**
 * 버튼 — 진행 중(loading)에도 **비활성으로 만들지 않는다**(T04-9.08, 웹 Button T04-9.05 와 같은 규칙).
 * 비활성 버튼은 포커스를 잃어 키보드 · 화면 읽기 사용자가 제자리를 놓친다. 대신 누름을 무시해 중복 호출을 막고,
 * 상태 설명 "진행 중"으로 화면 읽기 프로그램에 알린다(웹 aria-busy 대응). enabled = false 는 정말 누를 수 없을 때만.
 */
@Composable
fun NovaButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, variant: Variant = Variant.Primary, loading: Boolean = false, enabled: Boolean = true) {
    val t = Tokens.current
    val m = modifier.defaultMinSize(minHeight = Dimens.sizeTargetTouch)
        .then(if (loading) Modifier.semantics { stateDescription = "진행 중" } else Modifier)
    // 진행 중 누름은 무시 — rememberAction 밖(로그인 등)에서 부르는 onClick 도 두 번 가지 않게
    val press: () -> Unit = { if (!loading) onClick() }
    val content: @Composable () -> Unit = {
        if (loading) { CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp); Spacer(Modifier.size(Dimens.space2)) }
        Text(text, fontWeight = FontWeight.SemiBold)
    }
    when (variant) {
        Variant.Primary, Variant.Danger -> Button(
            onClick = press, enabled = enabled, modifier = m, shape = RoundedCornerShape(Dimens.radiusMd),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (variant == Variant.Danger) t.actionDanger else t.actionPrimary,
                contentColor = if (variant == Variant.Danger) t.actionOnDanger else t.actionOnPrimary,
            ),
        ) { content() }
        // 보조 · 고스트 글자는 대비 검사를 통과한 text.brand(라이트 · 다크 4.5:1 이상) — Material 기본 primary 를 쓰지 않는다
        Variant.Secondary -> OutlinedButton(
            onClick = press, enabled = enabled, modifier = m, shape = RoundedCornerShape(Dimens.radiusMd),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = t.textBrand),
            border = androidx.compose.foundation.BorderStroke(1.dp, t.borderControl),
        ) { content() }
        Variant.Ghost -> TextButton(onClick = press, enabled = enabled, modifier = m,
            colors = ButtonDefaults.textButtonColors(contentColor = t.textBrand)) { content() }
    }
}

@Composable
fun Card(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable () -> Unit) {
    val t = Tokens.current
    val base = modifier.fillMaxWidth()
        .background(t.bgSurface, RoundedCornerShape(Dimens.radiusLg))
        .border(1.dp, t.borderSubtle, RoundedCornerShape(Dimens.radiusLg))
    Box((if (onClick != null) base.clickable(onClick = onClick) else base).padding(Dimens.space4)) { content() }
}

@Composable
fun Title(text: String, modifier: Modifier = Modifier) =
    Text(text, modifier, color = Tokens.current.textPrimary, fontSize = Dimens.fontLg, fontWeight = FontWeight.SemiBold)

@Composable
fun Muted(text: String, modifier: Modifier = Modifier) =
    Text(text, modifier, color = Tokens.current.textMuted, fontSize = Dimens.fontSm)

/**
 * 배지 — 기본은 옅은 바탕(status.*Bg · *Fg). `solid` 는 진한 바탕(status.*Solid · onSolid)으로 경보를 강조할 때만 쓴다
 * (화면당 한 곳 권장 — 남발하면 강조가 사라진다, UX H8). 웹 Badge solid 와 같은 규칙: Link 는 솔리드 토큰이 없어 옅은 배지로,
 * 경고 솔리드의 글자는 statusOnWarningSolid(노랑 바탕 위 대비).
 */
@Composable
fun Badge(text: String, tone: Tone = Tone.Neutral, solid: Boolean = false) {
    val t = Tokens.current
    val (bg, fg) = if (solid && tone != Tone.Link) solidColors(t, tone) else when (tone) {
        Tone.Neutral -> t.statusNeutralBg to t.statusNeutralFg
        Tone.Info -> t.statusInfoBg to t.statusInfoFg
        Tone.Success -> t.statusSuccessBg to t.statusSuccessFg
        Tone.Warning -> t.statusWarningBg to t.statusWarningFg
        Tone.Danger -> t.statusDangerBg to t.statusDangerFg
        Tone.Link -> t.statusLinkBg to t.statusLinkFg
    }
    Text(text, Modifier.background(bg, RoundedCornerShape(Dimens.radiusSm)).padding(horizontal = Dimens.space2, vertical = 2.dp),
        color = fg, fontSize = Dimens.fontXs, fontWeight = FontWeight.SemiBold)
}

/** 솔리드 배지 색 — status.*Solid 바탕 + onSolid 글자(모드마다 잉크가 다르다 · 계획 REQ_05 판단 B2) */
private fun solidColors(t: ColorTokens, tone: Tone) = when (tone) {
    Tone.Success -> t.statusSuccessSolid to t.statusOnSolid
    Tone.Warning -> t.statusWarningSolid to t.statusOnWarningSolid
    Tone.Danger -> t.statusDangerSolid to t.statusOnSolid
    Tone.Info -> t.statusInfoSolid to t.statusOnSolid
    Tone.Neutral, Tone.Link -> t.statusNeutralSolid to t.statusOnSolid
}

/** 상태 배지 — 라벨 · 색은 매핑으로(enum · 색 하드코딩 금지) */
@Composable
fun StatusBadge(code: String, map: Map<String, Pair<String, Tone>>, solid: Boolean = false) {
    val m = map[code]
    Badge(m?.first ?: code, m?.second ?: Tone.Neutral, solid)
}

/**
 * AI 표식 — AI 가 만든 초안 · 요약에 붙인다(STD-AX L1). 색은 ai.* 토큰만. 글자 "AI" 를 함께 써서 색만으로 뜻을 전하지 않는다.
 * 화면 읽기는 `label`(기본 "AI 생성")을 읽는다. 실행 제안(L2)은 표식이 아니라 AiConfirmCard 로 한다. 웹 AiMark 와 같은 props.
 */
@Composable
fun AiMark(text: String = "AI", label: String = "AI 생성") {
    val t = Tokens.current
    val shape = RoundedCornerShape(Dimens.radiusSm)
    Row(
        Modifier.background(t.aiBg, shape).border(1.dp, t.aiBorder, shape)
            .padding(horizontal = Dimens.space2, vertical = 2.dp)
            .clearAndSetSemantics { contentDescription = label },
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dimens.space1),
    ) {
        Text("✦", color = t.aiFg, fontSize = Dimens.fontXs)
        Text(text, color = t.aiFg, fontSize = Dimens.fontXs, fontWeight = FontWeight.Bold)
    }
}

/**
 * 도메인(업무 모듈) 식별 태그 — 모듈 → 번호 슬롯(1~6) 매핑은 데이터로 받는다(코어는 업종 이름을 모른다, STD-DOMAIN-PACK).
 * map 값은 (라벨, 슬롯). 색은 domainNMark(점) · domainNText(글자)만 — 상태색과 섞지 않는다(상태는 옆에 StatusBadge 로 따로).
 * 매핑에 없는 코드 · 범위 밖 슬롯은 색 없이 코드 그대로 보인다. 웹 DomainTag 와 같은 규칙.
 */
@Composable
fun DomainTag(code: String, map: Map<String, Pair<String, Int>>) {
    val t = Tokens.current
    val m = map[code]
    val (mark, fg) = m?.let { domainColors(t, it.second) } ?: (t.borderControl to t.textSecondary)
    val shape = RoundedCornerShape(Dimens.radiusSm)
    Row(
        Modifier.background(t.bgSurface, shape).border(1.dp, t.borderSubtle, shape).padding(horizontal = Dimens.space2, vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dimens.space2),
    ) {
        Box(Modifier.size(Dimens.space2).background(mark, CircleShape).clearAndSetSemantics {}) // 점은 장식 — 이름 글자가 뜻을 전한다
        Text(m?.first ?: code, color = fg, fontSize = Dimens.fontXs, fontWeight = FontWeight.SemiBold)
    }
}

/** 슬롯 → (점, 글자) 색. 범위 밖이면 null(색 없이 그린다) */
private fun domainColors(t: ColorTokens, slot: Int): Pair<Color, Color>? = when (slot) {
    1 -> t.domain1Mark to t.domain1Text
    2 -> t.domain2Mark to t.domain2Text
    3 -> t.domain3Mark to t.domain3Text
    4 -> t.domain4Mark to t.domain4Text
    5 -> t.domain5Mark to t.domain5Text
    6 -> t.domain6Mark to t.domain6Text
    else -> null
}

/** 화면 머리 — 웹 PageHeader 대응 */
@Composable
fun ScreenHeader(title: String, description: String? = null, action: (@Composable () -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().padding(bottom = Dimens.space4), verticalAlignment = Alignment.Bottom) {
        Column(Modifier.weight(1f)) {
            Text(title, color = Tokens.current.textPrimary, fontSize = Dimens.font2xl, fontWeight = FontWeight.Bold)
            if (description != null) Muted(description, Modifier.padding(top = Dimens.space1))
        }
        action?.invoke()
    }
}

@Composable
fun NovaTextField(label: String, value: String, onValueChange: (String) -> Unit, modifier: Modifier = Modifier, error: String? = null, password: Boolean = false, required: Boolean = false) {
    // 오류는 입력란의 supportingText + semantics.error — 화면 읽기 프로그램이 '이 입력란의 오류'로 읽는다(WCAG 3.3.1)
    // 오류 문구는 liveRegion Polite — 제출 뒤 새로 나타난 오류(로그인 실패 포함)를 포커스를 옮기지 않아도 읽어 준다(WCAG 4.1.3 · T04-7.05)
    OutlinedTextField(
        value = value, onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth().then(if (error != null) Modifier.semantics { error(error) } else Modifier),
        label = { Text(if (required) "$label *" else label) }, isError = error != null, singleLine = true,
        supportingText = error?.let { { Text(it, Modifier.semantics { liveRegion = LiveRegionMode.Polite }, color = Tokens.current.statusDangerFg, fontSize = Dimens.fontXs) } },
        visualTransformation = if (password) androidx.compose.ui.text.input.PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
    )
}

/* ------------------------------------------------------------------ 상태 3종 (UX H1 · H9) */
@Composable
fun Loading(label: String = "불러오는 중") {
    Box(Modifier.fillMaxWidth().padding(Dimens.space8).semantics { contentDescription = label }, contentAlignment = Alignment.Center) { CircularProgressIndicator() }
}

@Composable
fun EmptyState(title: String, description: String? = null, action: (@Composable () -> Unit)? = null) {
    Column(Modifier.fillMaxWidth().padding(Dimens.space10), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(Dimens.space2)) {
        Text("📭", fontSize = Dimens.font3xl, modifier = Modifier.clearAndSetSemantics {}) // 장식 — 읽지 않는다
        Title(title)
        if (description != null) Muted(description)
        action?.invoke()
    }
}

/** 오류 — 무엇이 · 왜 · 어떻게(다시 시도). 상태 코드만 보여 주지 않는다 */
@Composable
fun ErrorState(message: String, code: String? = null, onRetry: (() -> Unit)? = null) {
    Column(Modifier.fillMaxWidth().padding(Dimens.space10), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(Dimens.space2)) {
        Text("⚠️", fontSize = Dimens.font3xl, modifier = Modifier.clearAndSetSemantics {}) // 장식 — 읽지 않는다
        Title("불러오지 못했습니다")
        Muted(message)
        if (code != null) Muted("오류 코드 $code")
        if (onRetry != null) NovaButton("다시 시도", onRetry, variant = Variant.Secondary)
    }
}

/** 목록 — 웹 DataTable 대응(모바일은 카드형 행) */
@Composable
fun <T> DataList(rows: List<T>, key: (T) -> Any, modifier: Modifier = Modifier, onClick: ((T) -> Unit)? = null, row: @Composable (T) -> Unit) {
    LazyColumn(modifier, verticalArrangement = Arrangement.spacedBy(Dimens.space2)) {
        items(rows, key = key) { r -> Card(onClick = onClick?.let { { it(r) } }) { row(r) } }
    }
}

/** 확인 대화상자 — 되돌릴 수 없는 액션 전에(UX H3 · H5). 취소가 먼저 · 위험 버튼은 Danger */
@Composable
fun ConfirmDialog(title: String, message: String? = null, confirmLabel: String = "확인", danger: Boolean = false, onResult: (Boolean) -> Unit) {
    AlertDialog(
        onDismissRequest = { onResult(false) },
        title = { Text(title) },
        text = message?.let { { Text(it) } },
        // 취소도 NovaButton(Ghost) — 글자색 text.brand(다크 7.65:1). Material 기본 TextButton 색에 기대지 않는다
        dismissButton = { NovaButton("취소", { onResult(false) }, variant = Variant.Ghost) },
        confirmButton = { NovaButton(confirmLabel, { onResult(true) }, variant = if (danger) Variant.Danger else Variant.Primary) },
    )
}

@Composable
fun SpacerV(height: androidx.compose.ui.unit.Dp = Dimens.space3) = Spacer(Modifier.height(height))
