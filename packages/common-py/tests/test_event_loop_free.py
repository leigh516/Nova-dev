"""동기 DB 일이 이벤트 루프를 막지 않음(T07-1.03 · review_261105_02 B3).

소비 · 릴레이 · 정리의 DB 부분은 `asyncio.to_thread` 로 돈다 — 느린 동기 핸들러 · 느린 쿼리가 도는 동안에도
같은 루프의 `/healthz` 가 바로 답한다(막히면 liveness 실패로 재시작 폭주). 서비스의 동기 핸들러 계약(handler(session, env))은 그대로.
세션마다 연결이 따로인 DB(파일 SQLite · 운영 MariaDB)에서 본다 — 연결 하나를 나눠 쓰는 메모리 SQLite 는 루프에서 그대로(마지막 테스트).
"""
from __future__ import annotations

import asyncio
import time

import httpx
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from nova_common import context
from nova_common.db import NovaBase
from nova_common.events import Envelope
from nova_common.service import Service

SLOW = 1.5  # 막히면 /healthz 가 이만큼 늦는다
FAST = 0.75  # 막히지 않으면 이 안에 답한다 — 첫 요청 준비 비용(실측 약 0.3초)과 느린 PC 여유를 SLOW 의 절반까지 둔다


def _svc(name: str, tmp_path=None) -> tuple[Service, type]:
    """서비스마다 Base 를 새로(outbox 표가 한 MetaData 에 두 번 붙지 않게). tmp_path 가 있으면 파일 SQLite. 반환: (서비스, 업무 표 모델)."""

    class Base(NovaBase):
        pass

    class Note(Base):
        __tablename__ = "loop_note"
        id: Mapped[str] = mapped_column(String(40), primary_key=True, comment="ID")

    url = f"sqlite:///{(tmp_path / (name + '.db')).as_posix()}" if tmp_path is not None else "sqlite://"
    s = Service(name, Base, "루프 시험", db_url=url)
    s.db.create_all(Base)
    return s, Note


