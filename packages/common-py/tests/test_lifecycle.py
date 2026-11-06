"""데이터 수명 · 격리 재처리 — 정리(purge_infra) · 정리 주기 · 격리 지표 · 재처리(R7 · R8 · REQ-261104-11-2 · -3).

정리 · 재처리는 nova_common 에만 둔다(반목표: 서비스마다 같은 코드 복제 금지)."""
import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import String, event, select
from sqlalchemy.orm import Mapped, mapped_column

from nova_common.db import Database, NovaBase
from nova_common.events import InMemoryBroker, InMemoryBus
from nova_common import outbox_admin
from nova_common import service as service_mod
from nova_common.service import Service

NOW = datetime(2026, 11, 4, 12, 0, 0)


def make(name: str):
    class Base(NovaBase):
        pass

    class Note(Base):
        __tablename__ = "note"
        id: Mapped[str] = mapped_column(String(40), primary_key=True)

    svc = Service(name, Base, "t", db_url="sqlite://")
    svc.init_db()
    broker = InMemoryBroker()
    svc.bus = InMemoryBus(name, broker, sync=True)
    return svc, broker


def run(c):
    return asyncio.new_event_loop().run_until_complete(c)


def _outbox_row(svc, s, n: int, *, sent_days_ago: float | None, created_days_ago: float = 30, parked: bool = False):
    o = svc.Outbox(
        event_id=f"e{n}", topic="t.x", key=f"k{n}", payload={},
        created_at=NOW - timedelta(days=created_days_ago),
        sent_at=None if sent_days_ago is None else NOW - timedelta(days=sent_days_ago),
        is_parked=parked,
    )
    s.add(o)
    return o


def _processed_row(svc, s, n: int, *, days_ago: float):
    s.add(svc.ProcessedEvent(event_id=f"p{n}", consumer=svc.name, topic="t.x", idempotency_key=f"i{n}",
                             processed_at=NOW - timedelta(days=days_ago)))


def _keys(svc, model, col):
    with svc.db.session() as s:
        return sorted(s.scalars(select(getattr(model, col))).all())


# ------------------------------------------------------------------ T03-4.01 정리
def test_purge_deletes_only_expired_sent_rows():
    """보관 기간(발행 7일 · 처리 기록 14일)이 지난 행만 지운다 — 기간 안의 행은 남긴다."""
    svc, _ = make("t-purge-exp")
    with svc.db.session() as s:
        _outbox_row(svc, s, 1, sent_days_ago=8)   # 지난 것
        _outbox_row(svc, s, 2, sent_days_ago=6)   # 기간 안
        _processed_row(svc, s, 1, days_ago=15)  # 지난 것
        _processed_row(svc, s, 2, days_ago=13)  # 기간 안
    got = svc.purge_infra(now=NOW)
    assert got == {"outbox": 1, "processed_event": 1}
    assert _keys(svc, svc.Outbox, "event_id") == ["e2"]
    assert _keys(svc, svc.ProcessedEvent, "event_id") == ["p2"]


def test_purge_keeps_unsent_and_parked():
    """미발행 · 격리 행은 아무리 오래돼도 지우지 않는다 — 격리 행은 사람이 판단한다(§5)."""
    svc, _ = make("t-purge-keep")
    with svc.db.session() as s:
        _outbox_row(svc, s, 1, sent_days_ago=None, created_days_ago=100)
        _outbox_row(svc, s, 2, sent_days_ago=None, created_days_ago=100, parked=True)
    assert svc.purge_infra(now=NOW) == {"outbox": 0, "processed_event": 0}
    assert _keys(svc, svc.Outbox, "event_id") == ["e1", "e2"]


def test_purge_respects_batch():
    """batch 개씩 끊어 지운다(큰 표를 한 문장으로 잠그지 않게) — 5행 · batch 2 → DELETE 3번, 다 지워진다."""
    svc, _ = make("t-purge-batch")
    with svc.db.session() as s:
        for n in range(5):
            _outbox_row(svc, s, n, sent_days_ago=30)
            _processed_row(svc, s, n, days_ago=30)
    deletes: list[str] = []

    @event.listens_for(svc.db.engine, "before_cursor_execute")
    def _spy(conn, cursor, statement, params, context, executemany):  # noqa: ANN001, ARG001
        if statement.lstrip().upper().startswith("DELETE"):
            deletes.append(statement.split()[2].strip('"'))

    got = svc.purge_infra(now=NOW, batch=2)
    assert got == {"outbox": 5, "processed_event": 5}
    assert deletes.count("outbox") == 3 and deletes.count("processed_event") == 3
    assert _keys(svc, svc.Outbox, "event_id") == [] and _keys(svc, svc.ProcessedEvent, "event_id") == []


# ------------------------------------------------------------------ T03-4.02 처리 기록 보관 기간 ≥ 토픽 보존일
TOPICS = Path(__file__).resolve().parents[3] / "infra" / "k3s" / "base" / "kafka-topics.txt"


