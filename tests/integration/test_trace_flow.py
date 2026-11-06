"""추적 ID 한 줄 흐름 통합 테스트(T03-5.06 · REQ-261104-11-6) — 게이트웨이 → 샘플 생성 → 아웃박스 → 브로커 → 소비까지 같은 trace_id.

devstack 하네스(한 프로세스 · InMemory 브로커 · ASGI 연결)를 그대로 쓴다. 다른 통합 파일이 수집 때 build() 를 이미 불렀어도
여기 고정물에서 다시 묶어(버스 · 브로커를 새로) 이 파일만의 브로커로 흐름을 본다.
"""
import asyncio

import httpx
import pytest
from sqlalchemy import select

import devstack
from nova_common import context
from nova_common.ids import is_uuid7

TOPIC = "sample.item.created"


@pytest.fixture(scope="module")
def stack():
    services, broker, gw = devstack.build()
    lp = asyncio.new_event_loop()
    asyncio.set_event_loop(lp)
    for svc in services.values():
        lp.run_until_complete(svc.startup(start_relay=False))
    yield lp, services, broker, gw
    for svc in services.values():
        lp.run_until_complete(svc.shutdown())
    lp.close()


def _req(lp, gw, method, path, headers=None, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gw), base_url="http://gw") as c:
            return await c.request(method, "/v1" + path, headers=headers or {}, **kw)

    return lp.run_until_complete(go())


def _create_and_follow(stack, request_headers):
    lp, services, broker, gw = stack
    r = _req(lp, gw, "POST", "/auth/login", json={"email": "user@nova.dev", "password": "nova1234"})
    assert r.status_code == 200, r.text
    auth = {"authorization": "Bearer " + r.json()["token"]}
    sample = services["sample"]
    seen: list[tuple[str | None, str]] = []

    def capture(_s, env):  # 소비 scope 안에서 컨텍스트가 무엇을 가졌는지 본다(핸들러 목록 끝에 잠시 붙인다)
        seen.append((context.current_trace_id(), env.data.get("id")))

    sample.handlers[TOPIC].append(capture)
    try:
        r = _req(lp, gw, "POST", "/sample/items", headers={**auth, **request_headers}, json={"name": "추적 항목"})
        assert r.status_code == 201, r.text
        item_id, rid = r.json()["id"], r.headers["x-request-id"]
        with sample.db.session() as s:  # 아웃박스 행(릴레이 전)
            row = s.scalars(select(sample.Outbox).where(sample.Outbox.topic == TOPIC, sample.Outbox.key == item_id)).one()
            outbox_trace = row.payload["trace_id"]
        assert lp.run_until_complete(devstack.pump(services, broker)) >= 1
    finally:
        sample.handlers[TOPIC].remove(capture)
    sent = [e for e in broker.log if e.type == TOPIC and e.key == item_id]
    return rid, outbox_trace, [e.trace_id for e in sent], [t for t, i in seen if i == item_id]


def test_trace_id_follows_gateway_to_consumer(stack):
    rid, outbox_trace, sent, consumed = _create_and_follow(stack, {"x-request-id": "req-trace-flow-0001"})
    assert rid == "req-trace-flow-0001"  # 게이트웨이 응답
    assert outbox_trace == rid  # 샘플이 받은 x-request-id → emit 봉투
    assert sent == [rid]  # 브로커로 나간 봉투
    assert consumed == [rid]  # 소비 scope 에서 되살림


def test_trace_id_generated_at_gateway_when_missing(stack):
    rid, outbox_trace, sent, consumed = _create_and_follow(stack, {})
    assert is_uuid7(rid)  # 헤더가 없으면 게이트웨이가 새로 — 그 뒤로는 같은 ID
    assert outbox_trace == rid and sent == [rid] and consumed == [rid]
