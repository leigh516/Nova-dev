"""모든 서비스 Base 가 제약 이름 규칙(NovaBase)을 따른다 — ADR-011 · REQ-261104-11-1.

DB 가 임의로 지은 제약 이름은 DB 마다 달라 마이그레이션으로 지우거나 바꿀 수 없다. 그래서 서비스 카탈로그의 모든 서비스와
서비스 템플릿이 NovaBase 를 상속하고, 실제로 만든 표의 인덱스 · UNIQUE · FK 이름이 규칙 접두어를 갖는지 본다."""
import importlib
import os
import re
from pathlib import Path

from sqlalchemy import create_engine, inspect

import devstack
from nova_common import catalog
from nova_common.db import NAMING_CONVENTION, NovaBase

ROOT = Path(__file__).resolve().parents[1]


def _service_bases():
    for n in catalog.names():  # 이름만 import 할 뿐 DB 에 붙지 않게 메모리 DB 로
        os.environ.setdefault("DATABASE_URL_" + catalog.get(n).env, "sqlite://")
    devstack._paths()
    return {n: importlib.import_module(f"{catalog.get(n).package}.main").svc.Base for n in catalog.names()}


def test_all_service_constraints_named():
    bases = _service_bases()
    assert bases, "서비스 카탈로그가 비었다"
    for name, Base in bases.items():
        assert issubclass(Base, NovaBase), f"{name}: Base 가 nova_common.db.NovaBase 를 상속하지 않는다"
        assert Base.metadata.naming_convention == NAMING_CONVENTION, f"{name}: 제약 이름 규칙이 없다"
        eng = create_engine("sqlite://")
        Base.metadata.create_all(eng)
        ins = inspect(eng)
        for table in ins.get_table_names():
            for i in ins.get_indexes(table):
                assert i["name"].startswith(f"ix_{table}_"), f"{name}.{table}: 인덱스 이름 {i['name']}"
            for u in ins.get_unique_constraints(table):
                assert (u["name"] or "").startswith(f"uq_{table}_"), f"{name}.{table}: UNIQUE 이름 {u['name']}"
            for f in ins.get_foreign_keys(table):
                assert (f["name"] or "").startswith(f"fk_{table}_"), f"{name}.{table}: FK 이름 {f['name']}"


def test_template_base_is_nova_base():
    text = (ROOT / "services/_template/__PKG__/models.py").read_text(encoding="utf-8")
    assert "class Base(NovaBase):" in text
    assert re.search(r"^from nova_common\.db import .*\bNovaBase\b", text, re.M)
