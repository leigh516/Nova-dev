package kr.nova.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import kr.nova.shared.AppStore
import kr.nova.shared.Item
import kr.nova.shared.archiveItem
import kr.nova.shared.createItem
import kr.nova.shared.deleteItem
import kr.nova.shared.fmtAt
import kr.nova.shared.itemNameError
import kr.nova.shared.restoreItem
import kr.nova.uikit.BackLink
import kr.nova.uikit.Card
import kr.nova.uikit.ConfirmDialog
import kr.nova.uikit.DemoAccount
import kr.nova.uikit.DetailScreen
import kr.nova.uikit.Dimens
import kr.nova.uikit.EmptyText
import kr.nova.uikit.ListScreen
import kr.nova.uikit.LoginScreen
import kr.nova.uikit.Muted
import kr.nova.uikit.Notice
import kr.nova.uikit.NovaButton
import kr.nova.uikit.NovaTextField
import kr.nova.uikit.ScreenHeader
import kr.nova.uikit.SpacerV
import kr.nova.uikit.StatusBadge
import kr.nova.uikit.Title
import kr.nova.uikit.Tone
import kr.nova.uikit.Variant
import kr.nova.uikit.rememberAction

/*
 * 샘플 앱 화면 — 템플릿(kr.nova.uikit Templates.kt) 호출 + 이 화면만의 데이터 정의(ui.md §1).
 * 앱 화면 함수 이름은 템플릿 이름(LoginScreen · ListScreen …)과 겹치지 않게 업무 이름으로 짓는다.
 */

/** 상태 표시 매핑 — 실제 프로젝트는 서버 설정 API 에서 읽는다(웹 lib/app.ts ITEM_STATUS 와 같게) */
val ITEM_STATUS = mapOf("active" to ("사용 중" to Tone.Success), "archived" to ("보관됨" to Tone.Neutral))
val ACTIVITY_LABEL = mapOf("created" to "만듦", "archived" to "보관함", "restored" to "보관 풂", "updated" to "고침")

/** 개발용 계정 — 개발 빌드 샘플(웹 로그인 화면 demo 와 같은 계정) */
private val DEMO = listOf(DemoAccount("사용자", "user@nova.dev"), DemoAccount("책임자", "manager@nova.dev"))

/** @screen 로그인 · @status 완료 */
@Composable
fun SignInScreen(store: AppStore) {
    LoginScreen(
        "Nova", onLogin = { email, pw, onError -> store.login(email, pw, onError) },
        subtitle = "개발용 계정으로 바로 들어갈 수 있습니다", demo = DEMO, demoPassword = "nova1234",
        help = "비밀번호는 nova1234 · 사용자 user@nova.dev · 책임자 manager@nova.dev",
    )
}

/** @screen 항목 목록 · @status 완료 */
@Composable
fun ItemsScreen(store: AppStore, notify: (Notice) -> Unit, onOpen: (String) -> Unit, onLogout: () -> Unit) {
    val state by store.items.collectAsState()
    var name by remember { mutableStateOf("") }
    var nameErr by remember { mutableStateOf<String?>(null) }
    var confirmDelete by remember { mutableStateOf<Item?>(null) }
    LaunchedEffect(Unit) { store.loadItems() }
    val create = rememberAction(notify, success = "항목을 만들었습니다", then = { name = ""; store.loadItems() }) { store.api.createItem(name.trim()) }

    ListScreen(
        "항목", state, onRetry = { store.loadItems() }, key = { it.id },
        description = "보관하면 남고, 삭제하면 사라집니다",
        actions = { NovaButton("로그아웃", onLogout, variant = Variant.Ghost) },
        toolbar = {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dimens.space2)) {
                NovaTextField("새 항목 이름", name, { name = it; nameErr = null }, Modifier.weight(1f), error = nameErr)
                // 상한은 서버 계약(Contract.ITEM_NAME_MAX)에서 — 화면에 숫자를 쓰지 않는다
                NovaButton("만들기", { val e = itemNameError(name); if (e != null) nameErr = e else create.run() }, loading = create.running)
            }
        },
        empty = EmptyText("아직 항목이 없습니다", "위에서 첫 항목을 만들어 보세요"),
        onRowClick = { onOpen(it.id) },
    ) { item -> ItemRow(store, item, notify, onDelete = { confirmDelete = item }) }

    confirmDelete?.let { item ->
        val remove = rememberAction(notify, success = "삭제했습니다", then = { store.loadItems() }) { store.api.deleteItem(item.id) }
        ConfirmDialog("'${item.name}' 을(를) 삭제할까요?", "삭제하면 되돌릴 수 없습니다. 잠시 숨기려면 '보관'을 쓰세요.", confirmLabel = "삭제", danger = true) { ok ->
            confirmDelete = null
            if (ok) remove.run()
        }
    }
}

