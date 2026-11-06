package kr.nova.shared

import kotlin.test.Test
import kotlin.test.assertEquals

/** 템플릿 상태 3종 판정 — ListScreen · DetailScreen 이 이 판정 하나로 로딩 · 빈 · 오류 · 내용을 고른다(T07-3.03) */
class ViewPhaseTest {
    private val err = ApiException(500, "server", "서버 오류")
    private fun page(vararg names: String) = Page(names.toList(), names.size, 1, 20)

    @Test fun 처음_값은_로딩이다() {
        // 불러오기 전 첫 화면에 '항목 없음'이 번쩍이지 않게 — 데이터도 오류도 없으면 로딩
        assertEquals(ViewPhase.Loading, Loadable<Page<String>>().phase())
    }

    @Test fun 불러오는_중이고_데이터가_없으면_로딩() {
        assertEquals(ViewPhase.Loading, Loadable<Page<String>>(loading = true).phase())
    }

    @Test fun 데이터가_없고_오류면_오류() {
        assertEquals(ViewPhase.Error, Loadable<Page<String>>(error = err).phase())
    }

    @Test fun 비었으면_빈_상태() {
        assertEquals(ViewPhase.Empty, Loadable(page()).phase(isEmpty = { it.items.isEmpty() }))
    }

    @Test fun 내용이_있으면_내용() {
        assertEquals(ViewPhase.Content, Loadable(page("가")).phase(isEmpty = { it.items.isEmpty() }))
    }

    @Test fun 새로_고치는_중에도_이전_데이터를_보인다() {
        // load() 는 다시 불러올 때 데이터를 남긴다 — 목록이 스피너로 깜박이지 않게
        assertEquals(ViewPhase.Content, Loadable(page("가"), loading = true).phase(isEmpty = { it.items.isEmpty() }))
    }

    @Test fun 새로_고치다_실패해도_이전_데이터를_보인다() {
        // 실패 알림은 rememberAction · 스낵바가 맡는다 — 화면을 오류로 갈아엎지 않는다(기존 ItemsScreen 동작)
        assertEquals(ViewPhase.Content, Loadable(page("가"), error = err).phase(isEmpty = { it.items.isEmpty() }))
    }

    @Test fun 받지_않는_데이터는_없는_것으로_본다() {
        // 상세 화면 — 앞서 본 다른 항목의 데이터가 남아 있으면 그것을 보이지 않고 로딩(또는 오류)
        val stale = Loadable("다른-id")
        assertEquals(ViewPhase.Loading, stale.phase(accept = { it == "이-id" }))
        assertEquals(ViewPhase.Error, stale.copy(error = err).phase(accept = { it == "이-id" }))
        assertEquals(ViewPhase.Content, stale.phase(accept = { it == "다른-id" }))
    }
}