async def _healthz_latency(svc: Service, slow_job) -> tuple[float, object]:
    """slow_job 을 띄워 두고 /healthz 를 한 번 부른다. 반환: (느린 일을 띄운 뒤 응답까지 걸린 초, slow_job 결과).

    시각은 느린 일을 띄우기 **전**부터 잰다 — 루프가 막히면 아래 sleep(0.05) 부터 SLOW 만큼 늦게 깨어나므로 그것도 잡힌다."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=svc.app), base_url="http://t") as c:
        started = time.perf_counter()
        job = asyncio.create_task(slow_job)
        await asyncio.sleep(0.05)  # 느린 일이 시작되게
        r = await c.get("/healthz")
        took = time.perf_counter() - started
    assert r.status_code == 200
    return took, await job


def test_slow_sync_handler_does_not_block_healthz(tmp_path):
    svc, Note = _svc("loop-consume", tmp_path)
    seen = {}

    @svc.on("t.loop.slow")
    def slow(s, env):  # 동기 핸들러 — 계약 그대로(session, env)
        time.sleep(SLOW)
        s.add(Note(id=env.id))
        seen["tenant"] = context.current_tenant()

    env = Envelope(type="t.loop.slow", source="x", key="k", idempotency_key="x:k:1", tenant="t-1")
    took, _ = asyncio.run(_healthz_latency(svc, svc._consume(env)))
    assert took < FAST, f"/healthz 가 {took:.2f}초 막혔습니다"
    assert seen["tenant"] == "t-1"  # 스레드로 넘겨도 발행 때 테넌트로 처리
    with svc.db.session() as s:
        assert s.get(Note, env.id) is not None  # 핸들러 변경이 커밋됐다


def test_handler_emit_from_thread_wakes_relay(tmp_path):
    """스레드에서 돈 핸들러가 emit 해도 릴레이를 깨운다(asyncio.Event 는 루프 스레드에서만 set)."""
    svc, _ = _svc("loop-emit", tmp_path)

    @svc.on("t.loop.emit")
    def h(s, env):
        svc.emit(s, "t.loop.out", "k", {"from": env.id})

    async def go():
        svc._wake.clear()
        await svc._consume(Envelope(type="t.loop.emit", source="x", key="k", idempotency_key="x:k:2"))
        await asyncio.sleep(0)  # call_soon_threadsafe 로 넘긴 set 이 돌게
        return svc._wake.is_set()

    assert asyncio.run(go()) is True


def test_slow_relay_query_does_not_block_healthz(monkeypatch, tmp_path):
    svc, _ = _svc("loop-relay", tmp_path)
    real = svc._pending_outbox

    def slow_query(limit, dialect_name):
        time.sleep(SLOW)
        return real(limit, dialect_name)

    monkeypatch.setattr(svc, "_pending_outbox", slow_query)
    took, sent = asyncio.run(_healthz_latency(svc, svc.flush_outbox()))
    assert took < FAST, f"/healthz 가 {took:.2f}초 막혔습니다"
    assert sent == 0


def test_slow_purge_does_not_block_healthz(monkeypatch, tmp_path):
    svc, _ = _svc("loop-purge", tmp_path)
    svc.purge_interval = 3600

    def slow_purge(*_a, **_k):
        time.sleep(SLOW)
        return {"outbox": 0, "processed_event": 0}

    monkeypatch.setattr(svc, "purge_infra", slow_purge)

    async def one_round():
        t = asyncio.create_task(svc._purge_loop())
        await asyncio.sleep(SLOW + 0.3)
        t.cancel()

    took, _ = asyncio.run(_healthz_latency(svc, one_round()))
    assert took < FAST, f"/healthz 가 {took:.2f}초 막혔습니다"


def test_async_handler_still_runs_on_loop_with_context(tmp_path):
    """비동기 핸들러(async def)도 계약 그대로 — 루프에서 돌고, 테넌트 컨텍스트 · 같은 세션을 쓴다."""
    svc, Note = _svc("loop-async", tmp_path)
    seen = {}

    @svc.on("t.loop.async")
    async def h(s, env):
        await asyncio.sleep(0)
        seen["tenant"] = context.current_tenant()
        seen["on_loop"] = asyncio.get_running_loop() is svc._loop
        s.add(Note(id=env.id))

    env = Envelope(type="t.loop.async", source="x", key="k", idempotency_key="x:k:3", tenant="t-9")
    asyncio.run(svc._consume(env))
    assert seen == {"tenant": "t-9", "on_loop": True}
    with svc.db.session() as s:
        assert s.get(Note, env.id) is not None


def test_shared_connection_db_stays_on_loop(tmp_path, monkeypatch):
    """메모리 SQLite(StaticPool — 연결 하나를 모두가 나눠 씀)는 스레드로 넘기지 않는다 — 요청 스레드와 같은 연결을
    동시에 써 트랜잭션이 섞이는 것을 막는다(sample 테스트 간헐 실패로 실측). 파일 SQLite 는 스레드로."""
    mem, _ = _svc("loop-mem")
    filed, _ = _svc("loop-file", tmp_path)
    assert mem._db_on_loop is True and filed._db_on_loop is False

    threads = []
    real = asyncio.to_thread

    async def spy(fn, *a, **k):
        threads.append(fn)
        return await real(fn, *a, **k)

    monkeypatch.setattr(asyncio, "to_thread", spy)
    for s in (mem, filed):
        @s.on("t.loop.mem")
        def h(_s, _env):
            pass

    asyncio.run(mem._consume(Envelope(type="t.loop.mem", source="x", key="k", idempotency_key="x:k:4")))
    asyncio.run(mem.flush_outbox())
    assert threads == []
    asyncio.run(filed._consume(Envelope(type="t.loop.mem", source="x", key="k", idempotency_key="x:k:5")))
    assert threads  # 파일 DB 는 스레드로 넘긴다
