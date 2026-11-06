"""식별자 — DB 기본키 · 이벤트 ID 는 UUID version 7 (RFC 9562, ADR-003).

UUIDv7 = 앞 48비트가 유닉스 밀리초 → **생성 순서대로 정렬**된다. 그래서
- B-tree 인덱스 끝에만 붙어 삽입이 빠르고(무작위 v4 의 페이지 분할 · 단편화 없음)
- 문자열(소문자 36자)로 저장해도 사전순 = 시간순이라 정렬 · 페이지 넘김이 그대로 맞다
- 서버 · 클라이언트 · 오프라인 어디서 만들어도 충돌하지 않는다(중앙 시퀀스 불필요)

    from nova_common.ids import new_id, id_column, ref_column, uuid7_time
    class Order(Base):
        id: Mapped[str] = id_column()                 # CHAR(36) PK, 기본값 new_id()
        customer_id: Mapped[str] = ref_column()       # 다른 개체를 가리키는 칸(CHAR(36))
    new_id()                                          # '0192f4a3-7c1e-7a2b-8f00-3c5d...'

구현: RFC 9562 §6.2 방법 1(전용 카운터) — 같은 밀리초 안에서는 12비트 rand_a 를 1씩 올려 **프로세스 안 단조 증가**를
보장하고, 카운터가 넘치면 시각을 1ms 앞당긴다. 나머지 62비트는 암호학적 난수.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import mapped_column

UUID_LEN = 36  # 문자열 표현 길이(하이픈 포함, 소문자)

_lock = threading.Lock()
_last_ms = 0
_counter = 0


def uuid7() -> uuid.UUID:
    """RFC 9562 UUID version 7 — 프로세스 안에서 엄격히 증가한다."""
    global _last_ms, _counter
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms > _last_ms:
            _last_ms = ms
            _counter = int.from_bytes(os.urandom(2), "big") & 0x7FF  # 시작값은 하위 11비트 난수(넘침 여유 확보)
        else:
            _counter += 1
            if _counter > 0xFFF:  # 12비트 넘침 → 다음 밀리초로
                _last_ms += 1
                _counter = 0
        ms, counter = _last_ms, _counter
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | counter << 64 | 0b10 << 62 | rand_b
    return uuid.UUID(int=value)


def new_id() -> str:
    """새 기본키 · 이벤트 ID — UUIDv7 소문자 36자 문자열."""
    return str(uuid7())


def uuid7_time(value: str | uuid.UUID) -> datetime:
    """UUIDv7 에 들어 있는 생성 시각(UTC)."""
    u = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    if u.version != 7:
        raise ValueError(f"UUID version 7 이 아닙니다: {u}")
    return datetime.fromtimestamp((u.int >> 80) / 1000, tz=timezone.utc)


def is_uuid7(value: str) -> bool:
    try:
        u = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return u.version == 7 and u.variant == uuid.RFC_4122 and str(u) == value


def require_uuid7(value: str, *, code: str = "not_found", message: str = "찾는 항목이 없습니다") -> str:
    """경로 ID 형식 검사 — UUIDv7 정규형(소문자 36자)이 아니면 DB 조회 전에 404(REQ-261104-11-7).

    형식이 틀린 ID 는 '없는 것'과 같다 — 500 이나 422 로 내부 형식을 드러내지 않는다.
    대문자 · 하이픈 없는 꼴도 받지 않는다(저장된 값은 소문자 정규형뿐이라 같은 행을 두 이름으로 부르지 않게).
    """
    from .service import ApiError  # 지연 import — service 가 ids 를 쓰므로 순환을 피한다(context.require_tenant 와 같은 방식)

    if not isinstance(value, str) or not is_uuid7(value):
        raise ApiError(404, code, message)
    return value


def id_column(**kw):
    """기본키 칸 — CHAR(36) UUIDv7, 기본값 new_id()."""
    return mapped_column(String(UUID_LEN), primary_key=True, default=new_id, **kw)


def ref_column(*, nullable: bool = False, index: bool = True, **kw):
    """다른 개체를 가리키는 칸(UUIDv7 문자열). 서비스 경계 밖 개체는 FK 를 걸지 않는다(서비스는 자기 DB 만)."""
    return mapped_column(String(UUID_LEN), nullable=nullable, index=index, **kw)
