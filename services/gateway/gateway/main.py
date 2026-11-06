"""gateway — 클라이언트(웹 · 모바일 앱)의 유일한 진입점. /v1/* 만 공개한다.

라우팅 표는 services.json 의 routes, 권한 표는 rbac.json(또는 GW_RBAC_SERVICE), 메뉴 · 플래그는 menu.json(또는 GW_FLAGS_SERVICE).
"""
from __future__ import annotations

import inspect
import json
import os
import time

import httpx
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ValidationError

from nova_common import Envelope, catalog, runtime
from nova_common import auth as jwt
from nova_common.validate import Email

from . import monitoring
from .app import app, svc
from .routing import (
    OWN_PERMS,
    TOKEN_COOKIE,
    AuthError,
    Caller,
    authenticate,
    client_ip,
    error,
    flags,
    is_internal,
    limiter,
    load_json,
    log,
    new_request_id,
    proxy,
    rbac,
    required_perm,
    unsafe_path,
)

GW_DEV_LOGIN = runtime.register_dev_feature("GW_DEV_LOGIN", "게이트웨이 개발용 로그인(dev_users.json)")
CORS_ORIGINS = [o for o in os.getenv("GW_CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",") if o]
COOKIE_PATH = "/v1"
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")
COOKIE_SETTING_PATHS = ("/v1/auth/login", "/v1/auth/logout")
# 쿠키 수명 = 토큰 수명. 숫자를 새로 박지 않고 발급 함수(nova_common.auth.encode)의 기본 수명을 그대로 쓴다
TOKEN_TTL_SECONDS: int = inspect.signature(jwt.encode).parameters["ttl_seconds"].default


def check_cors_origins(origins: list[str]) -> None:
    """쿠키는 늘 발급하므로 CORS 허용 목록에 `*` 가 있으면 기동을 거부한다(자격 증명 쿠키 + 전체 허용은 위험 — ADR-014)."""
    if "*" in origins:
        raise RuntimeError("GW_CORS_ORIGINS 에 '*' 를 쓸 수 없습니다 — 쿠키 인증은 허용할 출처를 정확히 나열해야 합니다")


check_cors_origins(CORS_ORIGINS)


def cookie_secure() -> bool:
    """Secure 속성 — GW_COOKIE_SECURE(true/1 · false/0)가 있으면 그 값, 없으면 운영(NOVA_ENV=prod)일 때 켠다."""
    raw = os.getenv("GW_COOKIE_SECURE", "").strip().lower()
    if raw in ("true", "1"):
        return True
    if raw in ("false", "0"):
        return False
    return runtime.is_prod()


def set_token_cookie(resp: Response, token: str) -> None:
    """로그인 응답에 인증 쿠키를 심는다(HttpOnly · SameSite=Lax · Path=/v1 · Max-Age=토큰 수명)."""
    resp.set_cookie(TOKEN_COOKIE, token, max_age=TOKEN_TTL_SECONDS, path=COOKIE_PATH, httponly=True,
                    samesite="lax", secure=cookie_secure())


def clear_token_cookie(resp: Response) -> None:
    """심을 때와 같은 이름 · 경로 · 속성으로 Max-Age=0 을 내려 브라우저가 쿠키를 지우게 한다."""
    resp.set_cookie(TOKEN_COOKIE, "", max_age=0, path=COOKIE_PATH, httponly=True, samesite="lax", secure=cookie_secure())


# 권한 · 플래그가 바뀌었다는 이벤트를 받으면 캐시를 바로 다시 받는다(토픽은 해당 서비스가 생길 때 kafka-topics.txt 에 등록).
# 방송 — 캐시는 복제본마다 따로 있으므로 모든 복제본이 받아야 한다(그룹 `gateway.<instance>`, REQ-261104-11-4).
# 일반 구독이면 그룹 'gateway' 하나라 복제본 하나만 무효화되고 나머지는 TTL 까지 낡은 권한으로 응답한다.
@svc.on("platform.feature.changed", broadcast=True)
def on_flag_changed(_s, _env: Envelope):
    flags.invalidate()


@svc.on("platform.rbac.changed", broadcast=True)
def on_rbac_changed(_s, _env: Envelope):
    rbac.invalidate()


@app.middleware("http")
async def gateway(request: Request, call_next):
    """레이트리밋 · 인증 · 요청 ID · CORS. 실제 라우팅은 각 엔드포인트/프록시가 한다."""
    path = request.url.path
    origin = request.headers.get("origin", "")
    cors = {"access-control-allow-origin": origin, "access-control-allow-credentials": "true", "vary": "Origin"} \
        if origin in CORS_ORIGINS or "*" in CORS_ORIGINS else {}
    if request.method == "OPTIONS" and path.startswith("/v1/"):
        return JSONResponse({}, headers={**cors, "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE",
                                         "access-control-allow-headers": "authorization,content-type,x-request-id",
                                         "access-control-max-age": "600"})
    if not path.startswith("/v1/"):
        return await call_next(request)
    rid = new_request_id(request)
    # 로그인 CSRF — 쿠키를 심고 지우는 경로는 익명이어도 Origin 이 있으면 허용 목록이어야 한다.
    # Origin 이 아예 없는 요청(모바일 앱 · 서버 간 호출)은 브라우저 교차 출처 폼이 아니므로 통과
    if request.method == "POST" and path in COOKIE_SETTING_PATHS and origin and origin not in CORS_ORIGINS:
        return error(403, "csrf_origin", "허용되지 않은 출처의 요청입니다. 서비스 화면에서 다시 시도하세요")
    try:
        caller = authenticate(request)
    except AuthError as e:
        log.info("토큰 거부(%s %s): %s", request.method, path, e)  # 사유는 로그로만 — 화면 문구는 한국어 안내만
        if path == "/v1/auth/logout":  # 깨진 · 만료 쿠키 때문에 로그아웃이 막히면 쿠키를 지울 길이 없다
            request.state.caller, request.state.rid = Caller(), rid
            resp = await call_next(request)
            resp.headers["x-request-id"] = rid
            resp.headers.update(cors)  # 다른 출처 웹이 응답을 읽을 수 있게 정상 경로와 같이 CORS 를 붙인다
            return resp
        resp = error(401, "invalid_token", "로그인이 만료되었거나 올바르지 않습니다. 다시 로그인하세요")
        resp.headers.update(cors)
        return resp
    # CSRF — 쿠키로 인증된 쓰기만 Origin 이 허용 목록이어야 한다(Bearer 는 브라우저가 자동으로 붙이지 않으므로 면제, ADR-014)
    if (caller.user_id and request.method in WRITE_METHODS and request.cookies.get(TOKEN_COOKIE)
            and not request.headers.get("authorization", "").lower().startswith("bearer ") and origin not in CORS_ORIGINS):
        resp = error(403, "csrf_origin", "허용되지 않은 출처의 요청입니다. 서비스 화면에서 다시 시도하세요")
        resp.headers.update(cors)
        return resp
    ok, retry = limiter.allow(caller.user_id or f"ip:{client_ip(request)}")  # XFF 는 신뢰 홉 수만큼만(GW_TRUSTED_HOPS)
    if not ok:
        resp = error(429, "rate_limited", "요청이 너무 많습니다. 잠시 후 다시 시도하세요", retry_after=round(retry, 2))
        resp.headers.update(cors)
        return resp
    request.state.caller, request.state.rid = caller, rid
    resp = await call_next(request)
    resp.headers["x-request-id"] = rid
    for k, v in cors.items():
        resp.headers[k] = v
    return resp


def caller_of(request: Request) -> Caller:
    return getattr(request.state, "caller", Caller())


# ------------------------------------------------------------------ 게이트웨이 자체 API
@app.get("/v1/menu")
async def menu(request: Request, channel: str = "web"):
    """호출자 권한으로 거른 메뉴 + 점검 중 기능."""
    return await flags.menu(channel, caller_of(request))


@app.get("/v1/me")
async def me(request: Request):
    c = caller_of(request)
    if not c.user_id:
        return error(401, "unauthenticated", "로그인이 필요합니다")
    return {"id": c.user_id, "name": c.name, "role": c.role, "tenant": c.tenant}


class LoginIn(BaseModel):
    """개발 로그인 입력 — 이메일 규칙은 공통 한 곳(nova_common.validate.Email: 공백 제거 · 소문자 · 254자 · 형식)."""

    email: Email
    password: str | None = None  # 비밀번호 틀림 · 없음은 형식 오류가 아니라 401 invalid_credentials


@app.post("/v1/auth/login")
async def dev_login(request: Request):
    """개발용 로그인. /auth 경로를 소유한 서비스(iam 등)가 있으면 그쪽으로 넘긴다."""
    if catalog.route_for("/auth/login"):
        resp = await proxy(request, "/auth/login", caller_of(request), getattr(request.state, "rid", ""))
        if 200 <= resp.status_code < 300:  # 성공 응답 본문의 token 으로 쿠키를 심는다 — 본문은 그대로 돌려준다
            try:
                tok = json.loads(resp.body).get("token")
            except (ValueError, AttributeError):  # JSON 이 아니거나 객체가 아니면 쿠키 없이 그대로
                tok = None
            if isinstance(tok, str) and tok:
                set_token_cookie(resp, tok)
        return resp
    if not runtime.dev_feature(GW_DEV_LOGIN):
        return error(404, "no_route", "로그인 서비스가 없습니다")
    # text/plain 등 '단순 요청' 폼 전송으로 다른 사이트가 로그인을 일으키지 못하게 JSON 만 받는다(로그인 CSRF)
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return error(415, "unsupported_media_type", "JSON 형식으로 보내 주세요")
    try:
        body = await request.json()
    except ValueError:  # 본문이 JSON 이 아니면 빈 입력으로 — 아래 검증이 422 칸 오류로 알려 준다
        body = {}
    try:
        cred = LoginIn.model_validate(body if isinstance(body, dict) else {})
    except ValidationError as e:
        # 서비스 공통 422 처리기(nova_common.service)에 맡긴다 — 본문 칸이므로 loc 앞에 body 를 붙여 FastAPI 모양과 같게
        raise RequestValidationError([{**x, "loc": ("body", *x["loc"])} for x in e.errors()]) from e
    data = load_json("GW_DEV_USERS_FILE", "dev_users.json")
    user = next((u for u in data["users"] if u["email"] == cred.email), None)
    if user is None or cred.password != data["password"]:
        return error(401, "invalid_credentials", "이메일 또는 비밀번호가 맞지 않습니다")
    token = jwt.encode({"sub": user["id"], "role": user["role"], "name": user["name"], "tenant": user.get("tenant")})
    resp = JSONResponse({"token": token, "user": {k: user.get(k) for k in ("id", "email", "name", "role", "tenant")}})
    set_token_cookie(resp, token)  # 본문 token 은 모바일 · 이행기 웹용으로 유지(ADR-014)
    return resp


@app.post("/v1/auth/logout")
async def logout():
    """인증 쿠키를 지운다. 비로그인이어도 204 — 이미 로그아웃된 상태가 목표 상태이므로 오류가 아니다."""
    resp = Response(status_code=204)
    clear_token_cookie(resp)
    return resp


async def _ops(request: Request) -> Caller | JSONResponse:
    c = caller_of(request)
    p = request.url.path.removeprefix("/v1")
    g = await rbac.check(c, next(v for k, v in OWN_PERMS.items() if p.startswith(k)))
    return g or c


@app.get("/v1/ops/monitoring/overview")
async def mon_overview(request: Request):
    c = await _ops(request)
    if isinstance(c, JSONResponse):
        return c
    return await monitoring.overview()


RECENT_NOTIFICATIONS: list[dict] = []


@app.get("/v1/ops/monitoring/alerts")
async def mon_alerts(request: Request):
    c = await _ops(request)
    if isinstance(c, JSONResponse):
        return c
    if monitoring.prom_url():
        try:
            data = await monitoring.prom("/api/v1/alerts", {})
            return {"source": "prometheus", "alerts": [
                {"name": a["labels"].get("alertname"), "severity": a["labels"].get("severity", ""),
                 "service": a["labels"].get("service", a["labels"].get("job", "")),
                 "summary": a.get("annotations", {}).get("summary", ""), "state": a.get("state")}
                for a in data.get("alerts", [])]}
        except Exception as e:  # Prometheus 장애 → 직접 수집으로
            log.warning("Prometheus 알림 조회 실패 — 직접 수집으로 대신합니다: %s", e)
    ov = await monitoring.overview()
    return {"source": ov["source"], "alerts": ov["alerts"], "recent": RECENT_NOTIFICATIONS[:20]}


@app.post("/internal/alertmanager", include_in_schema=False)
async def alertmanager_webhook(request: Request):
    """Alertmanager 웹훅 수신(클러스터 내부 전용 — 인그레스는 /v1 만 노출). 운영 화면 알림 이력으로 보여 준다."""
    body = await request.json()
    for a in body.get("alerts", []):
        RECENT_NOTIFICATIONS.insert(0, {"name": a.get("labels", {}).get("alertname"), "severity": a.get("labels", {}).get("severity"),
                                        "status": a.get("status"), "summary": a.get("annotations", {}).get("summary", ""), "at": a.get("startsAt")})
    del RECENT_NOTIFICATIONS[100:]
    return {"ok": True}


@app.get("/v1/ops/monitoring/query")
async def mon_query(request: Request, q: str):
    c = await _ops(request)
    if isinstance(c, JSONResponse):
        return c
    if not monitoring.prom_url():
        return error(503, "prometheus_unavailable", "Prometheus 가 설정되지 않았습니다(PROMETHEUS_URL). 개요는 직접 수집으로 볼 수 있습니다")
    try:
        return await monitoring.prom("/api/v1/query", {"query": q})
    except (httpx.HTTPError, RuntimeError) as e:
        return error(502, "prometheus_error", str(e)[:200])


@app.get("/v1/ops/monitoring/range")
async def mon_range(request: Request, q: str, minutes: int = 30, step: int = 15):
    c = await _ops(request)
    if isinstance(c, JSONResponse):
        return c
    if not monitoring.prom_url():
        return error(503, "prometheus_unavailable", "Prometheus 가 설정되지 않았습니다(PROMETHEUS_URL)")
    end = time.time()
    try:
        return await monitoring.prom("/api/v1/query_range", {"query": q, "start": end - max(1, min(minutes, 1440)) * 60,
                                                             "end": end, "step": max(5, step)})
    except (httpx.HTTPError, RuntimeError) as e:
        return error(502, "prometheus_error", str(e)[:200])


# ------------------------------------------------------------------ 프록시 (마지막에 등록)
@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def passthrough(path: str, request: Request):
    p = "/" + path
    if unsafe_path(p) or is_internal(p):  # %2e%2e 등으로 /internal · /metrics 에 닿는 우회 차단
        return error(404, "no_route", f"없는 주소입니다: /v1{p}")
    perm = required_perm(p, request.method)
    if perm is None:
        return error(404, "no_route", f"없는 주소입니다: /v1{p}")
    c = caller_of(request)
    g = await rbac.check(c, perm)
    if g is not None:
        return g
    f = await flags.blocked(p)
    if f is not None:
        return error(503, "maintenance", f.get("maintenance_msg") or f"'{f['label']}' 기능은 점검 중입니다. 잠시 후 다시 이용하세요", feature=f["key"])
    return await proxy(request, p, c, getattr(request.state, "rid", ""))


__all__ = ["app", "svc"]
