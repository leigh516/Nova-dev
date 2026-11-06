package kr.nova.shared

/** sample 서비스 API — 업무 API 는 ApiClient 확장 함수로 붙인다(공통 클라이언트를 고치지 않는다). */
suspend fun ApiClient.items(q: String? = null, page: Int = 1, size: Int = 20, sort: String? = null): Page<Item> =
    get("sample/items", mapOf("q" to q, "page" to page, "size" to size, "sort" to sort))

suspend fun ApiClient.item(id: String): Item = get("sample/items/$id")

suspend fun ApiClient.createItem(name: String, memo: String? = null): Item = post("sample/items", ItemIn(name, memo))

suspend fun ApiClient.archiveItem(id: String): Item = post("sample/items/$id/archive")

suspend fun ApiClient.restoreItem(id: String): Item = post("sample/items/$id/restore")

suspend fun ApiClient.deleteItem(id: String) = delete("sample/items/$id")
