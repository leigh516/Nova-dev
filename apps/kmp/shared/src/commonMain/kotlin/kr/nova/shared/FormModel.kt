package kr.nova.shared

/**
 * 폼 칸 정의 — 웹 @nova/ui FormField 와 같은 이름 · 같은 검사 문구(ui.md 규칙 8 · 9). 모바일 FormScreen 이 그린다(T07-3.03).
 * 지금은 문자열 칸만 — 선택 · 스위치 · 날짜는 웹 T07-3.01 이 정한 모양을 따라 다음에 넣는다.
 * 상한은 화면에 숫자를 쓰지 않고 Contract.<스키마>_<칸>_MAX 를 넘긴다(ui.md 규칙 14).
 */
data class FormField(
    val key: String,
    val label: String,
    val required: Boolean = false,
    val maxLength: Int? = null,
    val password: Boolean = false,
    val help: String? = null,
    val validate: ((String) -> String?)? = null,
)

/** 한 칸의 오류 문구 — 맞으면 null. 순서: 필수 → 상한 → 칸 검사(웹 useFormModel check 와 같다) */
fun fieldError(f: FormField, value: String): String? {
    if (f.required && value.isBlank()) return "${f.label}을(를) 입력하세요"
    val max = f.maxLength
    if (max != null && value.length > max) return "${max}자 이하로 입력하세요 (지금 ${value.length}자)"
    return f.validate?.invoke(value)
}

/** 오류가 있는 칸만 칸 순서대로 — 첫 오류 칸을 고를 때도 쓴다 */
fun formErrors(fields: List<FormField>, values: Map<String, String>): Map<String, String> =
    buildMap { fields.forEach { f -> fieldError(f, values[f.key] ?: "")?.let { put(f.key, it) } } }

/** 처음 값 — 칸마다 채우고 없으면 빈 문자열. 폼에 없는 키는 버린다 */
fun initialValues(fields: List<FormField>, initial: Map<String, String>): Map<String, String> =
    fields.associate { it.key to (initial[it.key] ?: "") }
