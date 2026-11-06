"""gateway 골격 — 상태 없는 게이트웨이. DB 는 공통 인프라 테이블(멱등 소비 기록)용 메모리 SQLite."""
import os
from contextlib import asynccontextmanager

from nova_common import clients
from nova_common.db import NovaBase
from nova_common.service import Service


class Base(NovaBase):  # 제약 이름 규칙(ADR-011) — migrations 폴더가 없으니 create_all 그대로
    pass


svc = Service("gateway", Base, "Nova Gateway", db_url=os.getenv("DATABASE_URL_GATEWAY", "sqlite://"))
app = svc.app

_service_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _lifespan(a):
    """공통 수명 주기를 그대로 돌고, 끝날 때 프록시 · 수집이 쓰던 공유 연결 풀을 닫는다(T04-6.06).

    NOVA_SKIP_LIFESPAN 이어도 닫는다 — 풀은 서비스 기동과 무관하게 요청이 만들기 때문이다."""
    try:
        async with _service_lifespan(a):
            yield
    finally:
        await clients.aclose_all()


app.router.lifespan_context = _lifespan
