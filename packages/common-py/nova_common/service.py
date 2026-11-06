"""서비스 팩토리 — 모든 Nova 마이크로서비스의 공통 골격.

제공: FastAPI 앱 · 수명주기(DB 생성 → 시드 → 버스 시작 → 아웃박스 릴레이) · /healthz /readyz /metrics ·
RED 메트릭 미들웨어 · 오류 규약 {"error":{"code","message"}} · GW가 넣어주는 인증 헤더 → Principal ·
@svc.on(topic) 멱등 소비 데코레이터 · svc.emit() 아웃박스 발행.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import hashlib
import inspect
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import and_, delete, func, or_, select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import clients, context, packs
from . import outbox as _outbox
from . import runtime
from .db import Database, add_infra_tables, utcnow
from .events import Envelope, EventBus, InMemoryBus, make_bus
from .metrics import (
    EVENT_E2E_LAG,
    EVENT_HANDLER_LATENCY,
    EVENTS_CONSUMED,
    HTTP_INFLIGHT,
    HTTP_LATENCY,
    HTTP_REQUESTS,
    OUTBOX_PENDING,
    OUTBOX_QUARANTINED,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")



# 상태 코드 → (오류 코드, 한국어 문구). FastAPI · Starlette 가 직접 내는 오류를 규약 봉투로 바꿀 때 쓴다
_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    400: ("bad_request", "요청 형식이 올바르지 않습니다"),
    401: ("unauthenticated", "로그인이 필요합니다"),
    403: ("forbidden", "권한이 없습니다"),
    404: ("not_found", "요청한 주소를 찾을 수 없습니다"),
    405: ("method_not_allowed", "이 주소에서 허용되지 않는 요청 방식입니다"),
    406: ("not_acceptable", "응답 형식을 맞출 수 없습니다"),
    409: ("conflict", "다른 변경과 충돌했습니다. 새로 고친 뒤 다시 시도하세요"),
    413: ("payload_too_large", "요청이 너무 큽니다"),
    415: ("unsupported_media_type", "지원하지 않는 본문 형식입니다"),
    422: ("invalid_input", "입력값이 올바르지 않습니다"),
    429: ("too_many_requests", "요청이 너무 많습니다. 잠시 뒤 다시 시도하세요"),
}
# pydantic 검증 오류 종류 → 한국어(목록에 없는 종류는 원문 그대로)
_VALIDATION_MSG: dict[str, str] = {
    "missing": "필수 항목입니다",
    "string_too_short": "너무 짧습니다",
    "string_too_long": "너무 깁니다",
    "string_type": "문자열이어야 합니다",
    "int_parsing": "정수여야 합니다",
    "int_type": "정수여야 합니다",
    "float_parsing": "숫자여야 합니다",
    "bool_parsing": "참/거짓 값이어야 합니다",
    "greater_than_equal": "허용 범위보다 작습니다",
    "greater_than": "허용 범위보다 작습니다",
    "less_than_equal": "허용 범위보다 큽니다",
    "less_than": "허용 범위보다 큽니다",
    "enum": "허용된 값이 아닙니다",
    "literal_error": "허용된 값이 아닙니다",
    "json_invalid": "JSON 형식이 잘못되었습니다",
    "extra_forbidden": "허용되지 않는 항목입니다",
    "uuid_parsing": "UUID 형식이 아닙니다",
    "datetime_parsing": "날짜 · 시각 형식이 아닙니다",
    "date_parsing": "날짜 형식이 아닙니다",
}


# 데이터 수명 기본값(R7 · plan_REQ_03 §4). 처리 기록 보관 기간은 토픽 최대 보존일(kafka-topics.txt)보다 길어야 한다 —
# 보존 중인 메시지가 다시 전달될 때 처리 기록이 이미 지워져 있으면 중복 처리된다(test_processed_retention_covers_topic_retention)
OUTBOX_RETENTION_DAYS = 7
PROCESSED_EVENT_RETENTION_DAYS = 14
PURGE_INTERVAL = 3600
# 아웃박스 행을 SKIP LOCKED 로 집을 수 있는 방언(SQLite 는 행 잠금이 없다)
_ROW_LOCK_DIALECTS = frozenset({"mysql", "mariadb", "postgresql"})


class _AlreadyProcessed(Exception):
    """같은 이벤트(또는 같은 중복 제거 키)를 다른 소비자 인스턴스가 먼저 처리 완료 — processed_event 기본키 · UNIQUE(consumer, idempotency_key) 충돌."""

class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra: Any):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


@dataclass
class Principal:
    user_id: str | None
    role: str
    tenant: str | None
    name: str | None = None
    roles: tuple[str, ...] = ()  # GW 가 넣는 유효 역할(기본 역할 + 개인 · 그룹 역할). 비면 (role,)
    actor_type: str = "human"  # human | ai | system (STD-AX-001)

    @property
    def is_ai(self) -> bool:
        return self.actor_type == "ai"

    def require_human(self, what: str = "이 작업") -> "Principal":
        """AI 자동 실행을 허용하지 않는 작업(자동화 등급 L0 · L1 의 쓰기, L2 의 승인) — STD-AX-001"""
        self.require()
        if self.actor_type != "human":
            raise ApiError(403, "human_only", f"{what}은(는) 사람이 직접 해야 합니다(자동화 등급 정책). 초안을 확인한 뒤 직접 실행하세요")
        return self

    @property
    def all_roles(self) -> set[str]:
        return {self.role, *self.roles}

    def require(self, *roles: str) -> "Principal":
        if self.user_id is None:
            raise ApiError(401, "unauthenticated", "로그인이 필요합니다")
        mine = self.all_roles
        if roles and not (mine & set(roles)) and runtime.super_role() not in mine:
            raise ApiError(403, "forbidden", f"권한이 없습니다 (필요: {', '.join(roles)})")
        return self


def principal(request: Request) -> Principal:
    """GW가 JWT를 검증한 뒤 넣어주는 헤더. 서비스는 클러스터 내부(NetworkPolicy)에서만 접근 가능."""
    h = request.headers
    return Principal(
        user_id=h.get("x-user-id") or None,
        role=h.get("x-role") or "guest",
        tenant=h.get("x-tenant") or None,
        name=unquote(h.get("x-user-name") or "") or None,  # GW가 퍼센트 인코딩(헤더는 ASCII)
        roles=tuple(r for r in (h.get("x-roles") or "").split(",") if r),
        actor_type=context.normalize_actor_type(h.get("x-actor-type")),  # 모르는 값은 'ai'(안전한 쪽) — 거짓 human 금지
    )


class Service:
    def __init__(self, name: str, Base, title: str, version: str = "0.1.0", db_url: str | None = None,  # noqa: N803
                 migrations_dir: Path | None = None):
        self.name = name
        self.Base = Base
        # 스키마는 마이그레이션으로(ADR-011). 지정이 없으면 서비스 패키지 옆 migrations/ 를 찾고, 없으면 create_all(게이트웨이)
        self.migrations_dir: Path | None = migrations_dir if migrations_dir is not None else find_migrations(Base)
        self.Outbox, self.ProcessedEvent = add_infra_tables(Base)
        self.db = Database(name, db_url)
        self.bus: EventBus = make_bus(name)
        # 토픽 → 핸들러 목록. 한 서비스의 여러 모듈이 같은 토픽을 구독할 수 있다 — 한 이벤트 = 한 트랜잭션에서 등록 순서대로
        self.handlers: dict[str, list[Callable]] = {}
        self.broadcast_topics: set[str] = set()  # @svc.on(topic, broadcast=True) 로 등록한 토픽(복제본마다 받음)
        self.seeders: list[Callable[[Session], None]] = []
        self.background: list[Callable[[], Any]] = []
        self.relay_interval = float(os.getenv("OUTBOX_RELAY_INTERVAL", "0.2"))
        self.outbox_max_attempts = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "5"))
        # 데이터 수명(R7) — 발행된 아웃박스 행 · 처리 기록 보관 기간(일)과 정리 주기(초, 0 이하면 끔)
        self.outbox_retention_days = float(os.getenv("OUTBOX_RETENTION_DAYS", str(OUTBOX_RETENTION_DAYS)))
        self.processed_retention_days = float(
            os.getenv("PROCESSED_EVENT_RETENTION_DAYS", str(PROCESSED_EVENT_RETENTION_DAYS))
        )
        self.purge_interval = float(os.getenv("NOVA_PURGE_INTERVAL", str(PURGE_INTERVAL)))
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None  # _bind_loop 가 채운다(스레드 → 루프 깨우기)
        self._tasks: list[asyncio.Task] = []
        self.ready = False
        self.started_at = time.time()
        self.app = self._build_app(title, version)

    # ---------------------------------------------------------------- 이벤트
    def emit(self, session: Session, topic: str, key: str, data: dict, idempotency_key: str | None = None) -> Envelope:
        env = _outbox.emit(
            session, self.Outbox, source=self.name, topic=topic, key=key, data=data, idempotency_key=idempotency_key
        )
        self._notify()  # 동기 라우트 · 소비 스레드에서도 불린다
        return env

    def on(self, topic: str, *, broadcast: bool = False):
        """멱등 소비 핸들러 등록. handler(session, env) 는 sync/async 모두 가능.

        같은 토픽에 여러 번 등록하면(모듈별) 모두 실행된다. 하나라도 실패하면 그 이벤트의 모든 변경이 롤백되고 재시도·DLQ.
        같은 함수의 재등록(모듈 재import)은 무시한다.
        broadcast=True — 복제본마다 받는다(그룹 `<service>.<instance>`, Kafka 는 latest 부터). 캐시 무효화처럼 모든 복제본이
        알아야 하는 토픽에 쓴다. 한 토픽은 한 방식만 — 섞으면 등록 때 거부한다(구독은 토픽 단위라 둘을 함께 할 수 없다)."""
        if topic in self.handlers and (topic in self.broadcast_topics) != broadcast:
            raise ValueError(f"토픽 {topic} 은 이미 {'방송' if topic in self.broadcast_topics else '일반'} 구독으로 등록되어 있습니다 — "
                             "한 토픽에 방송 · 일반 구독을 섞을 수 없습니다")
        if broadcast:
            self.broadcast_topics.add(topic)

        def deco(fn: Callable):
            fns = self.handlers.setdefault(topic, [])
            key = (getattr(fn, "__module__", None), getattr(fn, "__qualname__", None))
            if not any(f is fn or (getattr(f, "__module__", None), getattr(f, "__qualname__", None)) == key for f in fns):
                fns.append(fn)
            return fn

        return deco

    def _consumer_name(self, topic: str) -> str:
        """처리 기록(processed_event.consumer)에 쓸 이름 — 방송 토픽은 복제본마다(`<service>.<instance>`).
        DB 를 함께 쓰는 복제본이 서비스 이름 하나로 기록하면 두 번째 복제본이 '중복'으로 건너뛴다.

        HOSTNAME(파드 이름)은 253자까지 될 수 있어 칸 길이(80)를 넘으면 MariaDB 가 'Data too long' 으로 소비를 멈춘다(🆕 T03-9.06).
        넘으면 앞부분을 자르고 전체 이름의 해시 10자를 붙인다 — 결정적이라 재전달 멱등이 유지되고, 앞부분이 같은
        두 인스턴스도 겹치지 않는다. 칸 안이면 그대로 둬 기존 기록과 이어진다. Kafka 그룹 이름은 그대로(칸 제약이 없다)."""
        if topic not in self.broadcast_topics:
            return self.name
        full = self.bus.broadcast_group
        limit = self.ProcessedEvent.__table__.c.consumer.type.length  # 칸 정의에서 읽는다 — 길이를 두 곳에 적지 않게
        if len(full) <= limit:
            return full
        digest = hashlib.sha256(full.encode()).hexdigest()[:10]
        return f"{full[:limit - len(digest) - 1]}~{digest}"

    def _subscribe_all(self) -> None:
        """등록한 핸들러를 버스에 구독한다(startup). 방송 토픽만 broadcast 인자를 넘긴다 — 일반 구독은 예전 호출 모양 그대로."""
        for topic in self.handlers:
            if topic in self.broadcast_topics:
                self.bus.subscribe(topic, self._consume, broadcast=True)
            else:
                self.bus.subscribe(topic, self._consume)

    def _already_processed(self, s: Session, env: Envelope) -> bool:
        """이 소비자가 이미 처리했나 — (consumer, idempotency_key) 로 판정(ADR-012 P1).

        idempotency_key 칸이 빈 옛 행(p0002 이전 기록)은 event_id 로 대체 판정한다. 대체 판정은 Contract(다음 판본 —
        보관 기간이 지나 빈 칸 행이 0 일 때)에서 지운다."""
        pe = self.ProcessedEvent
        hit = s.scalar(
            select(pe.event_id)
            .where(pe.consumer == self._consumer_name(env.type),
                   or_(pe.idempotency_key == env.idempotency_key, pe.event_id == env.id))
            .limit(1)
        )
        return hit is not None

    def _bind_loop(self) -> asyncio.AbstractEventLoop:
        """지금 도는 이벤트 루프를 돌려주고, 기억한 루프(릴레이가 도는 기동 루프)가 없거나 닫혔으면 이것으로 기억한다.
        스레드의 emit 은 기억한 루프의 릴레이를 깨운다 — 테스트의 일회용 루프(asyncio.run)가 기동 루프를 덮어쓰지 않게."""
        loop = asyncio.get_running_loop()
        if self._loop is None or self._loop.is_closed():
            self._loop = loop
        return loop

    def _notify(self) -> None:
        """릴레이를 깨운다. asyncio.Event 는 루프 스레드에서만 set 할 수 있다 — 스레드(소비 · 동기 라우트)에서는 루프로 넘긴다."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop
            if loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(self._wake.set)
                return
        self._wake.set()

    @staticmethod
    def _run_on_loop(loop: asyncio.AbstractEventLoop, aw) -> Any:  # noqa: ANN001
        """스레드에서 돈 핸들러가 awaitable 을 돌려주면(비동기 핸들러) 루프에서 끝까지 돌리고 결과를 기다린다.

        테넌트 · 추적 ID 컨텍스트를 그대로 넘긴다(run_coroutine_threadsafe 는 컨텍스트를 넘기지 않는다)."""
        ctx = contextvars.copy_context()
        done: concurrent.futures.Future = concurrent.futures.Future()

        async def runner():
            return await aw

        def start() -> None:
            task = loop.create_task(runner(), context=ctx)

            def finish(t: asyncio.Task) -> None:
                if t.cancelled():
                    done.cancel()
                elif t.exception() is not None:
                    done.set_exception(t.exception())
                else:
                    done.set_result(t.result())

            task.add_done_callback(finish)

        loop.call_soon_threadsafe(start)
        return done.result()

    @property
    def _db_on_loop(self) -> bool:
        """DB 일을 스레드로 넘기지 않고 루프에서 그대로 할 것인가 — 연결 하나를 모두가 나눠 쓰는 DB(메모리 SQLite · StaticPool)만.

        그 연결을 소비 · 릴레이 스레드와 요청 스레드가 동시에 쓰면 트랜잭션이 섞인다(한쪽 커밋이 다른 쪽 일을 커밋).
        메모리 DB 는 테스트 · 상태 없는 서비스(게이트웨이)뿐이라 루프 막힘보다 정합이 중요하다. 운영(MariaDB 풀) · 파일 SQLite 는 스레드로."""
        return isinstance(self.db.engine.pool, StaticPool)

    async def _db(self, fn: Callable, *args: Any) -> Any:
        """동기 DB 일 fn(*args) — 스레드에서(B3), 공유 연결 DB 는 루프에서 그대로(_db_on_loop)."""
        if self._db_on_loop:
            return fn(*args)
        return await asyncio.to_thread(fn, *args)

    def _record_processed(self, s: Session, env: Envelope) -> None:
        """핸들러 뒤 처리 기록을 남긴다. 핸들러 자신의 제약 위반은 첫 flush 에서(일반 실패 → 재시도 · DLQ),
        processed_event 충돌만 '동시 중복 처리'(_AlreadyProcessed)."""
        s.flush()
        s.add(self.ProcessedEvent(event_id=env.id, consumer=self._consumer_name(env.type), topic=env.type,
                                  idempotency_key=env.idempotency_key))
        try:
            s.flush()
        except IntegrityError as dup:
            raise _AlreadyProcessed from dup

    def _consume_once(self, env: Envelope, fns: list[Callable], loop: asyncio.AbstractEventLoop) -> bool:
        """한 번의 소비 시도(스레드에서 돈다). 반환: 처리했으면 True, 이미 처리한 이벤트면 False.
        동시 중복 처리(processed_event 충돌)는 _AlreadyProcessed, 핸들러 실패는 그 예외 그대로 — 트랜잭션은 롤백된다."""
        # 발행 때의 테넌트 · 행위자 · 추적 ID 로 처리 — 핸들러가 다시 emit · clients.call 해도 같은 추적 ID 가 이어진다
        with context.scope(env.tenant, env.actor_type, trace_id=env.trace_id), self.db.session() as s:
            if self._already_processed(s, env):
                return False
            for fn in fns:
                r = fn(s, env)  # 동기 핸들러 계약 그대로 — handler(session, env)
                if inspect.isawaitable(r):
                    self._run_on_loop(loop, r)
            self._record_processed(s, env)
        return True

    async def _consume_once_on_loop(self, env: Envelope, fns: list[Callable]) -> bool:
        """_consume_once 와 같은 일을 루프에서(공유 연결 DB — _db_on_loop). 비동기 핸들러는 바로 await 한다."""
        with context.scope(env.tenant, env.actor_type, trace_id=env.trace_id), self.db.session() as s:
            if self._already_processed(s, env):
                return False
            for fn in fns:
                r = fn(s, env)
                if inspect.isawaitable(r):
                    await r
            self._record_processed(s, env)
        return True

    async def _consume(self, env: Envelope) -> None:
        fns = self.handlers[env.type]
        started = time.perf_counter()
        try:
            occurred = datetime.fromisoformat(env.occurred_at)
            EVENT_E2E_LAG.labels(self.name, env.type).observe(
                max(0.0, (datetime.now(timezone.utc) - occurred).total_seconds())
            )
        except ValueError:
            pass
        last_err: Exception | None = None
        loop = self._bind_loop()
        for attempt in range(3):
            try:
                # DB 일(중복 판정 · 핸들러 · 처리 기록)은 스레드에서 — 느린 핸들러 · 쿼리가 루프(/healthz · 다른 소비)를 막지 않게(B3)
                done = (await self._consume_once_on_loop(env, fns) if self._db_on_loop
                        else await asyncio.to_thread(self._consume_once, env, fns, loop))
                if not done:
                    EVENTS_CONSUMED.labels(self.name, env.type, "duplicate").inc()
                    return
                EVENTS_CONSUMED.labels(self.name, env.type, "ok").inc()
                EVENT_HANDLER_LATENCY.labels(self.name, env.type).observe(time.perf_counter() - started)
                self._wake.set()
                return
            except _AlreadyProcessed:
                EVENTS_CONSUMED.labels(self.name, env.type, "duplicate").inc()
                return
            except Exception as e:  # 재시도 후 DLQ
                last_err = e
                EVENTS_CONSUMED.labels(self.name, env.type, "retry").inc()
                logging.getLogger(self.name).exception("핸들러 실패 topic=%s attempt=%s", env.type, attempt + 1)
                await asyncio.sleep(0.05 * (2**attempt))
        EVENTS_CONSUMED.labels(self.name, env.type, "dlq").inc()
        send = getattr(self.bus, "send_dlq", None)
        if send:
            await send(env, repr(last_err))
        else:  # DLQ 가 없는 버스 — 조용히 사라지지 않게 폐기 사실을 남긴다(로그 검색으로 재처리)
            logging.getLogger(self.name).error(
                "DLQ 없는 버스라 이벤트를 폐기 topic=%s id=%s key=%s err=%r", env.type, env.id, env.key, last_err
            )

    def _pending_outbox(self, limit: int, dialect_name: str):
        """미발행 · 격리 아닌 행을 오래된 것부터 고르는 문장.

        행 잠금이 있는 DB(MariaDB · MySQL · PostgreSQL)는 `FOR UPDATE SKIP LOCKED` — 복제본 여럿의 릴레이가 같은 행을
        동시에 보내지 않는다(다른 릴레이가 잡은 행은 건너뛰고, 그 트랜잭션이 끝나면 sent_at 이 차 있다 · B2).
        SQLite 는 행 잠금이 없어 그대로(로컬 · 테스트는 복제본 하나)."""
        ob = self.Outbox
        stmt = select(ob).where(ob.sent_at.is_(None), ob.is_parked.is_(False)).order_by(ob.id).limit(limit)
        if dialect_name in _ROW_LOCK_DIALECTS:
            stmt = stmt.with_for_update(skip_locked=True)
        return stmt

    async def flush_outbox(self, limit: int = 200) -> int:
        """미발행 아웃박스를 버스로 보낸다. 반환: 보낸 개수.

        DB 일(행 집기 · 기록 · 커밋)은 스레드에서, 발행은 루프에서(B3). 한 트랜잭션이 발행 내내 이어진다 —
        SKIP LOCKED 로 잡은 행 잠금이 커밋까지 유지되어 다른 복제본의 릴레이가 같은 행을 보내지 않는다(B2).
        세션은 한 번에 한 스레드만 쓴다(조회 → 발행 → 마무리 차례로). 공유 연결 DB 는 루프에서 그대로(_db_on_loop)."""
        self._bind_loop()
        s: Session = self.db.SessionLocal()
        try:
            stmt_dialect = self.db.engine.dialect.name
            rows = await self._db(lambda: s.scalars(self._pending_outbox(limit, stmt_dialect)).all())
            sent = await self._publish_rows(rows)
            await self._db(self._finish_flush, s)
        except Exception:
            await self._db(s.rollback)
            raise
        finally:
            await self._db(s.close)
        return sent

    def _finish_flush(self, s: Session) -> None:
        """릴레이 마무리(스레드) — 지표 갱신 뒤 커밋(sent_at · 시도 수 · 격리 표시가 함께 들어간다)."""
        self._refresh_outbox_gauges(s)
        s.commit()

    async def _publish_rows(self, rows: list) -> int:
        """집은 행을 차례로 발행한다(루프). 행 속성만 바꾸고 DB 에는 닿지 않는다 — 기록은 _finish_flush 가 한다."""
        sent, failed, tried = 0, [], set()

        async def attempt(row) -> bool:
            tried.add(row.id)
            try:
                await self.bus.publish(Envelope.model_validate(row.payload))
                row.sent_at = utcnow()
                return True
            except Exception as e:
                row.last_error = repr(e)[:500]
                failed.append(row)
                return False

        for i, row in enumerate(rows):
            if row.id in tried:  # 탐침으로 이미 보낸 행
                continue
            if await attempt(row):
                sent += 1
                continue
            if sent or len(failed) < 3:
                continue
            # 처음부터 연속 3회 실패 — 브로커 장애인지, 머리의 행 고유 문제(없는 토픽 · 크기 초과)인지 가른다.
            # 판별: 뒤쪽 행 하나를 '탐침'으로 보내 본다. 실패한 행들과 토픽이 다른 첫 행을 우선(토픽 고유 문제를
            # 피함), 없으면 배치의 마지막 행(머리에 몰린 크기 초과 행을 피함). 탐침이 성공하면 브로커는 살아 있으므로
            # 머리 행들의 실패를 행 고유 문제로 보고 시도 수를 늘린다(한계에서 격리 → 뒤 행이 영원히 막히지 않음).
            # 탐침도 실패하면 브로커 장애로 보고 시도 수를 늘리지 않고 다음 주기에 — 장애 동안 정상 행이 격리되지
            # 않는다. 탐침은 한 주기에 한 번(장애 시 발행 시도 최대 4회)이다.
            # 실패 행 뒤에 보낼 행이 없으면 판별할 수 없어 그대로 둔다(막히는 행이 없으니 해가 없고, 새 이벤트가
            # 들어오면 그 행이 탐침이 된다).
            bad_topics = {r.topic for r in failed}
            rest = [r for r in rows[i + 1:] if r.id not in tried]
            probe = next((r for r in rest if r.topic not in bad_topics), rest[-1] if rest else None)
            if probe is None or not await attempt(probe):
                break
            sent += 1
        # 같은 배치에서 다른 행은 나갔는데 이 행만 실패 → 행 고유 문제(없는 토픽·크기 초과 등). 반복되면 격리해 뒤를 막지 않는다
        if sent:
            for row in failed:
                row.attempts += 1
                if row.attempts >= self.outbox_max_attempts:
                    row.is_parked = True
                    logging.getLogger(self.name).error(
                        "아웃박스 행 격리(parked) id=%s topic=%s err=%s", row.id, row.topic, row.last_error
                    )
        return sent

    def _refresh_outbox_gauges(self, s: Session) -> None:
        """발행 대기(격리 제외)와 격리 행 수를 따로 낸다 — 섞이면 격리 행 때문에 OutboxBacklog 경보가 풀리지 않는다."""
        ob = self.Outbox
        rows = s.execute(
            select(ob.is_parked, func.count()).where(ob.sent_at.is_(None)).group_by(ob.is_parked)
        ).all()
        counts = {bool(parked): n for parked, n in rows}
        OUTBOX_PENDING.labels(self.name).set(counts.get(False, 0))
        OUTBOX_QUARANTINED.labels(self.name).set(counts.get(True, 0))

    async def _relay_loop(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.relay_interval * 10)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            try:
                while await self.flush_outbox():
                    pass
            except Exception:  # pragma: no cover
                logging.getLogger(self.name).exception("아웃박스 릴레이 오류")
            await asyncio.sleep(self.relay_interval)

    # ---------------------------------------------------------------- 데이터 수명 · 격리 재처리 (R7 · R8)
    def purge_infra(self, now: datetime | None = None, batch: int = 1000) -> dict[str, int]:
        """보관 기간이 지난 플랫폼 표 행을 batch 개씩 지운다. 반환: {"outbox": n, "processed_event": m}.

        - outbox: 발행된 행(sent_at 있음)만 — sent_at + OUTBOX_RETENTION_DAYS 가 지난 것. 미발행 · 격리 행은 지우지 않는다
        - processed_event: processed_at + PROCESSED_EVENT_RETENTION_DAYS 가 지난 것
        한 번에 다 지우지 않고 batch 개씩 트랜잭션을 나눈다 — 큰 표를 한 문장으로 오래 잠그지 않게."""
        if batch < 1:
            raise ValueError(f"batch 는 1 이상이어야 합니다: {batch}")
        now = now or utcnow()
        ob, pe = self.Outbox, self.ProcessedEvent
        out_cut = now - timedelta(days=self.outbox_retention_days)
        pe_cut = now - timedelta(days=self.processed_retention_days)
        return {
            "outbox": self._delete_in_batches(
                ob, (ob.id,), and_(ob.sent_at.is_not(None), ob.sent_at < out_cut, ob.is_parked.is_(False)), batch
            ),
            "processed_event": self._delete_in_batches(pe, (pe.event_id, pe.consumer), pe.processed_at < pe_cut, batch),
        }

    def parked_rows(self, limit: int = 100) -> list[dict]:
        """격리(parked) 행 목록 — 오래된 것부터. 재처리 전에 원인(last_error)을 보려고 쓴다."""
        ob = self.Outbox
        with self.db.session() as s:
            rows = s.scalars(
                select(ob).where(ob.is_parked.is_(True), ob.sent_at.is_(None)).order_by(ob.id).limit(limit)
            ).all()
            return [
                {"id": r.id, "event_id": r.event_id, "topic": r.topic, "key": r.key, "attempts": r.attempts,
                 "last_error": r.last_error, "created_at": r.created_at.isoformat() if r.created_at else None}
                for r in rows
            ]

    def requeue_parked(self, ids: list[int] | None) -> int:
        """격리 행을 발행 대기로 되돌린다. ids=None 이면 전부, 빈 목록이면 아무것도 하지 않는다(실수로 '전부'가 되지 않게).

        attempts 는 0 으로(다시 OUTBOX_MAX_ATTEMPTS 번 기회), last_error 는 남긴다(원인 추적). 원인이 그대로면 한계에서
        다시 격리된다. 반환: 해제한 행 수. 격리 행이 아닌 id(이미 발행 · 없는 id)는 건너뛴다."""
        if ids is not None and not ids:
            return 0
        ob = self.Outbox
        cond = and_(ob.is_parked.is_(True), ob.sent_at.is_(None))
        if ids is not None:
            cond = and_(cond, ob.id.in_(list(ids)))
        with self.db.session() as s:
            n = s.execute(
                update(ob).where(cond).values(is_parked=False, attempts=0).execution_options(synchronize_session=False)
            ).rowcount or 0
            self._refresh_outbox_gauges(s)
        logging.getLogger(self.name).warning(
            "아웃박스 격리 해제 %s건(%s) — 다음 릴레이 주기에 다시 발행합니다", n, "전부" if ids is None else f"id {sorted(ids)}"
        )
        if n:
            self._notify()
        return n

    async def _purge_loop(self) -> None:
        """기동 직후 한 번, 그 뒤 purge_interval 초마다 정리. 실패는 로그만 남기고 다음 주기에 다시 한다 —
        정리 지연은 저장 공간 문제일 뿐 정합성 문제가 아니라서 서비스를 멈추지 않는다(plan_REQ_03 §6)."""
        log = logging.getLogger(self.name)
        while True:
            try:
                done = await self._db(self.purge_infra)  # 큰 삭제가 루프를 막지 않게(B3)
                if any(done.values()):
                    log.info("보관 기간이 지난 행 정리 outbox=%s processed_event=%s", done["outbox"], done["processed_event"])
            except Exception:
                log.exception("플랫폼 표 정리 실패 — %s초 뒤 다시 시도합니다", self.purge_interval)
            await asyncio.sleep(self.purge_interval)

    def _delete_in_batches(self, model, pk: tuple, cond, batch: int) -> int:  # noqa: ANN001
        """조건에 맞는 행의 기본키를 batch 개 고르고 그 행만 지우기를 반복한다(DB 마다 DELETE … LIMIT 지원이 달라 키로 끊는다)."""
        total = 0
        while True:
            with self.db.session() as s:
                keys = s.execute(select(*pk).where(cond).limit(batch)).all()
                if not keys:
                    return total
                target = pk[0].in_([k[0] for k in keys]) if len(pk) == 1 else tuple_(*pk).in_([tuple(k) for k in keys])
                s.execute(delete(model).where(target).execution_options(synchronize_session=False))
            total += len(keys)
            if len(keys) < batch:
                return total

    # ---------------------------------------------------------------- 수명주기
    def seed(self, fn: Callable[[Session], None]):
        self.seeders.append(fn)
        return fn

    def init_db(self) -> None:
        """스키마를 맞춘 뒤 시드. migrations 폴더가 있으면 플랫폼 + 서비스 분기 heads 까지(옛 create_all DB 는 stamp 뒤),
        없으면 create_all(상태 없는 메모리 DB — 게이트웨이). 마이그레이션이 실패하면 예외 그대로 → 기동 거부."""
        if self.migrations_dir is not None:
            from . import migrate

            migrate.upgrade(self.db, self.Base, self.migrations_dir)
        else:
            self.db.create_all(self.Base)
        for fn in self.seeders:
            with self.db.session() as s:
                fn(s)

    def load_packs(self) -> list[str]:
        """켜진 도메인 팩(NOVA_PACKS)의 이 서비스용 구현을 불러온다(STD-DOMAIN-PACK-001)."""
        try:
            from . import catalog

            pkg = catalog.get(self.name).package
        except Exception:
            pkg = self.name.replace("-", "_")
        done = packs.load(pkg)
        # 포트 선언(@packs.port)은 서비스 모듈을 import 할 때 채워진다. load_packs 는 startup(lifespan)에서 불리므로
        # 이 시점엔 서비스의 라우터 모듈이 모두 import 돼 있다 → 여기서 '선언 안 된 포트를 구현한 팩'(오타)을 잡는다.
        packs.verify(pkg)
        return done

    @property
    def uses_db(self) -> bool:
        """업무 표가 있는 서비스인가. 공통 인프라 표(outbox · processed_event)만 둔 게이트웨이 같은 상태 없는 서비스는 False —
        이들은 메모리 sqlite 가 정상이라 운영 검사 · 준비 확인(DB 점검)에서 뺀다."""
        infra = {self.Outbox.__table__.name, self.ProcessedEvent.__table__.name}
        return any(t not in infra for t in self.Base.metadata.tables)

    async def startup(self, start_relay: bool = True) -> None:
        self._loop = asyncio.get_running_loop()  # 스레드(동기 라우트 · 소비)의 emit 이 이 루프의 릴레이를 깨운다
        # 운영에서 dev 비밀키 · 개발 기능 · sqlite · 메모리 버스면 기동 거부.
        # DB 검사는 '업무 표가 있는' 서비스만 — 게이트웨이처럼 공통 인프라 표(outbox · processed_event)만 두는
        # 상태 없는 서비스는 메모리 sqlite 가 정상이다. 버스 검사는 업무 표(→ emit 가능)나 구독이 있는 서비스만 —
        # 이들이 메모리 버스면 서비스 간 이벤트가 프로세스 밖으로 나가지 못하고 사라진다.
        uses_db = self.uses_db
        uses_bus = uses_db or bool(self.handlers)
        runtime.assert_prod_safe(
            self.name,
            db_url=self.db.url if uses_db else None,
            in_memory_bus=uses_bus and isinstance(self.bus, InMemoryBus),
        )
        self.load_packs()
        self.init_db()
        self._subscribe_all()
        await self.bus.start()
        if start_relay:
            self._tasks.append(asyncio.create_task(self._relay_loop()))
        if self.purge_interval > 0:  # NOVA_PURGE_INTERVAL 0 이하 = 정리 끔(외부 잡으로 돌릴 때)
            self._tasks.append(asyncio.create_task(self._purge_loop()))
        for bg in self.background:
            self._tasks.append(asyncio.create_task(bg()))
        self.ready = True

    async def shutdown(self) -> None:
        self.ready = False
        for t in self._tasks:
            t.cancel()
        await self.bus.stop()

    def _build_app(self, title: str, version: str) -> FastAPI:
        svc = self

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            if os.getenv("NOVA_SKIP_LIFESPAN") != "1":
                await svc.startup()
            yield
            if os.getenv("NOVA_SKIP_LIFESPAN") != "1":
                await svc.shutdown()

        app = FastAPI(title=title, version=version, lifespan=lifespan, root_path=os.getenv("ROOT_PATH", ""))

        @app.middleware("http")
        async def unhandled_error(request: Request, call_next):
            """처리되지 않은 예외 → 500 봉투. 원문(내부 정보 · 비밀이 섞일 수 있음)은 응답에 싣지 않고 로그에만.
            Exception 처리기 대신 미들웨어로 잡는 이유: Starlette 는 Exception 처리기를 부른 뒤 예외를 다시 던져
            서버 로그가 두 번 남는다. 가장 먼저 등록해 가장 안쪽이므로 테넌트 컨텍스트가 살아 있고 RED 메트릭에 500 으로 잡힌다."""
            try:
                return await call_next(request)
            except Exception:
                logging.getLogger(svc.name).exception("처리되지 않은 예외 method=%s path=%s", request.method, request.url.path)
                return JSONResponse(
                    status_code=500,
                    content={"error": {"code": "internal_error",
                                       "message": "서버 오류가 발생했습니다. 잠시 뒤 다시 시도하고, 계속되면 관리자에게 알려 주세요"}},
                )

        @app.middleware("http")
        async def request_context(request: Request, call_next):
            """게이트웨이가 검증해 넣은 테넌트 · 행위자를 요청 동안 컨텍스트에(STD-TENANCY-001 ③).
            추적 ID 는 x-request-id 를 받아(형식 밖 · 없음이면 새로) 심고 응답 헤더로 돌려준다(REQ-261104-11-6) —
            unhandled_error 보다 바깥이라 500 응답에도 붙는다."""
            trace_id = context.trace_from_header(request.headers.get("x-request-id"))
            with context.scope(request.headers.get("x-tenant") or None, request.headers.get("x-actor-type") or "human",
                               trace_id=trace_id):
                response = await call_next(request)
            response.headers["x-request-id"] = trace_id
            return response

        @app.middleware("http")
        async def red_metrics(request: Request, call_next):
            path = request.url.path
            if path in ("/metrics", "/healthz", "/readyz"):
                return await call_next(request)
            HTTP_INFLIGHT.labels(svc.name).inc()
            started = time.perf_counter()
            status = 500
            try:
                response = await call_next(request)
                status = response.status_code
                return response
            finally:
                route = request.scope.get("route")
                tmpl = getattr(route, "path", "unmatched")
                HTTP_INFLIGHT.labels(svc.name).dec()
                HTTP_REQUESTS.labels(svc.name, request.method, tmpl, str(status)).inc()
                HTTP_LATENCY.labels(svc.name, request.method, tmpl).observe(time.perf_counter() - started)

        @app.exception_handler(ApiError)
        async def api_error(_req: Request, exc: ApiError):
            return JSONResponse(
                status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, **exc.extra}}
            )

        @app.exception_handler(clients.UpstreamError)
        async def upstream_error(_req: Request, exc: clients.UpstreamError):
            """서비스 간 호출(clients.call) 오류를 잡지 않은 경우(T07-1.04 · B4).
            상대 4xx 는 같은 상태 · 상대 봉투 그대로(입력 오류 · 없음 · 권한을 사용자가 원래 문구로 본다 — 500 으로 뭉개지 않는다).
            상대 5xx · 연결 실패는 502, 시간 초과는 504 — 상대 내부 문구는 싣지 않고 로그에만."""
            if isinstance(exc, clients.UpstreamTimeout):
                status, code, message = 504, "upstream_timeout", "연결된 서비스의 응답이 늦어지고 있습니다. 잠시 후 다시 시도하세요"
            elif isinstance(exc, clients.UpstreamUnavailable):
                status, code, message = 502, "upstream_unavailable", "연결된 서비스에 닿을 수 없습니다. 잠시 후 다시 시도하세요"
            elif 400 <= exc.status < 500:
                body = exc.body
                if isinstance(body, dict) and isinstance(body.get("error"), dict) \
                        and {"code", "message"} <= set(body["error"]):
                    return JSONResponse(status_code=exc.status, content=body)
                code, message = _HTTP_ERRORS.get(exc.status, ("upstream_rejected", "연결된 서비스가 요청을 거절했습니다"))
                return JSONResponse(status_code=exc.status, content={"error": {"code": code, "message": message}})
            else:
                status, code, message = 502, "upstream_error", "연결된 서비스에서 오류가 났습니다. 잠시 후 다시 시도하세요"
            logging.getLogger(svc.name).warning("서비스 간 호출 실패 → %s service=%s status=%s body=%r",
                                                status, exc.service, exc.status, exc.body)
            return JSONResponse(status_code=status,
                                content={"error": {"code": code, "message": message, "service": exc.service}})

        # 규약: 모든 오류는 봉투 {"error":{"code","message"}} (docs/conventions/backend.md) — FastAPI 기본 {"detail":…} 을 바꾼다
        @app.exception_handler(RequestValidationError)
        async def validation_error(_req: Request, exc: RequestValidationError):
            fields = [
                {"loc": list(e.get("loc", ())), "msg": _VALIDATION_MSG.get(e.get("type", ""), e.get("msg", ""))}
                for e in exc.errors()
            ]
            names = ", ".join(dict.fromkeys(str(f["loc"][-1]) for f in fields if f["loc"]))
            where = f" ({names})" if names else ""
            return JSONResponse(
                status_code=422,
                content={"error": {"code": "invalid_input",
                                   "message": f"입력값이 올바르지 않습니다{where}. 표시된 항목을 고쳐 다시 시도하세요",
                                   "fields": fields}},
            )

        @app.exception_handler(StarletteHTTPException)
        async def http_error(_req: Request, exc: StarletteHTTPException):
            code, message = _HTTP_ERRORS.get(exc.status_code, ("http_error", "요청을 처리할 수 없습니다"))
            try:
                phrase = HTTPStatus(exc.status_code).phrase
            except ValueError:
                phrase = None
            if isinstance(exc.detail, str) and exc.detail and exc.detail != phrase:
                message = exc.detail  # 코드가 직접 넣은 설명은 살린다(표준 영어 문구만 한국어로 바꾼다)
            return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": message}},
                                headers=getattr(exc, "headers", None))

        @app.get("/healthz", include_in_schema=False)
        def healthz():
            if not svc.bus.healthy:  # 소비 루프 사망·정지 → liveness 실패로 재시작
                return JSONResponse(status_code=503, content={"status": "consumer_dead", "service": svc.name})
            return {"status": "ok", "service": svc.name, "version": version, "uptime_s": int(time.time() - svc.started_at)}

        @app.get("/readyz", include_in_schema=False)
        def readyz():
            if not svc.ready and os.getenv("NOVA_SKIP_LIFESPAN") != "1":
                return JSONResponse(status_code=503, content={"status": "starting"})
            # DB 서비스는 DB 에 닿을 때만 준비됨 — 닿지 못하면 트래픽에서만 뺀다(healthz 는 그대로 200 → 재시작 폭주 없음)
            if svc.uses_db and not svc.db.ping():
                return JSONResponse(status_code=503, content={"status": "db_unavailable"})
            return {"status": "ready", "bus": type(svc.bus).__name__}

        @app.get("/metrics", include_in_schema=False)
        def metrics():
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

        return app


def create_service(name: str, Base, title: str, version: str = "0.1.0") -> Service:  # noqa: N803
    return Service(name, Base, title, version)


def find_migrations(Base) -> Path | None:  # noqa: N803
    """서비스 Base 가 든 최상위 패키지 옆의 migrations/ (services/<svc>/<pkg>/models.py → services/<svc>/migrations).

    패키지가 아닌 모듈(테스트 파일 안의 Base)은 찾지 않는다 — 우연히 옆 폴더의 migrations 를 집어 오지 않게."""
    import sys

    top = sys.modules.get(Base.__module__.split(".")[0])
    if top is None or not hasattr(top, "__path__") or not getattr(top, "__file__", None):
        return None
    d = Path(top.__file__).resolve().parent.parent / "migrations"
    return d if (d / "versions").is_dir() else None


__all__ = ["Service", "create_service", "ApiError", "Principal", "principal", "InMemoryBus"]
