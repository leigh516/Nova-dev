"""서비스 간 동기 호출 클라이언트.

규칙(ARCHITECTURE 0.3): 앱/웹 → GW → 서비스, 사업 서비스 → 역량/플랫폼 API(계약 고정)만 동기 허용.
사업 ↔ 사업은 이벤트만. 주소는 `SVC_<NAME>_URL`(예: SVC_CAP_DEAL_URL) 또는 k3s 서비스 DNS 기본값.
테스트에서는 override()로 ASGI 트랜스포트를 꽂아 실제 네트워크 없이 서비스끼리 연결한다.
요청이 잦은 경로(GW 프록시 · 메트릭 수집)는 pooled()로 서비스마다 하나인 연결 풀을 재사용하고, 종료 때 aclose_all()로 닫는다.
"""
from __future__ import annotations

import asyncio
import os

import httpx

from . import context

_overrides: dict[str, httpx.AsyncBaseTransport] = {}


def base_url(service: str) -> str:
    env = "SVC_" + service.upper().replace("-", "_") + "_URL"
    return os.getenv(env) or f"http://{service}:8000"


def override(service: str, transport: httpx.AsyncBaseTransport) -> None:
    _overrides[service] = transport


def clear_overrides() -> None:
    _overrides.clear()


class UpstreamError(Exception):
    """상대 서비스가 4xx · 5xx 로 답했다. Service 의 오류 처리기가 응답으로 바꾼다(T07-1.04 · B4):
    4xx → 같은 상태 · 상대 봉투 그대로(사용자에게 원래 문구), 5xx → 502 upstream_error."""

    def __init__(self, service: str, status: int, body: object):
        super().__init__(f"{service} 가 {status} 로 응답했습니다: {body}")
        self.service = service
        self.status = status
        self.body = body


class UpstreamUnavailable(UpstreamError):
    """상대 서비스에 닿지 못했다(연결 거부 · 끊김) — 응답 502 upstream_unavailable. status 는 그 응답 상태."""

    def __init__(self, service: str, reason: object):
        super().__init__(service, 502, reason)


class UpstreamTimeout(UpstreamError):
    """상대 서비스가 제때 답하지 않았다 — 응답 504 upstream_timeout. status 는 그 응답 상태."""

    def __init__(self, service: str, reason: object):
        super().__init__(service, 504, reason)


async def call(
    service: str,
    method: str,
    path: str,
    *,
    json: object | None = None,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 3.0,
) -> object:
    """서비스 간 동기 호출 — 공유 연결 `pooled(service)` 를 쓴다(호출마다 새 연결을 열지 않는다 · B4).

    2xx → 본문(JSON, 비면 None). 4xx · 5xx → UpstreamError, 시간 초과 → UpstreamTimeout, 연결 실패 → UpstreamUnavailable.
    잡지 않으면 Service 가 각각 같은 상태(4xx) · 502 · 504 봉투로 답한다."""
    try:
        r = await pooled(service).request(method, path, json=json, params=params,
                                          headers={**context.headers(), **(headers or {})}, timeout=timeout)
    except httpx.TimeoutException as e:
        raise UpstreamTimeout(service, repr(e)) from e
    except httpx.TransportError as e:
        raise UpstreamUnavailable(service, repr(e)) from e
    if r.status_code >= 400:
        try:
            body = r.json()
        except ValueError:
            body = r.text
        raise UpstreamError(service, r.status_code, body)
    return r.json() if r.content else None


POOL_TIMEOUT = 5.0  # 공유 클라이언트 기본 시간 제한 — 호출마다 request(..., timeout=) 로 덮어쓴다

# 서비스 → (클라이언트, 만들 때의 override 트랜스포트, 주소, 이벤트 루프)
_pool: dict[str, tuple[httpx.AsyncClient, httpx.AsyncBaseTransport | None, str, object]] = {}


def _loop() -> object:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def pooled(service: str) -> httpx.AsyncClient:
    """서비스마다 하나인 공유 클라이언트 — 연결 풀(keep-alive)을 요청 사이에 재사용한다(plan_REQ_04 P7 · T04-6.05).

    `async with` 로 닫지 않는다(닫으면 풀이 사라진다). 프로세스 종료 때 `aclose_all()` 이 한 번에 닫는다.
    아래가 바뀌면 옛 객체를 쓰지 않고 새로 만든다:
    - override 트랜스포트(테스트가 갈아 끼움 — override 가 늘 이긴다)
    - 주소(SVC_<NAME>_URL)
    - 이벤트 루프(연결은 만든 루프에 묶인다 — 테스트 클라이언트는 요청마다 루프가 다를 수 있다)
    """
    transport = _overrides.get(service)
    url = "http://" + service if transport else base_url(service)
    loop = _loop()
    hit = _pool.get(service)
    if hit and not hit[0].is_closed and hit[1] is transport and hit[2] == url and hit[3] is loop:
        return hit[0]
    c = httpx.AsyncClient(base_url=url, transport=transport, timeout=POOL_TIMEOUT)
    _pool[service] = (c, transport, url, loop)
    return c


async def aclose_all() -> None:
    """공유 클라이언트를 모두 닫는다(서비스 종료 시). 다음 pooled() 는 새로 만든다.

    다른 이벤트 루프에서 만든 것은 그 루프에서만 닫을 수 있으므로 목록에서만 뺀다(연결은 그 루프와 함께 정리된다)."""
    loop = _loop()
    items = list(_pool.values())
    _pool.clear()
    for c, _t, _u, owner in items:
        if owner is loop and not c.is_closed:
            await c.aclose()


def http_client(service: str, timeout: float = 5.0) -> httpx.AsyncClient:
    """원시 응답이 필요한 호출(GW 프록시·메트릭 수집)용. override가 있으면 ASGI 트랜스포트로 연결."""
    transport = _overrides.get(service)
    return httpx.AsyncClient(base_url="http://" + service if transport else base_url(service), transport=transport, timeout=timeout)
