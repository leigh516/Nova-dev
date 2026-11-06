package kr.nova.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import kr.nova.shared.ApiException
import kr.nova.shared.FormField
import kr.nova.shared.Loadable
import kr.nova.shared.Page
import kr.nova.shared.emailError
import kr.nova.uikit.Card
import kr.nova.uikit.DetailScreen
import kr.nova.uikit.Dimens
import kr.nova.uikit.EmptyText
import kr.nova.uikit.FormScreen
import kr.nova.uikit.ListScreen
import kr.nova.uikit.Muted
import kr.nova.uikit.Notice
import kr.nova.uikit.NovaTheme
import kr.nova.uikit.Title
import kr.nova.uikit.Tokens

/**
 * 모바일 템플릿 갤러리(스냅숏 전용) — 서버 없이 상태 3종(로딩 · 빈 · 오류)과 입력 템플릿을 라이트 · 다크로 찍는다(T07-3.03).
 * 실제 데이터 화면(목록 · 상세)은 Snapshot 의 items · item-detail 캡처가 맡는다.
 */
@Composable
fun TemplateGallery(dark: Boolean) {
    val notify: (Notice) -> Unit = {}
    val failed = ApiException(503, "rbac_unavailable", "권한 확인이 잠시 안 됩니다. 잠시 뒤 다시 시도하세요")
    NovaTheme(dark = dark) {
        Column(
            Modifier.fillMaxSize().background(Tokens.current.bgCanvas).padding(Dimens.space4),
            verticalArrangement = Arrangement.spacedBy(Dimens.space4),
        ) {
            Title("ListScreen — 빈 상태")
            ListScreen<String>("항목", Loadable(Page(emptyList(), 0, 1, 20)), onRetry = {}, key = { it },
                empty = EmptyText("아직 항목이 없습니다", "위에서 첫 항목을 만들어 보세요")) { Muted(it) }

            Title("ListScreen — 오류")
            ListScreen<String>("항목", Loadable(error = failed), onRetry = {}, key = { it }) { Muted(it) }

            Title("DetailScreen — 불러오는 중")
            DetailScreen<String>(Loadable(loading = true), title = { it }, onRetry = {}) { Card { Muted(it) } }

            Title("FormScreen")
            FormScreen(
                "새 항목", listOf(
                    FormField("name", "이름", required = true, help = "목록에 보이는 이름입니다"),
                    FormField("email", "알림 받을 이메일", validate = ::emailError),
                ),
                notify = notify, onSubmit = {}, description = "필수 칸은 * 로 표시합니다", onCancel = {},
            )
        }
    }
}
