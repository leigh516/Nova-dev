"""sample — 마이그레이션(플랫폼 + 서비스 분기)이 모델과 같고, 옛 create_all DB 도 행을 보존한 채 올라간다(ADR-011)."""
from sqlalchemy import text

from nova_common import migrate
from nova_common.db import Database

from sample.main import svc

P_HEAD = migrate.platform_head()  # 플랫폼 분기 최신 리비전 — 손으로 적지 않는다(리비전을 더할 때 함께 따라온다)
S_HEAD = "s0002"  # 서비스 분기 최신 — 샘플 표 구조 정정(REQ-261104-12 P2 · P5)

# create_all 시절 = s0001(baseline) 모양의 sample 표 — 옛 DB 는 이 모양이라고 보고 stamp 된다(지금 모델로 만들면 s0002 가 이미 바뀐 칸을 다시 바꾼다)
LEGACY_SAMPLE_DDL = (
    "CREATE TABLE item (id VARCHAR(36) NOT NULL, tenant_id VARCHAR(40), name VARCHAR(100) NOT NULL, memo TEXT, "
    "status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL, created_by VARCHAR(40), updated_at DATETIME NOT NULL, "
    "updated_by VARCHAR(40), PRIMARY KEY (id))",
    "CREATE INDEX ix_item_tenant_id ON item (tenant_id)",
    "CREATE INDEX ix_item_status ON item (status)",
    "CREATE TABLE item_activity (id INTEGER NOT NULL, item_id VARCHAR(36) NOT NULL, kind VARCHAR(40) NOT NULL, "
    "event_id VARCHAR(36) NOT NULL, at DATETIME NOT NULL, PRIMARY KEY (id))",
    "CREATE INDEX ix_item_activity_item_id ON item_activity (item_id)",
)


def test_sample_uses_migrations():
    assert svc.migrations_dir is not None and svc.migrations_dir.name == "migrations"


def test_sample_migration_matches_models():
    db = Database("sample-migration-check", "sqlite://")
    migrate.upgrade(db, svc.Base, svc.migrations_dir)
    assert migrate.drift(db, svc.Base) == [], '모델과 마이그레이션이 다르다 — python nova.py migrate sample new "<설명>"'
    assert migrate.status(db, svc.Base, svc.migrations_dir)["current"] == [P_HEAD, S_HEAD]


# create_all 시절(p0001 모양 · 이름 규칙 없음) 플랫폼 표 — SQLAlchemy 가 그때 내던 DDL 그대로
LEGACY_PLATFORM_DDL = (
    "CREATE TABLE outbox (id INTEGER NOT NULL, event_id VARCHAR(40) NOT NULL, topic VARCHAR(120) NOT NULL, \"key\" VARCHAR(80) NOT NULL, "
    "payload JSON NOT NULL, created_at DATETIME NOT NULL, sent_at DATETIME, attempts INTEGER NOT NULL, last_error TEXT, "
    "parked BOOLEAN NOT NULL, PRIMARY KEY (id), UNIQUE (event_id))",
    "CREATE INDEX ix_outbox_topic ON outbox (topic)",
    "CREATE INDEX ix_outbox_sent_at ON outbox (sent_at)",
    "CREATE INDEX ix_outbox_parked ON outbox (parked)",
    "CREATE TABLE processed_event (event_id VARCHAR(40) NOT NULL, consumer VARCHAR(80) NOT NULL, topic VARCHAR(120) NOT NULL, "
    "ok BOOLEAN NOT NULL, at DATETIME NOT NULL, PRIMARY KEY (event_id, consumer))",
    "INSERT INTO processed_event (event_id, consumer, topic, ok, at) VALUES ('e-old', 'sample', 't', 1, '2026-11-04 00:00:00')",
)


def test_legacy_sample_db_is_stamped_and_rows_kept(tmp_path):
    """개발자 PC 의 data/sample.db(create_all 시절) — 검토 초점 1번(plan_REQ_03 §11.2)."""
    db = Database("sample-legacy", f"sqlite:///{(tmp_path / 'sample.db').as_posix()}")
    # 옛 DB 는 baseline(p0001 · s0001)으로 stamp 되므로 표는 그때 모양이어야 한다 — 지금 모델로 만들면 뒤 리비전이 이미 바뀐 칸을 다시 바꾼다
    with db.engine.begin() as c:
        for ddl in LEGACY_PLATFORM_DDL + LEGACY_SAMPLE_DDL:
            c.execute(text(ddl))
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO item (id, name, status, created_at, updated_at) VALUES ('i1', '옛 항목', 'active', '2026-11-04', '2026-11-04')"))
    migrate.upgrade(db, svc.Base, svc.migrations_dir)
    assert migrate.status(db, svc.Base, svc.migrations_dir)["up_to_date"]
    with db.engine.connect() as c:
        assert c.execute(text("SELECT name FROM item WHERE id='i1'")).scalar_one() == "옛 항목"
        assert c.execute(text("SELECT is_ok FROM processed_event WHERE event_id='e-old' AND idempotency_key IS NULL")).scalar_one() == 1
    assert migrate.drift(db, svc.Base) == []


