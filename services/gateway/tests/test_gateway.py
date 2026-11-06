"""게이트웨이 — 라우팅 · 권한(guest/user/manager/admin) · 스푸핑 방지 · /internal 차단 · 개발 로그인 · 메뉴 · 점검 · 모니터링."""
import copy
import re

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from nova_common import Envelope, auth, clients
from nova_common.ids import is_uuid7
from gateway import main as gw_main
from gateway import routing
from gateway.main import app

METRICS = """# HELP nova_http_requests_total x
# TYPE nova_http_requests_total counter
nova_http_requests_total{service="sample",method="GET",route="/sample/items",status="200"} 90
nova_http_requests_total{service="sample",method="GET",route="/sample/items",status="500"} 10
# HELP nova_outbox_pending x
# TYPE nova_outbox_pending gauge
nova_outbox_pending{service="sample"} 3
"""


def echo_app(name: str) -> FastAPI:
    a = FastAPI()

    @a.get("/healthz")
    def healthz():
        return {"status": "ok", "version": "t", "uptime_s": 1}

    @a.get("/metrics")
    def metrics():
        return PlainTextResponse(METRICS if name == "sample" else "")

    @a.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def echo(path: str, request: Request):
        return {"service": name, "path": "/" + path, "user": request.headers.get("x-user-id"),
                "role": request.headers.get("x-role"), "roles": request.headers.get("x-roles"),
                "tenant": request.headers.get("x-tenant"), "actor": request.headers.get("x-actor-type"),
                "rid": request.headers.get("x-request-id")}

    return a


@pytest.fixture
def client():
    for s in ("sample", "gateway"):
        clients.override(s, httpx.ASGITransport(app=echo_app(s)))
    routing.rbac.reset()
    routing.flags.flags = []
    routing.flags.loaded_at = 0.0
    routing.limiter.buckets.clear()
    yield TestClient(app)
    clients.clear_overrides()


def token(role: str, sub: str = "U-1", tenant: str = "T-1") -> dict:
    return {"authorization": "Bearer " + auth.encode({"sub": sub, "role": role, "name": "홍길동", "tenant": tenant})}


