"""방송 소비(REQ-261104-11-4 · R9) — 일반 토픽은 서비스(그룹)당 한 번, 방송 토픽은 인스턴스(복제본)마다.

Kafka 는 실제 브로커 없이 aiokafka 대역으로 그룹 · 시작 위치 · 소비 루프 · 건강 상태를 본다(실제 Kafka 동작은 e2e-kafka 몫).
"""
import asyncio

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nova_common.events import Envelope, InMemoryBroker, InMemoryBus
from nova_common.service import Service


def run(c):
    return asyncio.new_event_loop().run_until_complete(c)


def _replica(name, broker, db_url="sqlite://"):
    """같은 서비스의 복제본 하나 — 자기 버스(인스턴스) · 같은 브로커."""

    class Base(DeclarativeBase):
        pass

    class Item(Base):
        __tablename__ = "item"
        id: Mapped[str] = mapped_column(String(40), primary_key=True)

    svc = Service(name, Base, "t", db_url=db_url)
    svc.init_db()
    svc.bus = InMemoryBus(name, broker, sync=True)
    return svc


def _wire(svc, seen):
    @svc.on("t.cache.changed", broadcast=True)
    def on_cache(_s, env):
        seen.append(("cache", svc.bus.instance, env.id))

    @svc.on("t.order.placed")
    def on_order(_s, env):
        seen.append(("order", svc.bus.instance, env.id))

    svc._subscribe_all()  # startup 의 구독 부분만(시드 · 릴레이 없이)


def _ev(topic, key="K"):
    return Envelope(type=topic, source="iam", key=key, idempotency_key=f"iam:{topic}:{key}")


# ---------------------------------------------------------------- T03-5.07 InMemory
def test_broadcast_reaches_every_instance():
    broker, seen = InMemoryBroker(), []
    a, b = _replica("t-gw", broker), _replica("t-gw", broker)
    for svc in (a, b):
        _wire(svc, seen)
    assert a.bus.instance != b.bus.instance  # 버스 하나 = 인스턴스 하나
    run(broker.deliver(_ev("t.cache.changed")))
    assert sorted(i for k, i, _ in seen if k == "cache") == sorted([a.bus.instance, b.bus.instance])


def test_normal_topic_once_per_group():
    broker, seen = InMemoryBroker(), []
    a, b = _replica("t-gw", broker), _replica("t-gw", broker)
    for svc in (a, b):
        _wire(svc, seen)
    run(broker.deliver(_ev("t.order.placed")))
    assert len([1 for k, *_ in seen if k == "order"]) == 1  # 일반 토픽은 그룹(서비스)당 한 번 — 예전과 같다


def test_broadcast_on_shared_db_is_not_deduped_across_instances(tmp_path):
    """복제본이 DB 를 함께 쓰는 서비스 — 처리 기록 소비자 이름이 서비스 이름 하나면 두 번째 복제본이 '중복'으로 건너뛴다.
    방송 소비 기록은 인스턴스마다(`<service>.<instance>`)."""
    url = f"sqlite:///{(tmp_path / 'shared.db').as_posix()}"
    broker, seen = InMemoryBroker(), []
    a, b = _replica("t-db", broker, url), _replica("t-db", broker, url)
    for svc in (a, b):
        _wire(svc, seen)
    env = _ev("t.cache.changed")
    run(broker.deliver(env))
    assert len([1 for k, *_ in seen if k == "cache"]) == 2
    run(broker.deliver(env))  # 같은 메시지 재전달 — 인스턴스마다 한 번씩만(멱등은 그대로)
    assert len([1 for k, *_ in seen if k == "cache"]) == 2


