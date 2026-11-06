"""컨텍스트 전파(STD-TENANCY-001 · STD-AX-001)와 도메인 팩 포트(STD-DOMAIN-PACK-001)."""
import asyncio
import json

import httpx
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nova_common import ApiError, Envelope, clients, context, packs, principal
from nova_common.events import InMemoryBroker, InMemoryBus
from nova_common.service import Service


def make(name):
    class Base(DeclarativeBase):
        pass

    class Row(Base):
        __tablename__ = "row"
        id: Mapped[str] = mapped_column(String(10), primary_key=True)
        tenant_id: Mapped[str | None] = context.tenant_column()

    svc = Service(name, Base, name, db_url="sqlite://")
    svc.bus = InMemoryBus(name, InMemoryBroker())
    svc.init_db()
    return svc, Row


def test_middleware_sets_context_and_emit_carries_it():
    svc, Row = make("ctx-a")
    seen = {}

    @svc.app.post("/rows/{rid}")
    def create(rid: str, request: Request):
        seen["tenant"], seen["actor"] = context.current_tenant(), context.current_actor_type()
        with svc.db.session() as s:
            s.add(Row(id=rid, tenant_id=context.current_tenant()))
            svc.emit(s, "t.row.created", rid, {"id": rid})
        return {"ok": True}

    c = TestClient(svc.app)
    assert c.post("/rows/r1", headers={"x-tenant": "T-1", "x-actor-type": "ai"}).status_code == 200
    assert seen == {"tenant": "T-1", "actor": "ai"}
    assert context.current_tenant() is None  # 요청이 끝나면 원래대로
    with svc.db.session() as s:
        env = s.scalars(select(svc.Outbox)).one().payload
    assert env["tenant"] == "T-1" and env["actor_type"] == "ai"


def test_consumer_runs_in_publisher_tenant():
    svc, Row = make("ctx-b")
    got = []

    @svc.on("t.row.created")
    def h(s, env):
        got.append((context.current_tenant(), context.current_actor_type()))

    asyncio.run(svc._consume(Envelope(type="t.row.created", source="x", key="k", idempotency_key="i", tenant="T-9", actor_type="system")))
    assert got == [("T-9", "system")]


def test_tenant_filter_isolates():
    svc, Row = make("ctx-c")
    with svc.db.session() as s:
        s.add_all([Row(id="a", tenant_id="T-1"), Row(id="b", tenant_id="T-2"), Row(id="c", tenant_id=None)])
    with svc.db.session() as s:
        with context.scope("T-1"):
            assert [r.id for r in s.scalars(context.tenant_filter(select(Row), Row))] == ["a"]
        assert [r.id for r in s.scalars(context.tenant_filter(select(Row), Row))] == ["c"]  # 테넌트 없음 → 다른 조직 행이 새지 않음
    with pytest.raises(ApiError) as e:
        context.require_tenant()
    assert e.value.code == "tenant_required"


def test_clients_propagate_context_headers():
    from fastapi import FastAPI

    echo = FastAPI()

    @echo.get("/who")
    def who(request: Request):
        return {"tenant": request.headers.get("x-tenant"), "actor": request.headers.get("x-actor-type")}

    clients.override("echo-svc", httpx.ASGITransport(app=echo))
    try:
        async def go():
            with context.scope("T-5", "ai"):
                return await clients.call("echo-svc", "GET", "/who")
        assert asyncio.run(go()) == {"tenant": "T-5", "actor": "ai"}
    finally:
        clients.clear_overrides()


def test_principal_require_human():
    from nova_common import Principal

    with pytest.raises(ApiError) as e:
        Principal(user_id="U", role="user", tenant=None, actor_type="ai").require_human("승인")
    assert e.value.code == "human_only"
    assert Principal(user_id="U", role="user", tenant=None).require_human()


# ------------------------------------------------------------------ 도메인 팩
@pytest.fixture
def pack_root(tmp_path, monkeypatch):
    p = tmp_path / "packs" / "demo" / "policies"
    p.mkdir(parents=True)
    (tmp_path / "packs" / "__init__.py").write_text("")
    (tmp_path / "packs" / "demo" / "__init__.py").write_text("")
    (p / "__init__.py").write_text("")
    (tmp_path / "packs" / "demo" / "pack.json").write_text(json.dumps({"name": "demo"}))
    (p / "svcx.py").write_text("from nova_common.packs import implement\n@implement('svcx.greet')\ndef g(n):\n    return 'pack:' + n\n")
    monkeypatch.setenv("NOVA_PACKS_ROOT", str(tmp_path))
    packs.reset()
    yield tmp_path
    packs.reset()
    import sys
    for m in [m for m in sys.modules if m == "packs" or m.startswith("packs.")]:
        del sys.modules[m]


@packs.port("svcx.greet")
def greet(n):
    return "core:" + n


def test_port_default_then_pack_override(pack_root, monkeypatch):
    assert packs.get("svcx.greet")("a") == "core:a"
    monkeypatch.setenv("NOVA_PACKS", "demo")
    assert packs.load("svcx") == ["demo"]
    assert packs.get("svcx.greet")("a") == "pack:a" and packs.active()["svcx.greet"] == "demo"


def test_enabled_missing_pack_fails_loudly(pack_root, monkeypatch):
    monkeypatch.setenv("NOVA_PACKS", "nope")
    with pytest.raises(packs.PackError, match="찾을 수 없습니다"):
        packs.load("svcx")


def test_undeclared_port_is_error():
    with pytest.raises(packs.PackError):
        packs.get("no.such.port")
