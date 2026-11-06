package kr.nova.uikit

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import kr.nova.shared.ApiException
import kr.nova.shared.FormField
import kr.nova.shared.Loadable
import kr.nova.shared.Page
import kr.nova.shared.ViewPhase
import kr.nova.shared.emailError
import kr.nova.shared.formErrors
import kr.nova.shared.initialValues
import kr.nova.shared.phase

/*
 * 화면 템플릿 — 웹 @nova/ui templates/pages.tsx 와 같은 이름(ui.md 규칙 9): LoginPage ↔ LoginScreen · ListPage ↔ ListScreen ·
 * DetailPage ↔ DetailScreen · FormPage ↔ FormScreen. 화면은 템플릿 호출 + 데이터 정의만(ui.md §1).
 * 로딩 · 빈 · 오류는 템플릿이 그린다(규칙 5) — 판정은 shared ViewPhase(kmp-test 가 검사).
 * 웹은 템플릿이 경로(source)로 직접 불러오지만, 모바일은 AppStore 의 Loadable 을 받는다(불러오기는 저장소가 맡는 앱 구조 그대로).
 */

/** 빈 상태 문구 — 기본값은 웹 ListPage 와 같다 */
data class EmptyText(val title: String = "아직 항목이 없습니다", val description: String? = null)

/** 상세 위 돌아가기 — 웹 crumbs 대응(모바일은 한 단계 위만) */
data class BackLink(val label: String, val onClick: () -> Unit)

/** 로그인 데모 계정 — 개발 빌드에서만 넘긴다(웹 LoginPage demo 와 같은 모양) */
data class DemoAccount(val label: String, val email: String)

/** 오류 상태 — Loadable 의 오류를 무엇이 · 왜 · 어떻게(다시 시도)로 */
@Composable
private fun LoadError(e: ApiException?, onRetry: () -> Unit) = ErrorState(e?.message ?: "", e?.code, onRetry)

/* ------------------------------------------------------------------ 목록 */
/**
 * 목록 — 머리(제목 · 설명 · 머리 행동) → 도구줄(검색 · 새로 만들기 등, 상태와 무관하게 늘 보임) → 로딩 · 빈 · 오류 · DataList.
 * 다시 불러오는 중 · 실패해도 이전 목록을 보인다(ViewPhase). 주 행동은 화면당 하나(UX H8).
 *   ListScreen("항목", state, onRetry = { store.loadItems() }, key = { it.id }, onRowClick = { open(it.id) }) { ItemRow(it) }
 */
@Composable
fun <T> ListScreen(
    title: String,
    state: Loadable<Page<T>>,
    onRetry: () -> Unit,
    key: (T) -> Any,
    modifier: Modifier = Modifier,
    description: String? = null,
    actions: (@Composable () -> Unit)? = null,
    toolbar: (@Composable () -> Unit)? = null,
    empty: EmptyText = EmptyText(),
    onRowClick: ((T) -> Unit)? = null,
    row: @Composable (T) -> Unit,
) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(Dimens.space3)) {
        ScreenHeader(title, description, actions)
        toolbar?.invoke()
        when (state.phase(isEmpty = { it.items.isEmpty() })) {
            ViewPhase.Loading -> Loading()
            ViewPhase.Error -> LoadError(state.error, onRetry)
            ViewPhase.Empty -> EmptyState(empty.title, empty.description)
            ViewPhase.Content -> DataList(state.data!!.items, key = key, onClick = onRowClick, row = row)
        }
    }
}

/* ------------------------------------------------------------------ 상세 */
/**
 * 상세 — 돌아가기 → 로딩 · 오류 → 머리(제목 · 행동) + 본문. 빈 상태는 없다(단건).
 * accept 로 앞서 본 다른 건의 데이터가 남아 있으면 보이지 않는다(id 비교).
 *   DetailScreen(state, title = { it.name }, onRetry = { store.loadItem(id) }, accept = { it.id == id }, back = BackLink("항목", onBack)) { d -> … }
 */
@Composable
fun <T> DetailScreen(
    state: Loadable<T>,
    title: (T) -> String,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
    accept: (T) -> Boolean = { true },
    back: BackLink? = null,
    description: ((T) -> String?)? = null,
    actions: (@Composable (T) -> Unit)? = null,
    content: @Composable ColumnScope.(T) -> Unit,
) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(Dimens.space3)) {
        if (back != null) NovaButton("← ${back.label}", back.onClick, variant = Variant.Ghost)
        when (state.phase(accept = accept)) {
            ViewPhase.Loading -> Loading()
            ViewPhase.Error -> LoadError(state.error, onRetry)
            ViewPhase.Empty, ViewPhase.Content -> {
                val d = state.data!!
                val act: (@Composable () -> Unit)? = if (actions == null) null else ({ actions(d) })
                ScreenHeader(title(d), description?.invoke(d), act)
                content(d)
            }
        }
    }
}

