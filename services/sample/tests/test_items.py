"""sample — CRUD · 테넌트 격리 · 아웃박스 발행 · 멱등 소비 · 목록 계약."""
import asyncio
import functools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nova_common import Envelope, new_id
from nova_common.ids import is_uuid7
from sample.main import app, svc
from sample.models import ItemActivity

H = {"x-user-id": "U-1", "x-role": "user", "x-tenant": "T-1"}
H2 = {"x-user-id": "U-2", "x-role": "user", "x-tenant": "T-2"}


@pytest.fixture(scope="module")
def client():
    """배경 DB 루프(릴레이 · 정리) 없이 기동한다 — test_no_background_loop_shares_memory_db 의 이유.
    라우트는 작업 스레드에서 돌지만 테스트 스레드는 응답을 기다리므로, 루프가 DB 를 안 쓰면 한 번에 한 스레드만 연결을 쓴다."""
    interval = svc.purge_interval
    svc.startup = functools.partial(type(svc).startup, svc, start_relay=False)  # lifespan 이 부르는 기동
    svc.purge_interval = 0
    try:
        with TestClient(app) as c:
            yield c
    finally:
        del svc.startup  # 클래스 메서드로 되돌린다
        svc.purge_interval = interval


def test_no_background_loop_shares_memory_db(client):
    """메모리 DB(StaticPool)는 sqlite 연결 하나를 모든 스레드가 나눠 쓴다. 테스트 스레드가 직접 쓰는 동안(add_activity · consume)
    루프 스레드의 릴레이 · 정리가 같은 연결에서 COMMIT 하면 sqlite3 가 'commit returned NULL'(SystemError)로 깨지거나
    트랜잭션이 섞인다(ISS-261105-01 과 같은 뿌리). 그래서 이 묶음은 배경 DB 루프 없이 돈다 — 발행 · 소비는 직접 부른다."""
    assert svc.purge_interval <= 0
    assert [t for t in svc._tasks if not t.done()] == []


def topics() -> list[str]:
    with svc.db.session() as s:
        return [o.topic for o in s.scalars(select(svc.Outbox)).all()]


def test_create_list_get(client):
    r = client.post("/sample/items", json={"name": "첫 항목"}, headers=H)
    assert r.status_code == 201
    item = r.json()
    assert is_uuid7(item["id"]) and item["status"] == "active"  # 기본키 = UUIDv7
    assert "sample.item.created" in topics()
    page = client.get("/sample/items", headers=H).json()
    assert page["total"] >= 1 and page["page"] == 1 and page["size"] == 20
    assert client.get(f"/sample/items/{item['id']}", headers=H).json()["name"] == "첫 항목"


