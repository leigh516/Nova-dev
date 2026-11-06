"""라우팅 · 인증 · 권한(RBAC) · 기능 플래그(점검 503) · 레이트리밋 · 프록시.

요청 흐름: 레이트리밋 → JWT 검증(실패 401) → 라우트(services.json routes, 없으면 404) → 권한 검사(<모듈>.<행위>)
→ 플래그 OFF 경로 503 → 업스트림 프록시.
- 클라이언트가 보낸 X-User-* 헤더는 항상 제거하고 게이트웨이가 검증한 값으로만 다시 넣는다(스푸핑 방지)
- `/internal/...` 은 서비스끼리만 쓰는 계약 API — 게이트웨이는 절대 바깥으로 넘기지 않는다
"""
from __future__ import annotations

import json
import logging
import math
import os
import posixpath
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from nova_common import auth as jwt
from nova_common import catalog, clients, context, runtime
from nova_common.context import ACTOR_TYPES

log = logging.getLogger("gateway")
HERE = Path(__file__).resolve().parent

METHOD_ACTION = {"GET": "read", "HEAD": "read", "POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}
# 게이트웨이 자체 API 의 권한
OWN_PERMS = {"/ops/monitoring": "ops.read"}
SPOOFABLE = ("x-user-id", "x-role", "x-roles", "x-tenant", "x-user-name", "x-actor-type")
HOP = {"host", "content-length", "connection", "keep-alive", "transfer-encoding", "authorization", "accept-encoding", "cookie"}
TOKEN_COOKIE = os.getenv("GW_TOKEN_COOKIE", "nova_token")


def load_json(env: str, default: str) -> dict:
    return json.loads(Path(os.getenv(env) or HERE / default).read_text(encoding="utf-8"))


_JSON_CACHE: dict[Path, tuple[int, int, dict]] = {}  # 경로 → (수정 시각 ns, 크기, 파싱 결과)


def load_json_cached(env: str, default: str) -> dict:
    """load_json 과 같되, 파일의 수정 시각 · 크기가 그대로면 지난 파싱 결과를 돌려준다(T04-6.08 — 메뉴는 요청마다 읽힌다).

    돌려준 dict 는 공유되므로 고치지 않는다(읽기만)."""
    p = Path(os.getenv(env) or HERE / default)
    st = p.stat()
    hit = _JSON_CACHE.get(p)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2]
    data = json.loads(p.read_text(encoding="utf-8"))
    _JSON_CACHE[p] = (st.st_mtime_ns, st.st_size, data)
    return data


def error(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, **extra}})


def is_internal(path: str) -> bool:
    return path == "/internal" or path.startswith("/internal/")


def unsafe_path(path: str) -> bool:
    """디코드된 경로에 점 조각(. · ..) · 빈 조각 · 백슬래시 · NUL 이 있으면 참 — 이런 경로는 라우트하지 않는다(404).

    Starlette 는 `%2e%2e` 를 `..` 로 디코드해 넘기고, 프록시(httpx)는 `..` 를 정규화한다 — 그대로 두면
    `/sample/%2e%2e/internal/x` 가 권한 · /internal 검사는 `/sample/...` 로 통과하고 업스트림에는 `/internal/x` 로 닿는다.
    """
    if "\\" in path or "\x00" in path:
        return True
    if posixpath.normpath(path) != path:
        return True
    return any(seg in ("", ".", "..") for seg in path.split("/")[1:])


# ------------------------------------------------------------------ 권한키
_OVERRIDES: list[tuple[re.Pattern, str]] | None = None


def overrides() -> list[tuple[re.Pattern, str]]:
    global _OVERRIDES
    if _OVERRIDES is None:
        _OVERRIDES = [(re.compile(o["pattern"]), o["action"]) for o in load_json("GW_RBAC_FILE", "rbac.json").get("overrides", [])]
    return _OVERRIDES


def required_perm(path: str, method: str) -> str | None:
    """/v1 을 뗀 경로 · 메서드 → 권한키 `<모듈>.<행위>`. 라우트가 없으면 None."""
    target = catalog.route_for(path)
    if target is None:
        return None
    spec = catalog.get(target)
    module = spec.perm or spec.name
    action = next((a for p, a in overrides() if p.search(path)), None) or METHOD_ACTION.get(method.upper(), "read")
    return f"{module}.{action}"


def perm_matches(granted: frozenset[str] | set[str], perm: str) -> bool:
    """'*' = 전부, 'sample.*' = 모듈 전체."""
    if "*" in granted or perm in granted:
        return True
    module = perm.split(".", 1)[0]
    return f"{module}.*" in granted


