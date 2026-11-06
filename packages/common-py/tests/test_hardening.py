"""심층 감사 P1 회귀 테스트 — 아웃박스 머리 막힘 · 개발 버스 DLQ · 오류 봉투 · 목록 상한 · 운영 안전 검사 · JWT · 팩 포트 오타 · 행위자 기본값 · 한국어 로그."""
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy import String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nova_common import auth, context, packs, runtime
from nova_common.events import Envelope, EventBus, InMemoryBroker, InMemoryBus, KafkaBus
from nova_common.paging import Page
from nova_common.service import Service, principal


def make(name, *, business_table=True):
    class Base(DeclarativeBase):
        pass

    if business_table:
        class Item(Base):
            __tablename__ = "item"
            id: Mapped[str] = mapped_column(String(20), primary_key=True)

    svc = Service(name, Base, name, db_url="sqlite://")
    svc.init_db()
    broker = InMemoryBroker()
    svc.bus = InMemoryBus(name, broker, sync=True)
    return svc, broker


def run(c):
    return asyncio.new_event_loop().run_until_complete(c)


# ------------------------------------------------------------------ 1. 아웃박스 머리 막힘
def test_outbox_poison_head_rows_do_not_block_forever():
    """맨 앞의 독 행 3개가 매번 실패해도 뒤의 정상 행 10개는 나가고, 독 행은 시도 수가 늘어 결국 격리된다."""
    svc, broker = make("t-head")
    real = svc.bus.publish

    async def publish(env):
        if env.type == "t.bad":
            raise RuntimeError("MessageSizeTooLarge")
        await real(env)

    svc.bus.publish = publish
    with svc.db.session() as s:
        for i in range(3):
            svc.emit(s, "t.bad", f"b{i}", {})
        for i in range(10):
            svc.emit(s, "t.good", f"g{i}", {})
    run(svc.flush_outbox())
    assert sorted(e.key for e in broker.log) == sorted(f"g{i}" for i in range(10))  # 첫 주기에 정상 10개가 나간다
    for i in range(svc.outbox_max_attempts):
        with svc.db.session() as s:  # 운영처럼 정상 이벤트가 계속 들어온다
            svc.emit(s, "t.good", f"n{i}", {})
        run(svc.flush_outbox())
    with svc.db.session() as s:
        bad = s.scalars(select(svc.Outbox).where(svc.Outbox.topic == "t.bad")).all()
        assert len(bad) == 3 and all(r.is_parked and r.sent_at is None for r in bad)
        good = s.scalars(select(svc.Outbox).where(svc.Outbox.topic == "t.good")).all()
        assert all(r.sent_at is not None and not r.is_parked for r in good)


# ------------------------------------------------------------------ 2. 개발 버스 DLQ
def test_inmemory_bus_has_dlq_and_kafka_too():
    assert hasattr(KafkaBus, "send_dlq") and hasattr(InMemoryBus, "send_dlq")
    svc, broker = make("t-mem-dlq")

    @svc.on("t.boom")
    def h(s, env):
        raise ValueError("boom")

    run(svc._consume(Envelope(type="t.boom", source="x", key="k", idempotency_key="x:k")))
    assert len(broker.dlq) == 1 and broker.dlq[0][0].type == "t.boom" and "boom" in broker.dlq[0][1]


def test_bus_without_dlq_logs_error(caplog):
    class NoDlqBus(EventBus):
        async def publish(self, env):  # noqa: D401
            pass

        def subscribe(self, topic, handler):
            pass

    svc, _ = make("t-no-dlq")
    svc.bus = NoDlqBus()

    @svc.on("t.boom")
    def h(s, env):
        raise ValueError("boom")

    with caplog.at_level(logging.ERROR):
        run(svc._consume(Envelope(type="t.boom", source="x", key="k", idempotency_key="x:k")))
    assert any("폐기" in r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR)


# ------------------------------------------------------------------ 3. 오류 봉투
class _Body(BaseModel):
    name: str = Field(min_length=1)


def _err_client():
    svc, _ = make("t-env")

    @svc.app.post("/things")
    def create(body: _Body):
        return {"name": body.name}

    @svc.app.get("/boom")
    def boom():
        raise RuntimeError("비밀 내부 정보 sk-123")

    return TestClient(svc.app, raise_server_exceptions=False)


def test_validation_error_is_enveloped():
    r = _err_client().post("/things", json={"name": ""})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "invalid_input" and re.search("[가-힣]", err["message"])
    assert err["fields"] and err["fields"][0]["loc"][-1] == "name" and err["fields"][0]["msg"]
    assert "detail" not in r.json()


def test_not_found_and_method_not_allowed_are_enveloped():
    c = _err_client()
    r = c.get("/no-such-path")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert re.search("[가-힣]", r.json()["error"]["message"])
    r = c.delete("/things")
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed"
    assert re.search("[가-힣]", r.json()["error"]["message"])


