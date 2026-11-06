"""기동 마이그레이션 잠금(T07-1.01 · review_261105_02 B1) — 복제본 둘이 동시에 기동해도 DDL 은 한 번만.

MariaDB 는 `GET_LOCK('<서비스>:migrate', 초)` 로 감싸고 끝나면 `RELEASE_LOCK`. 못 얻으면 시간 초과 뒤 기동 실패.
SQLite(로컬 · 테스트)는 잠금 SQL 을 내지 않는다. 실제 MariaDB 없이 방언 분기만 단위로 본다.
"""
from __future__ import annotations

import pytest

from nova_common import migrate


class _Dialect:
    def __init__(self, name: str):
        self.name = name


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConn:
    """실행한 SQL 과 인자를 적어 두는 가짜 연결 — GET_LOCK 응답(1 · 0 · None)을 고를 수 있다."""

    def __init__(self, dialect: str, got=1):
        self.dialect = _Dialect(dialect)
        self.got = got
        self.calls: list[tuple[str, dict]] = []

    def execute(self, stmt, params=None):
        sql = str(stmt)
        self.calls.append((sql, dict(params or {})))
        if "GET_LOCK" in sql:
            return _Result(self.got)
        return _Result(1)


@pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
def test_lock_wraps_with_get_and_release(dialect):
    conn = _FakeConn(dialect)
    with migrate.migration_lock(conn, "sample", timeout=7):
        assert len(conn.calls) == 1  # 안에서는 잠금만 얻은 상태
    sqls = [c[0] for c in conn.calls]
    assert "GET_LOCK" in sqls[0] and "RELEASE_LOCK" in sqls[1]
    assert conn.calls[0][1] == {"name": "sample:migrate", "timeout": 7}
    assert conn.calls[1][1] == {"name": "sample:migrate"}


def test_lock_released_even_when_migration_fails():
    conn = _FakeConn("mysql")
    with pytest.raises(ValueError):
        with migrate.migration_lock(conn, "sample", timeout=1):
            raise ValueError("마이그레이션 실패 흉내")
    assert "RELEASE_LOCK" in conn.calls[-1][0]


@pytest.mark.parametrize("got", [0, None])
def test_lock_timeout_refuses_start(got, caplog):
    """못 얻으면(0 = 시간 초과, NULL = 오류) 마이그레이션을 하지 않고 기동 실패 — 한국어 로그와 함께."""
    conn = _FakeConn("mysql", got=got)
    ran = []
    with pytest.raises(RuntimeError, match="마이그레이션 잠금"):
        with migrate.migration_lock(conn, "sample", timeout=3):
            ran.append(1)
    assert ran == []
    assert not any("RELEASE_LOCK" in c[0] for c in conn.calls)  # 얻지 못한 잠금은 풀지 않는다
    assert any("마이그레이션 잠금" in r.getMessage() for r in caplog.records)


def test_sqlite_no_lock_sql():
    conn = _FakeConn("sqlite")
    with migrate.migration_lock(conn, "sample", timeout=3):
        pass
    assert conn.calls == []


def test_lock_timeout_from_env(monkeypatch):
    monkeypatch.setenv("NOVA_MIGRATE_LOCK_TIMEOUT", "42")
    conn = _FakeConn("mysql")
    with migrate.migration_lock(conn, "sample"):
        pass
    assert conn.calls[0][1]["timeout"] == 42


def test_upgrade_takes_lock(monkeypatch):
    """upgrade() 가 실제로 잠금 안에서 돈다 — SQLite 에서도 잠금 함수를 거친다(SQL 은 내지 않음)."""
    from nova_common.db import Database, NovaBase, add_infra_tables

    class Base(NovaBase):
        pass

    add_infra_tables(Base)
    db = Database("lock-svc", "sqlite://")
    seen = []
    real = migrate.migration_lock

    def spy(conn, service, timeout=None):
        seen.append(service)
        return real(conn, service, timeout)

    monkeypatch.setattr(migrate, "migration_lock", spy)
    migrate.upgrade(db, Base)
    assert seen == ["lock-svc"]
