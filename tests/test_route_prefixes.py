"""라우터 접두어 = services.json routes (REQ-261104-11-10).

게이트웨이는 services.json 의 routes 접두어로만 서비스에 넘긴다. 서비스가 그 밖에 라우트를 두면 바깥에서 닿지 않는 죽은 API 가 되고,
접두어에 라우트가 하나도 없으면 게이트웨이 표에만 있는 빈 경로가 된다. 둘 다 여기서 잡는다.
대상 밖: 헬스 · 지표(/healthz /readyz /metrics) · FastAPI 문서 경로 · `/internal`(서비스 간 계약 API — 게이트웨이를 거치지 않는다).
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

from fastapi import APIRouter, FastAPI

import devstack
from nova_common import catalog

ROOT = Path(__file__).resolve().parents[1]
INFRA_PATHS = {"/healthz", "/readyz", "/metrics"}


def _under(path: str, prefix: str) -> bool:
    prefix = prefix.rstrip("/") or "/"
    return prefix == "/" or path == prefix or path.startswith(prefix + "/")


def route_paths(app: FastAPI) -> list[str]:
    """앱의 모든 라우트 경로. FastAPI 0.16x 는 include_router 한 라우터를 감싼 채 두므로(effective_route_contexts) 펼친다."""
    out = []
    for r in app.routes:
        if hasattr(r, "effective_route_contexts"):
            out += [c.path for c in r.effective_route_contexts()]
        elif getattr(r, "path", None) is not None:
            out.append(r.path)
        else:
            raise AssertionError(f"경로를 읽을 수 없는 라우트 형식: {type(r).__name__} — 이 검사를 FastAPI 판에 맞게 고친다")
    return out


def prefix_violations(app: FastAPI, prefixes: tuple[str, ...]) -> list[str]:
    """접두어 밖 라우트 · 라우트 없는 접두어 목록(비면 정상)."""
    skip = INFRA_PATHS | {u for u in (app.docs_url, app.redoc_url, app.openapi_url, app.swagger_ui_oauth2_redirect_url) if u}
    paths = [p for p in route_paths(app) if p not in skip and not _under(p, "/internal")]
    out = [f"접두어 밖 라우트: {p}" for p in paths if not any(_under(p, pre) for pre in prefixes)]
    out += [f"라우트가 없는 접두어: {pre}" for pre in prefixes if not any(_under(p, pre) for p in paths)]
    if not prefixes:
        out.append("services.json routes 가 비었다")
    return out


def _service_apps() -> dict[str, FastAPI]:
    names = [n for n in catalog.names() if n != catalog.gateway()]
    for n in names:  # import 만 할 뿐 DB 에 붙지 않게 메모리 DB 로
        os.environ.setdefault("DATABASE_URL_" + catalog.get(n).env, "sqlite://")
    devstack._paths()
    return {n: importlib.import_module(f"{catalog.get(n).package}.main").app for n in names}


def test_service_routes_match_catalog_prefixes():
    apps = _service_apps()
    assert apps, "업무 서비스가 카탈로그에 없다"
    bad = {n: v for n, app in apps.items() if (v := prefix_violations(app, catalog.get(n).routes))}
    assert not bad, f"services.json routes 와 라우터 접두어가 어긋난다: {bad}"


def test_template_router_prefix_is_service_route():
    """새 서비스는 routes ["/<이름>"] 로 등록된다(new_service.py) — 템플릿 라우터 접두어도 같아야 한다."""
    text = (ROOT / "services/_template/__PKG__/records.py").read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/__SERVICE__")' in text
    assert 'route = f"/{name}"' in (ROOT / "scripts/new_service.py").read_text(encoding="utf-8")


def test_wrong_prefix_fake_service_fails():
    """접두어를 틀리게 한 가짜 서비스 — 밖 라우트와 빈 접두어를 둘 다 잡아야 한다."""
    app = FastAPI()
    router = APIRouter(prefix="/orders")
    router.add_api_route("/items", lambda: {}, methods=["GET"])
    app.include_router(router)
    app.add_api_route("/healthz", lambda: {}, methods=["GET"])
    app.add_api_route("/internal/sync", lambda: {}, methods=["POST"])
    assert prefix_violations(app, ("/order",)) == ["접두어 밖 라우트: /orders/items", "라우트가 없는 접두어: /order"]
    assert prefix_violations(app, ("/orders",)) == []  # 맞추면 통과 — 헬스 · /internal 은 대상 밖
    assert prefix_violations(app, ("/orders", "/billing")) == ["라우트가 없는 접두어: /billing"]
    assert prefix_violations(app, ()) == ["접두어 밖 라우트: /orders/items", "services.json routes 가 비었다"]
