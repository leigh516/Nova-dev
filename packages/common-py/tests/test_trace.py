"""추적 ID(x-request-id) 전파 — context → 서비스 응답 · clients.call 헤더 → 이벤트 봉투 · Kafka 헤더 → 소비 scope (REQ-261104-11-6)."""
import asyncio

import pytest

from nova_common import context
from nova_common.ids import is_uuid7


def run(c):
    return asyncio.new_event_loop().run_until_complete(c)


# ---------------------------------------------------------------- T03-5.01 context
def test_scope_sets_and_resets_trace_id():
    assert context.current_trace_id() is None
    with context.scope("T-1", "human", trace_id="trace-0001"):
        assert context.current_trace_id() == "trace-0001"
        with context.scope("T-2", trace_id="trace-0002"):  # 안쪽 블록은 자기 값
            assert context.current_trace_id() == "trace-0002"
        assert context.current_trace_id() == "trace-0001"  # 나오면 되돌린다
    assert context.current_trace_id() is None


@pytest.mark.parametrize("bad", [None, "", "short", "x" * 65, "has space 123", "한글추적아이디입니다", "a/b/c/d/e/f"])
def test_trace_from_header_rejects_bad_format(bad):
    tid = context.trace_from_header(bad)
    assert tid != bad and is_uuid7(tid)  # 형식 밖이면 새 ID(UUIDv7) — 추적 실패가 요청 실패가 되지 않게


@pytest.mark.parametrize("good", ["abcd1234", "req-2026-11-04-0001", "A" * 64])
def test_trace_from_header_keeps_valid_value(good):
    assert context.trace_from_header(good) == good


# ---------------------------------------------------------------- T03-5.02 서비스 미들웨어
def _svc(name="t-trace"):
    from sqlalchemy import String
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    from nova_common.events import InMemoryBroker, InMemoryBus
    from nova_common.service import Service

    class Base(DeclarativeBase):
        pass

    class Item(Base):
        __tablename__ = "item"
        id: Mapped[str] = mapped_column(String(40), primary_key=True)

    svc = Service(name, Base, "t", db_url="sqlite://")
    svc.init_db()
    broker = InMemoryBroker()
    svc.bus = InMemoryBus(name, broker, sync=True)

    @svc.app.get("/t/trace")
    def _seen():
        return {"trace": context.current_trace_id()}

    return svc, broker


@pytest.fixture
def trace_client(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("NOVA_SKIP_LIFESPAN", "1")
    svc, _ = _svc()
    return TestClient(svc.app)


def test_request_id_header_roundtrip(trace_client):
    r = trace_client.get("/t/trace", headers={"x-request-id": "req-abc-12345"})
    assert r.status_code == 200
    assert r.json()["trace"] == "req-abc-12345"  # 처리 중 컨텍스트에 심겼다
    assert r.headers["x-request-id"] == "req-abc-12345"  # 응답 헤더로 돌려준다


def test_request_id_missing_or_bad_gets_new_id(trace_client):
    for h in ({}, {"x-request-id": "bad id!"}):
        r = trace_client.get("/t/trace", headers=h)
        tid = r.headers["x-request-id"]
        assert is_uuid7(tid) and r.json()["trace"] == tid  # 응답 헤더 = 처리 중 추적 ID


def test_request_id_on_error_responses(trace_client):
    r = trace_client.get("/t/none", headers={"x-request-id": "req-404-00001"})
    assert r.status_code == 404 and r.headers["x-request-id"] == "req-404-00001"  # 오류 응답도 따라갈 수 있게


# ---------------------------------------------------------------- T03-5.03 clients.call
def test_clients_propagate_request_id():
    import httpx
    from fastapi import FastAPI, Request

    from nova_common import clients

    up = FastAPI()

    @up.get("/echo")
    def echo(request: Request):
        return {"rid": request.headers.get("x-request-id"), "tenant": request.headers.get("x-tenant")}

    clients.override("t-up", httpx.ASGITransport(app=up))
    try:
        async def go():
            with context.scope("T-1", "human", trace_id="trace-call-0001"):
                inside = await clients.call("t-up", "GET", "/echo")
            outside = await clients.call("t-up", "GET", "/echo")  # 추적 ID 가 없으면 헤더도 싣지 않는다
            return inside, outside

        inside, outside = run(go())
    finally:
        clients.clear_overrides()
    assert inside == {"rid": "trace-call-0001", "tenant": "T-1"}
    assert outside["rid"] is None
    assert context.headers() == {"x-actor-type": "human"}  # 컨텍스트 밖 헤더는 그대로


# ---------------------------------------------------------------- T03-5.04 봉투 · 소비 · Kafka 헤더
def test_emit_carries_trace_and_consumer_restores():
    from sqlalchemy import select

    svc, broker = _svc("t-trace-ev")
    seen = []

    @svc.on("t.trace.ev")
    def h(_s, env):
        seen.append((context.current_trace_id(), context.current_tenant()))

    svc.bus.subscribe("t.trace.ev", svc._consume)
    with context.scope("T-9", "human", trace_id="trace-emit-0001"), svc.db.session() as s:
        env = svc.emit(s, "t.trace.ev", "k1", {})
    assert env.trace_id == "trace-emit-0001"
    with svc.db.session() as s:  # 아웃박스 행에도 실린다(릴레이가 이 봉투를 그대로 보낸다)
        assert s.scalars(select(svc.Outbox)).one().payload["trace_id"] == "trace-emit-0001"
    assert context.current_trace_id() is None
    run(svc.flush_outbox())
    assert broker.log[-1].trace_id == "trace-emit-0001"
    assert seen == [("trace-emit-0001", "T-9")]  # 소비 scope 에서 되살렸다


def test_kafka_publish_headers_include_trace():
    from nova_common.events import Envelope, KafkaBus

    sent = []

    class _FakeProducer:
        async def send_and_wait(self, topic, value, key=None, headers=None):
            sent.append((topic, dict(headers or [])))

    bus = KafkaBus("t-kafka", "unused:9092")
    bus.producer = _FakeProducer()
    with_trace = Envelope(type="t.ev", source="x", key="k", idempotency_key="x:k:1", trace_id="trace-kafka-01")
    without = Envelope(type="t.ev", source="x", key="k", idempotency_key="x:k:2")
    run(bus.publish(with_trace))
    run(bus.publish(without))
    assert sent[0][1]["trace_id"] == b"trace-kafka-01"
    assert sent[0][1]["idempotency_key"] == b"x:k:1" and sent[0][1]["source"] == b"x"  # 기존 헤더 유지
    assert "trace_id" not in sent[1][1]  # 없으면 빈 헤더를 싣지 않는다
