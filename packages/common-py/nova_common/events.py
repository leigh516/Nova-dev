"""이벤트 봉투 + 이벤트 버스.

토픽 규칙: `<svc>.<entity>.<verb>` (예: sample.item.created). 파티션 키 = 집계 ID(예: 항목 ID)라
같은 집계의 이벤트는 순서가 보장된다. 소비는 at-least-once + 멱등키(processed_event)로 정확히-한번 효과.

- KafkaBus    : aiokafka. 컨슈머 그룹 = 서비스명, 수동 커밋(핸들러 성공 후), 실패 3회 → `<topic>.dlq`.
- InMemoryBus : 단위/통합 테스트용. 여러 서비스 인스턴스가 하나의 브로커 객체를 공유한다.

방송 구독(subscribe(..., broadcast=True) · @svc.on(topic, broadcast=True), REQ-261104-11-4): 일반 토픽은 그룹(서비스)당
한 번이지만, 방송 토픽은 그룹이 `<service>.<instance>` 라 복제본마다 받는다(권한 · 플래그 캐시 무효화처럼 모든 복제본이 알아야 할 일).
인스턴스 = 버스 하나. Kafka 는 KAFKA_INSTANCE_ID → HOSTNAME(파드 이름) → 임의 값 순으로 정한다.
"""
from __future__ import annotations

import asyncio
import time
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

from .ids import new_id
from .metrics import CONSUMER_LAG, EVENTS_PUBLISHED

log = logging.getLogger("nova.events")

Handler = Callable[["Envelope"], Awaitable[None]]


class Envelope(BaseModel):
    """모든 이벤트 공통 봉투 (packages/common-py/events/envelope.avsc 와 동일 필드)."""

    id: str = Field(default_factory=new_id)  # UUIDv7 (ADR-003)
    type: str  # = topic
    source: str  # 발행 서비스
    key: str  # 파티션 키(집계 ID)
    idempotency_key: str  # 소비 측 중복 제거 키 — 기본 {source}:{topic}:{key}:{event_id}, 업무 키는 emit 에 명시(ADR-012)
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1
    trace_id: str | None = None
    tenant: str | None = None  # 발행 시점 테넌트(STD-TENANCY-001 ④ — 이벤트에도 네임스페이스)
    actor_type: str = "human"  # human | ai | system — 감사 분리(STD-AX-001 ②)
    data: dict[str, Any] = Field(default_factory=dict)

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Envelope":
        return cls.model_validate(json.loads(raw))


def instance_id() -> str:
    """이 프로세스(복제본)의 인스턴스 이름 — 방송 그룹 접미사. KAFKA_INSTANCE_ID → HOSTNAME → 임의 값.
    임의 값이면 재시작마다 새 그룹이 생긴다(빈 그룹은 Kafka 가 offsets.retention 뒤 지운다 — 계획 §11.5)."""
    return os.getenv("KAFKA_INSTANCE_ID") or os.getenv("HOSTNAME") or new_id()[-12:]


class EventBus:
    """서비스가 쓰는 최소 인터페이스."""

    service: str = "unknown"
    instance: str = "default"  # 방송 그룹 · 방송 처리 기록의 접미사(복제본 구분)
    healthy: bool = True  # 소비 루프가 살아 있는지(/healthz 가 본다)

    @property
    def broadcast_group(self) -> str:
        """방송 토픽의 소비자 그룹 — 복제본마다 다르다."""
        return f"{self.service}.{self.instance}"

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def publish(self, env: Envelope) -> None:
        raise NotImplementedError

    def subscribe(self, topic: str, handler: Handler, *, broadcast: bool = False) -> None:
        raise NotImplementedError


class InMemoryBroker:
    """테스트용 공유 브로커: 토픽 → [(group, handler)]. 같은 그룹은 한 번만 받는다."""

    def __init__(self) -> None:
        self.subs: dict[str, dict[str, Handler]] = defaultdict(dict)
        self.log: list[Envelope] = []
        self.dlq: list[tuple[Envelope, str]] = []  # (봉투, 사유) — Kafka 의 `<topic>.dlq` 에 해당
        self.pending: list[asyncio.Task] = []

    async def deliver(self, env: Envelope) -> None:
        self.log.append(env)
        for _group, handler in list(self.subs.get(env.type, {}).items()):
            await handler(env)

    async def drain(self, rounds: int = 50) -> None:
        """테스트에서 사가가 끝날 때까지 대기."""
        for _ in range(rounds):
            if not self.pending:
                await asyncio.sleep(0)
                if not self.pending:
                    return
            tasks, self.pending = self.pending, []
            await asyncio.gather(*tasks)