def test_validation_and_auth(client):
    assert client.post("/sample/items", json={"name": ""}, headers=H).status_code == 422
    r = client.post("/sample/items", json={"name": "x"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_tenant_isolation(client):
    item = client.post("/sample/items", json={"name": "T1 전용"}, headers=H).json()
    r = client.get(f"/sample/items/{item['id']}", headers=H2)
    assert r.status_code == 404 and r.json()["error"]["code"] == "item_not_found"
    assert all(i["name"] != "T1 전용" for i in client.get("/sample/items", headers=H2).json()["items"])


def test_archive_restore_and_conflict(client):
    item = client.post("/sample/items", json={"name": "보관할 것"}, headers=H).json()
    assert client.post(f"/sample/items/{item['id']}/archive", headers=H).json()["status"] == "archived"
    r = client.patch(f"/sample/items/{item['id']}", json={"name": "y"}, headers=H)
    assert r.status_code == 409 and "보관" in r.json()["error"]["message"]
    assert client.post(f"/sample/items/{item['id']}/restore", headers=H).json()["status"] == "active"
    assert client.patch(f"/sample/items/{item['id']}", json={"name": "y"}, headers=H).json()["name"] == "y"


def test_sort_whitelist(client):
    assert client.get("/sample/items?sort=-name", headers=H).status_code == 200
    assert client.get("/sample/items?sort=tenant_id", headers=H).json()["error"]["code"] == "invalid_sort"


def test_status_filter_whitelist(client):
    """T03-9.03 — 모르는 status 는 정렬과 같은 규칙: 400 + 같은 오류 봉투(빈 목록으로 숨기지 않는다). 허용 값은 모델 원천."""
    from sample.models import ITEM_STATUSES

    iid = client.post("/sample/items", json={"name": "상태 필터"}, headers=H).json()["id"]
    client.post(f"/sample/items/{iid}/archive", headers=H)
    for st in ITEM_STATUSES:
        r = client.get(f"/sample/items?status={st}", headers=H)
        assert r.status_code == 200 and all(i["status"] == st for i in r.json()["items"]), (st, r.text)
    assert iid in [i["id"] for i in client.get("/sample/items?status=archived&size=100", headers=H).json()["items"]]
    assert client.get("/sample/items?status=", headers=H).status_code == 200  # 빈 값 = 필터 없음(화면이 비운 채 보낼 때)
    for bad in ("deleted", "ARCHIVED", "active "):
        r = client.get("/sample/items", params={"status": bad}, headers=H)
        assert r.status_code == 400, (bad, r.text)
        err = r.json()["error"]
        assert err["code"] == "invalid_status" and bad.strip() in err["message"], err
        assert err["allowed"] == sorted(ITEM_STATUSES)


def test_consumer_is_idempotent(client):
    # 실제 항목이어야 한다 — 없는 항목의 이벤트는 건너뛴다(test_late_event_after_delete_is_skipped). 릴레이가 낸 행과 섞이지 않게 event_id 로 센다
    key = client.post("/sample/items", json={"name": "멱등 확인"}, headers=H).json()["id"]
    env = Envelope(type="sample.item.created", source="sample", key=key, tenant="T-1", idempotency_key="k-x", data={})
    asyncio.run(svc._consume(env))
    asyncio.run(svc._consume(env))  # 재전달
    with svc.db.session() as s:
        rows = s.scalars(select(ItemActivity).where(ItemActivity.event_id == env.id)).all()
    assert len(rows) == 1 and rows[0].kind == "created"


def test_example_pack_changes_rule(client, monkeypatch):
    """도메인 팩(STD-DOMAIN-PACK-001): 코어는 그대로, 팩을 켜면 규칙이 바뀐다."""
    from nova_common import packs

    assert client.post("/sample/items", json={"name": "  가   나  "}, headers=H).json()["name"] == "가   나"  # 코어: 앞뒤만
    monkeypatch.setenv("NOVA_PACKS", "example")
    packs.reset()
    try:
        assert svc.load_packs() == ["example"]
        assert client.post("/sample/items", json={"name": "  가   나  "}, headers=H).json()["name"] == "가 나"  # 팩: 공백 접기
    finally:
        packs.reset()


# ------------------------------------------------------------------ 심층 감사 회귀 테스트
def outbox_count(topic: str, key: str) -> int:
    with svc.db.session() as s:
        return len(s.scalars(select(svc.Outbox).where(svc.Outbox.topic == topic, svc.Outbox.key == key)).all())


def test_blank_name_rejected_on_create_and_update(client):
    for blank in ("   ", "\t \n"):
        r = client.post("/sample/items", json={"name": blank}, headers=H)
        assert r.status_code == 422, r.text  # 공백만 → 정규화하면 빈 이름
    item = client.post("/sample/items", json={"name": "원래 이름"}, headers=H).json()
    assert client.patch(f"/sample/items/{item['id']}", json={"name": "   "}, headers=H).status_code == 422
    assert client.get(f"/sample/items/{item['id']}", headers=H).json()["name"] == "원래 이름"


def test_search_escapes_like_wildcards(client):
    Q = {**H, "x-tenant": "T-SEARCH"}
    for n in ("가나다", "라마바", "50%할인", "a_b"):
        client.post("/sample/items", json={"name": n}, headers=Q)
    assert [i["name"] for i in client.get("/sample/items?q=%25", headers=Q).json()["items"]] == ["50%할인"]
    assert [i["name"] for i in client.get("/sample/items?q=_", headers=Q).json()["items"]] == ["a_b"]
    assert client.get("/sample/items?q=%25%25", headers=Q).json()["total"] == 0


def test_archive_twice_emits_once_and_restore_active_is_noop(client):
    item = client.post("/sample/items", json={"name": "두 번 보관"}, headers=H).json()
    first = client.post(f"/sample/items/{item['id']}/archive", headers=H).json()
    second = client.post(f"/sample/items/{item['id']}/archive", headers=H)
    assert second.status_code == 200 and second.json()["status"] == "archived"
    assert second.json()["updated_at"] == first["updated_at"]  # 같은 상태로의 전이 = 바꾸지 않는다
    assert outbox_count("sample.item.archived", item["id"]) == 1
    restored = client.post(f"/sample/items/{item['id']}/restore", headers=H).json()
    again = client.post(f"/sample/items/{item['id']}/restore", headers=H).json()
    assert again["status"] == "active" and again["updated_at"] == restored["updated_at"]


def test_ai_actor_cannot_hard_delete(client):
    """STD-AX-001 — 되돌릴 수 없는 영구 삭제는 사람만(AI 는 403 human_only)."""
    item = client.post("/sample/items", json={"name": "AI 삭제 시도"}, headers=H).json()
    r = client.delete(f"/sample/items/{item['id']}", headers={**H, "x-actor-type": "ai"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "human_only"
    assert client.get(f"/sample/items/{item['id']}", headers=H).status_code == 200
    assert client.delete(f"/sample/items/{item['id']}", headers={**H, "x-actor-type": "human"}).status_code == 204
    assert client.get(f"/sample/items/{item['id']}", headers=H).status_code == 404


def test_other_tenant_cannot_modify(client):
    item = client.post("/sample/items", json={"name": "T1 원본", "memo": "메모"}, headers=H).json()
    iid = item["id"]
    for method, url, kw in (("PATCH", f"/sample/items/{iid}", {"json": {"name": "탈취"}}),
                            ("POST", f"/sample/items/{iid}/archive", {}),
                            ("POST", f"/sample/items/{iid}/restore", {}),
                            ("DELETE", f"/sample/items/{iid}", {})):
        r = client.request(method, url, headers=H2, **kw)
        assert r.status_code == 404 and r.json()["error"]["code"] == "item_not_found", (method, url)
    now = client.get(f"/sample/items/{iid}", headers=H).json()
    assert (now["name"], now["memo"], now["status"], now["updated_at"]) == ("T1 원본", "메모", "active", item["updated_at"])
    assert outbox_count("sample.item.archived", iid) == 0


def test_non_uuid7_path_is_404(client, monkeypatch):
    """경로 ID 가 UUIDv7 정규형이 아니면 DB 조회 전에 404 item_not_found(REQ-261104-11-7, 500 아님).

    SQLite 는 대소문자를 가려 어차피 못 찾지만, MariaDB 의 대소문자 무시 정렬에서는 대문자 ID 가 같은 행을 찾는다 —
    그래서 결과만이 아니라 '조회가 일어나지 않았다'를 단언한다.
    """
    import uuid

    from sqlalchemy.orm import Session

    item = client.post("/sample/items", json={"name": "형식 검사"}, headers=H).json()
    iid = item["id"]
    looked: list = []
    real_get = Session.get
    monkeypatch.setattr(Session, "get", lambda self, model, ident, *a, **k: looked.append(ident) or real_get(self, model, ident, *a, **k))
    for bad in ("abc", iid.upper(), iid.replace("-", ""), str(uuid.uuid4())):
        for method, url, kw in (("GET", f"/sample/items/{bad}", {}),
                                ("PATCH", f"/sample/items/{bad}", {"json": {"name": "바꿈"}}),
                                ("POST", f"/sample/items/{bad}/archive", {}),
                                ("POST", f"/sample/items/{bad}/restore", {}),
                                ("DELETE", f"/sample/items/{bad}", {})):
            r = client.request(method, url, headers=H, **kw)
            assert r.status_code == 404 and r.json()["error"]["code"] == "item_not_found", (method, bad)
    assert looked == [], "형식이 틀린 ID 로 DB 를 조회했다"
    assert client.get(f"/sample/items/{iid}", headers=H).status_code == 200


def test_ai_actor_write_rejected(client):
    """STD-AX-001 L1 — AI 는 초안까지, 저장은 사람(ADR-012 P4). 생성 · 수정 · 보관 · 보관 해제 모두 403 human_only."""
    AI = {**H, "x-actor-type": "ai"}
    item = client.post("/sample/items", json={"name": "사람이 만든 것"}, headers=H).json()
    iid = item["id"]
    archived = client.post("/sample/items", json={"name": "보관된 것"}, headers=H).json()["id"]
    assert client.post(f"/sample/items/{archived}/archive", headers=H).status_code == 200
    before = len(topics())
    for method, url, kw in (("POST", "/sample/items", {"json": {"name": "AI 가 만든 것"}}),
                            ("PATCH", f"/sample/items/{iid}", {"json": {"name": "AI 수정"}}),
                            ("POST", f"/sample/items/{iid}/archive", {}),
                            ("POST", f"/sample/items/{archived}/restore", {})):
        r = client.request(method, url, headers=AI, **kw)
        assert r.status_code == 403 and r.json()["error"]["code"] == "human_only", (method, url)
    assert len(topics()) == before  # 거부된 쓰기는 이벤트도 남기지 않는다
    assert client.get(f"/sample/items/{iid}", headers=H).json()["name"] == "사람이 만든 것"
    assert client.get(f"/sample/items/{archived}", headers=H).json()["status"] == "archived"
    # 사람은 그대로 통과(명시 human · 헤더 없음 둘 다)
    HUMAN = {**H, "x-actor-type": "human"}
    assert client.patch(f"/sample/items/{iid}", json={"name": "사람 수정"}, headers=HUMAN).status_code == 200
    assert client.post(f"/sample/items/{iid}/archive", headers=H).status_code == 200
    assert client.post(f"/sample/items/{iid}/restore", headers=HUMAN).status_code == 200
    assert client.post("/sample/items", json={"name": "사람 생성"}, headers=HUMAN).status_code == 201


# ------------------------------------------------------------------ REQ-261104-12 P2 — 활동 표 정정(UUIDv7 · 테넌트 · recorded_at)
# 이 묶음은 릴레이 없이 돈다(client 고정구) — 소비는 svc._consume 를 직접 부르고, 행은 event_id 로 찾아 결과를 결정적으로 만든다.
def consume(env: Envelope) -> None:
    asyncio.run(svc._consume(env))


def activity_of(event_id: str) -> ItemActivity:
    with svc.db.session() as s:
        return s.scalars(select(ItemActivity).where(ItemActivity.event_id == event_id)).one()


def event(topic: str, item_id: str, tenant: str | None = "T-1") -> Envelope:
    return Envelope(type=topic, source="sample", key=item_id, tenant=tenant, idempotency_key=f"test:{topic}:{new_id()}",
                    data={"id": item_id})


def test_activity_pk_is_uuid7(client):
    """ADR-003 — 활동 기본키도 UUIDv7(INTEGER 일련번호 아님)."""
    iid = client.post("/sample/items", json={"name": "기본키 확인"}, headers=H).json()["id"]
    env = event("sample.item.created", iid)
    consume(env)
    assert is_uuid7(activity_of(env.id).id)


def test_activity_records_event_tenant(client):
    """STD-TENANCY-001 ④ — 소비자는 봉투의 테넌트를 활동에 저장한다(손으로 나르지 않는다)."""
    iid = client.post("/sample/items", json={"name": "테넌트 기록"}, headers=H).json()["id"]
    env = event("sample.item.created", iid, tenant="T-1")
    consume(env)
    assert activity_of(env.id).tenant_id == "T-1"


def add_activity(item_id: str, kind: str, tenant: str | None = "T-1", recorded_at=None) -> None:
    """활동 행을 직접 넣는다 — 시각 · 테넌트를 정해 조회 규칙만 시험한다."""
    with svc.db.session() as s:
        s.add(ItemActivity(tenant_id=tenant, item_id=item_id, kind=kind, event_id=new_id(),
                           **({"recorded_at": recorded_at} if recorded_at else {})))


def kinds_of(client, item_id: str, headers=H) -> list[str]:
    return [a["kind"] for a in client.get(f"/sample/items/{item_id}", headers=headers).json()["activity"]]


def test_activity_tenant_isolation(client):
    """같은 item_id 를 가진 다른 테넌트 활동이 상세에 섞이지 않는다(STD-TENANCY-001 ③ tenant_filter)."""
    iid = client.post("/sample/items", json={"name": "격리 확인"}, headers=H).json()["id"]
    add_activity(iid, "mine", tenant="T-1")
    add_activity(iid, "theirs", tenant="T-2")
    kinds = kinds_of(client, iid)
    assert "mine" in kinds and "theirs" not in kinds


def test_activity_order_recorded_at(client):
    """응답 키는 칸 이름 그대로 recorded_at(at 아님), 정렬은 (recorded_at, id) — 넣은 순서가 아니라 시각 순."""
    from datetime import datetime

    iid = client.post("/sample/items", json={"name": "정렬 확인"}, headers=H).json()["id"]
    add_activity(iid, "t2", recorded_at=datetime(2020, 1, 2))
    add_activity(iid, "t1", recorded_at=datetime(2020, 1, 1))
    add_activity(iid, "t3a", recorded_at=datetime(2020, 1, 3))
    add_activity(iid, "t3b", recorded_at=datetime(2020, 1, 3))  # 같은 시각 — 나중에 만든 id(UUIDv7)가 뒤
    act = client.get(f"/sample/items/{iid}", headers=H).json()["activity"]
    assert all(set(a) == {"kind", "recorded_at"} for a in act), act
    mine = [a for a in act if a["kind"].startswith("t")]
    assert [a["kind"] for a in mine] == ["t1", "t2", "t3a", "t3b"]
    assert mine[0]["recorded_at"] == "2020-01-01T00:00:00Z"


def test_detail_activity_capped(client):
    """REQ-261104-12-8 (P7) — 상세 활동은 최신 50건(ACTIVITY_LIMIT)만, 넘치면 activity_truncated. 보이는 순서는 시각 오름차순 그대로."""
    from datetime import datetime, timedelta

    from sample.items import ACTIVITY_LIMIT

    assert ACTIVITY_LIMIT == 50
    iid = client.post("/sample/items", json={"name": "활동 많음"}, headers=H).json()["id"]
    start = datetime(2020, 1, 1)
    for n in range(60):
        add_activity(iid, f"n{n}", recorded_at=start + timedelta(minutes=n))
    d = client.get(f"/sample/items/{iid}", headers=H).json()
    kinds = [a["kind"] for a in d["activity"]]
    assert len(kinds) == 50 and d["activity_truncated"] is True
    assert "n0" not in kinds and "n59" in kinds  # 오래된 것이 잘린다
    times = [a["recorded_at"] for a in d["activity"]]
    assert times == sorted(times)
    few = client.post("/sample/items", json={"name": "활동 적음"}, headers=H).json()["id"]
    add_activity(few, "only")
    assert client.get(f"/sample/items/{few}", headers=H).json()["activity_truncated"] is False


# ------------------------------------------------------------------ REQ-261104-12-6 (P3) — 보관 풀기 · 삭제 이벤트
def test_restore_emits_restored_once(client):
    """보관 풀기는 sample.item.restored 를 한 번만 — 이미 active 면(중복 클릭 · 재시도) 이벤트 없음."""
    iid = client.post("/sample/items", json={"name": "풀 것"}, headers=H).json()["id"]
    assert client.post(f"/sample/items/{iid}/restore", headers=H).status_code == 200  # 처음부터 active
    assert outbox_count("sample.item.restored", iid) == 0
    client.post(f"/sample/items/{iid}/archive", headers=H)
    client.post(f"/sample/items/{iid}/restore", headers=H)
    client.post(f"/sample/items/{iid}/restore", headers=H)
    assert outbox_count("sample.item.restored", iid) == 1


def test_consumer_records_restored(client):
    iid = client.post("/sample/items", json={"name": "풂 기록"}, headers=H).json()["id"]
    env = event("sample.item.restored", iid)
    consume(env)
    assert activity_of(env.id).kind == "restored"


def test_delete_removes_activity_and_emits_deleted(client):
    """삭제는 같은 트랜잭션에서 그 항목의 활동을 지우고 sample.item.deleted(바깥 구독자용 사실 통지)를 낸다."""
    iid = client.post("/sample/items", json={"name": "지울 것"}, headers=H).json()["id"]
    consume(event("sample.item.created", iid))
    add_activity(iid, "archived")
    assert client.delete(f"/sample/items/{iid}", headers=H).status_code == 204
    with svc.db.session() as s:
        assert s.scalars(select(ItemActivity).where(ItemActivity.item_id == iid)).all() == []
    assert outbox_count("sample.item.deleted", iid) == 1


def test_late_event_after_delete_is_skipped(client):
    """삭제 뒤 늦게 도착한 이벤트는 활동을 다시 만들지 않는다 — 처리 기록은 남아 재전달해도 같다(plan §6 열림)."""
    iid = client.post("/sample/items", json={"name": "늦은 이벤트"}, headers=H).json()["id"]
    assert client.delete(f"/sample/items/{iid}", headers=H).status_code == 204
    env = event("sample.item.archived", iid)
    consume(env)
    consume(env)  # 재전달
    with svc.db.session() as s:
        assert s.scalars(select(ItemActivity).where(ItemActivity.item_id == iid)).all() == []
        assert s.scalars(select(svc.ProcessedEvent).where(svc.ProcessedEvent.event_id == env.id)).all() != []
