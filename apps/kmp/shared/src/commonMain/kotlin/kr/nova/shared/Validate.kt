package kr.nova.shared

// 입력 검사 — 상한 · 형식은 서버 계약(Contract, scripts/gen_contract.py 생성물)에서만 가져온다. 화면에 숫자를 쓰지 않는다(plan_REQ_04 P9)
// 문구는 웹(@nova/sdk emailError · @nova/ui FormFields)과 같게 — 같은 상황은 같은 말(ui.md 규칙 8)

private val EMAIL_RE = Regex(Contract.EMAIL_PATTERN)

/** 이메일 칸 오류 문구 — 맞으면 null. 빈 값은 '필수' 검사가 따로 알리므로 null. 앞뒤 공백은 서버처럼 떼고 본다 */
fun emailError(value: String): String? {
    val s = value.trim()
    if (s.isEmpty()) return null
    return if (s.length <= Contract.EMAIL_MAX && EMAIL_RE.matches(s)) null else "이메일 형식이 아닙니다. 예: name@example.com"
}

/** 새 항목 이름 칸 오류 문구 — 맞으면 null. 공백만은 서버도 거부한다(sample ItemIn) */
fun itemNameError(value: String): String? = when {
    value.isBlank() -> "이름을 입력하세요"
    value.length > Contract.ITEM_NAME_MAX -> "${Contract.ITEM_NAME_MAX}자 이하로 입력하세요 (지금 ${value.length}자)"
    else -> null
}