def test_guest_can_read_public_but_not_write(client):
    r = client.get("/v1/sample/items")
    assert r.status_code == 200 and r.json()["service"] == "sample" and r.json()["role"] == "guest"
    r = client.post("/v1/sample/items", json={"name": "x"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_user_write_and_headers_injected(client):
    body = client.post("/v1/sample/items", json={"name": "x"}, headers=token("user")).json()
    assert body["user"] == "U-1" and body["tenant"] == "T-1" and body["roles"] == "user" and body["actor"] == "human"


def test_permission_by_role(client):
    r = client.delete("/v1/sample/items/IT-1", headers=token("user"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_perm"
    assert r.json()["error"]["perm"] == "sample.delete"
    assert client.delete("/v1/sample/items/IT-1", headers=token("manager")).status_code == 200  # sample.*
    assert client.delete("/v1/sample/items/IT-1", headers=token("admin")).status_code == 200  # *


def test_required_perm_and_override():
    assert routing.required_perm("/sample/items/IT-1/archive", "POST") == "sample.update"
    assert routing.required_perm("/sample/items", "POST") == "sample.create"
    assert routing.required_perm("/sample/items", "GET") == "sample.read"
    assert routing.required_perm("/nothing", "GET") is None


def test_spoofed_headers_are_replaced(client):
    r = client.get("/v1/sample/items", headers={"x-user-id": "U-EVIL", "x-role": "admin", "x-tenant": "T-X"})
    assert r.json()["user"] is None and r.json()["role"] == "guest" and r.json()["tenant"] is None


def test_internal_and_unknown_paths_are_404(client):
    assert client.get("/v1/internal/rbac", headers=token("admin")).status_code == 404
    assert client.get("/v1/unknown/x", headers=token("admin")).json()["error"]["code"] == "no_route"


def test_invalid_token_401(client):
    r = client.get("/v1/sample/items", headers={"authorization": "Bearer nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"
    assert "다시 로그인" in r.json()["error"]["message"]


def test_dev_login_issues_token(client):
    r = client.post("/v1/auth/login", json={"email": "user@nova.dev", "password": "nova1234"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "user"
    me = client.get("/v1/me", headers={"authorization": "Bearer " + r.json()["token"]})
    assert me.json()["id"] == "01a1a19a-d2c9-747d-aaa4-25129915198a"  # dev_users.json user@nova.dev
    client.cookies.clear()  # 로그인이 쿠키를 심었다 — 이어지는 틀린 로그인은 쿠키 없는 새 방문자로(쓰기 CSRF 검사 대상이 아니게)
    bad = client.post("/v1/auth/login", json={"email": "user@nova.dev", "password": "x"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_credentials"


def test_login_rejects_malformed_email(client):
    """T04-4.02 — 개발 로그인도 공통 Email 규칙(nova_common.validate). 형식 오류는 422 invalid_input + fields(검토 초점 11.2)."""
    r = client.post("/v1/auth/login", json={"email": "user@", "password": "nova1234"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "invalid_input" and "email" in err["message"]
    assert [f["loc"] for f in err["fields"]] == [["body", "email"]] and err["fields"][0]["msg"]
    ok = client.post("/v1/auth/login", json={"email": " User@Nova.dev ", "password": "nova1234"})  # 정규화 뒤 성공
    assert ok.status_code == 200 and ok.json()["user"]["email"] == "user@nova.dev"


def test_dev_login_can_be_turned_off(client, monkeypatch):
    monkeypatch.setenv("GW_DEV_LOGIN", "0")
    assert client.post("/v1/auth/login", json={"email": "user@nova.dev", "password": "nova1234"}).status_code == 404


def test_menu_filtered_by_permission(client):
    guest = {i["key"] for i in client.get("/v1/menu").json()["items"]}
    admin = {i["key"] for i in client.get("/v1/menu", headers=token("admin")).json()["items"]}
    assert "items" in guest and "ops" not in guest
    assert "ops" in admin


def test_maintenance_flag_503(client):
    routing.flags.flags = [{"key": "sample", "label": "샘플", "enabled": False, "api_prefixes": ["/sample"], "maintenance_msg": "점검 중입니다"}]
    r = client.get("/v1/sample/items", headers=token("user"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "maintenance"
    assert client.get("/v1/menu").json()["maintenance"][0]["key"] == "sample"


def test_rate_limit(client):
    routing.limiter.rps, routing.limiter.burst = 0.001, 2
    try:
        codes = [client.get("/v1/sample/items").status_code for _ in range(3)]
    finally:
        routing.limiter.rps, routing.limiter.burst = 20, 60
    assert codes[-1] == 429


def test_rbac_service_mode_fail_closed(client, monkeypatch):
    monkeypatch.setenv("GW_RBAC_SERVICE", "sample")  # echo 응답에는 roles 가 없다 → 표를 못 만든다
    routing.rbac.reset()
    r = client.get("/v1/sample/items", headers=token("user"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "rbac_unavailable"  # 권한 없음이 아니라 일시 장애(ADR-012 P10)


def test_rbac_unavailable_has_retry_after(client, monkeypatch):
    """권한 원천 장애 503 은 Retry-After(초, 음성 캐시 GW_RBAC_RETRY)를 달고, 오류 봉투는 그대로다."""
    monkeypatch.setenv("GW_RBAC_SERVICE", "sample")
    routing.rbac.reset()
    monkeypatch.setattr(routing.rbac, "retry", 7.0)
    r = client.get("/v1/sample/items", headers=token("user"))
    assert r.status_code == 503
    assert r.headers["retry-after"] == "7"
    err = r.json()["error"]
    assert err["code"] == "rbac_unavailable" and err["message"] and err["perm"] == "sample.read"


def test_monitoring_requires_ops_perm_and_scrapes(client):
    assert client.get("/v1/ops/monitoring/overview", headers=token("user")).status_code == 403
    r = client.get("/v1/ops/monitoring/overview", headers=token("manager"))
    assert r.status_code == 200
    rows = {s["service"]: s for s in r.json()["services"]}
    assert rows["sample"]["up"] and rows["sample"]["outbox_pending"] == 3


def test_cors_preflight(client):
    r = client.options("/v1/sample/items", headers={"origin": "http://localhost:3000"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


# ------------------------------------------------------------------ 심층 감사 회귀 테스트
@pytest.mark.parametrize("url", [
    "/v1/sample/%2e%2e/internal/x",
    "/v1/sample/%2E%2E/metrics",
    "/v1/sample/items/x/%2e%2e/%2e%2e/internal/y",
    "/v1/sample/.%2e/internal/x",
    "/v1/sample/%2e/items",
    "/v1/sample//internal/x",
    "/v1/sample/..%5cinternal%5cx",
])
def test_encoded_dot_segments_do_not_reach_upstream(client, url):
    """인코딩한 점 경로(%2e%2e)로 /internal · /metrics 에 닿으면 안 된다 — 비로그인 · 관리자 모두 404."""
    for h in ({}, token("admin")):
        r = client.get(url, headers=h)
        assert r.status_code == 404, (url, r.status_code, r.text)
        assert r.json()["error"]["code"] == "no_route"
        assert "service" not in r.json()  # 업스트림(echo)까지 가지 않았다


def test_rate_limit_ignores_spoofed_xff_by_default(client):
    """기본(GW_TRUSTED_HOPS=0)은 X-Forwarded-For 를 무시 — 매번 다른 값을 보내도 같은 버킷."""
    routing.limiter.rps, routing.limiter.burst = 0.001, 2
    try:
        codes = [client.get("/v1/sample/items", headers={"x-forwarded-for": f"10.0.0.{i}"}).status_code for i in range(3)]
    finally:
        routing.limiter.rps, routing.limiter.burst = 20, 60
    assert codes[-1] == 429


def test_client_ip_trusted_hops(monkeypatch):
    class R:
        def __init__(self, xff):
            self.headers = {"x-forwarded-for": xff} if xff else {}
            self.client = type("C", (), {"host": "10.9.9.9"})()

    monkeypatch.delenv("GW_TRUSTED_HOPS", raising=False)
    assert routing.client_ip(R("1.1.1.1, 2.2.2.2")) == "10.9.9.9"
    monkeypatch.setenv("GW_TRUSTED_HOPS", "1")  # 인그레스 1개 — 인그레스가 덧붙인 맨 오른쪽 값이 실제 클라이언트
    assert routing.client_ip(R("6.6.6.6, 2.2.2.2")) == "2.2.2.2"  # 왼쪽 6.6.6.6 은 위조 가능
    monkeypatch.setenv("GW_TRUSTED_HOPS", "2")
    assert routing.client_ip(R("6.6.6.6, 3.3.3.3, 2.2.2.2")) == "3.3.3.3"
    assert routing.client_ip(R("")) == "10.9.9.9"


def test_rate_limiter_evicts_oldest_not_all():
    lim = routing.RateLimiter(rps=0.001, burst=2, max_buckets=3)
    lim.allow("a")
    lim.allow("a")  # a 는 토큰을 다 썼다
    lim.allow("b")
    lim.allow("c")
    lim.allow("a")  # a 를 최근에 썼다 → b 가 가장 오래됨
    lim.allow("d")  # 상한 초과 → b 만 지운다
    assert set(lim.buckets) == {"a", "c", "d"}
    assert lim.allow("a")[0] is False  # 전체 clear 였다면 a 가 새 버킷으로 풀려났을 것


def test_unknown_actor_type_is_401(client):
    bad = {"authorization": "Bearer " + auth.encode({"sub": "U-1", "role": "user", "actor_type": "robot"})}
    r = client.get("/v1/sample/items", headers=bad)
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"
    ai = {"authorization": "Bearer " + auth.encode({"sub": "U-1", "role": "user", "actor_type": "ai"})}
    assert client.get("/v1/sample/items", headers=ai).json()["actor"] == "ai"


def test_invalid_token_message_has_no_english_reason(client):
    msg = client.get("/v1/sample/items", headers={"authorization": "Bearer nope"}).json()["error"]["message"]
    assert not re.search(r"[A-Za-z]", msg), msg  # 'malformed' 같은 영어 사유는 로그로만


# ---- 서비스 모드 권한 원천(/internal/rbac) 흉내
RBAC_TABLE = {"roles": {"guest": ["sample.read"], "user": ["sample.read", "sample.create"],
                        "editor": ["sample.*"], "manager": ["sample.*", "ops.read"]},
              "grants": {}, "bases": {}, "blocked": []}


def source_app(route: str, state: dict) -> FastAPI:
    """echo 앱 앞에 원천 경로(/internal/rbac · /internal/features)를 붙인다. state: down · calls · body."""
    a = echo_app("sample")

    @a.get(route)
    def _src():
        state["calls"] += 1
        if state["down"]:
            return PlainTextResponse("down", status_code=500)
        return state["body"]

    a.router.routes.insert(0, a.router.routes.pop())  # catch-all echo 보다 먼저
    return a


@pytest.fixture
def rbac_src(client, monkeypatch):
    """GW_RBAC_SERVICE=sample — 원천 상태(표 · 장애 · 호출 수)를 테스트가 바꾼다."""
    state = {"body": copy.deepcopy(RBAC_TABLE), "down": False, "calls": 0}
    clients.override("sample", httpx.ASGITransport(app=source_app("/internal/rbac", state)))
    monkeypatch.setenv("GW_RBAC_SERVICE", "sample")
    routing.rbac.reset()
    yield state
    routing.rbac.reset()


def test_rbac_blocked_user(client, rbac_src):
    rbac_src["body"]["blocked"] = ["U-1"]
    r = client.get("/v1/sample/items", headers=token("user"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_user"
    assert client.get("/v1/sample/items", headers=token("user", sub="U-2")).status_code == 200


def test_rbac_grants_add_role(client, rbac_src):
    assert client.delete("/v1/sample/items/IT-1", headers=token("user")).status_code == 403
    rbac_src["body"]["grants"] = {"U-1": ["editor"]}
    routing.rbac.reset()
    r = client.delete("/v1/sample/items/IT-1", headers=token("user"))
    assert r.status_code == 200 and r.json()["roles"] == "user,editor"


def test_rbac_bases_replace_token_role(client, rbac_src):
    rbac_src["body"]["bases"] = {"U-1": "user"}  # 토큰은 manager 지만 표가 기본 역할을 user 로 바꿨다(강등)
    r = client.delete("/v1/sample/items/IT-1", headers=token("manager"))
    assert r.status_code == 403 and r.json()["error"]["perm"] == "sample.delete"


def test_rbac_ignores_roles_claim_in_token(client, rbac_src):
    t = {"authorization": "Bearer " + auth.encode({"sub": "U-1", "role": "user", "roles": ["user", "editor", "admin"]})}
    r = client.delete("/v1/sample/items/IT-1", headers=t)
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_perm"
    assert client.get("/v1/sample/items", headers=t).json()["roles"] == "user"


def test_rbac_stale_then_fail_closed(client, rbac_src):
    assert client.get("/v1/sample/items", headers=token("user")).status_code == 200
    rbac_src["down"] = True
    routing.rbac.fetched_at -= routing.rbac.ttl + 1  # TTL 지남, stale 안 → 마지막 표로 계속
    assert client.get("/v1/sample/items", headers=token("user")).status_code == 200
    routing.rbac.fetched_at -= routing.rbac.stale + 1  # stale 도 지남 → 닫는다
    routing.rbac.failed_at = None  # 음성 캐시를 건너뛰고 바로 다시 판정
    r = client.get("/v1/sample/items", headers=token("user"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "rbac_unavailable"


def test_rbac_negative_cache_does_not_retry_every_request(client, rbac_src):
    rbac_src["down"] = True
    for _ in range(3):
        assert client.get("/v1/sample/items", headers=token("user")).json()["error"]["code"] == "rbac_unavailable"
    assert rbac_src["calls"] == 1  # 실패 뒤 짧은 시간은 다시 부르지 않는다(매 요청 2초 대기 방지)


def test_rbac_changed_event_invalidates_cache(client, rbac_src):
    assert "platform.rbac.changed" in gw_main.svc.handlers
    assert client.get("/v1/sample/items", headers=token("user")).status_code == 200
    rbac_src["body"]["blocked"] = ["U-1"]
    assert client.get("/v1/sample/items", headers=token("user")).status_code == 200  # TTL 캐시 — 아직 모른다
    gw_main.on_rbac_changed(None, Envelope(type="platform.rbac.changed", source="iam", key="U-1", idempotency_key="rbac-1", data={}))
    assert client.get("/v1/sample/items", headers=token("user")).json()["error"]["code"] == "forbidden_user"


def test_flag_source_negative_cache(client, monkeypatch):
    state = {"body": [], "down": True, "calls": 0}
    clients.override("sample", httpx.ASGITransport(app=source_app("/internal/features", state)))
    monkeypatch.setenv("GW_FLAGS_SERVICE", "sample")
    for _ in range(3):
        assert client.get("/v1/sample/items", headers=token("user")).status_code == 200  # 플래그 원천 장애 = 가용성 우선
    assert state["calls"] == 1


def test_cors_disallowed_origin_has_no_allow_header(client):
    for r in (client.options("/v1/sample/items", headers={"origin": "http://evil.example"}),
              client.get("/v1/sample/items", headers={"origin": "http://evil.example"})):
        assert "access-control-allow-origin" not in r.headers
        assert "access-control-allow-credentials" not in r.headers


def test_direct_scrape_alerts_outbox_quarantined():
    """Prometheus 가 없을 때 게이트웨이 직접 수집도 alert_rules 의 OutboxQuarantined 와 같은 판단(격리 > 0 → warning)."""
    from gateway import monitoring

    ov = {"services": [
        {"service": "sample", "up": True, "outbox_quarantined": 2},
        {"service": "other", "up": True, "outbox_quarantined": 0},
    ]}
    hits = [a for a in monitoring.evaluate_alerts(ov) if a["name"] == "OutboxQuarantined"]
    assert [(a["service"], a["severity"]) for a in hits] == [("sample", "warning")]
    assert "2" in hits[0]["summary"]


def test_direct_scrape_reads_quarantined_gauge(client, monkeypatch):
    """직접 수집이 /metrics 의 nova_outbox_quarantined 를 서비스 행에 담는다(경보 판단의 입력)."""
    from gateway import monitoring

    monkeypatch.setattr(monitoring, "CACHE_TTL", 0)  # 앞 테스트의 5초 캐시가 새 지표를 가리지 않게
    monkeypatch.setitem(globals(), "METRICS", METRICS + "# HELP nova_outbox_quarantined x\n# TYPE nova_outbox_quarantined gauge\n"
                        'nova_outbox_quarantined{service="sample"} 4\n')
    r = client.get("/v1/ops/monitoring/overview", headers=token("manager"))
    rows = {s["service"]: s for s in r.json()["services"]}
    assert rows["sample"]["outbox_quarantined"] == 4
    assert any(a["name"] == "OutboxQuarantined" and a["service"] == "sample" for a in r.json()["alerts"])


def test_gateway_request_id_reaches_upstream(client, monkeypatch):
    """T03-5.05 — 게이트웨이 요청 ID 규칙 = context.trace_from_header. 업스트림 · 응답 · 게이트웨이 자신의 서비스 호출이 같은 ID."""
    r = client.get("/v1/sample/items", headers={**token("user"), "x-request-id": "req-gw-000001"})
    assert r.status_code == 200 and r.json()["rid"] == "req-gw-000001" and r.headers["x-request-id"] == "req-gw-000001"
    seen = []
    a = echo_app("sample")

    @a.get("/internal/rbac")
    def _src(request: Request):
        seen.append(request.headers.get("x-request-id"))
        return copy.deepcopy(RBAC_TABLE)

    a.router.routes.insert(0, a.router.routes.pop())
    clients.override("sample", httpx.ASGITransport(app=a))
    monkeypatch.setenv("GW_RBAC_SERVICE", "sample")
    routing.rbac.reset()
    try:
        for bad in ({}, {"x-request-id": "bad id!"}):
            routing.rbac.reset()  # 매번 원천을 다시 부르게
            r = client.get("/v1/sample/items", headers={**token("user"), **bad})
            rid = r.headers["x-request-id"]
            assert is_uuid7(rid), rid  # 새 ID 도 공통 규칙(UUIDv7)
            assert r.json()["rid"] == rid  # 업스트림이 받은 것 = 응답 헤더
            assert seen[-1] == rid  # 게이트웨이가 권한 원천을 부를 때도 같은 ID
    finally:
        routing.rbac.reset()


def test_rbac_changed_event_invalidates_every_replica(monkeypatch):
    """T03-5.09 — 복제본 두 개가 한 브로커에 붙어도 권한 · 플래그 무효화가 둘 다에 닿는다(방송). 같은 key 두 번도 두 번 모두."""
    import asyncio

    from nova_common.db import NovaBase
    from nova_common.events import InMemoryBroker, InMemoryBus
    from nova_common.ids import new_id
    from nova_common.service import Service

    assert {"platform.rbac.changed", "platform.feature.changed"} <= gw_main.svc.broadcast_topics
    calls = {"rbac": 0, "flags": 0}
    monkeypatch.setattr(routing.rbac, "invalidate", lambda: calls.__setitem__("rbac", calls["rbac"] + 1))
    monkeypatch.setattr(routing.flags, "invalidate", lambda: calls.__setitem__("flags", calls["flags"] + 1))
    broker = InMemoryBroker()
    replicas = []
    for _ in range(2):
        class Base(NovaBase):
            pass

        rep = Service("gateway", Base, "gw", db_url="sqlite://")  # 복제본마다 자기 메모리 DB(처리 기록)
        rep.init_db()
        rep.bus = InMemoryBus("gateway", broker, sync=True)
        rep.handlers = {t: list(fns) for t, fns in gw_main.svc.handlers.items()}  # main.py 가 등록한 그대로
        rep.broadcast_topics = set(gw_main.svc.broadcast_topics)
        rep._subscribe_all()
        replicas.append(rep)

    def ev(topic):
        eid = new_id()  # 기본 중복 제거 키처럼 이벤트 id 를 넣는다 — key 가 같아도 다른 사건
        return Envelope(id=eid, type=topic, source="iam", key="U-1", idempotency_key=f"iam:{topic}:U-1:{eid}")

    lp = asyncio.new_event_loop()
    try:
        first, second = ev("platform.rbac.changed"), ev("platform.rbac.changed")
        for e in (first, second, first):  # 마지막은 같은 메시지 재전달 — 복제본마다 한 번씩만
            lp.run_until_complete(broker.deliver(e))
        lp.run_until_complete(broker.deliver(ev("platform.feature.changed")))
    finally:
        lp.close()
    assert calls == {"rbac": 4, "flags": 2}  # 2 복제본 × 2 사건 · 2 복제본 × 1 사건


def test_proxy_and_scrape_reuse_pooled_client_closed_on_shutdown(client):
    """T04-6.06 — 프록시 · 메트릭 수집이 서비스마다 공유 클라이언트(clients.pooled)를 쓰고, 게이트웨이 종료 때 닫힌다."""
    with TestClient(app) as c:  # 수명 주기(lifespan)를 돈다 — 요청들이 한 이벤트 루프를 공유
        assert c.get("/v1/sample/items", headers=token("user")).status_code == 200
        first = clients._pool["sample"][0]
        assert c.get("/v1/sample/items", headers=token("user")).status_code == 200
        assert c.get("/v1/ops/monitoring/overview", headers=token("manager")).status_code == 200
        assert clients._pool["sample"][0] is first  # 프록시 · 수집이 같은 연결 풀
        assert "gateway" in clients._pool  # 수집도 pooled 를 거친다
    assert first.is_closed and not clients._pool


def test_prom_queries_concurrent(monkeypatch):
    """T04-6.07 — 운영 개요의 Prometheus 질의 전부를 클라이언트 하나로 한꺼번에 낸다(직렬 대기 없음)."""
    import asyncio

    from gateway import monitoring

    state = {"now": 0, "peak": 0, "total": 0, "clients": 0}

    class Counting(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            state["now"] += 1
            state["total"] += 1
            state["peak"] = max(state["peak"], state["now"])
            await asyncio.sleep(0.02)  # 모두가 동시에 걸려 있을 시간
            state["now"] -= 1
            return httpx.Response(200, json={"status": "success", "data": {"resultType": "vector", "result": []}})

    real = httpx.AsyncClient

    def counting_client(*a, **kw):
        state["clients"] += 1
        return real(*a, **kw)

    monkeypatch.setenv("PROMETHEUS_URL", "http://prom.test")
    monkeypatch.setattr(monitoring, "PROM_TRANSPORT", Counting())
    monkeypatch.setattr(monitoring.httpx, "AsyncClient", counting_client)
    ov = asyncio.run(monitoring.prom_overview())
    assert ov["source"] == "prometheus"
    assert state["total"] == len(monitoring.PROM_Q) + 6  # 서비스별 10 + up 1 + 토픽 3 + 업무 2
    assert state["peak"] == state["total"]  # 전부 동시에
    assert state["clients"] == 1  # 질의마다 새 클라이언트를 만들지 않는다


def test_menu_cache_reload_on_mtime(client, monkeypatch, tmp_path):
    """T04-6.08 — menu.json 은 파일 수정 시각이 바뀔 때만 다시 파싱한다. 권한 거르기는 요청마다 그대로."""
    import json
    import os

    menu = tmp_path / "menu.json"

    def write(label: str) -> None:
        menu.write_text(json.dumps({"items": [
            {"key": "a", "label": label, "path": "/a", "channels": ["web"], "perm": None},
            {"key": "ops", "label": "운영", "path": "/ops", "channels": ["web"], "perm": "ops.read"},
        ], "features": []}, ensure_ascii=False), encoding="utf-8")

    write("가")
    monkeypatch.setenv("GW_MENU_FILE", str(menu))
    labels = lambda h=None: {i["key"]: i["label"] for i in client.get("/v1/menu", headers=h or {}).json()["items"]}  # noqa: E731
    assert labels() == {"a": "가"}  # 비로그인 — ops 는 걸러진다
    assert labels(token("admin")) == {"a": "가", "ops": "운영"}  # 같은 캐시에서도 호출자마다 거른다

    st = menu.stat()
    write("나")  # 같은 크기 · 같은 수정 시각 → 다시 읽지 않는다(캐시가 실제로 쓰인다는 증거)
    os.utime(menu, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert labels() == {"a": "가"}

    os.utime(menu, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))  # 수정 시각이 바뀌면 다시 읽는다
    assert labels() == {"a": "나"}


def _failing_upstream(exc: Exception) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc
    return httpx.MockTransport(handler)


def test_proxy_timeout_is_504(client):
    """업스트림이 제때 답하지 않으면 504 upstream_timeout — 어느 서비스인지 service 칸으로(REQ-261104-11-10)."""
    clients.override("sample", _failing_upstream(httpx.ReadTimeout("느림")))
    r = client.get("/v1/sample/items", headers=token("user"))
    assert r.status_code == 504
    err = r.json()["error"]
    assert (err["code"], err["service"]) == ("upstream_timeout", "sample")
    assert err["message"] == "서버 응답이 늦어지고 있습니다. 잠시 후 다시 시도하세요"


def test_proxy_connect_error_is_502(client):
    """업스트림에 붙지 못하면 502 upstream_unavailable — 시간 초과(504)와 구분한다."""
    clients.override("sample", _failing_upstream(httpx.ConnectError("연결 거부")))
    r = client.post("/v1/sample/items", json={"name": "x"}, headers=token("user"))
    assert r.status_code == 502
    err = r.json()["error"]
    assert (err["code"], err["service"]) == ("upstream_unavailable", "sample")
    assert err["message"] == "서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요"


# ------------------------------------------------------------------ T04-8 httpOnly 쿠키 인증(ADR-014 Expand)
def _cookie_token(role: str = "user") -> str:
    return auth.encode({"sub": "U-1", "role": role, "name": "홍길동", "tenant": "T-1"})


def test_login_sets_httponly_cookie(client):
    """T04-8.01 — 로그인이 nova_token 쿠키를 심는다(HttpOnly · SameSite=Lax · Path=/v1 · Max-Age=토큰 수명). 본문 token 은 유지."""
    r = client.post("/v1/auth/login", json={"email": "user@nova.dev", "password": "nova1234"})
    sc = r.headers["set-cookie"]
    assert sc.startswith(f"{routing.TOKEN_COOKIE}={r.json()['token']}")
    assert "HttpOnly" in sc and "samesite=lax" in sc.lower() and "Path=/v1" in sc
    assert "Max-Age=604800" in sc and "Secure" not in sc  # 개발 기본은 Secure 끔
    bad = client.post("/v1/auth/login", json={"email": "user@nova.dev", "password": "x"})
    assert "set-cookie" not in bad.headers  # 실패 로그인은 쿠키를 심지 않는다


def test_cookie_secure_follows_env(client, monkeypatch):
    """T04-8.01 — GW_COOKIE_SECURE 가 true 면 Secure, false 면 끔(없으면 NOVA_ENV=prod 기본)."""
    monkeypatch.setenv("GW_COOKIE_SECURE", "true")
    r = client.post("/v1/auth/login", json={"email": "user@nova.dev", "password": "nova1234"})
    assert "Secure" in r.headers["set-cookie"]
    monkeypatch.setenv("GW_COOKIE_SECURE", "0")
    r = client.post("/v1/auth/login", json={"email": "user@nova.dev", "password": "nova1234"})
    assert "Secure" not in r.headers["set-cookie"]


def test_cookie_secure_default_follows_nova_env(monkeypatch):
    """T04-8.01 — GW_COOKIE_SECURE 가 없을 때의 기본: NOVA_ENV=prod 면 Secure 켬, 환경이 없으면 끔(운영 회귀 방지)."""
    monkeypatch.delenv("GW_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("NOVA_ENV", "prod")
    assert gw_main.cookie_secure() is True
    monkeypatch.delenv("NOVA_ENV", raising=False)
    assert gw_main.cookie_secure() is False


def test_proxied_login_sets_cookie(client, monkeypatch):
    """T04-8.02 — /auth 를 소유한 서비스로 넘긴 로그인 응답의 본문 token 으로도 쿠키를 심는다. 본문은 그대로."""
    def authsvc() -> FastAPI:
        a = FastAPI()

        @a.post("/auth/login")
        async def login(request: Request):
            body = await request.json()
            if body.get("password") != "ok":
                return JSONResponse({"error": {"code": "invalid_credentials", "message": "x"}}, status_code=401)
            return {"token": "T.O.K", "user": {"id": "U-9"}}

        return a

    clients.override("authsvc", httpx.ASGITransport(app=authsvc()))
    orig = gw_main.catalog.route_for
    monkeypatch.setattr(gw_main.catalog, "route_for", lambda p: "authsvc" if p == "/auth/login" else orig(p))
    r = client.post("/v1/auth/login", json={"password": "ok"})
    assert r.json() == {"token": "T.O.K", "user": {"id": "U-9"}}
    assert r.headers["set-cookie"].startswith(f"{routing.TOKEN_COOKIE}=T.O.K") and "HttpOnly" in r.headers["set-cookie"]
    bad = client.post("/v1/auth/login", json={"password": "no"})
    assert bad.status_code == 401 and "set-cookie" not in bad.headers


def test_logout_clears_cookie(client):
    """T04-8.03 — POST /v1/auth/logout 은 쿠키를 지우고(Max-Age=0) 비로그인이어도 204."""
    r = client.post("/v1/auth/logout")
    assert r.status_code == 204
    sc = r.headers["set-cookie"]
    assert sc.startswith(f"{routing.TOKEN_COOKIE}=") and "Max-Age=0" in sc and "Path=/v1" in sc and "HttpOnly" in sc
    # 쿠키 로그인 상태(허용 Origin)에서도 204, 깨진 쿠키여도 로그아웃은 된다
    ok = client.post("/v1/auth/logout", headers={"cookie": f"{routing.TOKEN_COOKIE}={_cookie_token()}", "origin": "http://localhost:3000"})
    assert ok.status_code == 204 and "Max-Age=0" in ok.headers["set-cookie"]
    broken = client.post("/v1/auth/logout", headers={"cookie": f"{routing.TOKEN_COOKIE}=broken", "origin": "http://localhost:3000"})
    assert broken.status_code == 204
    # 우회 경로도 CORS 헤더가 있어야 다른 출처 웹(credentials:include)이 응답을 읽는다
    assert broken.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert broken.headers["access-control-allow-credentials"] == "true" and "Max-Age=0" in broken.headers["set-cookie"]


def test_cookie_write_requires_allowed_origin(client):
    """T04-8.04 — 쿠키로 인증된 쓰기는 Origin 이 허용 목록일 때만. 허용 통과 · 없음 403 · 다른 출처 403 · 읽기는 대상 아님."""
    ck = {"cookie": f"{routing.TOKEN_COOKIE}={_cookie_token()}"}
    ok = client.post("/v1/sample/items", json={"name": "x"}, headers={**ck, "origin": "http://localhost:3000"})
    assert ok.status_code == 200 and ok.json()["user"] == "U-1"
    for hdr in ({}, {"origin": "http://evil.example"}):
        r = client.post("/v1/sample/items", json={"name": "x"}, headers={**ck, **hdr})
        assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_origin"
        assert "출처" in r.json()["error"]["message"]
    bad = client.post("/v1/sample/items", json={"name": "x"}, headers={**ck, "origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers  # 허용 밖 출처에는 CORS 허용을 주지 않는다
    assert client.get("/v1/sample/items", headers=ck).status_code == 200  # 안전한 메서드는 검사하지 않는다
    assert client.post("/v1/sample/items", json={"name": "x"}).status_code == 401  # 비로그인은 대상 아님(기존 401)


def test_login_logout_origin_guard(client):
    """T04-8.11 보안 — 쿠키를 심고 지우는 두 경로는 익명이어도 Origin 헤더가 있으면 허용 목록이어야 한다(로그인 CSRF 방지)."""
    cred = {"email": "user@nova.dev", "password": "nova1234"}
    evil = client.post("/v1/auth/login", json=cred, headers={"origin": "http://evil.example"})  # (a)
    assert evil.status_code == 403 and evil.json()["error"]["code"] == "csrf_origin"
    assert "set-cookie" not in evil.headers and "access-control-allow-origin" not in evil.headers
    ok = client.post("/v1/auth/login", json=cred, headers={"origin": "http://localhost:3000"})  # (b)
    assert ok.status_code == 200 and "HttpOnly" in ok.headers["set-cookie"]
    client.cookies.clear()
    app_login = client.post("/v1/auth/login", json=cred)  # (c) Origin 없음 = 모바일 · 서버 호출
    assert app_login.status_code == 200 and app_login.json()["token"]
    client.cookies.clear()
    out = client.post("/v1/auth/logout", headers={"origin": "http://evil.example"})  # (e)
    assert out.status_code == 403 and out.json()["error"]["code"] == "csrf_origin" and "set-cookie" not in out.headers
    assert client.post("/v1/auth/logout").status_code == 204  # Origin 없음은 통과


def test_dev_login_requires_json_content_type(client):
    """T04-8.11 보안 — 개발 로그인은 application/json 만. text/plain 폼 전송(단순 요청)은 415."""
    r = client.post("/v1/auth/login", content='{"email":"user@nova.dev","password":"nova1234"}',
                    headers={"content-type": "text/plain"})  # (d)
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_media_type"
    assert "JSON" in r.json()["error"]["message"] and "set-cookie" not in r.headers


def test_bearer_exempt_from_origin(client):
    """T04-8.04 — Bearer 요청은 Origin 이 없거나 낯설어도 면제(모바일 · 서버 호출)."""
    assert client.post("/v1/sample/items", json={"name": "x"}, headers=token("user")).status_code == 200
    r = client.post("/v1/sample/items", json={"name": "x"}, headers={**token("user"), "origin": "http://evil.example"})
    assert r.status_code == 200


def test_cookie_mode_refuses_wildcard_cors():
    """T04-8.05 — GW_CORS_ORIGINS 에 `*` 가 있으면 기동 거부(쿠키는 늘 발급하므로 늘 거부)."""
    with pytest.raises(RuntimeError, match="GW_CORS_ORIGINS"):
        gw_main.check_cors_origins(["http://localhost:3000", "*"])
    gw_main.check_cors_origins(["http://localhost:3000"])  # 정확한 목록은 통과
