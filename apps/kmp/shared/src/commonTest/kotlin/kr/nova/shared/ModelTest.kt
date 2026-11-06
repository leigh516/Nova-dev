package kr.nova.shared

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** 상세 응답 계약 — 활동 시각 키 recorded_at(T04-2.05) · 상한 표시 activity_truncated(T04-6.04) */
class ModelTest {
    private val base = """"id":"1","name":"가","status":"active","created_at":"2026-11-03T05:05:00Z","updated_at":"2026-11-03T05:05:00Z""""

    @Test
    fun activityUsesRecordedAt() {
        val item = NovaJson.decodeFromString(Item.serializer(),
            """{$base,"activity":[{"kind":"restored","recorded_at":"2026-11-03T05:06:00Z"}],"activity_truncated":true}""")
        assertEquals("2026-11-03T05:06:00Z", item.activity.single().recordedAt)
        assertTrue(item.activityTruncated)
    }

    @Test
    fun truncatedDefaultsToFalse() {
        val item = NovaJson.decodeFromString(Item.serializer(), "{$base}")
        assertFalse(item.activityTruncated)
    }
}