/* ------------------------------------------------------------------ 입력 */
/**
 * 입력 — 머리 → 칸(FormField) → 취소 · 제출. 제출은 rememberAction(진행 중 누름 무시 · 성공/오류 알림 · 후속).
 * 칸 오류는 고친 칸 · 제출한 뒤에 보이고, 제출 때 오류가 있으면 첫 오류 칸으로 포커스를 옮긴다(UX H5 · H9 — 웹 FormPage 와 같다).
 * 실패하면 입력은 그대로 남는다. 서버 칸별 오류(422 fields)를 칸 옆에 보이는 것은 아직 없다 — 오류 알림으로만.
 */
@Composable
fun FormScreen(
    title: String,
    fields: List<FormField>,
    notify: (Notice) -> Unit,
    onSubmit: suspend (Map<String, String>) -> Any?,
    modifier: Modifier = Modifier,
    description: String? = null,
    initial: Map<String, String> = emptyMap(),
    submitLabel: String = "저장",
    success: String = "저장했습니다",
    onCancel: (() -> Unit)? = null,
    then: (() -> Unit)? = null,
) {
    var values by remember { mutableStateOf(initialValues(fields, initial)) }
    var touched by remember { mutableStateOf(emptySet<String>()) }
    val focus = remember(fields) { fields.associate { it.key to FocusRequester() } }
    val errors = formErrors(fields, values)
    val action = rememberAction<Any?>(notify, success = success, then = { then?.invoke() }) { onSubmit(values) }
    val submit: () -> Unit = {
        touched = fields.map { it.key }.toSet()
        val first = fields.firstOrNull { it.key in errors }
        if (first != null) focus[first.key]?.requestFocus() else action.run()
    }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(Dimens.space3)) {
        ScreenHeader(title, description)
        Card {
            Column(verticalArrangement = Arrangement.spacedBy(Dimens.space3)) {
                fields.forEach { f ->
                    val shown = errors[f.key]?.takeIf { f.key in touched }
                    NovaTextField(
                        f.label, values[f.key] ?: "", { v -> values = values + (f.key to v); touched = touched + f.key },
                        Modifier.focusRequester(focus.getValue(f.key)), error = shown, password = f.password, required = f.required,
                    )
                    if (shown == null) f.help?.let { Muted(it) } // 오류가 보이면 도움말 대신 오류 하나만
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dimens.space2, Alignment.End)) {
                    if (onCancel != null) NovaButton("취소", onCancel, variant = Variant.Ghost)
                    NovaButton(submitLabel, submit, loading = action.running)
                }
            }
        }
    }
}

/* ------------------------------------------------------------------ 로그인 */
/**
 * 로그인 — 제목 · 부제 → 이메일 · 비밀번호 → 로그인 → 데모 계정(개발 빌드만) · 도움 문구.
 * 형식은 서버와 같은 규칙(emailError)으로 먼저 본다 — 틀린 형식을 보내 '계정 없음'으로 오해하지 않게(웹 LoginPage 와 같다).
 * onLogin 은 실패할 때만 onError 를 부른다 — 성공하면 앱이 화면을 바꾼다(그동안 버튼은 '확인 중…'으로 남는다).
 * 아이디 저장(rememberId) · 링크(links)는 아직 없다.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LoginScreen(
    title: String,
    onLogin: (email: String, password: String, onError: (ApiException) -> Unit) -> Unit,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    demo: List<DemoAccount> = emptyList(),
    demoPassword: String? = null,
    help: String? = null,
) {
    var email by remember { mutableStateOf(demo.firstOrNull()?.email ?: "") }
    var pw by remember { mutableStateOf(demoPassword ?: "") }
    var err by remember { mutableStateOf<String?>(null) }
    var emailErr by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(Dimens.space3)) {
        ScreenHeader(title, subtitle)
        NovaTextField("이메일", email, { email = it; emailErr = null }, required = true, error = emailErr)
        NovaTextField("비밀번호", pw, { pw = it }, password = true, required = true, error = err)
        NovaButton(if (busy) "확인 중…" else "로그인", {
            if (email.isBlank() || pw.isBlank()) { err = "이메일과 비밀번호를 입력하세요"; return@NovaButton }
            emailError(email)?.let { emailErr = it; err = null; return@NovaButton }
            busy = true; err = null; emailErr = null
            onLogin(email, pw) { e -> err = e.message; busy = false }
        }, Modifier.fillMaxWidth(), loading = busy)
        if (demo.isNotEmpty()) {
            Muted("개발용 계정")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(Dimens.space2)) {
                demo.forEach { d -> NovaButton(d.label, { email = d.email; emailErr = null }, variant = Variant.Secondary) }
            }
        }
        if (help != null) Muted(help)
    }
}