# ------------------------------------------------------------------ 인증
@dataclass
class Caller:
    user_id: str | None = None
    role: str = "guest"
    tenant: str | None = None
    name: str | None = None
    roles: list[str] = field(default_factory=list)
    effective: bool = False  # True 면 x-roles 로 서비스에 전달(권한 검사를 통과한 유효 역할)
    actor_type: str = "human"  # human | ai | system — 감사 분리(STD-AX)

    def headers(self) -> dict[str, str]:
        if not self.user_id:
            return {"x-role": "guest"}
        h = {"x-user-id": self.user_id, "x-role": self.role, "x-actor-type": self.actor_type}
        if self.tenant:
            h["x-tenant"] = str(self.tenant)
        if self.name:
            h["x-user-name"] = quote(self.name)  # 헤더는 ASCII — 서비스에서 unquote
        if self.effective and self.roles:
            h["x-roles"] = ",".join(self.roles)
        return h


class AuthError(Exception):
    pass


def client_ip(request: Request) -> str:
    """레이트리밋 키용 클라이언트 IP. X-Forwarded-For 의 맨 왼쪽 값은 클라이언트가 위조할 수 있으므로
    신뢰 홉 수(GW_TRUSTED_HOPS)만큼 오른쪽에서 고른다. 기본 0 = XFF 를 무시하고 TCP 상대(request.client.host)를 쓴다."""
    peer = request.client.host if request.client else "?"
    try:
        hops = int(os.getenv("GW_TRUSTED_HOPS", "0"))
    except ValueError:
        hops = 0
    if hops <= 0:
        return peer
    chain = [x.strip() for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()] + [peer]
    return chain[-(hops + 1)] if len(chain) > hops else chain[0]


def authenticate(request: Request) -> Caller:
    h = request.headers.get("authorization", "")
    token = h[7:] if h.lower().startswith("bearer ") else request.cookies.get(TOKEN_COOKIE, "")
    if not token:
        return Caller()
    try:
        c = jwt.decode(token)
    except jwt.InvalidToken as e:
        raise AuthError(str(e)) from e
    actor_type = c.get("actor_type", "human")
    if actor_type not in ACTOR_TYPES:  # 모르는 행위자는 감사 분리(STD-AX-001)를 깨므로 받지 않는다
        raise AuthError(f"모르는 actor_type: {actor_type!r}")
    role = c.get("role", "user")
    return Caller(user_id=c.get("sub"), role=role, tenant=c.get("tenant"), name=c.get("name"),
                  roles=list(c.get("roles") or [role]), actor_type=actor_type)


