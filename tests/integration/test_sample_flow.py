"""전체 서비스 한 프로세스 통합 테스트 — 모든 호출은 게이트웨이(/v1)를 통해서만 한다(실제 클라이언트와 같은 경로).

새 서비스를 추가하면 그 서비스의 핵심 시나리오를 여기(또는 같은 폴더 새 파일)에 게이트웨이 경유로 추가한다.
"""
import asyncio

import httpx
import pytest

import devstack

SERVICES, BROKER, GW = devstack.build()


@pytest.fixture(scope="module")
def loop():
    lp = asyncio.new_event_loop()
    asyncio.set_event_loop(lp)
    for svc in SERVICES.values():
        lp.run_until_complete(svc.startup(start_relay=False))
    yield lp
    for svc in SERVICES.values():
        lp.run_until_complete(svc.shutdown())
    lp.close()


class Api:
    def __init__(self, token=None):
        self.h = {"authorization": f"Bearer {token}"} if token else {}

    async def __call__(self, method, path, **kw):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=GW), base_url="http://gw") as c:
            return await c.request(method, "/v1" + path, headers=self.h, **kw)


def call(loop, api, method, path, **kw):
    return loop.run_until_complete(api(method, path, **kw))


def login(loop, email):
    r = call(loop, Api(), "POST", "/auth/login", json={"email": email, "password": "nova1234"})
    assert r.status_code == 200, r.text
    return Api(r.json()["token"])


def settle(loop):
    return loop.run_until_complete(devstack.pump(SERVICES, BROKER))


def test_login_create_event_consumed(loop):
    user = login(loop, "user@nova.dev")
    r = call(loop, user, "POST", "/sample/items", json={"name": "통합 항목"})
    assert r.status_code == 201, r.text
    item = r.json()
    assert r.headers["x-upstream"] == "sample"
    delivered = settle(loop)
    assert delivered >= 1
    d = call(loop, user, "GET", f"/sample/items/{item['id']}").json()
    assert [a["kind"] for a in d["activity"]] == ["created"]  # 아웃박스 → 브로커 → 멱등 소비


def test_permissions_through_gateway(loop):
    user, manager = login(loop, "user@nova.dev"), login(loop, "manager@nova.dev")
    item = call(loop, user, "POST", "/sample/items", json={"name": "지울 항목"}).json()
    r = call(loop, user, "DELETE", f"/sample/items/{item['id']}")
    assert r.status_code == 403 and r.json()["error"]["perm"] == "sample.delete"
    assert call(loop, manager, "DELETE", f"/sample/items/{item['id']}").status_code == 204
    assert call(loop, Api(), "POST", "/sample/items", json={"name": "x"}).status_code == 401


def test_tenant_comes_from_token_only(loop):
    user = login(loop, "user@nova.dev")
    user.h["x-tenant"] = "T-OTHER"  # 스푸핑 시도 — 게이트웨이가 지운다
    item = call(loop, user, "POST", "/sample/items", json={"name": "테넌트 확인"}).json()
    page = call(loop, login(loop, "admin@nova.dev"), "GET", "/sample/items", params={"q": "테넌트 확인"}).json()
    assert any(i["id"] == item["id"] for i in page["items"])  # 같은 T-DEMO 테넌트


def test_archive_emits_and_menu(loop):
    user = login(loop, "user@nova.dev")
    item = call(loop, user, "POST", "/sample/items", json={"name": "보관"}).json()
    assert call(loop, user, "POST", f"/sample/items/{item['id']}/archive").json()["status"] == "archived"
    settle(loop)
    kinds = [a["kind"] for a in call(loop, user, "GET", f"/sample/items/{item['id']}").json()["activity"]]
    assert kinds == ["created", "archived"]
    keys = {i["key"] for i in call(loop, user, "GET", "/menu").json()["items"]}
    assert "items" in keys and "ops" not in keys


def test_restore_and_delete_flow(loop):
    """REQ-261104-12-6 — 보관 풀기는 restored 활동을 남기고, 삭제는 활동을 지운 뒤 deleted 를 낸다(늦은 이벤트도 활동을 되살리지 않음)."""
    from sqlalchemy import func, select

    from sample.models import ItemActivity

    user, manager = login(loop, "user@nova.dev"), login(loop, "manager@nova.dev")
    item = call(loop, user, "POST", "/sample/items", json={"name": "풀고 지울 항목"}).json()
    call(loop, user, "POST", f"/sample/items/{item['id']}/archive")
    assert call(loop, user, "POST", f"/sample/items/{item['id']}/restore").json()["status"] == "active"
    settle(loop)
    d = call(loop, user, "GET", f"/sample/items/{item['id']}").json()
    assert [a["kind"] for a in d["activity"]] == ["created", "archived", "restored"]
    assert d["activity_truncated"] is False and all("recorded_at" in a for a in d["activity"])

    call(loop, user, "POST", f"/sample/items/{item['id']}/archive")  # 이 이벤트는 삭제보다 늦게 소비된다
    assert call(loop, manager, "DELETE", f"/sample/items/{item['id']}").status_code == 204
    settle(loop)
    sample = SERVICES["sample"]
    with sample.db.session() as s:
        left = s.scalar(select(func.count()).select_from(ItemActivity).where(ItemActivity.item_id == item["id"]))
        topics = [o.topic for o in s.scalars(select(sample.Outbox).where(sample.Outbox.key == item["id"]))]
    assert left == 0
    assert topics.count("sample.item.deleted") == 1 and topics.count("sample.item.restored") == 1
