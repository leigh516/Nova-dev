package kr.nova.shared

/**
 * 화면 상태 3종 + 내용 — 모바일 템플릿(ListScreen · DetailScreen)이 이 판정 하나로 무엇을 그릴지 고른다(ui.md 규칙 5 · T07-3.03).
 * Compose 와 무관한 판정이라 shared 에 두어 kmp-test 가 검사한다.
 */
enum class ViewPhase { Loading, Error, Empty, Content }

/**
 * 판정 순서 — 받은 데이터가 있으면 빈/내용, 없으면 오류가 있을 때 오류, 그 밖은 로딩.
 * - 다시 불러오는 중 · 다시 불러오다 실패해도 이전 데이터를 보인다(load() 가 데이터를 남긴다 — 실패 알림은 스낵바가 맡는다)
 * - 처음(데이터 · 오류 없음)은 로딩 — 첫 화면에 '항목 없음'이 번쩍이지 않게
 * @param accept 이 화면이 받을 데이터인가(상세: 앞서 본 다른 항목이 남아 있으면 없는 것으로 본다)
 * @param isEmpty 빈 상태로 볼 데이터인가(목록: 항목 0건)
 */
fun <T> Loadable<T>.phase(accept: (T) -> Boolean = { true }, isEmpty: (T) -> Boolean = { false }): ViewPhase {
    val d = data?.takeIf(accept)
    return when {
        d != null -> if (isEmpty(d)) ViewPhase.Empty else ViewPhase.Content
        error != null -> ViewPhase.Error
        else -> ViewPhase.Loading
    }
}