def _max_topic_retention_days() -> int:
    days = []
    for line in TOPICS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            _topic, _parts, retention = line.split()
            days.append(int(retention))
    assert days, f"토픽 카탈로그가 비었습니다: {TOPICS}"
    return max(days)


def test_processed_retention_covers_topic_retention(monkeypatch):
    """처리 기록이 토픽 메시지보다 먼저 지워지면, 보존 중인 메시지가 다시 전달될 때 중복 처리된다 — 기본값으로 막는다."""
    monkeypatch.delenv("PROCESSED_EVENT_RETENTION_DAYS", raising=False)
    longest = _max_topic_retention_days()
    assert service_mod.PROCESSED_EVENT_RETENTION_DAYS >= longest, (
        f"처리 기록 보관 기간 기본값 {service_mod.PROCESSED_EVENT_RETENTION_DAYS}일 < 토픽 최대 보존일 {longest}일 ({TOPICS.name})"
    )
    svc, _ = make("t-retention")
    assert svc.processed_retention_days >= longest


# ------------------------------------------------------------------ T03-4.03 정리 배경 작업
PURGE_WAIT_LIMIT = 10.0  # 두 번째 정리 주기를 기다리는 상한(초) — 정상이면 수십 ms 에 끝나고, 넘으면 정말 멈춘 것


def test_purge_loop_runs_and_survives_error(caplog):
    """기동하면 곧바로 한 번 정리하고 NOVA_PURGE_INTERVAL 마다 다시 한다. 한 주기가 실패해도 로그만 남기고 다음 주기로(§6 열림)."""
    svc, _ = make("t-purge-loop")
    svc.purge_interval = 0.01
    calls: list[int] = []

    def fake_purge(now=None, batch=1000):  # noqa: ARG001
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("DB 연결 끊김")
        return {"outbox": 0, "processed_event": 0}

    svc.purge_infra = fake_purge

    async def go():
        await svc.startup(start_relay=False)
        # 고정 시간(0.1초) 안에 두 주기를 기대하면 부하 때 깨진다 — 두 번째 주기가 올 때까지 기다리되 상한을 둔다
        deadline = asyncio.get_running_loop().time() + PURGE_WAIT_LIMIT
        while len(calls) < 2 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        await svc.shutdown()

    run(go())
    assert len(calls) >= 2, f"첫 주기 실패 뒤에도 다음 주기가 {PURGE_WAIT_LIMIT}초 안에 돌아야 합니다(실제 {len(calls)}회)"
    assert "정리" in caplog.text and "DB 연결 끊김" in caplog.text


# ------------------------------------------------------------------ T03-4.04 격리 지표 · pending 분리
def _gauge(name: str, service: str):
    return REGISTRY.get_sample_value(name, {"service": service})


def _park_two(svc):
    with svc.db.session() as s:
        _outbox_row(svc, s, 1, sent_days_ago=None, parked=True)
        _outbox_row(svc, s, 2, sent_days_ago=None, parked=True)


def test_quarantined_gauge_counts_parked():
    """격리 행 수는 nova_outbox_quarantined 로 따로 보인다(알림 OutboxQuarantined 의 근거)."""
    svc, _ = make("t-gauge-q")
    _park_two(svc)
    run(svc.flush_outbox())
    assert _gauge("nova_outbox_quarantined", "t-gauge-q") == 2


def test_pending_excludes_parked():
    """격리 행이 pending 에 섞이면 OutboxBacklog 경보가 풀리지 않는다(§12.1) — pending 은 발행 대기만."""
    svc, _ = make("t-gauge-p")
    _park_two(svc)
    run(svc.flush_outbox())
    assert _gauge("nova_outbox_pending", "t-gauge-p") == 0


# ------------------------------------------------------------------ T03-4.05 격리 목록 · 해제
def _poison(svc, bad_topic: str = "t.bad"):
    """bad_topic 발행만 실패하게 한다(행 고유 문제 — 크기 초과 등). 반환: 고장 스위치."""
    real = svc.bus.publish
    state = {"broken": True}

    async def publish(env):
        if state["broken"] and env.type == bad_topic:
            raise RuntimeError("MessageSizeTooLarge")
        await real(env)

    svc.bus.publish = publish
    return state


def _park_by_relay(svc):
    """릴레이로 실제 격리까지 — 정상 행이 함께 나가야 행 고유 실패로 보고 시도 수를 늘린다."""
    for i in range(svc.outbox_max_attempts):
        with svc.db.session() as s:
            svc.emit(s, "t.good", f"g{i}", {})
        run(svc.flush_outbox())