def test_unhandled_exception_is_enveloped_without_leaking(caplog):
    with caplog.at_level(logging.ERROR):
        r = _err_client().get("/boom")
    assert r.status_code == 500
    err = r.json()["error"]
    assert err["code"] == "internal_error" and "서버 오류" in err["message"]
    assert "sk-123" not in r.text  # 원문은 응답에 싣지 않는다
    assert any("sk-123" in (r.exc_text or "") or "sk-123" in r.getMessage() for r in caplog.records)


# ------------------------------------------------------------------ 4. 목록 page 상한
def test_page_has_upper_bound():
    svc, _ = make("t-page")

    @svc.app.get("/list")
    def lst(page: Page = Depends()):
        with svc.db.session() as s:
            s.execute(select(svc.Outbox).offset((page.page - 1) * page.size).limit(page.size)).all()
        return {"page": page.page}

    c = TestClient(svc.app, raise_server_exceptions=False)
    assert c.get("/list", params={"page": 100_000}).status_code == 200
    r = c.get("/list", params={"page": 10**19})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"


# ------------------------------------------------------------------ 5. 운영 안전 검사
@pytest.fixture
def prod_env(monkeypatch):
    monkeypatch.setenv("NOVA_ENV", "prod")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.delenv("NOVA_ALLOW_SQLITE", raising=False)
    monkeypatch.delenv("NOVA_DEMO", raising=False)
    for name in list(runtime.DEV_FEATURES):  # 다른 테스트가 등록한 개발 기능이 켜지지 않게
        monkeypatch.setenv(name, "0")


def test_prod_rejects_sqlite_and_inmemory_bus(prod_env, monkeypatch):
    assert runtime.prod_safety_errors() == []  # 하위 호환: 인자 없이 부르면 예전 검사만
    errs = runtime.prod_safety_errors(db_url="sqlite:///./data/x.db", in_memory_bus=True)
    assert any("DATABASE_URL" in e for e in errs) and any("KAFKA_BOOTSTRAP" in e for e in errs)
    assert runtime.prod_safety_errors(db_url="mysql+pymysql://u:p@h/db", in_memory_bus=False) == []
    monkeypatch.setenv("NOVA_ALLOW_SQLITE", "1")
    assert not any("DATABASE_URL" in e for e in runtime.prod_safety_errors(db_url="sqlite://"))


def test_prod_startup_refuses_sqlite_for_db_service(prod_env):
    svc, _ = make("t-prod-db")  # 업무 표가 있는 서비스 + sqlite + InMemoryBus
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        run(svc.startup(start_relay=False))


def test_prod_startup_allows_stateless_service(prod_env):
    """게이트웨이처럼 업무 표도 구독도 없는 서비스는 메모리 sqlite · 메모리 버스여도 막지 않는다."""
    svc, _ = make("t-prod-stateless", business_table=False)

    async def go():
        await svc.startup(start_relay=False)
        await svc.shutdown()

    run(go())
    assert svc.ready is False  # shutdown 까지 정상


def test_prod_startup_refuses_inmemory_bus_for_subscriber(prod_env):
    svc, _ = make("t-prod-sub", business_table=False)

    @svc.on("platform.x.changed")
    def h(s, env):
        pass

    with pytest.raises(RuntimeError, match="KAFKA_BOOTSTRAP"):
        run(svc.startup(start_relay=False))


# ------------------------------------------------------------------ 6. JWT
def test_jwt_rejects_foreign_issuer(monkeypatch):
    monkeypatch.setenv("JWT_ISSUER", "other")
    tok = auth.encode({"sub": "u1"}, secret="s3")
    monkeypatch.setenv("JWT_ISSUER", "nova")
    with pytest.raises(auth.InvalidToken, match="발급자"):
        auth.decode(tok, secret="s3")


def test_jwt_claims_cannot_override_reserved():
    now = int(time.time())
    tok = auth.encode({"sub": "u1", "exp": now + 10**9, "iss": "evil", "iat": 0}, ttl_seconds=60, secret="s3")
    p = auth.decode(tok, secret="s3")
    assert p["iss"] == auth.issuer() and p["exp"] <= now + 61 and p["iat"] >= now


def test_jwt_reasons_are_korean():
    tok = auth.encode({"sub": "u1"}, secret="s3")
    with pytest.raises(auth.InvalidToken, match="서명"):
        auth.decode(tok, secret="other")
    with pytest.raises(auth.InvalidToken, match="형식"):
        auth.decode("not-a-token", secret="s3")
    old = auth.encode({"sub": "u1"}, ttl_seconds=-1, secret="s3")
    with pytest.raises(auth.InvalidToken, match="만료"):
        auth.decode(old, secret="s3")


