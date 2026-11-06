package kr.nova.shared

/**
 * 화면 스택 — 내비게이션 라이브러리 없이 값 하나로(작은 앱의 기본값). 바꾸면 새 스택을 돌려준다(불변 —
 * Compose 상태에 그대로 넣으면 바뀜이 보인다). 시스템 뒤로 가기는 canPop 일 때만 앱이 받는다(T04-7.04).
 */
class BackStack<T> private constructor(val entries: List<T>) {
    constructor(root: T) : this(listOf(root))

    val current: T get() = entries.last()

    /** 첫 화면이 아니면 참 — 거짓이면 뒤로 가기를 시스템에 넘긴다(Android: 앱 닫힘) */
    val canPop: Boolean get() = entries.size > 1

    fun push(screen: T): BackStack<T> = BackStack(entries + screen)

    /** 첫 화면에서는 그대로(빈 스택을 만들지 않는다) */
    fun pop(): BackStack<T> = if (canPop) BackStack(entries.dropLast(1)) else this

    /** 탭 이동 · 로그인/로그아웃 — 스택을 한 화면으로 */
    fun reset(root: T): BackStack<T> = BackStack(listOf(root))

    override fun equals(other: Any?): Boolean = other is BackStack<*> && other.entries == entries
    override fun hashCode(): Int = entries.hashCode()
    override fun toString(): String = "BackStack($entries)"
}
