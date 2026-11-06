package kr.nova.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import kr.nova.uikit.AiConfirmCard
import kr.nova.uikit.AiLevel
import kr.nova.uikit.AiMark
import kr.nova.uikit.AiParam
import kr.nova.uikit.Badge
import kr.nova.uikit.Dimens
import kr.nova.uikit.DomainTag
import kr.nova.uikit.Muted
import kr.nova.uikit.Notice
import kr.nova.uikit.NovaTheme
import kr.nova.uikit.ScreenHeader
import kr.nova.uikit.StatusBadge
import kr.nova.uikit.Title
import kr.nova.uikit.Tokens
import kr.nova.uikit.Tone

/** 갤러리 가짜 데이터 — 서버 설정에서 읽은 매핑을 흉내 낸다(색 · enum 하드코딩 금지 규칙 그대로) */
private val ALERT_MAP = mapOf("crit" to ("위험" to Tone.Danger), "warn" to ("주의" to Tone.Warning), "ok" to ("정상" to Tone.Success))
private val TONE_LABEL = mapOf(Tone.Neutral to "중립", Tone.Info to "정보", Tone.Success to "성공", Tone.Warning to "경고", Tone.Danger to "위험", Tone.Link to "링크")
private val DOMAIN_MAP = mapOf(
    "fw" to ("방화벽" to 1), "ids" to ("침입 탐지" to 2), "net" to ("네트워크" to 3),
    "gpu" to ("GPU 서버" to 4), "ai" to ("AI 서비스" to 5), "bill" to ("과금" to 6),
)

/**
 * 모바일 부품 갤러리(스냅숏 전용 — 웹 /design 대응) — 계획 REQ_05 4단계 부품: 솔리드 배지 · AI 표식 · 도메인 태그 · AI 확인 카드.
 * onApprove 는 렌더만으로 불리면 안 된다 — 부르면 approveCalls 가 늘고 스냅숏이 실패한다.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun UikitGallery(dark: Boolean, onApprove: () -> Unit) {
    val notify: (Notice) -> Unit = {}
    NovaTheme(dark = dark) {
        Column(
            Modifier.fillMaxSize().background(Tokens.current.bgCanvas).padding(Dimens.space4),
            verticalArrangement = Arrangement.spacedBy(Dimens.space3),
        ) {
            ScreenHeader("모바일 부품", "토큰 부품 4종 — 라이트 · 다크 모두 의미 토큰만 씁니다")

            Title("솔리드 배지")
            Muted("경보 강조에만(화면당 한 곳 권장). 링크는 솔리드 토큰이 없어 옅은 배지로 그립니다")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(Dimens.space2), verticalArrangement = Arrangement.spacedBy(Dimens.space2)) {
                Tone.entries.forEach { Badge(TONE_LABEL.getValue(it), it, solid = true) }
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(Dimens.space2), verticalArrangement = Arrangement.spacedBy(Dimens.space2)) {
                Tone.entries.forEach { Badge(TONE_LABEL.getValue(it), it) }
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(Dimens.space2)) {
                listOf("crit", "warn", "ok", "unknown").forEach { StatusBadge(it, ALERT_MAP, solid = true) }
            }

            Title("AI 표식")
            Muted("AI 가 만든 초안 · 요약에 붙입니다(L1). 화면 읽기는 'AI 생성'으로 읽습니다")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(Dimens.space2)) {
                AiMark()
                AiMark(text = "AI 요약", label = "AI 요약")
            }

            Title("도메인 태그")
            Muted("모듈 → 번호 슬롯 매핑은 데이터로. 상태는 옆에 상태 배지로 따로 붙입니다")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(Dimens.space2), verticalArrangement = Arrangement.spacedBy(Dimens.space2)) {
                listOf("fw", "ids", "net", "gpu", "ai", "bill", "etc").forEach { DomainTag(it, DOMAIN_MAP) }
                StatusBadge("crit", ALERT_MAP)
            }

            Title("AI 확인 카드")
            AiConfirmCard(
                level = AiLevel.L2, title = "방화벽 외부 접속 차단",
                target = "방화벽 FW-SEOUL-02 외 2대", scope = "서울 관제센터 · 외부 접속 차단 30분",
                params = listOf(AiParam("차단 대상", "203.0.113.0/24"), AiParam("사유", "무차별 로그인 시도 1,240회")),
                undo = "차단 규칙 삭제(작업 기록에서 되돌리기)",
                onApprove = { onApprove() }, onCancel = {}, notify = notify,
            )
            AiConfirmCard(
                level = AiLevel.L2, title = "오래된 로그 영구 삭제",
                target = "관제 로그 2025년 1분기", scope = "전 테넌트 · 약 4.2TB",
                params = listOf(AiParam("보존 기한", "만료(1년)")),
                undo = null,
                onApprove = { onApprove() }, onCancel = {}, notify = notify, approveLabel = "승인하고 삭제",
            )
        }
    }
}
