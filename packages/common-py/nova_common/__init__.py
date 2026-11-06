"""Nova 공통 라이브러리 (packages/common-py).

모든 마이크로서비스가 같은 규칙으로 동작하도록 하는 최소 공통 기반:
- service.py   : FastAPI 서비스 팩토리 (/healthz · /readyz · /metrics · 오류 규약 · GW 헤더 인증 컨텍스트)
- events.py    : 이벤트 봉투(Envelope) + EventBus 인터페이스 (Kafka 운영 / InMemory 테스트)
- outbox.py    : 트랜잭셔널 아웃박스 + 릴레이, 멱등 소비(processed_event) · 재시도 · DLQ
- db.py        : 서비스 전용 DB (교차 스키마 금지) — SQLite(로컬) / MariaDB(k3s)
- metrics.py   : Prometheus 메트릭 (RED · 이벤트 · 아웃박스 · 사가 · 비즈니스 KPI)
- auth.py      : HS256 JWT (Core identity 발급 · GW 검증)
- clients.py   : 서비스 간 동기 호출 클라이언트 레지스트리
- catalog.py   : services.json(서비스 목록 단일 원천) · 게이트웨이 라우트
- paging.py    : 목록 API 계약(page · size · sort · q → items · total)
- runtime.py   : 실행 환경 · 운영 안전장치 · 개발 기능 등록
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

# 지연 적재(PEP 562) — `from nova_common import catalog` 같은 스크립트 쪽 사용이
# fastapi · sqlalchemy · prometheus 를 끌어오지 않게 한다(하위 프로세스마다 6~8초 절감).
# 공개 이름은 처음 접근할 때 해당 모듈에서 가져와 캐시한다.
_LAZY = {
    "Service": ".service", "create_service": ".service", "Principal": ".service",
    "ApiError": ".service", "principal": ".service",
    "Envelope": ".events", "EventBus": ".events", "InMemoryBus": ".events", "make_bus": ".events",
    "emit": ".outbox",
    "id_column": ".ids", "new_id": ".ids", "ref_column": ".ids",
}
_SUBMODULES = ("catalog", "runtime")

__all__ = [*_LAZY, *_SUBMODULES]

if TYPE_CHECKING:  # 타입 검사 · IDE 자동완성용 — 실행 시에는 불러오지 않는다
    from . import catalog, runtime  # noqa: F401
    from .events import Envelope, EventBus, InMemoryBus, make_bus  # noqa: F401
    from .ids import id_column, new_id, ref_column  # noqa: F401
    from .outbox import emit  # noqa: F401
    from .service import ApiError, Principal, Service, create_service, principal  # noqa: F401


def __getattr__(name: str):
    if name in _LAZY:
        value = getattr(importlib.import_module(_LAZY[name], __name__), name)
    elif name in _SUBMODULES:
        value = importlib.import_module(f".{name}", __name__)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value  # 다음 접근부터는 일반 속성
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
