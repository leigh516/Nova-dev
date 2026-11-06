"""마이그레이션 체계 — 제약 이름 규칙 · 실행기(플랫폼 + 서비스 분기) · 옛 create_all DB stamp (REQ-261104-11-1 · ADR-011)."""
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.orm import Mapped, mapped_column

from nova_common import db as nova_db
from nova_common import migrate

P_HEAD = "p0004"  # 플랫폼 분기 최신 리비전 — 플랫폼 마이그레이션을 더하면 함께 올린다


def _models():
    """규칙을 확인할 작은 모델 — 인덱스 · UNIQUE(한 칸 · 여러 칸) · FK · CHECK · PK 를 모두 가진다."""

    class Base(nova_db.NovaBase):
        pass

    class Parent(Base):
        __tablename__ = "parent"
        id: Mapped[str] = mapped_column(String(36), primary_key=True)
        code: Mapped[str] = mapped_column(String(20), unique=True)
        name: Mapped[str] = mapped_column(String(50), index=True)

    class Child(Base):
        __tablename__ = "child"
        __table_args__ = (UniqueConstraint("parent_id", "seq"), CheckConstraint("seq >= 0", name="seq_not_negative"))
        id: Mapped[str] = mapped_column(String(36), primary_key=True)
        parent_id: Mapped[str] = mapped_column(ForeignKey("parent.id"))
        seq: Mapped[int] = mapped_column(Integer)

    return Base


def test_constraint_names_follow_convention():
    Base = _models()
    assert Base.metadata.naming_convention == nova_db.NAMING_CONVENTION
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    ins = inspect(eng)
    assert {i["name"] for i in ins.get_indexes("parent")} == {"ix_parent_name"}
    assert {u["name"] for u in ins.get_unique_constraints("parent")} == {"uq_parent_code"}
    assert {u["name"] for u in ins.get_unique_constraints("child")} == {"uq_child_parent_id_seq"}
    assert [f["name"] for f in ins.get_foreign_keys("child")] == ["fk_child_parent_id_parent"]
    assert {c["name"] for c in ins.get_check_constraints("child")} == {"ck_child_seq_not_negative"}
    # PK 이름은 SQLite 가 되읽지 못하므로 메타데이터에서 본다(MariaDB 는 PRIMARY 로 고정)
    assert Base.metadata.tables["parent"].primary_key.name == "pk_parent"


def test_nova_base_gives_each_service_its_own_metadata():
    """서비스 Base 마다 MetaData 가 따로다 — 한 프로세스에 여러 서비스가 떠도 outbox 표가 부딪히지 않는다."""
    a, b = _models(), _models()
    assert a.metadata is not b.metadata
    assert a.metadata is not nova_db.NovaBase.metadata
    nova_db.add_infra_tables(a)
    nova_db.add_infra_tables(b)
    assert "outbox" in a.metadata.tables and "outbox" in b.metadata.tables


# ---------------------------------------------------------------- 실행기 (T03-2.03 · T03-2.04)
S0001 = '''"""시험 서비스 첫 표."""
from alembic import op
import sqlalchemy as sa

revision = "s0001"
down_revision = None
branch_labels = ("service",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "thing",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_thing")),
    )


def downgrade() -> None:
    op.drop_table("thing")
'''

S0002 = '''"""시험 서비스 칸 추가 — stamp 뒤 이것만 적용돼야 한다."""
from alembic import op
import sqlalchemy as sa

revision = "s0002"
down_revision = "s0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("thing") as b:
        b.add_column(sa.Column("note", sa.String(50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("thing") as b:
        b.drop_column("note")
'''


def _service_dir(tmp_path: Path, *revisions: str) -> Path:
    d = tmp_path / "migrations"
    (d / "versions").mkdir(parents=True)
    (d / "env.py").write_text("from nova_common.migrate import run_env\n\nrun_env()\n", encoding="utf-8")
    for i, src in enumerate(revisions, 1):
        (d / "versions" / f"{i:04d}_t.py").write_text(src, encoding="utf-8")
    return d


