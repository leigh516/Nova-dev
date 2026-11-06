"""sample 진입점 — `sample.main:app` (devstack · 카탈로그 테스트가 app 과 svc 를 찾는다)."""
from . import items
from .app import app, svc

for m in (items,):
    app.include_router(m.router)

__all__ = ["app", "svc"]
