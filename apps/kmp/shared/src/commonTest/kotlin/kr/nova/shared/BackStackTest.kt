package kr.nova.shared

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** 화면 스택 — 시스템 뒤로 가기는 canPop 일 때만 받는다(T04-7.03 · 7.04) */
class BackStackTest {
    @Test
    fun rootCannotPop() {
        val s = BackStack("목록")
        assertEquals("목록", s.current)
        assertFalse(s.canPop)
        assertSame(s, s.pop()) // 첫 화면에서 뒤로 가기는 앱이 받지 않는다(시스템 기본 — 앱 닫힘)
    }

    @Test
    fun pushThenPopReturnsToPrevious() {
        val s = BackStack("목록").push("상세")
        assertEquals("상세", s.current)
        assertTrue(s.canPop)
        val back = s.pop()
        assertEquals("목록", back.current)
        assertFalse(back.canPop)
    }

    @Test
    fun resetLeavesOnlyRoot() {
        val s = BackStack("목록").push("상세").push("상세2").reset("도움말")
        assertEquals(listOf("도움말"), s.entries)
        assertFalse(s.canPop)
    }

    @Test
    fun isImmutableValue() {
        val a = BackStack("목록")
        a.push("상세")
        assertEquals(listOf("목록"), a.entries) // 바꾼 값은 새 스택으로 — 상태 갱신이 Compose 에 보인다
        assertEquals(BackStack("목록").push("상세"), BackStack("목록").push("상세"))
    }
}
