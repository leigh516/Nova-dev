"""아웃박스 릴레이 행 잠금(T07-1.02 · review_261105_02 B2) — 복제본 여럿이 같은 DB 를 볼 때 한 행은 한 릴레이만 보낸다.

MariaDB · PostgreSQL: 미발행 행을 `SELECT … FOR UPDATE SKIP LOCKED` 로 집는다 — 다른 릴레이가 잡고 있는 행은 건너뛴다.
SQLite: 행 잠금이 없어 그대로(로컬 · 테스트는 복제본 하나). 실제 DB 없이 방언별 SQL 과 릴레이가 그 SQL 을 쓰는지 본다.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.dialects import mysql, postgresql, sqlite

from nova_common.db import NovaBase
from nova_common.service import Service


class Base(NovaBase):
    pass


svc = Service("relay-lock", Base, "릴레이 잠금", db_url="sqlite://")


def _sql(dialect_name: str, dialect) -> str:
    return str(svc._pending_outbox(10, dialect_name).compile(dialect=dialect)).upper()


@pytest.mark.parametrize("name,dialect", [("mysql", mysql.dialect()), ("mariadb", mysql.dialect()),
                                          ("postgresql", postgresql.dialect())])
def test_pending_rows_skip_locked_on_server_db(name, dialect):
    assert "FOR UPDATE SKIP LOCKED" in _sql(name, dialect)


def test_pending_rows_no_lock_on_sqlite():
    assert "FOR UPDATE" not in _sql("sqlite", sqlite.dialect())


def test_flush_uses_engine_dialect(monkeypatch):
    """릴레이는 연결된 DB 의 방언으로 문장을 만든다 — 방언 판단을 호출 쪽이 빠뜨리지 않게."""
    seen = []
    real = svc._pending_outbox

    def spy(limit, dialect_name):
        seen.append(dialect_name)
        return real(limit, dialect_name)

    monkeypatch.setattr(svc, "_pending_outbox", spy)
    svc.db.create_all(Base)
    asyncio.run(svc.flush_outbox())
    assert seen == ["sqlite"]