# ------------------------------------------------------------------ 권한(RBAC) 표
class RbacCache:
    """역할 → 권한 표.

    - 파일 모드(기본): `rbac.json`(GW_RBAC_FILE) — 역할 정본
    - 서비스 모드: GW_RBAC_SERVICE=<서비스> 의 `/internal/rbac` 를 TTL(30초) 캐시. 같은 모양 + grants(사용자별 추가 역할) ·
      bases(사용자별 기본 역할 대체) · blocked(차단 사용자). 장애 시 마지막 표를 GW_RBAC_STALE(300초)까지 쓰고, 그 뒤엔 닫는다(fail-closed)
    - 토큰의 roles 는 믿지 않는다(빼앗은 역할이 토큰에 남으므로) — 기본 역할 + 표가 준 추가 역할만
    """

    def __init__(self, ttl: float | None = None, stale: float | None = None, retry: float | None = None):
        self.ttl = ttl if ttl is not None else float(os.getenv("GW_RBAC_TTL", "30"))
        self.stale = stale if stale is not None else float(os.getenv("GW_RBAC_STALE", "300"))
        # 원천 실패 뒤 이 시간 동안은 다시 부르지 않는다(음성 캐시) — 장애 중 매 요청이 2초씩 기다리지 않게
        self.retry = retry if retry is not None else float(os.getenv("GW_RBAC_RETRY", "10"))
        self.reset()

    def reset(self) -> None:
        self.table: dict | None = None
        self.fetched_at = 0.0
        self.failed_at: float | None = None
        self.dirty = False

    def invalidate(self) -> None:
        self.dirty = True
        self.failed_at = None  # 변경 이벤트 = 원천이 살아 있다 → 바로 다시 받는다

    @staticmethod
    def _normalize(t: dict) -> dict:
        roles = {r: frozenset(v["perms"] if isinstance(v, dict) else v) for r, v in t["roles"].items()}
        return {
            "roles": roles,
            "grants": {u: tuple(r) for u, r in t.get("grants", {}).items()},
            "bases": dict(t.get("bases", {})),
            "blocked": frozenset(t.get("blocked", [])),
        }

    async def get(self) -> dict | None:
        service = os.getenv("GW_RBAC_SERVICE")
        now = time.monotonic()
        if self.table is not None and not self.dirty and (not service or now - self.fetched_at < self.ttl):
            return self.table
        if self.failed_at is not None and now - self.failed_at < self.retry:
            return self._fallback(now)
        try:
            raw = await clients.call(service, "GET", "/internal/rbac", timeout=2.0) if service else load_json("GW_RBAC_FILE", "rbac.json")
            self.table = self._normalize(raw)
            self.fetched_at, self.dirty, self.failed_at = now, False, None
        except Exception as e:
            log.warning("권한 표 갱신 실패(%s초 동안 다시 시도하지 않음): %s", self.retry, e)
            self.failed_at = now
            return self._fallback(now)
        return self.table

    def _fallback(self, now: float) -> dict | None:
        """원천 장애 중 — 마지막 표를 stale 까지만 쓰고, 그 뒤엔 닫는다(fail-closed)."""
        if self.table is None or now - self.fetched_at > self.stale:
            return None
        return self.table

    def roles_of(self, t: dict, caller: Caller) -> list[str]:
        if not caller.user_id:
            return ["guest"]
        base = t["bases"].get(caller.user_id, caller.role)
        return [base, *[r for r in t["grants"].get(caller.user_id, ()) if r != base]]

    async def allowed(self, caller: Caller, perm: str | None) -> bool:
        """메뉴 표시용 — 오류 없이 참/거짓."""
        if perm is None:
            return True
        t = await self.get()
        if t is None:
            return False
        roles = self.roles_of(t, caller)
        return runtime.super_role() in roles or any(perm_matches(t["roles"].get(r, frozenset()), perm) for r in roles)

    async def check(self, caller: Caller, perm: str) -> JSONResponse | None:
        t = await self.get()
        if t is None:
            # 권한 없음(403)이 아니라 원천 일시 장애 — 닫는 것(fail-closed)은 그대로, 상태 코드만 의미대로(ADR-012 P10).
            # Retry-After 는 음성 캐시 시간: 그 전에 다시 와도 원천을 부르지 않으므로 같은 503 만 받는다
            resp = error(503, "rbac_unavailable", "권한 정보를 확인할 수 없어 잠시 막았습니다. 잠시 후 다시 시도하세요", perm=perm)
            resp.headers["retry-after"] = str(max(1, math.ceil(self.retry)))
            return resp
        if caller.user_id and caller.user_id in t["blocked"]:
            return error(403, "forbidden_user", "이용이 제한된 계정입니다. 관리자에게 문의하세요")
        roles = self.roles_of(t, caller)
        if runtime.super_role() in roles or any(perm_matches(t["roles"].get(r, frozenset()), perm) for r in roles):
            if caller.user_id:
                caller.roles, caller.effective = roles, True
            return None
        if not caller.user_id:
            return error(401, "unauthenticated", "로그인이 필요합니다", perm=perm)
        return error(403, "forbidden_perm", f"이 기능을 쓸 권한이 없습니다 ({perm}). 필요하면 관리자에게 권한을 요청하세요", perm=perm)


rbac = RbacCache()


# ------------------------------------------------------------------ 기능 플래그 · 메뉴
class FlagCache:
    """기능 플래그 — 파일 모드(menu.json features) 또는 GW_FLAGS_SERVICE 의 `/internal/features`(TTL 캐시, 장애 시 마지막 값)."""

    def __init__(self, ttl: float | None = None, retry: float | None = None):
        self.ttl = ttl if ttl is not None else float(os.getenv("GW_FLAG_TTL", "30"))
        self.retry = retry if retry is not None else float(os.getenv("GW_FLAG_RETRY", "10"))  # 실패 뒤 다시 부르지 않는 시간
        self.flags: list[dict] = []
        self.loaded_at = 0.0
        self.failed_at: float | None = None

    def invalidate(self) -> None:
        self.loaded_at = 0.0
        self.failed_at = None

    async def get(self) -> list[dict]:
        service = os.getenv("GW_FLAGS_SERVICE")
        now = time.monotonic()
        if (self.flags or self.loaded_at) and (not service or now - self.loaded_at < self.ttl):
            return self.flags
        if service and self.failed_at is not None and now - self.failed_at < self.retry:
            return self.flags  # 음성 캐시 — 장애 중 매 요청 2초 대기 방지
        try:
            self.flags = await clients.call(service, "GET", "/internal/features", timeout=2.0) if service \
                else load_json("GW_MENU_FILE", "menu.json").get("features", [])
            self.loaded_at, self.failed_at = now, None
        except Exception as e:  # 이전 값으로 계속 서비스(가용성 우선)
            log.warning("기능 플래그 갱신 실패(%s초 동안 다시 시도하지 않음): %s", self.retry, e)
            self.failed_at = now
        return self.flags

    async def blocked(self, path: str) -> dict | None:
        for f in await self.get():
            if not f.get("enabled", True) and any(path == p or path.startswith(p.rstrip("/") + "/") for p in f.get("api_prefixes") or []):
                return f
        return None

    async def menu(self, channel: str, caller: Caller) -> dict:
        items = []
        for it in load_json_cached("GW_MENU_FILE", "menu.json").get("items", []):  # 파싱만 캐시 — 권한은 아래에서 요청마다
            if channel in it.get("channels", [channel]) and await rbac.allowed(caller, it.get("perm")):
                items.append({k: it.get(k) for k in ("key", "label", "icon", "path")})
        flags_ = await self.get()
        maint = [{"key": f["key"], "label": f["label"], "message": f.get("maintenance_msg") or "점검 중입니다"} for f in flags_ if not f.get("enabled", True)]
        return {"channel": channel, "items": items, "maintenance": maint, "features": {f["key"]: bool(f.get("enabled", True)) for f in flags_}}


