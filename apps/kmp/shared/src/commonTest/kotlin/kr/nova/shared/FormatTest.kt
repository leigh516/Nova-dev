package kr.nova.shared

import kotlinx.datetime.TimeZone
import kotlin.test.Test
import kotlin.test.assertEquals

/** fmtAt — 웹 sdk fmtAt 과 같은 형식 "YYYY-MM-DD HH:mm"(T04-7.01) */
class FormatTest {
    private val seoul = TimeZone.of("Asia/Seoul")

    @Test
    fun utcZuluToSeoul() = assertEquals("2026-11-03 14:05", fmtAt("2026-11-03T05:05:00Z", seoul))

    @Test
    fun noOffsetIsTreatedAsUtc() = assertEquals("2026-11-03 14:05", fmtAt("2026-11-03T05:05:00", seoul))

    @Test
    fun microsecondsWithoutOffset() = assertEquals("2026-11-03 14:05", fmtAt("2026-11-03T05:05:59.123456", seoul))

    @Test
    fun explicitOffsetIsRespected() = assertEquals("2026-11-03 14:05", fmtAt("2026-11-03T05:05:00+00:00", seoul))

    @Test
    fun dayRollsOverInLocalZone() = assertEquals("2026-11-04 08:30", fmtAt("2026-11-03T23:30:00Z", seoul))

    @Test
    fun utcZoneKeepsValue() = assertEquals("2026-01-02 03:04", fmtAt("2026-01-02T03:04:00Z", TimeZone.UTC))

    @Test
    fun emptyOrNullGivesEmpty() {
        assertEquals("", fmtAt(null, seoul))
        assertEquals("", fmtAt("", seoul))
    }

    @Test
    fun unparsableReturnsInput() = assertEquals("어제쯤", fmtAt("어제쯤", seoul))
}