def _thing_base(with_note: bool = False):
    class Base(nova_db.NovaBase):
        pass

    class Thing(Base):
        __tablename__ = "thing"
        id: Mapped[str] = mapped_column(String(36), primary_key=True)
        name: Mapped[str] = mapped_column(String(50))
        if with_note:
            note: Mapped[str | None] = mapped_column(String(50), nullable=True)

    nova_db.add_infra_tables(Base)
    return Base


def _legacy_base():
    """create_all 시절 옛 DB 모양 — 이름 규칙 없는 DeclarativeBase + p0001 당시 outbox · processed_event(이름 없는 UNIQUE).

    옛 DB 는 baseline(p0001)으로 stamp 되므로 지금 모델이 아니라 그때 모양으로 만들어야 뒤 리비전(p0002 …)을 시험할 수 있다."""
    from datetime import datetime

    from sqlalchemy import JSON, Boolean, DateTime, Text
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):
        pass

    class Thing(Base):
        __tablename__ = "thing"
        id: Mapped[str] = mapped_column(String(36), primary_key=True)
        name: Mapped[str] = mapped_column(String(50))

    class Outbox(Base):
        __tablename__ = "outbox"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        event_id: Mapped[str] = mapped_column(String(40), unique=True)
        topic: Mapped[str] = mapped_column(String(120), index=True)
        key: Mapped[str] = mapped_column(String(80))
        payload: Mapped[dict] = mapped_column(JSON)
        created_at: Mapped[datetime] = mapped_column(DateTime)
        sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
        attempts: Mapped[int] = mapped_column(Integer, default=0)
        last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
        parked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    class ProcessedEvent(Base):
        __tablename__ = "processed_event"
        event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
        consumer: Mapped[str] = mapped_column(String(80), primary_key=True)
        topic: Mapped[str] = mapped_column(String(120))
        ok: Mapped[bool] = mapped_column(Boolean, default=True)
        at: Mapped[datetime] = mapped_column(DateTime)

    return Base


def _versions(db) -> set[str]:
    with db.engine.connect() as c:
        return {r[0] for r in c.execute(text("SELECT version_num FROM alembic_version"))}


def test_upgrade_empty_db(tmp_path):
    db = nova_db.Database("t-mig", "sqlite://")
    Base = _thing_base()
    mdir = _service_dir(tmp_path, S0001)
    migrate.upgrade(db, Base, mdir)
    tables = set(inspect(db.engine).get_table_names())
    assert {"outbox", "processed_event", "thing", "alembic_version"} <= tables
    assert _versions(db) == {P_HEAD, "s0001"}  # 플랫폼 · 서비스 분기 heads 둘 다
    migrate.upgrade(db, Base, mdir)  # 다시 불러도 그대로(기동마다 불린다)
    st = migrate.status(db, Base, mdir)
    assert st["current"] == st["heads"] == [P_HEAD, "s0001"] and st["up_to_date"] and not st["legacy"]


def test_upgrade_platform_only_without_service_dir():
    db = nova_db.Database("t-mig-p", "sqlite://")
    Base = _thing_base()
    migrate.upgrade(db, Base, None)
    assert {"outbox", "processed_event"} <= set(inspect(db.engine).get_table_names())
    assert "thing" not in inspect(db.engine).get_table_names()  # 서비스 표는 서비스 분기 몫
    assert _versions(db) == {P_HEAD}


