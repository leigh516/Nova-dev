"""단일 프로세스 개발 서버 — Kafka·Docker 없이 전체 백엔드를 :8080 하나로 띄운다.

    python nova.py run                               # GW = http://127.0.0.1:8080/v1/...
    DEV_MEMORY_DB=1 uv run python scripts/dev_server.py   # 매번 깨끗한 메모리 DB
    HOST=0.0.0.0 uv run python scripts/dev_server.py      # 같은 망의 실기기에서 붙을 때만(기본은 이 PC 에서만 접속)

서비스 경계(자기 DB·이벤트·계약 API)는 그대로이고, 전송만 InMemoryBroker·ASGI 로 바뀐다.
바깥에 열리는 것은 게이트웨이뿐이다(운영과 같은 경계):
- 각 서비스는 /svc/<name>/metrics 만 노출한다(Prometheus 로컬 스크레이프용). 서비스 앱 전체를 마운트하지 않는다 —
  마운트하면 게이트웨이의 인증 · 권한 · 테넌트 검사를 건너뛰고 서비스 API 를 직접 부를 수 있다
- 게이트웨이의 /internal/* (예: /internal/alertmanager)은 이 PC(루프백)에서 온 요청만 받는다
  (서비스 간 계약 호출은 HTTP 가 아니라 ASGI 트랜스포트로 직접 연결되므로 영향 없음)
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request, Response  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from nova_common import catalog  # noqa: E402

DEFAULT_HOST = "127.0.0.1"


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host in ("localhost", "testclient"):  # testclient = Starlette TestClient 의 가상 주소
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _metrics_only(name: str, app) -> FastAPI:
    """서비스 앱의 /metrics 만 그대로 전달하는 작은 앱 — 그 밖의 경로는 404."""
    sub = FastAPI(title=f"{name} metrics", openapi_url=None, docs_url=None, redoc_url=None)

    @sub.get("/metrics", include_in_schema=False)
    async def metrics():
        import httpx

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://svc") as c:
            r = await c.get("/metrics")
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

    return sub


def build_root(services: dict, gw, broker=None) -> FastAPI:
    """개발 서버 루트 앱 구성 — 서비스는 /svc/<name>/metrics 만, 나머지는 게이트웨이. 테스트에서 직접 부른다."""

    @asynccontextmanager
    async def lifespan(_app):
        for svc in services.values():
            await svc.startup(start_relay=True)

        async def drain_loop():
            while True:
                await broker.drain()
                await asyncio.sleep(0.05)

        t = asyncio.create_task(drain_loop()) if broker is not None else None
        yield
        if t:
            t.cancel()
        for svc in services.values():
            await svc.shutdown()

    root = FastAPI(title="Nova dev stack", lifespan=lifespan)

    @root.middleware("http")
    async def internal_loopback_only(request: Request, call_next):
        p = request.url.path
        if (p == "/internal" or p.startswith("/internal/")) and not _is_loopback(request.client.host if request.client else None):
            return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "찾을 수 없는 경로입니다"}})
        return await call_next(request)

    for name, svc in services.items():
        if name != catalog.gateway():
            root.mount(f"/svc/{name}", _metrics_only(name, svc.app))
    root.mount("/", gw)
    return root


def create_app() -> FastAPI:
    import devstack

    os.environ.setdefault("NOVA_SKIP_LIFESPAN", "1")  # 하위 앱 lifespan 대신 여기서 일괄 기동
    services, broker, gw = devstack.build(memory_db=os.getenv("DEV_MEMORY_DB") == "1")
    return build_root(services, gw, broker)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host=os.getenv("HOST", DEFAULT_HOST), port=int(os.getenv("PORT", "8080")), log_level="info")
