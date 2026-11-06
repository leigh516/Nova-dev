"""__SERVICE__ 진입점 — `__PKG__.main:app` (app 과 svc 를 반드시 export)."""
from . import records
from .app import app, svc

for m in (records,):
    app.include_router(m.router)

__all__ = ["app", "svc"]
