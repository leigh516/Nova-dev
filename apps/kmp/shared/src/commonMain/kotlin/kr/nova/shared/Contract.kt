/* 생성 파일 — scripts/gen_contract.py (원천: 서비스 OpenAPI(sample) · nova_common/validate.py). 직접 고치지 않는다 — 원천을 고치고 python nova.py gen. */
package kr.nova.shared

/** 서버 계약 — 입력 길이 상한(서버 요청 스키마 그대로) · 이메일 형식. 화면에 숫자를 쓰지 않고 이것을 쓴다. */
object Contract {
    // ItemIn (sample)
    const val ITEM_NAME_MIN = 1
    const val ITEM_NAME_MAX = 100
    const val ITEM_MEMO_MAX = 2000
    // ItemPatch (sample)
    const val ITEM_PATCH_NAME_MIN = 1
    const val ITEM_PATCH_NAME_MAX = 100
    const val ITEM_PATCH_MEMO_MAX = 2000
    /** 이메일 형식 — 서버 Email 타입과 같은 정규식(앞뒤 공백을 뗀 값에 쓴다) */
    const val EMAIL_PATTERN = "^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\\.)+[A-Za-z]{2,}\$"
    const val EMAIL_MAX = 254
}