# ------------------------------------------------------------------ 7. 팩 포트 오타
@pytest.fixture
def typo_pack(tmp_path, monkeypatch):
    p = tmp_path / "packs" / "typo" / "policies"
    p.mkdir(parents=True)
    for d in (tmp_path / "packs", tmp_path / "packs" / "typo", p):
        (d / "__init__.py").write_text("")
    (tmp_path / "packs" / "typo" / "pack.json").write_text(json.dumps({"name": "typo"}))
    (p / "svcy.py").write_text(
        "from nova_common.packs import implement\n@implement('svcy.greeet')\ndef g(n):\n    return 'pack:' + n\n"
    )
    monkeypatch.setenv("NOVA_PACKS_ROOT", str(tmp_path))
    monkeypatch.setenv("NOVA_PACKS", "typo")
    packs.reset()
    yield tmp_path
    packs.reset()
    for m in [m for m in sys.modules if m == "packs" or m.startswith("packs.")]:
        del sys.modules[m]


@packs.port("svcy.greet")
def _greet(n):
    return "core:" + n


def test_pack_implementing_undeclared_port_fails(typo_pack):
    svc, _ = make("svcy")
    with pytest.raises(packs.PackError, match="svcy.greeet"):
        svc.load_packs()


# ------------------------------------------------------------------ 8. 행위자 기본값
def test_unknown_actor_type_is_not_recorded_as_human():
    with context.scope(None, "robot"):
        assert context.current_actor_type() == "ai"
    with context.scope(None, "system"):
        assert context.current_actor_type() == "system"
    with context.scope(None):
        assert context.current_actor_type() == "human"  # 명시하지 않으면 기존대로 사람


def test_principal_unknown_actor_header_cannot_pass_require_human():
    from nova_common import ApiError

    req = Request({"type": "http", "headers": [(b"x-user-id", b"U"), (b"x-actor-type", b"robot")]})
    p = principal(req)
    assert p.actor_type == "ai" and p.is_ai
    with pytest.raises(ApiError):
        p.require_human()


# ------------------------------------------------------------------ 9. 한국어 로그
def test_log_messages_are_korean():
    src_dir = Path(__file__).resolve().parents[1] / "nova_common"
    pat = re.compile(r"\.(?:debug|info|warning|error|exception|critical)\(\s*f?\"([^\"]*)\"")
    bad = []
    for f in ("events.py", "service.py"):
        for msg in pat.findall((src_dir / f).read_text(encoding="utf-8")):
            if not re.search("[가-힣]", msg):
                bad.append(f"{f}: {msg}")
    assert bad == []


# ------------------------------------------------------------------ 10. 준비 확인(readyz)의 DB 점검 — REQ-10-5 · T02-6.01
def _break_db(svc, tmp_path):
    """DB 엔진을 열 수 없는 경로로 바꿔 'DB 에 닿지 못함'을 진짜로 만든다(없는 폴더 안의 sqlite 파일)."""
    from sqlalchemy import create_engine

    svc.db.engine = create_engine(f"sqlite:///{(tmp_path / '없는폴더' / 'x.db').as_posix()}")


def test_database_ping_true_then_false_with_korean_log(tmp_path, caplog):
    from nova_common.db import Database

    db = Database("t-ping", "sqlite://")
    assert db.ping() is True
    from sqlalchemy import create_engine

    db.engine = create_engine(f"sqlite:///{(tmp_path / '없는폴더' / 'x.db').as_posix()}")
    with caplog.at_level(logging.WARNING):
        assert db.ping() is False  # 예외를 올리지 않고 False
    msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("DB" in m and re.search("[가-힣]", m) and "t-ping" in m for m in msgs), msgs


def test_readyz_reports_db_down_but_healthz_ok(tmp_path, monkeypatch):
    """DB 가 내려가면 readyz 만 닫힌다(503 db_unavailable) — healthz 는 200 이라 파드가 재시작 폭주하지 않는다."""
    monkeypatch.delenv("NOVA_SKIP_LIFESPAN", raising=False)
    svc, _ = make("t-ready-db")  # 업무 표가 있는 DB 서비스
    svc.ready = True
    c = TestClient(svc.app, raise_server_exceptions=False)
    r = c.get("/readyz")
    assert r.status_code == 200 and r.json()["status"] == "ready"

    _break_db(svc, tmp_path)
    r = c.get("/readyz")
    assert r.status_code == 503 and r.json() == {"status": "db_unavailable"}
    h = c.get("/healthz")
    assert h.status_code == 200 and h.json()["status"] == "ok"


def test_readyz_of_stateless_service_does_not_ping_db(tmp_path, monkeypatch):
    """게이트웨이처럼 업무 표가 없는 서비스는 DB 를 보지 않는다 — 예전 동작 그대로."""
    monkeypatch.delenv("NOVA_SKIP_LIFESPAN", raising=False)
    svc, _ = make("t-ready-stateless", business_table=False)
    svc.ready = True
    _break_db(svc, tmp_path)
    r = TestClient(svc.app, raise_server_exceptions=False).get("/readyz")
    assert r.status_code == 200 and r.json()["status"] == "ready"