@Composable
private fun ItemRow(store: AppStore, item: Item, notify: (Notice) -> Unit, onDelete: () -> Unit) {
    val archive = rememberAction(notify, success = "'${item.name}' 을(를) 보관했습니다",
        undo = { store.api.restoreItem(item.id) }, then = { store.loadItems() }) { store.api.archiveItem(item.id) }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dimens.space2)) {
        Column(Modifier.weight(1f)) {
            Title(item.name)
            Row(horizontalArrangement = Arrangement.spacedBy(Dimens.space2)) { StatusBadge(item.status, ITEM_STATUS); Muted(fmtAt(item.createdAt)) }
        }
        if (item.status == "active") NovaButton("보관", archive::run, variant = Variant.Secondary, loading = archive.running)
        NovaButton("삭제", onDelete, variant = Variant.Ghost)
    }
}

/** @screen 항목 상세 · @status 완료 */
@Composable
fun ItemDetailScreen(store: AppStore, id: String, notify: (Notice) -> Unit, onBack: () -> Unit) {
    val state by store.detail.collectAsState()
    LaunchedEffect(id) { store.loadItem(id) }
    DetailScreen(
        state, title = { it.name }, onRetry = { store.loadItem(id) },
        accept = { it.id == id }, back = BackLink("항목", onBack),
    ) { d ->
        Card { Column(verticalArrangement = Arrangement.spacedBy(Dimens.space2)) {
            StatusBadge(d.status, ITEM_STATUS)
            Muted("메모: ${d.memo ?: "—"}")
            Muted("만든 때: ${fmtAt(d.createdAt)}")
        } }
        Title("활동 기록")
        if (d.activity.isEmpty()) Muted("아직 기록이 없습니다. 이벤트가 처리되면 나타납니다.")
        d.activity.forEach { Text("• ${ACTIVITY_LABEL[it.kind] ?: it.kind}  ${fmtAt(it.recordedAt)}") }
        // 서버가 최근 50건으로 잘랐으면 알린다 — 전부라고 오해하지 않게(UX H1 · T04-6.04, 웹 상세와 같은 문구)
        if (d.activityTruncated) Muted("최근 50건만 보입니다")
    }
}

/** @screen 도움말 · @status 완료 */
@Composable
fun HelpScreen() {
    // 데이터가 없는 정적 화면 — 상태 3종이 필요 없어 템플릿 없이 머리 + 카드로(웹 도움말도 같다)
    Column(verticalArrangement = Arrangement.spacedBy(Dimens.space3)) {
        ScreenHeader("도움말", "자주 하는 일")
        listOf(
            "항목을 만들려면" to "이름을 쓰고 '만들기'를 누릅니다.",
            "잠시 숨기려면" to "'보관'을 누릅니다. 실수했다면 아래 알림의 '실행 취소'를 누르세요.",
            "완전히 지우려면" to "'삭제'를 누르고 확인합니다. 되돌릴 수 없습니다.",
            "권한이 없다고 나오면" to "알림의 내용을 관리자에게 알려 주세요.",
        ).forEach { (q, a) -> Card { Column { Title(q); SpacerV(Dimens.space1); Muted(a) } } }
    }
}
