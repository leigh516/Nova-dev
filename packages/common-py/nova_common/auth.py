"""최소 HS256 JWT. 운영에서 OIDC(RS256)로 교체할 수 있게 함수 경계(encode · decode)만 고정한다.

비밀키 · 발급자는 호출할 때마다 환경에서 읽는다(테스트 · 재설정 반영):
  JWT_SECRET  비밀키 (운영은 runtime.assert_prod_safe 가 기본값 · 32자 미만을 거부)
  JWT_ISSUER  발급자 (기본 "nova")
"""
import base64
import hashlib
import hmac
import json
import os
import time

from . import runtime


def issuer() -> str:
    return os.getenv("JWT_ISSUER", "nova")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def encode(claims: dict, ttl_seconds: int = 60 * 60 * 24 * 7, secret: str | None = None) -> str:
    now = int(time.time())
    # 예약 클레임(iss · iat · exp)은 호출자가 덮어쓸 수 없다 — 만료 없는 토큰 · 남의 발급자 위조 방지
    payload = {**claims, "iss": issuer(), "iat": now, "exp": now + ttl_seconds}
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps(payload, ensure_ascii=False).encode())
    sig = hmac.new((secret or runtime.jwt_secret()).encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(sig)}"


class InvalidToken(Exception):
    """토큰 거부. 사유 문구는 한국어(로그 · 오류 응답에 그대로 쓸 수 있다)."""


def decode(token: str, secret: str | None = None) -> dict:
    try:
        header, body, sig = token.split(".")
    except ValueError as e:
        raise InvalidToken("형식이 잘못된 토큰") from e
    expected = hmac.new((secret or runtime.jwt_secret()).encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    try:
        ok = hmac.compare_digest(expected, _unb64(sig))
        payload = json.loads(_unb64(body)) if ok else None
    except (ValueError, TypeError) as e:  # binascii.Error 는 ValueError 의 하위
        raise InvalidToken("형식이 잘못된 토큰") from e
    if not ok:
        raise InvalidToken("서명이 맞지 않음")
    if not isinstance(payload, dict):
        raise InvalidToken("형식이 잘못된 토큰")
    exp = payload.get("exp", 0)
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        raise InvalidToken("형식이 잘못된 토큰")
    if exp < time.time():
        raise InvalidToken("만료됨")
    if "iss" in payload and payload["iss"] != issuer():
        raise InvalidToken("발급자가 다름")
    return payload
