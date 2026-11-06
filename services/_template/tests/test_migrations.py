"""__SERVICE__ — 마이그레이션(플랫폼 + 서비스 분기)이 모델과 같다(ADR-011). 모델을 바꾸면 `python nova.py migrate __SERVICE__ new "<설명>"`."""
from nova_common import migrate
from nova_common.db import Database

from __PKG__.main import svc


def test_service_uses_migrations():
    assert svc.migrations_dir is not None and (svc.migrations_dir / "env.py").exists()


def test_migrations_match_models():
    db = Database("__SERVICE__-migration-check", "sqlite://")
    migrate.upgrade(db, svc.Base, svc.migrations_dir)
    assert migrate.drift(db, svc.Base) == [], "모델과 마이그레이션이 다르다 — python nova.py migrate __SERVICE__ new \"<설명>\""
    st = migrate.status(db, svc.Base, svc.migrations_dir)
    assert st["up_to_date"] and any(r.startswith("p") for r in st["current"])  # 플랫폼 분기도 올라갔다(번호는 플랫폼 판본마다 다르다)


def test_downgrade_service_branch():
    db = Database("__SERVICE__-migration-down", "sqlite://")
    migrate.upgrade(db, svc.Base, svc.migrations_dir)
    migrate.downgrade(db, svc.Base, svc.migrations_dir, "service@base")
    assert "s0001" not in migrate.status(db, svc.Base, svc.migrations_dir)["current"]