def test_requeue_parked_releases_and_publishes(caplog):
    """해제하면 parked 거짓 · attempts 0 · last_error 보존(원인 추적) → 다음 릴레이에서 나간다. 해제 건수는 로그로."""
    svc, broker = make("t-requeue")
    svc.outbox_max_attempts = 2
    state = _poison(svc)
    with svc.db.session() as s:
        svc.emit(s, "t.bad", "b1", {})
    _park_by_relay(svc)
    [row] = svc.parked_rows()
    assert row["topic"] == "t.bad" and row["key"] == "b1" and row["attempts"] == 2 and "MessageSizeTooLarge" in row["last_error"]
    assert svc.requeue_parked([]) == 0  # 빈 목록은 '전부'가 아니다
    state["broken"] = False  # 원인을 고쳤다
    assert svc.requeue_parked([row["id"]]) == 1
    with svc.db.session() as s:
        o = s.get(svc.Outbox, row["id"])
        assert not o.is_parked and o.attempts == 0 and "MessageSizeTooLarge" in (o.last_error or "")
    assert svc.parked_rows() == []
    assert "격리 해제" in caplog.text and "1건" in caplog.text
    run(svc.flush_outbox())
    assert "b1" in [e.key for e in broker.log]
    assert _gauge("nova_outbox_quarantined", "t-requeue") == 0


def test_requeued_row_failing_again_parks_again():
    """원인이 그대로면 한계에서 다시 격리된다 — 무한 재시도로 뒤 행이 막히지 않게(§6 닫힘). ids=None 은 전부."""
    svc, broker = make("t-requeue-again")
    svc.outbox_max_attempts = 2
    _poison(svc)
    with svc.db.session() as s:
        svc.emit(s, "t.bad", "b1", {})
        svc.emit(s, "t.bad", "b2", {})
    _park_by_relay(svc)
    assert len(svc.parked_rows()) == 2
    assert svc.requeue_parked(None) == 2
    assert svc.parked_rows() == []
    _park_by_relay(svc)
    again = svc.parked_rows()
    assert sorted(r["key"] for r in again) == ["b1", "b2"] and all(r["attempts"] == 2 for r in again)
    assert not [e for e in broker.log if e.type == "t.bad"]


# ------------------------------------------------------------------ T03-4.06 재처리 명령
ROOT = Path(__file__).resolve().parents[3]


def _cli(args, *, via_nova: bool = False, **env):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("NOVA_", "DATABASE_URL"))}
    e.update(PYTHONIOENCODING="utf-8", **env)
    head = [sys.executable, str(ROOT / "nova.py"), "parked"] if via_nova else [sys.executable, "-m", "nova_common.outbox_admin"]
    return subprocess.run([*head, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=e)


@pytest.mark.slow
def test_outbox_admin_cli_requeue(tmp_path):
    """운영자가 셸에서 격리 행을 보고(list — nova.py 연결) 골라 해제한다(requeue --id · --all). 서비스는 catalog 의
    `<pkg>.main:svc` 로 연다. 하위 프로세스 하나가 이 PC 에서 수 초라 명령 오용 경우는 아래 프로세스 안 테스트에서 본다."""
    url = f"sqlite:///{(tmp_path / 'sample.db').as_posix()}"
    svc, _ = make("t-cli")
    svc.db = Database("t-cli", url)
    svc.init_db()
    with svc.db.session() as s:
        for n in (1, 2):
            s.add(svc.Outbox(event_id=f"e{n}", topic="sample.item.created", key=f"k{n}", payload={}, attempts=5,
                             last_error="RuntimeError('MessageSizeTooLarge')", is_parked=True))
    svc.db.engine.dispose()  # 파일을 하위 프로세스와 나눠 쓴다

    listed = _cli(["sample", "list"], via_nova=True, DATABASE_URL_SAMPLE=url)
    assert listed.returncode == 0, listed.stdout + listed.stderr
    assert "2건" in listed.stdout and "sample.item.created" in listed.stdout and "MessageSizeTooLarge" in listed.stdout

    one = _cli(["sample", "requeue", "--id", "1"], DATABASE_URL_SAMPLE=url)
    assert one.returncode == 0 and "1건" in one.stdout, one.stdout + one.stderr
    rest = _cli(["sample", "requeue", "--all"], DATABASE_URL_SAMPLE=url)
    assert rest.returncode == 0 and "1건" in rest.stdout, rest.stdout + rest.stderr
    with svc.db.session() as s:
        rows = s.scalars(select(svc.Outbox)).all()
        assert all(not r.is_parked and r.attempts == 0 and r.last_error for r in rows)


def test_outbox_admin_requires_id_or_all(capsys):
    """--id 와 --all 이 둘 다 없으면 종료 코드 2(argparse) · 없는 서비스도 2 — 서비스를 열기 전에 끊으므로 프로세스 안에서 본다."""
    with pytest.raises(SystemExit) as e:
        outbox_admin.main(["sample", "requeue"])
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "--id" in err and "--all" in err
    with pytest.raises(SystemExit) as e:
        outbox_admin.main(["sample", "requeue", "--id", "1", "--all"])  # 둘 다 주는 것도 막는다
    assert e.value.code == 2
    assert outbox_admin.main(["no-such-svc", "list"]) == 2
    assert "서비스" in capsys.readouterr().err
