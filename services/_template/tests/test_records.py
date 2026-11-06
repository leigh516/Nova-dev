"""__SERVICE__ — 기본 동작(헬스 · 등록 · 목록 · 이벤트 발행 · 테넌트 격리)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from __PKG__.main import app, svc

H = {"x-user-id": "U-1", "x-role": "user", "x-tenant": "T-1"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/healthz").status_code == 200


def test_create_list_and_event(client):
    r = client.post("/__SERVICE__/records", json={"name": "첫 기록"}, headers=H)
    assert r.status_code == 201
    assert client.get("/__SERVICE__/records", headers=H).json()["total"] == 1
    with svc.db.session() as s:
        assert [o.topic for o in s.scalars(select(svc.Outbox)).all()] == ["__DOMAIN__.record.created"]
    other = {**H, "x-tenant": "T-2"}
    assert client.get(f"/__SERVICE__/records/{r.json()['id']}", headers=other).status_code == 404
    assert client.get("/__SERVICE__/records", headers=other).json()["total"] == 0  # 목록도 테넌트로 거른다


def test_blank_name_rejected(client):
    for blank in ("   ", "\t\n"):
        assert client.post("/__SERVICE__/records", json={"name": blank}, headers=H).status_code == 422


def test_search_escapes_like_wildcards(client):
    Q = {**H, "x-tenant": "T-SEARCH"}
    for n in ("가나다", "50%할인"):
        client.post("/__SERVICE__/records", json={"name": n}, headers=Q)
    assert [x["name"] for x in client.get("/__SERVICE__/records?q=%25", headers=Q).json()["items"]] == ["50%할인"]


def test_non_uuid7_path_is_404(client, monkeypatch):
    """경로 ID 가 UUIDv7 정규형이 아니면 DB 조회 전에 404(REQ-261104-11-7) — 조회 자체가 일어나지 않아야 한다
    (MariaDB 의 대소문자 무시 정렬에서는 대문자 ID 가 같은 행을 찾는다)."""
    import uuid

    from sqlalchemy.orm import Session

    rid = client.post("/__SERVICE__/records", json={"name": "형식 검사"}, headers=H).json()["id"]
    looked: list = []
    real_get = Session.get
    monkeypatch.setattr(Session, "get", lambda self, model, ident, *a, **k: looked.append(ident) or real_get(self, model, ident, *a, **k))
    for bad in ("abc", rid.upper(), rid.replace("-", ""), str(uuid.uuid4())):
        r = client.get(f"/__SERVICE__/records/{bad}", headers=H)
        assert r.status_code == 404 and r.json()["error"]["code"] == "record_not_found", bad
    assert looked == [], "형식이 틀린 ID 로 DB 를 조회했다"
    assert client.get(f"/__SERVICE__/records/{rid}", headers=H).status_code == 200


def test_ai_actor_write_rejected(client):
    """STD-AX-001 L1 — AI 는 초안까지, 저장은 사람(ADR-012). 사람은 그대로 통과."""
    r = client.post("/__SERVICE__/records", json={"name": "AI 기록"}, headers={**H, "x-actor-type": "ai"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "human_only"
    assert client.post("/__SERVICE__/records", json={"name": "사람 기록"}, headers={**H, "x-actor-type": "human"}).status_code == 201
