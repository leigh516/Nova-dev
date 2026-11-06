"""nova_common 단위 테스트 — 아웃박스 원자성 · 멱등 소비 · 재시도→DLQ · JWT."""
import asyncio
import time

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nova_common import auth
from nova_common.events import Envelope, InMemoryBroker, InMemoryBus
from nova_common.service import Service


def make(name="t-svc"):
    """테스트마다 독립 메타데이터(서비스는 자기 DB만)."""
    global Item

    class Base(DeclarativeBase):
        pass

    class Item(Base):  # noqa: F811
        __tablename__ = "item"
        id: Mapped[str] = mapped_column(String(20), primary_key=True)

    svc = Service(name, Base, "t", db_url="sqlite://")
    svc.init_db()
    broker = InMemoryBroker()
    svc.bus = InMemoryBus(name, broker, sync=True)
    return svc, broker


def run(c):
    return asyncio.new_event_loop().run_until_complete(c)


def test_outbox_written_in_same_transaction_and_rolled_back_together():
    svc, broker = make("t-outbox")
    with svc.db.session() as s:
        s.add(Item(id="a"))
        svc.emit(s, "t.item.created", "a", {"id": "a"})
    with pytest.raises(RuntimeError):
        with svc.db.session() as s:
            s.add(Item(id="b"))
            svc.emit(s, "t.item.created", "b", {"id": "b"})
            raise RuntimeError("비즈니스 실패 → 이벤트도 사라져야 함")
    with svc.db.session() as s:
        rows = s.scalars(select(svc.Outbox)).all()
        assert [r.key for r in rows] == ["a"]
        assert s.get(Item, "b") is None
    assert run(svc.flush_outbox()) == 1
    assert [e.key for e in broker.log] == ["a"]
    assert run(svc.flush_outbox()) == 0  # sent_at 기록 → 재발행 없음


def test_idempotent_consume_processes_once():
    svc, _ = make("t-idem")
    calls = []

    @svc.on("t.ping")
    def h(s, env):
        calls.append(env.id)
        s.add(Item(id=env.key))

    env = Envelope(type="t.ping", source="x", key="k1", idempotency_key="x:k1", data={})
    run(svc._consume(env))
    run(svc._consume(env))  # 재전달
    assert calls == [env.id]
    with svc.db.session() as s:
        assert s.get(svc.ProcessedEvent, (env.id, svc.name)) is not None


def test_principal_require_accepts_granted_roles():
    """GW 가 넣는 x-roles(기본 + 개인·그룹 부여 역할)도 역할 검사에 쓴다."""
    from nova_common import ApiError, Principal

    cs = Principal(user_id="U-3", role="cs", tenant=None, roles=("cs", "finance"))
    assert cs.require("finance") is cs
    with pytest.raises(ApiError):
        Principal(user_id="U-3", role="cs", tenant=None).require("finance")
    # 최상위 역할(NOVA_SUPER_ROLE, 기본 admin)은 모든 검사를 통과
    assert Principal(user_id="U-1", role="admin", tenant=None).require("finance")


def test_super_role_configurable(monkeypatch):
    from nova_common import ApiError, Principal

    monkeypatch.setenv("NOVA_SUPER_ROLE", "root")
    assert Principal(user_id="U-1", role="root", tenant=None).require("finance")
    with pytest.raises(ApiError):
        Principal(user_id="U-1", role="admin", tenant=None).require("finance")


def test_one_topic_many_module_handlers_run_atomically_in_order():
    """같은 토픽을 여러 모듈이 구독 — 덮어쓰지 않고 등록 순서대로 한 트랜잭션에서 실행."""
    svc, _ = make("t-multi")
    calls = []

    @svc.on("t.multi")
    def a(s, env):
        calls.append("a")
        s.add(Item(id="from-a"))

    @svc.on("t.multi")
    def b(s, env):
        calls.append("b")

    svc.on("t.multi")(a)  # 같은 함수 재등록(모듈 재import)은 무시
    env = Envelope(type="t.multi", source="x", key="k", idempotency_key="x:m1", data={})
    run(svc._consume(env))
    assert calls == ["a", "b"]
    with svc.db.session() as s:
        assert s.get(Item, "from-a") is not None


def test_one_topic_many_handlers_failure_rolls_back_all():
    svc, _ = make("t-multi-fail")

    @svc.on("t.multi")
    def a(s, env):
        s.add(Item(id="from-a"))

    @svc.on("t.multi")
    def b(s, env):
        raise RuntimeError("boom")

    run(svc._consume(Envelope(type="t.multi", source="x", key="k", idempotency_key="x:m2", data={})))
    with svc.db.session() as s:
        assert s.get(Item, "from-a") is None  # 한 모듈 실패 → 같은 이벤트의 다른 모듈 변경도 롤백(부분 반영 없음)


