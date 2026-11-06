/* 생성 파일 — scripts/gen_contract.py (원천: nova_common/validate.py). 직접 고치지 않는다 — 원천을 고치고 python nova.py gen. */
/** 이메일 형식 — 서버 Email 타입과 같은 정규식(앞뒤 공백을 뗀 값에 쓴다). */
export const EMAIL_PATTERN = "^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\\.)+[A-Za-z]{2,}$";
/** 이메일 전체 길이 상한(RFC 5321) */
export const EMAIL_MAX = 254;
