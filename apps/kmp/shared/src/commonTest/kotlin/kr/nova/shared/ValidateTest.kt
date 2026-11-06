package kr.nova.shared

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

/** 입력 검사 — 서버 계약(Contract, 생성물)과 같은 규칙 · 웹 sdk emailError 와 같은 문구(plan_REQ_04 T04-4.07) */
class ValidateTest {
    private val badEmail = "이메일 형식이 아닙니다. 예: name@example.com"

    @Test
    fun goodEmailPasses() = assertNull(emailError("user@nova.dev"))

    @Test
    fun spacesAndCaseLikeServer() = assertNull(emailError("  User@Nova.Dev "))

    @Test
    fun missingDomainFails() = assertEquals(badEmail, emailError("user@"))

    @Test
    fun oneLetterTldFails() = assertEquals(badEmail, emailError("a@b.c"))

    @Test
    fun emptyIsLeftToRequiredCheck() = assertNull(emailError("   "))

    @Test
    fun tooLongEmailFails() = assertEquals(badEmail, emailError("a".repeat(Contract.EMAIL_MAX) + "@nova.dev"))

    @Test
    fun nameBlankAsksForInput() = assertEquals("이름을 입력하세요", itemNameError("   "))

    @Test
    fun nameAtLimitPasses() = assertNull(itemNameError("가".repeat(Contract.ITEM_NAME_MAX)))

    @Test
    fun nameOverLimitTellsLimitAndNow() =
        assertEquals("${Contract.ITEM_NAME_MAX}자 이하로 입력하세요 (지금 ${Contract.ITEM_NAME_MAX + 1}자)",
            itemNameError("가".repeat(Contract.ITEM_NAME_MAX + 1)))

    @Test
    fun serverLimitIsGenerated() = assertEquals(100, Contract.ITEM_NAME_MAX)
}