def test_handler_failure_retries_then_dlq():
    """개발 버스(InMemoryBus)도 DLQ 를 갖는다 — 주입 없이 broker.dlq 에 쌓인다."""
    svc, broker = make("t-dlq")
    attempts = []

    @svc.on("t.boom")
    def h(s, env):
        attempts.append(1)
        raise ValueError("boom")

    run(svc._consume(Envelope(type="t.boom", source="x", key="k", idempotency_key="x:k")))
    assert len(attempts) == 3 and broker.dlq and broker.dlq[0][0].type == "t.boom"


def test_handler_integrity_error_is_not_mistaken_for_duplicate():
    """핸들러 자신의 유니크 충돌은 '중복 이벤트'가 아니다 → 재시도 후 DLQ, processed_event 미기록."""
    svc, _ = make("t-integrity")
    dlq, attempts = [], []

    async def send_dlq(env, err):
        dlq.append(err)

    svc.bus.send_dlq = send_dlq
    with svc.db.session() as s:
        s.add(Item(id="taken"))

    @svc.on("t.clash")
    def h(s, env):
        attempts.append(1)
        s.add(Item(id="taken"))  # 핸들러 안의 유니크 충돌
        s.flush()

    env = Envelope(type="t.clash", source="x", key="k", idempotency_key="x:k")
    run(svc._consume(env))
    assert len(attempts) == 3 and len(dlq) == 1 and "IntegrityError" in dlq[0]
    with svc.db.session() as s:
        assert s.get(svc.ProcessedEvent, (env.id, svc.name)) is None


def test_concurrent_duplicate_delivery_still_detected_by_processed_event_insert():
    """같은 이벤트가 동시에 두 번 처리돼 processed_event 삽입에서 충돌하면 그것만 중복으로 본다."""
    svc, _ = make("t-dup-race")
    env = Envelope(type="t.once", source="x", key="k", idempotency_key="x:k")
    calls = []

    @svc.on("t.once")
    def h(s, env):
        calls.append(1)
        if len(calls) == 1:  # 첫 처리 도중 다른 소비자가 먼저 완료한 상황을 흉내
            with svc.db.session() as other:
                other.add(svc.ProcessedEvent(event_id=env.id, consumer=svc.name, topic=env.type))

    dlq = []

    async def send_dlq(env, err):
        dlq.append(err)

    svc.bus.send_dlq = send_dlq
    run(svc._consume(env))
    assert calls == [1] and dlq == []


class _FakeConsumer:
    """aiokafka 컨슈머 대역: 커밋 전 오류가 나면 seek_to_committed 로 같은 메시지를 다시 준다."""

    def __init__(self, msgs, fail_commit_once=True):
        from collections import namedtuple

        self.TP = namedtuple("TP", "topic partition")
        self.msgs, self.committed, self.pos = msgs, 0, 0
        self.fail_commit_once, self.seeks = fail_commit_once, 0

    async def getmany(self, timeout_ms=0):
        await asyncio.sleep(0)
        batch = self.msgs[self.pos:]
        self.pos = len(self.msgs)
        return {self.TP("t.ev", 0): batch} if batch else {}

    async def commit(self):
        if self.fail_commit_once:
            self.fail_commit_once = False
            raise RuntimeError("CommitFailedError: rebalance")
        self.committed = self.pos

    async def seek_to_committed(self):
        self.seeks += 1
        self.pos = self.committed


def test_kafka_loop_survives_handler_dlq_and_commit_failures():
    """컨슈머 루프는 예외 한 번에 죽지 않고, 커밋 지점으로 되감아 다시 처리한다. 상태는 healthy 로 노출."""
    from types import SimpleNamespace

    from nova_common.events import KafkaBus

    bus = KafkaBus("t-loop", "unused:9092")
    bus.retry_backoff = 0
    envs = [Envelope(type="t.ev", source="x", key=f"k{i}", idempotency_key=f"x:k{i}") for i in range(2)]
    bus.consumer = _FakeConsumer([SimpleNamespace(value=e.to_bytes()) for e in envs])
    seen, boom = [], {"n": 1}

    async def handler(env):
        if env.key == "k1" and boom["n"]:
            boom["n"] -= 1
            raise RuntimeError("DLQ 발행 실패(브로커 장애)")
        seen.append(env.key)

    bus.subscribe("t.ev", handler)

    async def scenario():
        task = asyncio.create_task(bus._loop())
        bus._loop_task = task
        for _ in range(200):
            await asyncio.sleep(0)
            if bus.consumer.committed == 2:
                break
        alive = bus.healthy
        task.cancel()
        return alive

    alive = run(scenario())
    assert bus.consumer.committed == 2 and bus.consumer.seeks >= 1
    # 유실 없음: 실패한 배치는 되감겨 다시 전달된다(최소 1회 — 실제 중복은 _consume 의 processed_event 가 흡수)
    assert {"k0", "k1"} <= set(seen)
    assert alive is True


def test_kafka_bus_unhealthy_when_loop_task_died():
    from nova_common.events import KafkaBus

    bus = KafkaBus("t-dead", "unused:9092")
    assert bus.healthy is True  # 시작 전(소비 없음)은 정상

    async def die():
        raise RuntimeError("x")

    async def scenario():
        bus._loop_task = asyncio.create_task(die())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return bus.healthy

    assert run(scenario()) is False


