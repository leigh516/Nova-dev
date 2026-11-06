"""멱등 소비 — 중복 제거 키(idempotency_key) 기록 · 기본 키 · (소비자, 키) 판정 · 옛 행 대체 판정 · 동시 중복(ADR-012 P1 · REQ-261104-11-8)."""
import asyncio

from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

from nova_common.db import NovaBase
from nova_common.events import Envelope, InMemoryBroker, InMemoryBus
from nova_common.service import Service


def make(name: str):
    class Base(NovaBase):
        pass

    class Note(Base):
        __tablename__ = "note"
        id: Mapped[str] = mapped_column(String(40), primary_key=True)

    svc = Service(name, Base, "t", db_url="sqlite://")
    svc.init_db()
    svc.bus = InMemoryBus(name, InMemoryBroker(), sync=True)
    return svc, Note


def run(c):
    return asyncio.new_event_loop().run_until_complete(c)


def _rows(svc):
    with svc.db.session() as s:
        return s.scalars(select(svc.ProcessedEvent)).all()


def test_processed_event_records_idempotency_key():
    svc, _ = make("t-idem-rec")
    svc.on("t.ping")(lambda s, env: None)
    env = Envelope(type="t.ping", source="x", key="k1", idempotency_key="x:t.ping:k1:업무1")
    run(svc._consume(env))
    [row] = _rows(svc)
    assert row.event_id == env.id and row.idempotency_key == "x:t.ping:k1:업무1"


def test_default_idempotency_key_unique_per_event():
    """키를 명시하지 않으면 {source}:{topic}:{key}:{event_id} — 같은 집계의 두 번째 이벤트가 버려지지 않는다(D2)."""
    svc, _ = make("t-idem-default")
    with svc.db.session() as s:
        a = svc.emit(s, "t.item.updated", "k1", {"n": 1})
        b = svc.emit(s, "t.item.updated", "k1", {"n": 2})
        c = svc.emit(s, "t.item.updated", "k1", {"n": 3}, idempotency_key="업무:1")
    assert a.idempotency_key == f"t-idem-default:t.item.updated:k1:{a.id}"
    assert a.idempotency_key != b.idempotency_key
    assert c.idempotency_key == "업무:1"  # 명시 키는 그대로


def test_same_key_different_event_consumed_once():
    """같은 업무 사건(명시 키 같음)이 다른 이벤트 id 로 두 번 오면 한 번만 처리 · 다른 소비자는 따로 처리."""
    svc, Note = make("t-idem-key")
    calls = []

    @svc.on("t.paid")
    def h(s, env):
        calls.append(env.id)
        s.add(Note(id=env.id))

    first = Envelope(type="t.paid", source="x", key="o1", idempotency_key="x:t.paid:o1:결제1")
    again = Envelope(type="t.paid", source="x", key="o1", idempotency_key="x:t.paid:o1:결제1")
    other = Envelope(type="t.paid", source="x", key="o1", idempotency_key="x:t.paid:o1:결제2")
    assert first.id != again.id
    for env in (first, again, other):
        run(svc._consume(env))
    assert calls == [first.id, other.id]


def test_legacy_row_without_key_still_dedupes():
    """칸이 빈 옛 처리 기록(배포 전 행)은 event_id 로 판정한다 — Contract 전까지의 대체 판정."""
    svc, _ = make("t-idem-legacy")
    calls = []
    svc.on("t.old")(lambda s, env: calls.append(env.id))
    env = Envelope(type="t.old", source="x", key="k", idempotency_key="x:t.old:k")
    with svc.db.session() as s:
        s.add(svc.ProcessedEvent(event_id=env.id, consumer=svc.name, topic=env.type))  # 옛 행 — idempotency_key 없음
    run(svc._consume(env))
    assert calls == []


def test_concurrent_same_key_is_duplicate():
    """처리 도중 다른 인스턴스가 같은 키(다른 이벤트 id)를 먼저 기록 — UNIQUE(consumer, idempotency_key) 충돌은 duplicate(DLQ 아님)."""
    svc, Note = make("t-idem-race")
    calls, dlq = [], []

    async def send_dlq(env, err):
        dlq.append(err)

    svc.bus.send_dlq = send_dlq
    env = Envelope(type="t.once", source="x", key="k", idempotency_key="x:t.once:k:업무")

    @svc.on("t.once")
    def h(s, e):
        calls.append(1)
        s.add(Note(id=e.id))
        if len(calls) == 1:  # 다른 인스턴스가 같은 업무 사건을 다른 이벤트 id 로 먼저 끝낸 상황
            with svc.db.session() as other:
                other.add(svc.ProcessedEvent(event_id="다른-이벤트", consumer=svc.name, topic=e.type, idempotency_key=e.idempotency_key))

    run(svc._consume(env))
    assert calls == [1] and dlq == []
    with svc.db.session() as s:
        assert s.get(Note, env.id) is None  # 중복으로 본 처리의 업무 쓰기는 되돌려진다
        assert [r.event_id for r in s.scalars(select(svc.ProcessedEvent))] == ["다른-이벤트"]
