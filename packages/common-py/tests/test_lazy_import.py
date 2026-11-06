"""nova_common 지연 적재 — 공개 이름은 그대로 import 되고, 무거운 의존성은 필요할 때만 불린다."""
import subprocess
import sys

import pytest

PUBLIC = [
    "Service", "create_service", "Principal", "ApiError", "principal",
    "Envelope", "EventBus", "InMemoryBus", "make_bus", "emit",
    "id_column", "new_id", "ref_column", "catalog", "runtime",
]


def _run(code: str) -> str:
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        stdin=subprocess.DEVNULL, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.mark.parametrize("name", PUBLIC)
def test_public_name_imports(name):
    import nova_common

    assert getattr(nova_common, name) is not None
    assert name in nova_common.__all__
    assert name in dir(nova_common)
    exec(f"from nova_common import {name}")


def test_all_lists_exactly_public_names():
    import nova_common

    assert sorted(nova_common.__all__) == sorted(PUBLIC)


def test_unknown_name_raises_attribute_error():
    import nova_common

    with pytest.raises(AttributeError):
        nova_common.no_such_name  # noqa: B018


def test_bare_import_does_not_load_heavy_deps():
    out = _run(
        "import sys, nova_common; "
        "print([m for m in ('fastapi','sqlalchemy','prometheus_client') if m in sys.modules])"
    )
    assert out == "[]"


def test_catalog_only_does_not_load_heavy_deps():
    out = _run(
        "import sys; from nova_common import catalog; "
        "print([m for m in ('fastapi','sqlalchemy') if m in sys.modules])"
    )
    assert out == "[]"


def test_service_access_loads_fastapi():
    out = _run("import sys; from nova_common import Service; print('fastapi' in sys.modules)")
    assert out == "True"