def test_outbox_poison_row_does_not_block_later_events():
    """발행이 계속 실패하는 행(없는 토픽 등)이 뒤의 이벤트를 영원히 막으면 안 된다 → 격리(parked) 후 다음 행 진행."""
    svc, broker = make("t-poison")
    real = svc.bus.publish

    async def publish(env):
        if env.type == "t.bad":
            raise RuntimeError("UnknownTopicOrPartition")
        await real(env)

    svc.bus.publish = publish
    with svc.db.session() as s:
        svc.emit(s, "t.bad", "x", {})
    for i in range(svc.outbox_max_attempts + 1):
        with svc.db.session() as s:  # 뒤이어 정상 이벤트가 계속 들어온다
            svc.emit(s, "t.good", f"y{i}", {})
        run(svc.flush_outbox())
    assert [e.type for e in broker.log] == ["t.good"] * (svc.outbox_max_attempts + 1)  # 독 행이 뒤를 막지 않음
    with svc.db.session() as s:
        bad = s.scalar(select(svc.Outbox).where(svc.Outbox.topic == "t.bad"))
        assert bad.sent_at is None and bad.is_parked and bad.attempts >= svc.outbox_max_attempts


def test_outbox_broker_outage_does_not_park_rows():
    """브로커 전체 장애(모든 발행 실패)는 행 고유 문제가 아니다 → 격리·시도 횟수 증가 없음, 순서 보존."""
    svc, broker = make("t-outage")

    async def down(env):
        raise RuntimeError("broker down")

    real, svc.bus.publish = svc.bus.publish, down
    with svc.db.session() as s:
        for i in range(5):
            svc.emit(s, "t.ev", f"k{i}", {})
    for _ in range(svc.outbox_max_attempts + 2):
        assert run(svc.flush_outbox()) == 0
    with svc.db.session() as s:
        assert all(not r.is_parked and r.attempts == 0 for r in s.scalars(select(svc.Outbox)))
    svc.bus.publish = real
    assert run(svc.flush_outbox()) == 5 and [e.key for e in broker.log] == [f"k{i}" for i in range(5)]


def test_envelope_roundtrip():
    e = Envelope(type="a.b.c", source="s", key="k", idempotency_key="i", data={"n": 1, "한글": "값"})
    assert Envelope.from_bytes(e.to_bytes()) == e


def test_jwt_roundtrip_expiry_tamper_and_malformed():
    tok = auth.encode({"sub": "u1", "role": "customer"}, secret="s3")
    assert auth.decode(tok, secret="s3")["sub"] == "u1"
    with pytest.raises(auth.InvalidToken):
        auth.decode(tok, secret="other")
    h, p, sig = tok.split(".")
    with pytest.raises(auth.InvalidToken):
        auth.decode(f"{h}.{p}x.{sig}", secret="s3")
    with pytest.raises(auth.InvalidToken):
        auth.decode("not-a-token", secret="s3")
    with pytest.raises(auth.InvalidToken):
        auth.decode("@@@.###.$$$", secret="s3")
    old = auth.encode({"sub": "u1"}, ttl_seconds=-1, secret="s3")
    time.sleep(0.01)
    with pytest.raises(auth.InvalidToken):
        auth.decode(old, secret="s3")


# ------------------------------------------------------------------ 운영 안전장치
def test_prod_refuses_dev_defaults(monkeypatch):
    from nova_common import runtime

    monkeypatch.setenv("NOVA_ENV", "prod")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    errs = runtime.prod_safety_errors()
    assert any("JWT_SECRET" in e for e in errs)
    monkeypatch.setenv("JWT_SECRET", "nova-dev-secret-change-me")
    assert any("JWT_SECRET" in e for e in runtime.prod_safety_errors())
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    runtime.register_dev_feature("T_DEV_SHOW_CODE", "인증번호 응답 노출")
    monkeypatch.setenv("T_DEV_SHOW_CODE", "1")
    assert any("T_DEV_SHOW_CODE" in e for e in runtime.prod_safety_errors())
    monkeypatch.delenv("T_DEV_SHOW_CODE")
    assert runtime.prod_safety_errors() == []
    # 운영에서는 개발 기능 기본값이 꺼진다
    assert runtime.dev_feature("T_DEV_SHOW_CODE") is False and runtime.dev_feature("NOVA_DEMO") is False


def test_dev_features_on_by_default_outside_prod(monkeypatch):
    from nova_common import runtime

    monkeypatch.delenv("NOVA_ENV", raising=False)
    monkeypatch.delenv("T_DEV_SHOW_CODE", raising=False)
    assert runtime.dev_feature("T_DEV_SHOW_CODE") is True
    monkeypatch.setenv("T_DEV_SHOW_CODE", "0")
    assert runtime.dev_feature("T_DEV_SHOW_CODE") is False
    assert runtime.prod_safety_errors() == []


def test_service_startup_fails_closed_in_unsafe_prod(monkeypatch):
    svc, _ = make("t-prod")
    monkeypatch.setenv("NOVA_ENV", "prod")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="운영 안전장치"):
        run(svc.startup(start_relay=False))
