"""공유 HTTP 클라이언트(T04-6.05) — 서비스마다 연결 풀을 하나로 재사용하고, 테스트용 override 는 그대로 이긴다."""
import asyncio

import httpx

from nova_common import clients


def _transport(name: str) -> httpx.MockTransport:
    return httpx.MockTransport(lambda req: httpx.Response(200, json={"via": name, "path": req.url.path}))


def test_clients_pooled():
    async def go():
        clients.override("svc-a", _transport("A"))
        try:
            a1, a2 = clients.pooled("svc-a"), clients.pooled("svc-a")
            assert a1 is a2  # 같은 서비스 = 같은 객체(연결 재사용)
            assert clients.pooled("svc-b") is not a1  # 서비스마다 따로
            assert (await a1.get("/x")).json() == {"via": "A", "path": "/x"}  # override 트랜스포트로 간다

            clients.override("svc-a", _transport("A2"))  # override 를 바꾸면 새 트랜스포트를 쓰는 새 객체
            a3 = clients.pooled("svc-a")
            assert a3 is not a1 and (await a3.get("/y")).json()["via"] == "A2"

            await clients.aclose_all()  # 닫으면 모두 닫히고, 다음 호출은 새로 만든다
            assert a3.is_closed
            a4 = clients.pooled("svc-a")
            assert a4 is not a3 and not a4.is_closed
            await clients.aclose_all()
        finally:
            clients.clear_overrides()

    asyncio.run(go())


def test_clients_pooled_not_shared_across_event_loops():
    """다른 이벤트 루프(테스트 클라이언트 요청마다 · 다른 asyncio.run)에서는 묶인 연결을 넘겨 쓰지 않는다."""
    clients.override("svc-a", _transport("A"))
    try:
        async def grab():
            return clients.pooled("svc-a")

        first = asyncio.run(grab())
        second = asyncio.run(grab())
        assert first is not second
        asyncio.run(clients.aclose_all())
    finally:
        clients.clear_overrides()


def test_clients_pooled_follows_base_url(monkeypatch):
    """주소(SVC_<NAME>_URL)가 바뀌면 옛 주소의 클라이언트를 쓰지 않는다."""
    async def go():
        monkeypatch.setenv("SVC_SVC_C_URL", "http://one:8000")
        c1 = clients.pooled("svc-c")
        monkeypatch.setenv("SVC_SVC_C_URL", "http://two:8000")
        c2 = clients.pooled("svc-c")
        assert c1 is not c2 and str(c2.base_url).startswith("http://two:8000")
        await clients.aclose_all()

    asyncio.run(go())


# ---------------------------------------------------------------- T07-1.04 서비스 간 호출 오류 전달 (review_261105_02 B4)
import pytest  # noqa: E402

from nova_common.db import NovaBase  # noqa: E402
from nova_common.service import Service  # noqa: E402


def _caller_app(upstream: httpx.MockTransport):
    """`/proxy` 에서 up-svc 를 clients.call 로 부르는 서비스 — 상대 오류가 호출한 쪽 응답으로 어떻게 나가는지 본다."""

    class Base(NovaBase):
        pass

    svc = Service("caller-svc", Base, "호출 시험", db_url="sqlite://")

    @svc.app.get("/proxy")
    async def proxy():
        return await clients.call("up-svc", "GET", "/thing")

    clients.override("up-svc", upstream)
    return svc.app


def _through(upstream: httpx.MockTransport) -> httpx.Response:
    async def go():
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_caller_app(upstream)), base_url="http://t") as c:
                return await c.get("/proxy")
        finally:
            await clients.aclose_all()
            clients.clear_overrides()

    return asyncio.run(go())


def test_upstream_4xx_envelope_passed_through():
    """상대가 404 봉투를 내면 호출한 서비스도 404 · 같은 봉투(사용자에게 원래 문구 — plan_REQ_07 §11.2)."""
    body = {"error": {"code": "item_not_found", "message": "품목을 찾을 수 없습니다"}}
    r = _through(httpx.MockTransport(lambda req: httpx.Response(404, json=body)))
    assert r.status_code == 404
    assert r.json() == body


def test_upstream_4xx_without_envelope_gets_standard_envelope():
    r = _through(httpx.MockTransport(lambda req: httpx.Response(409, text="conflict")))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict" and r.json()["error"]["message"]


def test_upstream_5xx_is_502():
    r = _through(httpx.MockTransport(lambda req: httpx.Response(500, json={"error": {"code": "internal_error", "message": "x"}})))
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "upstream_error"
    assert r.json()["error"]["service"] == "up-svc"


@pytest.mark.parametrize("exc,status,code", [
    (httpx.ConnectError("연결 거부"), 502, "upstream_unavailable"),
    (httpx.ReadTimeout("늦음"), 504, "upstream_timeout"),
])
def test_upstream_transport_failure(exc, status, code):
    def boom(req):
        raise exc

    r = _through(httpx.MockTransport(boom))
    assert r.status_code == status
    assert r.json()["error"]["code"] == code
    assert r.json()["error"]["service"] == "up-svc"


def test_call_raises_upstream_error_with_status():
    async def go():
        clients.override("up-svc", httpx.MockTransport(lambda req: httpx.Response(403, json={"error": {"code": "forbidden", "message": "권한 없음"}})))
        try:
            with pytest.raises(clients.UpstreamError) as ei:
                await clients.call("up-svc", "GET", "/x")
            return ei.value
        finally:
            await clients.aclose_all()
            clients.clear_overrides()

    err = asyncio.run(go())
    assert err.status == 403 and err.service == "up-svc"


def test_call_uses_pooled_client(monkeypatch):
    """call() 이 호출마다 새 연결을 열지 않고 pooled(service) 의 공유 연결을 쓴다."""
    used = []
    real = clients.pooled

    def spy(service):
        c = real(service)
        used.append(c)
        return c

    monkeypatch.setattr(clients, "pooled", spy)

    async def go():
        clients.override("up-svc", _transport("U"))
        try:
            a = await clients.call("up-svc", "GET", "/one")
            b = await clients.call("up-svc", "GET", "/two")
            assert not used[0].is_closed  # 호출 뒤 닫지 않는다(풀 유지)
            return a, b
        finally:
            await clients.aclose_all()
            clients.clear_overrides()

    a, b = asyncio.run(go())
    assert a == {"via": "U", "path": "/one"} and b["path"] == "/two"
    assert len(used) == 2 and used[0] is used[1]