def test_sample_downgrade_service_branch():
    db = Database("sample-migration-down", "sqlite://")
    migrate.upgrade(db, svc.Base, svc.migrations_dir)
    migrate.downgrade(db, svc.Base, svc.migrations_dir, "service@base")
    assert migrate.status(db, svc.Base, svc.migrations_dir)["current"] == [P_HEAD]


def _s0001_db_with_rows(tmp_path) -> Database:
    """s0001 까지 올린 DB + 옛 모양의 행(정수 활동 ID · at · 지워진 항목의 고아 활동 1건)."""
    db = Database("sample-s0002", f"sqlite:///{(tmp_path / 'sample.db').as_posix()}")
    migrate.upgrade(db, svc.Base, svc.migrations_dir)
    migrate.downgrade(db, svc.Base, svc.migrations_dir, "s0001")
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO item (id, tenant_id, name, status, created_at, created_by, updated_at, updated_by) VALUES "
                       "('i1', 'T-1', '옛 항목', 'active', '2026-11-04', '01a1a19a-d2c9-747b-a454-3bcb1e16a767', '2026-11-04', NULL)"))
        for n, (item_id, kind, at) in enumerate((("i1", "created", "2026-11-04 00:00:00"), ("i1", "archived", "2026-11-04 00:00:00"),
                                                 ("gone", "created", "2026-11-03 00:00:00")), start=1):
            c.execute(text("INSERT INTO item_activity (id, item_id, kind, event_id, at) VALUES (:n, :i, :k, :e, :a)"),
                      {"n": n, "i": item_id, "k": kind, "e": f"e{n}", "a": at})
    return db


def test_s0002_keeps_rows_and_order(tmp_path):
    """옛 활동 행이 지워지지 않고 UUIDv7 ID · 항목의 테넌트 · recorded_at 으로 올라간다 — 같은 시각 안의 옛 순서도 그대로."""
    from nova_common.ids import is_uuid7

    db = _s0001_db_with_rows(tmp_path)
    migrate.upgrade(db, svc.Base, svc.migrations_dir)
    assert migrate.status(db, svc.Base, svc.migrations_dir)["current"] == [P_HEAD, S_HEAD]
    assert migrate.drift(db, svc.Base) == []
    with db.engine.connect() as c:
        rows = c.execute(text("SELECT id, tenant_id, item_id, kind, recorded_at FROM item_activity ORDER BY recorded_at, id")).all()
        assert c.execute(text("SELECT created_by FROM item WHERE id='i1'")).scalar_one() == "01a1a19a-d2c9-747b-a454-3bcb1e16a767"
    assert [(r.item_id, r.kind) for r in rows] == [("gone", "created"), ("i1", "created"), ("i1", "archived")]
    assert all(is_uuid7(r.id) for r in rows)
    assert [r.tenant_id for r in rows] == [None, "T-1", "T-1"]  # 고아 활동은 테넌트를 알 수 없다 — 지우지 않고 NULL


def test_s0002_downgrade_restores_old_shape(tmp_path):
    """되돌리기 — 정수 ID(보이던 순서) · at 칸으로 돌아가고 행은 그대로."""
    db = _s0001_db_with_rows(tmp_path)
    migrate.upgrade(db, svc.Base, svc.migrations_dir)
    migrate.downgrade(db, svc.Base, svc.migrations_dir, "s0001")
    with db.engine.connect() as c:
        rows = c.execute(text("SELECT id, item_id, kind FROM item_activity ORDER BY id")).all()
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(item_activity)"))}
    assert [(r.id, r.item_id, r.kind) for r in rows] == [(1, "gone", "created"), (2, "i1", "created"), (3, "i1", "archived")]
    assert cols == {"id", "item_id", "kind", "event_id", "at"}