class InMemoryBus(EventBus):
    def __init__(self, service: str, broker: InMemoryBroker | None = None, sync: bool = False, instance: str | None = None):
        self.service = service
        self.broker = broker or InMemoryBroker()
        self.sync = sync
        # 버스 객체 하나 = 복제본 하나. 테스트에서 같은 서비스 버스 두 개를 한 브로커에 붙이면 복제본 둘이 된다
        self.instance = instance or new_id()[-12:]

    async def publish(self, env: Envelope) -> None:
        EVENTS_PUBLISHED.labels(self.service, env.type).inc()
        if self.sync:
            await self.broker.deliver(env)
        else:
            self.broker.pending.append(asyncio.ensure_future(self.broker.deliver(env)))

    def subscribe(self, topic: str, handler: Handler, *, broadcast: bool = False) -> None:
        # 그룹 = 브로커 subs 의 키. 일반은 서비스 이름(복제본끼리 덮어써 한 번만), 방송은 복제본마다 따로
        self.broker.subs[topic][self.broadcast_group if broadcast else self.service] = handler

    async def send_dlq(self, env: Envelope, reason: str) -> None:
        """개발 · 테스트에서도 재시도 끝에 실패한 이벤트를 버리지 않고 브로커의 dlq 목록에 남긴다."""
        self.broker.dlq.append((env, reason))
        log.error("DLQ 로 보냄 service=%s topic=%s id=%s reason=%s", self.service, env.type, env.id, reason)


