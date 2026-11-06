package kr.nova.shared

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

/** FormScreen 칸 검사 — 문구는 웹 useFormModel check 와 같다(ui.md 규칙 8 · T07-3.03) */
class FormModelTest {
    private val name = FormField("name", "이름", required = true, maxLength = 5)
    private val memo = FormField("memo", "메모")
    private val email = FormField("email", "이메일", validate = ::emailError)

    @Test fun 필수_칸이_비면_입력하라고_한다() {
        assertEquals("이름을(를) 입력하세요", fieldError(name, "  "))
    }

    @Test fun 상한을_넘으면_지금_글자_수를_알린다() {
        assertEquals("5자 이하로 입력하세요 (지금 6자)", fieldError(name, "가나다라마바"))
    }

    @Test fun 사용자_검사를_마지막에_한다() {
        assertEquals("이메일 형식이 아닙니다. 예: name@example.com", fieldError(email, "nova"))
        assertNull(fieldError(email, "a@nova.dev"))
    }

    @Test fun 선택_칸은_비어도_된다() {
        assertNull(fieldError(memo, ""))
    }

    @Test fun 폼_오류는_오류가_있는_칸만_순서대로() {
        val errs = formErrors(listOf(name, memo, email), mapOf("name" to "", "email" to "x"))
        assertEquals(listOf("name", "email"), errs.keys.toList())
    }

    @Test fun 처음_값은_칸마다_채우고_없으면_빈_문자열() {
        assertEquals(mapOf("name" to "가", "memo" to "", "email" to ""), initialValues(listOf(name, memo, email), mapOf("name" to "가", "기타" to "무시")))
    }
}