def test_upgrade_stamps_legacy_create_all_db(tmp_path):
    """create_all 로 만든 옛 DB(alembic_version 없음) — baseline stamp 뒤 그 다음 마이그레이션만 적용, 행 보존."""
    db = nova_db.Database("t-legacy", f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    old = _legacy_base()
    db.create_all(old)
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO thing (id, name) VALUES ('a', '옛 행')"))
        c.execute(text("INSERT INTO outbox (event_id, topic, key, payload, created_at, attempts, parked) VALUES ('e1', 't', 'k', '{}', '2026-11-04 00:00:00', 0, 0)"))
    assert migrate.status(db, old, _service_dir(tmp_path / "x", S0001))["legacy"]
    new = _thing_base(with_note=True)
    migrate.upgrade(db, new, _service_dir(tmp_path, S0001, S0002))
    assert _versions(db) == {P_HEAD, "s0002"}
    assert "note" in {c["name"] for c in inspect(db.engine).get_columns("thing")}
    with db.engine.connect() as c:
        assert c.execute(text("SELECT name FROM thing WHERE id='a'")).scalar_one() == "옛 행"
        assert c.execute(text("SELECT count(*) FROM outbox")).scalar_one() == 1


def test_platform_migration_matches_models():
    """플랫폼 분기(p0001 …)로 만든 outbox · processed_event 가 add_infra_tables 모델과 차이 0."""
    db = nova_db.Database("t-mig-cmp", "sqlite://")
    Base = _thing_base()
    migrate.upgrade(db, Base, None)
    infra = nova_db.NovaBase.metadata.__class__(naming_convention=nova_db.NAMING_CONVENTION)
    for name in ("outbox", "processed_event"):
        Base.metadata.tables[name].to_metadata(infra)
    with db.engine.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), infra)
    diff = [d for d in diff if not (d[0] == "remove_table" and d[1].name == "alembic_version")]
    assert diff == []


def test_platform_downgrade_removes_tables():
    db = nova_db.Database("t-mig-down", "sqlite://")
    Base = _thing_base()
    migrate.upgrade(db, Base, None)
    migrate.downgrade(db, Base, None, "platform@base")
    assert not {"outbox", "processed_event"} & set(inspect(db.engine).get_table_names())


# ---------------------------------------------------------------- p0002 처리 기록 중복 제거 키 (T03-3.01)
UQ_KEY = "uq_processed_event_consumer_idempotency_key"


def _pe_columns(db) -> dict:
    return {c["name"]: c for c in inspect(db.engine).get_columns("processed_event")}


def _pe_uniques(db) -> dict:
    return {u["name"]: u["column_names"] for u in inspect(db.engine).get_unique_constraints("processed_event")}


def test_p0002_adds_column_and_unique():
    db = nova_db.Database("t-p0002", "sqlite://")
    migrate.upgrade(db, _thing_base(), None)
    cols = _pe_columns(db)
    assert "idempotency_key" in cols and cols["idempotency_key"]["nullable"]
    assert _pe_uniques(db)[UQ_KEY] == ["consumer", "idempotency_key"]
    ins = "INSERT INTO processed_event (event_id, consumer, topic, idempotency_key, {cols}) VALUES (:e, 'c', 't', :k, 1, '2026-11-04 00:00:00')"
    names = "is_ok, processed_at" if "processed_at" in cols else "ok, at"
    with db.engine.begin() as c:
        c.execute(text(ins.format(cols=names)), {"e": "e1", "k": None})
        c.execute(text(ins.format(cols=names)), {"e": "e2", "k": None})  # 빈 키(옛 행)는 여럿이어도 된다
        c.execute(text(ins.format(cols=names)), {"e": "e3", "k": "같은키"})
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with db.engine.begin() as c:
            c.execute(text(ins.format(cols=names)), {"e": "e4", "k": "같은키"})


def test_p0002_downgrade_removes_column_and_unique():
    db = nova_db.Database("t-p0002-down", "sqlite://")
    migrate.upgrade(db, _thing_base(), None)
    migrate.downgrade(db, _thing_base(), None, "p0001")
    assert "idempotency_key" not in _pe_columns(db) and UQ_KEY not in _pe_uniques(db)
    assert _versions(db) == {"p0001"}