class KafkaBus(EventBus):
    """소비자 두 개 — 일반(그룹 = 서비스, earliest) · 방송(그룹 = `<service>.<instance>`, latest). 둘 다 같은 소비 루프 ·
    lag 게이지 · 건강 판정을 쓴다. 어느 쪽 루프든 죽으면 healthy 거짓(→ /healthz 503 → 재시작)."""

    def __init__(self, service: str, bootstrap: str, instance: str | None = None):
        self.service = service
        self.bootstrap = bootstrap
        self.instance = instance or instance_id()
        self.handlers: dict[str, Handler] = {}
        self.broadcast_handlers: dict[str, Handler] = {}
        self.producer = None
        self.consumer = None
        self.broadcast_consumer = None
        self._loop_task: asyncio.Task | None = None
        self._broadcast_task: asyncio.Task | None = None
        self.retry_backoff = 1.0  # 배치 실패 후 재시도 간격(초, 최대 30)
        self._beat = time.monotonic()
        self._broadcast_beat = time.monotonic()
        self._lag_task: asyncio.Task | None = None

    async def start(self) -> None:
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap,
            acks="all",
            enable_idempotence=True,
            linger_ms=5,  # 작은 배치로 처리량↑·CPU↓
            compression_type="lz4" if _has_lz4() else None,
            client_id=f"{self.service}-producer",
        )
        await self.producer.start()
        if self.handlers:
            self.consumer = AIOKafkaConsumer(
                *self.handlers.keys(),
                bootstrap_servers=self.bootstrap,
                group_id=self.service,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
                client_id=f"{self.service}-consumer",
                max_poll_records=100,
            )
            await self.consumer.start()
            self._loop_task = asyncio.create_task(self._loop())
        if self.broadcast_handlers:
            # latest — 새 복제본은 기동 때 원천(권한 · 플래그 표)을 처음부터 받으므로 지난 방송을 다시 읽을 필요가 없다(계획 §2)
            self.broadcast_consumer = AIOKafkaConsumer(
                *self.broadcast_handlers.keys(),
                bootstrap_servers=self.bootstrap,
                group_id=self.broadcast_group,
                enable_auto_commit=False,
                auto_offset_reset="latest",
                client_id=f"{self.service}-{self.instance}-broadcast",
                max_poll_records=100,
            )
            await self.broadcast_consumer.start()
            self._broadcast_task = asyncio.create_task(
                self._loop(self.broadcast_consumer, self.broadcast_handlers, broadcast=True)
            )
        if self.consumer or self.broadcast_consumer:
            self._lag_task = asyncio.create_task(self._lag_loop())
        log.info("Kafka 버스 시작 service=%s instance=%s topics=%s broadcast=%s",
                 self.service, self.instance, list(self.handlers), list(self.broadcast_handlers))

    async def stop(self) -> None:
        for t in (self._loop_task, self._broadcast_task, self._lag_task):
            if t:
                t.cancel()
        for c in (self.consumer, self.broadcast_consumer):
            if c:
                await c.stop()
        if self.producer:
            await self.producer.stop()

    async def publish(self, env: Envelope) -> None:
        assert self.producer is not None, "버스가 시작되지 않았습니다"
        headers = [("idempotency_key", env.idempotency_key.encode()), ("source", env.source.encode())]
        if env.trace_id:  # 봉투를 풀지 않는 도구(kcat · UI)에서도 추적 ID 로 메시지를 찾게(REQ-261104-11-6)
            headers.append(("trace_id", env.trace_id.encode()))
        await self.producer.send_and_wait(env.type, env.to_bytes(), key=env.key.encode(), headers=headers)
        EVENTS_PUBLISHED.labels(self.service, env.type).inc()

    def subscribe(self, topic: str, handler: Handler, *, broadcast: bool = False) -> None:
        (self.broadcast_handlers if broadcast else self.handlers)[topic] = handler

    @property
    def healthy(self) -> bool:  # type: ignore[override]
        """어느 소비 루프든 태스크가 죽었거나 2분 넘게 폴링이 없으면 비정상 → /healthz 503 → 파드 재시작."""
        return _loop_alive(self._loop_task, self._beat) and _loop_alive(self._broadcast_task, self._broadcast_beat)

    async def _loop(self, consumer=None, handlers: dict[str, Handler] | None = None, *, broadcast: bool = False) -> None:  # noqa: ANN001
        """한 배치 처리 → 커밋. 어느 단계든 실패하면 커밋 지점으로 되감아 다시 처리(멱등 소비가 중복 흡수). 루프는 죽지 않는다.
        인자를 주지 않으면 일반 소비자(self.consumer · self.handlers)."""
        consumer = consumer or self.consumer
        handlers = self.handlers if handlers is None else handlers
        assert consumer is not None
        failures = 0
        while True:
            if broadcast:
                self._broadcast_beat = time.monotonic()
            else:
                self._beat = time.monotonic()
            try:
                batches = await consumer.getmany(timeout_ms=500)
                for tp, msgs in batches.items():
                    for msg in msgs:
                        try:
                            env = Envelope.from_bytes(msg.value)
                        except Exception:  # 손상 메시지는 DLQ로
                            await self._dlq(tp.topic, msg.value, "봉투 해석 실패")
                            continue
                        await handlers[tp.topic](env)
                if batches:
                    await consumer.commit()
                failures = 0
            except asyncio.CancelledError:
                raise
            except Exception:
                failures += 1
                log.exception("소비 배치 실패(연속 %s회, 방송=%s) — 커밋 지점으로 되감아 다시 처리", failures, broadcast)
                try:
                    await consumer.seek_to_committed()
                except Exception:  # pragma: no cover - 되감기 실패도 다음 주기에 재시도
                    log.exception("커밋 지점 되감기(seek_to_committed) 실패")
                await asyncio.sleep(min(30.0, self.retry_backoff * (2 ** min(failures - 1, 5))))

    async def _dlq(self, topic: str, raw: bytes, reason: str) -> None:
        if self.producer:
            await self.producer.send_and_wait(f"{topic}.dlq", raw, headers=[("reason", reason.encode())])

    async def send_dlq(self, env: Envelope, reason: str) -> None:
        await self._dlq(env.type, env.to_bytes(), reason)

    async def _lag_loop(self) -> None:
        """컨슈머 lag을 Prometheus 게이지로 노출 (Grafana Kafka 대시보드·알림 RB-13)."""
        while True:
            await asyncio.sleep(15)
            for consumer in (self.consumer, self.broadcast_consumer):  # 방송 토픽은 이름이 달라 게이지 칸이 겹치지 않는다
                if consumer is None:
                    continue
                try:
                    parts = consumer.assignment()
                    ends = await consumer.end_offsets(list(parts))
                    for tp in parts:
                        pos = await consumer.position(tp)
                        CONSUMER_LAG.labels(self.service, tp.topic, str(tp.partition)).set(max(0, ends[tp] - pos))
                except Exception as e:  # pragma: no cover
                    log.debug("컨슈머 lag 확인 실패: %s", e)


def _loop_alive(task: asyncio.Task | None, beat: float) -> bool:
    """소비 루프 하나의 건강 — 시작 안 함(None)은 정상, 끝났거나 2분 넘게 폴링이 없으면 비정상."""
    if task is None:
        return True
    if task.done():
        return False
    return time.monotonic() - beat < 120


def _has_lz4() -> bool:
    try:
        import lz4  # noqa: F401

        return True
    except ImportError:
        return False


def make_bus(service: str) -> EventBus:
    """KAFKA_BOOTSTRAP 이 있으면 Kafka, 없으면 단일 프로세스 InMemory(개발용)."""
    bootstrap = os.getenv("KAFKA_BOOTSTRAP")
    if bootstrap:
        return KafkaBus(service, bootstrap)
    log.warning("KAFKA_BOOTSTRAP 미설정 — InMemoryBus 사용(서비스 간 이벤트 전달 없음)")
    return InMemoryBus(service)