flags = FlagCache()


# ------------------------------------------------------------------ 레이트리밋 (토큰 버킷)
@dataclass
class Bucket:
    tokens: float
    at: float = field(default_factory=time.monotonic)


class RateLimiter:
    def __init__(self, rps: float | None = None, burst: float | None = None, max_buckets: int | None = None):
        self.rps = rps if rps is not None else float(os.getenv("GW_RATE_RPS", "20"))
        self.burst = burst if burst is not None else float(os.getenv("GW_RATE_BURST", "60"))
        self.max_buckets = max_buckets if max_buckets is not None else int(os.getenv("GW_RATE_MAX_BUCKETS", "50000"))
        self.buckets: dict[str, Bucket] = {}  # 삽입 순서 = 최근 사용 순서(LRU)

    def allow(self, key: str) -> tuple[bool, float]:
        now = time.monotonic()
        b = self.buckets.pop(key, None)  # 다시 넣어 맨 뒤(가장 최근)로 보낸다
        if b is None:
            b = Bucket(tokens=self.burst, at=now)
        self.buckets[key] = b
        # 메모리 상한 — 전체를 비우면 키를 많이 만들어 남의 버킷까지 리셋할 수 있으니 가장 오래 안 쓴 것부터 지운다
        while len(self.buckets) > self.max_buckets:
            del self.buckets[next(iter(self.buckets))]
        b.tokens = min(self.burst, b.tokens + (now - b.at) * self.rps)
        b.at = now
        if b.tokens >= 1:
            b.tokens -= 1
            return True, 0.0
        return False, (1 - b.tokens) / self.rps


limiter = RateLimiter()


# ------------------------------------------------------------------ 프록시
async def proxy(request: Request, path: str, caller: Caller, request_id: str) -> Response:
    target = None if is_internal(path) or unsafe_path(path) else catalog.route_for(path)
    if target is None:
        return error(404, "no_route", f"없는 주소입니다: /v1{path}")
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP and k.lower() not in SPOOFABLE}
    headers.update(caller.headers())
    headers["x-request-id"] = request_id
    body = await request.body()
    try:
        # 서비스마다 공유 클라이언트 — 요청마다 새 연결(TCP 핸드셰이크)을 열지 않는다(T04-6.06). 닫지 않는다: 종료 때 aclose_all
        r = await clients.pooled(target).request(request.method, path, params=list(request.query_params.multi_items()),
                                                 content=body or None, headers=headers,
                                                 timeout=float(os.getenv("GW_UPSTREAM_TIMEOUT", "5")))
    except httpx.TimeoutException:
        return error(504, "upstream_timeout", "서버 응답이 늦어지고 있습니다. 잠시 후 다시 시도하세요", service=target)
    except httpx.HTTPError as e:
        log.warning("업스트림 %s 연결 오류: %s", target, e)
        return error(502, "upstream_unavailable", "서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요", service=target)
    out = {k: v for k, v in r.headers.items() if k.lower() not in ("content-length", "transfer-encoding", "connection", "content-encoding")}
    out["x-request-id"] = request_id
    out["x-upstream"] = target
    return Response(content=r.content, status_code=r.status_code, headers=out)


def new_request_id(request: Request) -> str:
    """요청 ID — 규칙은 context.trace_from_header 한 곳(형식 밖 · 없음이면 새 UUIDv7).

    정한 ID 를 요청 헤더에도 다시 심는다. 안쪽 공통 미들웨어(Service.request_context)가 이 헤더로 컨텍스트를 채우므로,
    심지 않으면 형식 밖 · 없는 헤더일 때 거기서 또 다른 새 ID 를 만들어 게이트웨이 자신의 서비스 호출
    (권한 · 플래그 원천)이 응답과 다른 ID 로 나간다."""
    rid = context.trace_from_header(request.headers.get("x-request-id"))
    raw = [(k, v) for k, v in request.scope["headers"] if k.lower() != b"x-request-id"]
    request.scope["headers"] = [*raw, (b"x-request-id", rid.encode())]
    return rid