def test_p0002_on_legacy_db_keeps_rows_and_outbox_unique(tmp_path):
    """옛 create_all DB(이름 없는 UNIQUE(outbox.event_id)) — stamp 뒤 플랫폼 리비전을 올려도 행 · UNIQUE 가 남는다."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    db = nova_db.Database("t-legacy-p", f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    db.create_all(_legacy_base())
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO processed_event (event_id, consumer, topic, ok, at) VALUES ('e1', 'c', 't', 1, '2026-11-04 00:00:00')"))
        c.execute(text("INSERT INTO outbox (event_id, topic, key, payload, created_at, attempts, parked) VALUES ('o1', 't', 'k', '{}', '2026-11-04 00:00:00', 0, 0)"))
    migrate.upgrade(db, _thing_base(), None)
    assert _versions(db) == {P_HEAD}
    with db.engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM processed_event WHERE event_id='e1' AND idempotency_key IS NULL")).scalar_one() == 1
        assert c.execute(text("SELECT count(*) FROM outbox")).scalar_one() == 1
    with pytest.raises(IntegrityError):  # outbox.event_id UNIQUE 가 batch 표 복사 뒤에도 살아 있다
        with db.engine.begin() as c:
            c.execute(text("INSERT INTO outbox (event_id, topic, key, payload, created_at, attempts, {p}) VALUES ('o1', 't', 'k', '{{}}', '2026-11-04 00:00:00', 0, 0)".format(
                p="is_parked" if "is_parked" in {x["name"] for x in inspect(db.engine).get_columns("outbox")} else "parked")))


# ---------------------------------------------------------------- p0003 칸 이름 규약 맞추기 (T03-3.06 · ADR-012 D3)
def _cols(db, table) -> set[str]:
    return {c["name"] for c in inspect(db.engine).get_columns(table)}


def test_p0003_renames_platform_columns():
    db = nova_db.Database("t-p0003", "sqlite://")
    migrate.upgrade(db, _thing_base(), None)
    assert {"is_parked"} <= _cols(db, "outbox") and "parked" not in _cols(db, "outbox")
    assert {"is_ok", "processed_at"} <= _cols(db, "processed_event") and not {"ok", "at"} & _cols(db, "processed_event")
    assert "ix_outbox_is_parked" in {i["name"] for i in inspect(db.engine).get_indexes("outbox")}
    assert _pe_uniques(db)[UQ_KEY] == ["consumer", "idempotency_key"]  # p0002 제약은 표 복사 뒤에도 남는다


def test_p0003_downgrade_restores_old_names():
    db = nova_db.Database("t-p0003-down", "sqlite://")
    migrate.upgrade(db, _thing_base(), None)
    migrate.downgrade(db, _thing_base(), None, "p0002")
    assert "parked" in _cols(db, "outbox") and "is_parked" not in _cols(db, "outbox")
    assert {"ok", "at"} <= _cols(db, "processed_event") and not {"is_ok", "processed_at"} & _cols(db, "processed_event")
    assert "ix_outbox_parked" in {i["name"] for i in inspect(db.engine).get_indexes("outbox")}
    assert _versions(db) == {"p0002"}


def test_p0003_legacy_db_keeps_values_and_unnamed_unique(tmp_path):
    """옛 create_all DB — 이름 없는 UNIQUE(outbox.event_id) 가 batch 표 복사(naming_convention) 뒤에도 남고 값이 새 칸으로 옮겨진다.

    되돌리면(downgrade) 옛 칸 이름으로 값이 돌아오고 UNIQUE 도 남는다."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    db = nova_db.Database("t-p0003-legacy", f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    db.create_all(_legacy_base())
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO outbox (event_id, topic, key, payload, created_at, attempts, parked) VALUES ('o1', 't', 'k', '{}', '2026-11-04 00:00:00', 3, 1)"))
        c.execute(text("INSERT INTO processed_event (event_id, consumer, topic, ok, at) VALUES ('e1', 'c', 't', 1, '2026-11-04 01:02:03')"))
    migrate.upgrade(db, _thing_base(), None)
    with db.engine.connect() as c:
        assert c.execute(text("SELECT is_parked, attempts FROM outbox WHERE event_id='o1'")).one() == (1, 3)
        assert c.execute(text("SELECT is_ok, processed_at FROM processed_event WHERE event_id='e1'")).one() == (1, "2026-11-04 01:02:03")
    dup = "INSERT INTO outbox (event_id, topic, key, payload, created_at, attempts, {p}) VALUES ('o1', 't', 'k', '{{}}', '2026-11-04 00:00:00', 0, 0)"
    with pytest.raises(IntegrityError):
        with db.engine.begin() as c:
            c.execute(text(dup.format(p="is_parked")))
    # batch 에 naming_convention 을 주어 이름 없던 UNIQUE 에 규칙 이름이 붙는다 → 옛 DB 도 모델과 차이 0(제약 이름 포함)
    assert {u["name"] for u in inspect(db.engine).get_unique_constraints("outbox")} == {"uq_outbox_event_id"}
    assert migrate.drift(db, _thing_base()) == []
    migrate.downgrade(db, _thing_base(), None, "p0001")
    with db.engine.connect() as c:
        assert c.execute(text("SELECT parked FROM outbox WHERE event_id='o1'")).scalar_one() == 1
        assert c.execute(text("SELECT ok, at FROM processed_event WHERE event_id='e1'")).one() == (1, "2026-11-04 01:02:03")
    with pytest.raises(IntegrityError):
        with db.engine.begin() as c:
            c.execute(text(dup.format(p="parked")))