def test_broadcast_consumer_name_fits_processed_event_column():
    """🆕 T03-9.06 — 처리 기록 소비자 이름 `<service>.<instance>` 가 processed_event.consumer(80자)를 넘지 않는다.
    HOSTNAME(파드 이름)은 253자까지 될 수 있어 MariaDB 에서 'Data too long' 으로 소비가 멈춘다. SQLite 는 길이를 강제하지 않으므로
    길이를 직접 단언한다. 줄인 이름은 결정적이어야 하고(재전달 멱등), 앞부분이 같은 두 인스턴스가 겹치면 안 된다."""
    broker, seen = InMemoryBroker(), []
    long_a = "nova-gateway-" + "x" * 200 + "-a"
    long_b = "nova-gateway-" + "x" * 200 + "-b"  # 앞 200자가 같다 — 단순 자르기면 둘이 같은 이름이 된다
    a, b = _replica("t-gw", broker), _replica("t-gw", broker)
    a.bus.instance, b.bus.instance = long_a, long_b
    for svc in (a, b):
        _wire(svc, seen)
    limit = a.ProcessedEvent.__table__.c.consumer.type.length
    assert limit == 80
    na, nb = a._consumer_name("t.cache.changed"), b._consumer_name("t.cache.changed")
    assert len(na) <= limit and len(nb) <= limit
    assert na != nb and na.startswith("t-gw.nova-gateway-")
    assert na == a._consumer_name("t.cache.changed")  # 결정적
    assert a._consumer_name("t.order.placed") == "t-gw"  # 일반 토픽은 서비스 이름 그대로
    short = _replica("t-gw", broker)
    short.bus.instance = "pod-1"
    _wire(short, seen)
    assert short._consumer_name("t.cache.changed") == "t-gw.pod-1"  # 짧으면 그대로(기존 기록과 이어진다)
    run(broker.deliver(_ev("t.cache.changed")))
    assert len([1 for k, *_ in seen if k == "cache"]) == 3  # 긴 이름 둘 · 짧은 이름 하나 모두 받는다
    with a.db.session() as s:
        assert [len(c) for c in s.scalars(select(a.ProcessedEvent.consumer)).all()] == [len(na)]


def test_on_rejects_mixed_broadcast_flags():
    svc = _replica("t-mix", InMemoryBroker())

    @svc.on("t.x")
    def h1(_s, _e):
        pass

    with pytest.raises(ValueError, match="방송"):
        @svc.on("t.x", broadcast=True)
        def h2(_s, _e):
            pass


# ---------------------------------------------------------------- T03-5.08 KafkaBus (aiokafka 대역 — 실제 Kafka 없음)
class _FakeKafkaConsumer:
    made: list["_FakeKafkaConsumer"] = []

    def __init__(self, *topics, **kw):
        self.topics, self.kw = topics, kw
        self.queue: list[bytes] = []
        self.commits, self.started, self.stopped = 0, False, False
        _FakeKafkaConsumer.made.append(self)

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def getmany(self, timeout_ms=0):
        await asyncio.sleep(0)
        if not self.queue:
            return {}
        from collections import namedtuple
        from types import SimpleNamespace

        tp = namedtuple("TP", "topic partition")(self.topics[0], 0)
        batch, self.queue = [SimpleNamespace(value=v) for v in self.queue], []
        return {tp: batch}

    async def commit(self):
        self.commits += 1

    async def seek_to_committed(self):
        pass

    def assignment(self):
        return set()


class _FakeKafkaProducer:
    def __init__(self, **kw):
        self.kw = kw

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send_and_wait(self, *a, **kw):
        pass


@pytest.fixture
def fake_kafka(monkeypatch):
    import aiokafka

    _FakeKafkaConsumer.made = []
    monkeypatch.setattr(aiokafka, "AIOKafkaConsumer", _FakeKafkaConsumer)
    monkeypatch.setattr(aiokafka, "AIOKafkaProducer", _FakeKafkaProducer)
    return _FakeKafkaConsumer


async def _noop(_env):
    pass


