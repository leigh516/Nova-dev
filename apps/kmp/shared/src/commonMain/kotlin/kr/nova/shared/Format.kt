package kr.nova.shared

import kotlinx.datetime.Instant
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toInstant
import kotlinx.datetime.toLocalDateTime

/* 표시 형식(UX H2 — 사용자 지역 기준). 웹 @nova/sdk fmtAt 과 규칙 쌍 — 한쪽을 바꾸면 다른 쪽도 바꾼다 */

private val OFFSET = Regex("""(?:[zZ]|[+-]\d\d:\d\d)$""")

/**
 * 서버 시각(UTC ISO) → 지역 시각 "2026-11-03 14:05".
 * - 끝에 Z · 오프셋이 없으면 UTC 로 본다(서버가 오프셋 없이 내보내는 경우)
 * - 비었으면 "", 해석할 수 없으면 받은 글자 그대로(화면이 깨지지 않게 — 웹과 같다)
 * - tz 기본값은 기기 시간대. 프로젝트 시간대 주입은 R10(REQ-261104-11) 뒤로 미뤘다 — 그래서 인자를 열어 둔다
 */
fun fmtAt(iso: String?, tz: TimeZone = TimeZone.currentSystemDefault()): String {
    if (iso.isNullOrEmpty()) return ""
    val instant = try {
        if (OFFSET.containsMatchIn(iso)) Instant.parse(iso) else LocalDateTime.parse(iso).toInstant(TimeZone.UTC)
    } catch (e: IllegalArgumentException) {
        // 해석 실패는 오류가 아니라 표시 대체 — 원문을 보여 준다(kotlinx-datetime 의 DateTimeFormatException 은 이 하위형)
        return iso
    }
    val t = instant.toLocalDateTime(tz)
    return "${t.year}-${p2(t.monthNumber)}-${p2(t.dayOfMonth)} ${p2(t.hour)}:${p2(t.minute)}"
}

private fun p2(n: Int) = n.toString().padStart(2, '0')