# ---------------------------------------------------------------- Service.init_db (T03-2.05)
def test_init_db_uses_migrations_when_present(tmp_path):
    from nova_common.service import Service


    class SBase(nova_db.NovaBase):
        pass

    class Thing(SBase):
        __tablename__ = "thing"
        id: Mapped[str] = mapped_column(String(36), primary_key=True)
        name: Mapped[str] = mapped_column(String(50))

    seen = []
    svc = Service("t-init", SBase, "t", db_url="sqlite://", migrations_dir=_service_dir(tmp_path, S0001))
    svc.seed(lambda s: seen.append(s.get(Thing, "x")))  # 시드는 마이그레이션 뒤에 돈다(표가 있어야 조회된다)
    svc.init_db()
    assert _versions(svc.db) == {P_HEAD, "s0001"} and seen == [None]


def test_init_db_without_migrations_keeps_create_all():
    """migrations 폴더가 없는 서비스(게이트웨이 · 테스트 Base)는 예전대로 create_all — alembic_version 을 만들지 않는다."""
    from nova_common.service import Service

    class GBase(nova_db.NovaBase):
        pass

    svc = Service("t-init-gw", GBase, "t", db_url="sqlite://")
    assert svc.migrations_dir is None
    svc.init_db()
    tables = set(inspect(svc.db.engine).get_table_names())
    assert {"outbox", "processed_event"} <= tables and "alembic_version" not in tables


# ---------------------------------------------------------------- p0004 중복 제거 키 칸 넓히기 (T03-9.04 · 사용자 결정 2026-11-04 (A))
def test_idempotency_key_column_fits_longest_default_key():
    """기본 키 `{source}:{topic}:{key}:{event_id}` 의 최대 길이가 칸에 들어간다 — 넘치면 MariaDB 엄격 모드에서 DLQ 로 간다.

    각 부분의 상한은 모델 칸 길이에서 읽는다(source 는 소비자 칸 길이 — 서비스 이름이 소비자 이름이다)."""
    from nova_common.ids import new_id

    Base = _thing_base()
    pe, ob = Base.metadata.tables["processed_event"], Base.metadata.tables["outbox"]
    longest = f"{'s' * pe.c.consumer.type.length}:{'t' * ob.c.topic.type.length}:{'k' * ob.c.key.type.length}:{new_id()}"
    assert len(longest) <= pe.c.idempotency_key.type.length


def test_p0004_widens_idempotency_key_and_downgrade_restores():
    db = nova_db.Database("t-p0004", "sqlite://")
    migrate.upgrade(db, _thing_base(), None)
    col = next(c for c in inspect(db.engine).get_columns("processed_event") if c["name"] == "idempotency_key")
    assert col["type"].length == 320
    assert _pe_uniques(db)[UQ_KEY] == ["consumer", "idempotency_key"]  # 넓힌 뒤에도 UNIQUE 는 남는다
    migrate.downgrade(db, _thing_base(), None, "p0003")
    col = next(c for c in inspect(db.engine).get_columns("processed_event") if c["name"] == "idempotency_key")
    assert col["type"].length == 200 and _versions(db) == {"p0003"}
