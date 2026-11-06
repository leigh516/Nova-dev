"""입력 공통 검증 — 서버 · 웹 · 모바일이 같은 규칙을 쓰도록 한 곳에 둔다(plan_REQ_04 P9 · T04-4.01).

EMAIL_PATTERN 은 계약 생성기(gen_contract)가 그대로 TS · Kotlin 으로 옮긴다. 그래서 JS RegExp · Kotlin Regex ·
Python re · pydantic(Rust regex) 모두에서 같은 뜻인 문법만 쓴다 — 이름 붙은 그룹 · 앞/뒤보기 · 인라인 플래그 금지.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

EMAIL_MAX = 254  # RFC 5321 경로 상한(전체 주소)
# 로컬부 + @ + 점으로 나뉜 도메인(라벨은 영숫자로 시작 · 끝, 마지막 라벨 2자 이상). 대문자는 화면 쪽 원문 검사를 위해 허용한다
EMAIL_PATTERN = (
    r"^[A-Za-z0-9._%+-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,}$"
)

# 앞뒤 공백 제거 · 소문자 → 그다음 길이 · 형식 검사(pydantic 문자열 검사기는 정규화를 먼저 한다)
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=EMAIL_MAX, pattern=EMAIL_PATTERN),
]

__all__ = ["EMAIL_MAX", "EMAIL_PATTERN", "Email"]
