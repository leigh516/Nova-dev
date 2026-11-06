"""트랜잭셔널 아웃박스 + 멱등 소비.

발행: 비즈니스 변경과 같은 DB 트랜잭션에 outbox 행을 쓰고(emit), 릴레이가 Kafka로 보낸 뒤 sent_at을 기록한다.
     → DB 커밋과 이벤트 발행의 원자성 보장(이중 쓰기 문제 제거).
소비: processed_event(consumer, idempotency_key) 를 핸들러와 같은 트랜잭션에 기록 → 재전달돼도 한 번만 반영(ADR-012 P1).
     기본 idempotency_key 는 `{source}:{topic}:{key}:{event_id}`(이벤트마다 다르다 — 같은 집계의 다음 이벤트를 버리지 않는다).
     같은 업무 사건의 재발행을 한 번만 처리하려면 emit(..., idempotency_key=<업무 키>) 로 명시한다.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import context
from .events import Envelope
from .ids import new_id


def emit(
    session: Session,
    outbox_model,
    *,
    source: str,
    topic: str,
    key: str,
    data: dict[str, Any],
    idempotency_key: str | None = None,
) -> Envelope:
    event_id = new_id()  # 기본 중복 제거 키에 넣으려고 봉투보다 먼저 만든다
    env = Envelope(
        id=event_id,
        type=topic,
        source=source,
        key=key,
        idempotency_key=idempotency_key or f"{source}:{topic}:{key}:{event_id}",
        trace_id=context.current_trace_id(),  # 요청 → 이벤트 → 소비를 한 추적 ID 로(REQ-261104-11-6)
        tenant=context.current_tenant(),
        actor_type=context.current_actor_type(),
        data=data,
    )
    session.add(outbox_model(event_id=env.id, topic=topic, key=key, payload=env.model_dump()))
    return env
