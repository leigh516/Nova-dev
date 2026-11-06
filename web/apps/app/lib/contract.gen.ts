/* 생성 파일 — scripts/gen_contract.py (원천: 서비스 OpenAPI(sample)). 직접 고치지 않는다 — 원천을 고치고 python nova.py gen. */
/** 입력 길이 상한 — 서버 요청 스키마(pydantic Field min_length · max_length) 그대로. 화면에 숫자를 쓰지 않고 이것을 쓴다. */
export const LIMITS = {
  ItemIn: { name: { minLength: 1, maxLength: 100 }, memo: { maxLength: 2000 } },  // sample
  ItemPatch: { name: { minLength: 1, maxLength: 100 }, memo: { maxLength: 2000 } },  // sample
} as const;
