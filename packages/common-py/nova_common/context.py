"""요청 컨텍스트 — 테넌트 · 행위자(사람/AI/시스템)를 손으로 나르지 않고 전파한다(STD-TENANCY-001 ③ · STD-AX-001 ②).

전파 경로:  JWT 클레임 → 게이트웨이 검증(x-tenant · x-actor-type 헤더) → 서비스 미들웨어(이 컨텍스트에 심음)
           → clients.call(헤더로 다음 서비스에) · svc.emit(이벤트 봉투 tenant · actor_type) → 소비자(봉투에서 다시 심음)
추적 ID 도 같은 길로 흐른다(REQ-261104-11-6): 헤더 x-request-id → 이 컨텍스트 → 응답 · clients.call 헤더 x-request-id
           → 봉투 trace_id(+ Kafka 헤더 trace_id) → 소비 scope.
클라이언트가 보낸 값은 믿지 않는다 — 게이트웨이가 스푸핑 헤더를 지우고 검증한 값만 넣는다.

    from nova_common.context import current_tenant, tenant_filter, tenant_column, require_tenant
    q = tenant_filter(select(Order), Order)                 # WHERE tenant_id = 현재 테넌트
    tenant_id: Mapped[str | None] = tenant_column()        # 업무 표의 테넌트 칸
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from sqlalchemy import Select, String
from sqlalchemy.orm import mapped_column

from .ids import new_id

_tenant: ContextVar[str | None] = ContextVar("nova_tenant", default=None)
_actor: ContextVar[str] = ContextVar("nova_actor_type", default="human")
_trace: ContextVar[str | None] = ContextVar("nova_trace_id", default=None)
ACTOR_TYPES = ("human", "ai", "system")
# 받아들이는 추적 ID 형식 — 게이트웨이가 예전부터 쓰던 규칙 그대로(헤더 · 로그에 안전한 문자만, 길이 제한)
_TRACE_RE = re.compile(r"[A-Za-z0-9\-]{8,64}")


def current_tenant() -> str | None:
    return _tenant.get()


def current_actor_type() -> str:
    return _actor.get()


def current_trace_id() -> str | None:
    """지금 처리 중인 요청 · 이벤트의 추적 ID(없으면 None — 배치 · 시험 코드)."""
    return _trace.get()


def trace_from_header(value: str | None) -> str:
    """들어온 x-request-id 를 검사해 쓸 추적 ID 를 돌려준다. 형식 밖이면 새 ID(UUIDv7) —
    추적 실패가 요청 실패가 되면 안 되므로 거절하지 않고 바꾼다(계획 §6 '열림')."""
    if value and _TRACE_RE.fullmatch(value):
        return value
    return new_id()


def normalize_actor_type(actor_type: str | None) -> str:
    """행위자 값 정규화 — 비었으면(명시 없음) 'human', 알 수 없는 값은 'ai'.
    알 수 없는 값을 'human' 으로 바꾸면 감사 기록이 거짓 '사람'이 되고 require_human 을 통과할 수 있다(STD-AX-001).
    'ai' 는 가장 제한이 많은 쪽이라(사람 전용 작업 거부 · AI 로 감사) 안전하다."""
    if not actor_type:
        return "human"
    return actor_type if actor_type in ACTOR_TYPES else "ai"


@contextmanager
def scope(tenant: str | None, actor_type: str | None = None, *, trace_id: str | None = None) -> Iterator[None]:
    """이 블록 동안 테넌트 · 행위자 · 추적 ID 를 바꾼다(미들웨어 · 이벤트 소비 · 배치가 쓴다).
    테넌트와 마찬가지로 trace_id 를 주지 않으면 이 블록의 추적 ID 는 없음(None)이다 — 바깥 값이 몰래 새지 않게."""
    t1 = _tenant.set(tenant)
    t2 = _actor.set(normalize_actor_type(actor_type))
    t3 = _trace.set(trace_id)
    try:
        yield
    finally:
        _tenant.reset(t1)
        _actor.reset(t2)
        _trace.reset(t3)


def headers() -> dict[str, str]:
    """서비스 간 호출에 실을 헤더(clients.call 이 자동으로 붙인다)."""
    h = {"x-actor-type": current_actor_type()}
    t = current_tenant()
    if t:
        h["x-tenant"] = t
    tid = current_trace_id()
    if tid:  # 같은 요청의 서비스 간 호출을 한 줄로 따라가게(REQ-261104-11-6)
        h["x-request-id"] = tid
    return h


def require_tenant() -> str:
    """테넌트가 꼭 있어야 하는 곳에서 — 없으면 400(테넌트 필터 없는 쿼리는 보안사고, STD-TENANCY-001)."""
    from .service import ApiError

    t = current_tenant()
    if not t:
        raise ApiError(400, "tenant_required", "소속 조직(테넌트)을 알 수 없어 처리할 수 없습니다. 다시 로그인하세요")
    return t


def tenant_filter(query: Select, model) -> Select:  # noqa: ANN001
    """현재 테넌트의 행만. 테넌트가 없으면(단일 조직 · 비로그인) tenant_id IS NULL 행만 — 다른 조직 행이 새지 않는다."""
    return query.where(model.tenant_id == current_tenant()) if current_tenant() else query.where(model.tenant_id.is_(None))


def tenant_column(*, nullable: bool = True):
    """업무 표의 테넌트 칸 — STD-TENANCY-001 ① (M1 공유 스키마). 단일 조직이면 비워 둬도 된다."""
    return mapped_column(String(40), index=True, nullable=nullable, comment="테넌트(STD-TENANCY-001)")
