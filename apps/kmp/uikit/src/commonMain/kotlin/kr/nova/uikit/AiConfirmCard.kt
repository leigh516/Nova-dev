package kr.nova.uikit

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/** 자동화 등급 — 사람 승인이 필요한 실행(L2)만 AiConfirmCard 로. 웹 `level: "L2"` 대응 */
enum class AiLevel { L2 }

/** 실행 파라미터 한 줄 — 웹 params `{ label, value }` 대응 */
data class AiParam(val label: String, val value: String)

/**
 * AI 확인 카드(STD-AX L2) — AI 가 제안한 **실행**을 사람이 읽고 승인한다. 표식(AiMark)만 붙이는 L1 과 다르다.
 * 웹 AiConfirmCard 와 같은 props 이름(level · title · target · scope · params · undo · onApprove · onCancel, 선택 approveLabel · success).
 * 모바일만 `notify` 를 더 받는다 — 웹은 토스트를 컨텍스트로, 모바일은 rememberAction 이 알림 함수를 인자로 받는다(ui.md 규칙 4).
 * 🔴 승인 API 는 require_human — 카드는 사람이 누르게 할 뿐 서버를 지키지 못한다. onApprove 가 부르는 서버 핸들러는
 *    `Principal.require_human()`(nova_common service.py)으로 AI 주체를 403 으로 막아야 한다(계획 REQ_05 §11 판단 D).
 * 실수 막기(UX H5):
 * - 렌더만으로 onApprove 를 부르지 않는다 — 승인 버튼을 눌렀을 때만(LaunchedEffect 는 포커스만 옮긴다)
 * - 기본 포커스는 **취소** — 키보드 Enter 를 그냥 쳐도 실행되지 않는다
 * - 대상 · 범위 · 파라미터 · 되돌림을 누르기 전에 모두 보인다. undo 가 null 이면 "되돌릴 수 없습니다" + 위험 버튼
 * 상태(계획 §5): 제안 → 승인중(둘 다 잠김) → 완료(성공 알림 · 버튼 없음) / 실패(서버 문구 · 다시 시도 · 취소). 취소는 onCancel(카드를 닫는 것은 부모)
 */
@Composable
fun AiConfirmCard(
    level: AiLevel,
    title: String,
    target: String,
    scope: String,
    params: List<AiParam>,
    undo: String?,
    onApprove: suspend () -> Unit,
    onCancel: () -> Unit,
    notify: (Notice) -> Unit,
    modifier: Modifier = Modifier,
    approveLabel: String = "승인하고 실행",
    success: String = "승인했습니다 — 실행을 요청했습니다",
) {
    val t = Tokens.current
    var done by remember { mutableStateOf(false) }
    val approve = rememberAction<Unit>(notify, success = success, then = { done = true }) { onApprove() }
    val cancelFocus = remember { FocusRequester() }
    // 처음 그릴 때 취소에 포커스 — 실행은 여기서 하지 않는다
    LaunchedEffect(Unit) { cancelFocus.requestFocus() }
    val irreversible = undo == null
    val shape = RoundedCornerShape(Dimens.radiusLg)
    Column(
        modifier.fillMaxWidth().background(t.bgSurface, shape).border(1.dp, t.aiBorder, shape).padding(Dimens.space4),
        verticalArrangement = Arrangement.spacedBy(Dimens.space3),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dimens.space2)) {
            AiMark(text = "AI 제안", label = "AI 제안")
            Text(title, Modifier.weight(1f).semantics { heading() }, color = t.textPrimary, fontSize = Dimens.fontLg, fontWeight = FontWeight.SemiBold)
        }
        Badge("${level.name} · 사람 승인 필요", Tone.Info)
        Muted("AI 가 만든 실행안입니다. 사람이 읽고 승인해야 실행되며, 서버도 사람의 승인만 받습니다.")
        Column(verticalArrangement = Arrangement.spacedBy(Dimens.space2)) {
            AiRow("대상", target)
            AiRow("범위", scope)
            params.forEach { AiRow(it.label, it.value) }
            AiRow("되돌림", undo ?: "되돌릴 수 없습니다", danger = irreversible)
        }
        val err = approve.error
        if (err != null && !approve.running) {
            Text("실행하지 못했습니다 — ${err.message ?: "요청을 처리하지 못했습니다"}",
                Modifier.semantics { liveRegion = LiveRegionMode.Assertive },
                color = t.statusDangerFg, fontSize = Dimens.fontSm, fontWeight = FontWeight.SemiBold)
        }
        if (done) {
            Muted("승인했습니다. 실행 결과는 작업 기록에서 확인하세요.", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dimens.space2, Alignment.End)) {
                NovaButton("취소", onCancel, Modifier.focusRequester(cancelFocus), variant = Variant.Secondary, enabled = !approve.running)
                NovaButton(if (err != null) "다시 시도" else approveLabel, approve::run,
                    variant = if (irreversible) Variant.Danger else Variant.Primary, loading = approve.running)
            }
        }
    }
}

/** 파라미터 한 줄 — 라벨(흐린 글자) 1 : 값 3 폭. 되돌릴 수 없음은 위험 글자로 강조 */
@Composable
private fun AiRow(label: String, value: String, danger: Boolean = false) {
    val t = Tokens.current
    Row(Modifier.fillMaxWidth()) {
        Text(label, Modifier.weight(1f), color = t.textMuted, fontSize = Dimens.fontSm)
        Text(value, Modifier.weight(3f), color = if (danger) t.statusDangerFg else t.textPrimary, fontSize = Dimens.fontSm,
            fontWeight = if (danger) FontWeight.Bold else FontWeight.Normal)
    }
}
