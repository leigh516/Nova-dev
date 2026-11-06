"""이메일 공통 검증(T04-4.01) — 서버 · 웹 · 모바일이 같은 규칙을 쓰도록 한 곳에 둔다(plan_REQ_04 P9)."""
import re

import pytest
from pydantic import BaseModel, ValidationError

from nova_common.validate import EMAIL_MAX, EMAIL_PATTERN, Email


class In(BaseModel):
    email: Email


@pytest.mark.parametrize("raw,expected", [
    (" User@Nova.dev ", "user@nova.dev"),  # 검토 초점 11.2 — 앞뒤 공백 · 대문자는 정규화 뒤 통과
    ("a.b+tag@sub.example.co.kr", "a.b+tag@sub.example.co.kr"),
])
def test_email_normalized(raw, expected):
    assert In(email=raw).email == expected


@pytest.mark.parametrize("raw", ["user@", "@nova.dev", "user", "user@nova", "us er@nova.dev", "user@nova..dev", "", "   "])
def test_email_rejects_malformed(raw):
    with pytest.raises(ValidationError):
        In(email=raw)


def test_email_length_cap():
    local = "a" * 64
    domain = ("b" * 60 + ".") * 3 + "kr"  # 64@ + 185 = 250자
    ok = f"{local}@{domain}"
    assert len(ok) <= EMAIL_MAX and In(email=ok).email == ok
    too_long = f"{local}@{'c' * (EMAIL_MAX - 64 - 1 - 3)}x.kr"
    assert len(too_long) == EMAIL_MAX + 1
    with pytest.raises(ValidationError):
        In(email=too_long)


def test_email_pattern_is_portable():
    """JS(RegExp) · Kotlin(Regex) 로 그대로 옮길 수 있는 부분만 — 이름 붙은 그룹 · 뒤보기 · 인라인 플래그 없음."""
    assert EMAIL_PATTERN.startswith("^") and EMAIL_PATTERN.endswith("$")
    for bad in ("(?P<", "(?<", "(?i", "\\A", "\\Z", "(?="):
        assert bad not in EMAIL_PATTERN
    assert re.fullmatch(EMAIL_PATTERN, "user@nova.dev")