def _kafka_bus(name="gateway"):
    from nova_common.events import KafkaBus

    bus = KafkaBus(name, "unused:9092")
    bus.subscribe("t.order.placed", _noop)
    bus.subscribe("platform.rbac.changed", _noop, broadcast=True)
    return bus


def test_kafka_group_ids(fake_kafka, monkeypatch):
    monkeypatch.setenv("KAFKA_INSTANCE_ID", "gw-0")
    monkeypatch.setenv("HOSTNAME", "gateway-7d9f-abcde")
    bus = _kafka_bus()
    assert bus.instance == "gw-0"  # 명시 값이 먼저

    async def go():
        await bus.start()
        await bus.stop()

    run(go())
    groups = {c.kw["group_id"]: c.topics for c in fake_kafka.made}
    assert groups == {"gateway": ("t.order.placed",), "gateway.gw-0": ("platform.rbac.changed",)}
    assert len({c.kw["client_id"] for c in fake_kafka.made}) == 2  # 두 소비자를 브로커에서 구분
    assert all(c.started and c.stopped for c in fake_kafka.made)

    monkeypatch.delenv("KAFKA_INSTANCE_ID")
    assert _kafka_bus().instance == "gateway-7d9f-abcde"  # 다음은 파드 이름
    monkeypatch.delenv("HOSTNAME")
    a, b = _kafka_bus(), _kafka_bus()
    assert a.instance and a.instance != b.instance  # 둘 다 없으면 임의 값 — 복제본끼리 겹치지 않게


def test_kafka_broadcast_starts_from_latest(fake_kafka, monkeypatch):
    monkeypatch.setenv("KAFKA_INSTANCE_ID", "gw-1")
    from nova_common.events import KafkaBus

    got = []

    async def on_rbac(env):
        got.append(env.key)

    bus = KafkaBus("gateway", "unused:9092")
    bus.subscribe("platform.rbac.changed", on_rbac, broadcast=True)  # 방송만 있는 서비스 — 일반 소비자는 만들지 않는다

    async def go():
        await bus.start()
        (bc,) = fake_kafka.made
        bc.queue.append(_ev("platform.rbac.changed", key="U-1").to_bytes())
        for _ in range(50):
            await asyncio.sleep(0)
            if got:
                break
        healthy = bus.healthy
        await bus.stop()
        return bc, healthy

    bc, healthy = run(go())
    assert bc.kw["auto_offset_reset"] == "latest"  # 새 파드는 기동 때 표를 새로 받으므로 지난 무효화를 다시 읽지 않는다
    assert bc.kw["enable_auto_commit"] is False and bc.kw["group_id"] == "gateway.gw-1"
    assert got == ["U-1"] and bc.commits >= 1 and healthy is True  # 방송 소비 루프가 돈다


def test_kafka_normal_consumer_stays_earliest(fake_kafka, monkeypatch):
    monkeypatch.setenv("KAFKA_INSTANCE_ID", "gw-2")
    bus = _kafka_bus()

    async def go():
        await bus.start()
        await bus.stop()

    run(go())
    normal = next(c for c in fake_kafka.made if c.kw["group_id"] == "gateway")
    assert normal.kw["auto_offset_reset"] == "earliest"  # 일반 토픽은 예전 그대로 — 유실 없음


def test_kafka_bus_unhealthy_when_broadcast_loop_died(fake_kafka, monkeypatch):
    monkeypatch.setenv("KAFKA_INSTANCE_ID", "gw-3")
    bus = _kafka_bus()

    async def go():
        await bus.start()
        assert bus.healthy is True
        bus._broadcast_task.cancel()  # 방송 소비 루프만 죽는다(일반 루프는 산다)
        for _ in range(5):
            await asyncio.sleep(0)
        dead = bus.healthy
        await bus.stop()
        return dead

    assert run(go()) is False  # 무효화를 못 받는 게이트웨이가 낡은 권한으로 응답하지 않게 → healthz 503 → 재시작
