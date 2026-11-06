"""성능 측정 — 게이트웨이 경로 네 가지의 p50 · p95 (plan_REQ_04 6단계 P7 · T04-6.01).

읽기 전용 · 출력만: 저장소 파일 · 개발 DB 를 건드리지 않는다. 서비스는 devstack 하네스(한 프로세스 · 메모리 SQLite ·
InMemory 브로커)로 띄우고, 연결 재사용 효과가 보이도록 아래 두 가지만 실제 TCP(127.0.0.1)로 둔다.

| 측정 | 내용 |
|---|---|
| 항목 상세 | 활동 500건이 쌓인 항목을 게이트웨이로 GET (sample 은 ASGI 연결) |
| 프록시 | 게이트웨이 → 업스트림(로컬 uvicorn 에코 서버, 실제 TCP) GET 200회 |
| 운영 개요 | PROMETHEUS_URL = 가짜 Prometheus(로컬 uvicorn, 질의마다 50ms 지연) |
| 메뉴 | GET /v1/menu 200회(menu.json 파싱 · 권한 거르기) |

사용: `uv run python scripts/perf_probe.py [--note "동시 부하 있음"] [--json]`
고치기 전 · 뒤를 같은 조건(같은 PC · 같은 횟수)으로 돌려 표를 비교한다 — 기록은 main 이 docs/verification 에 남긴다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import socket
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# 측정이 레이트리밋 · 개요 캐시에 걸리지 않게 — 게이트웨이 모듈을 import 하기 전에 정한다
os.environ["GW_RATE_RPS"] = "1000000"
os.environ["GW_RATE_BURST"] = "1000000"
os.environ["GW_MONITOR_CACHE"] = "0"
os.environ.setdefault("NOVA_SKIP_LIFESPAN", "1")

ACTIVITY_COUNT = 500
PROM_DELAY_S = 0.05


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(app, port: int):
    """uvicorn 을 별도 스레드에서 띄운다(실제 TCP). 반환: Server — should_exit 로 멈춘다."""
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError(f"측정용 로컬 서버가 10초 안에 뜨지 않았습니다(포트 {port})")
        time.sleep(0.02)
    return server


def echo_upstream():
    from fastapi import FastAPI

    a = FastAPI()

    @a.api_route("/{path:path}", methods=["GET", "POST"])
    async def echo(path: str):
        return {"path": "/" + path, "ok": True}

    return a


def fake_prometheus():
    """질의마다 PROM_DELAY_S 만큼 늦게 답하는 가짜 Prometheus — 직렬 질의 수가 그대로 지연으로 보인다."""
    from fastapi import FastAPI

    a = FastAPI()

    @a.get("/api/v1/query")
    async def query(query: str = ""):
        await asyncio.sleep(PROM_DELAY_S)
        return {"status": "success", "data": {"resultType": "vector", "result": []}}

    return a


def pct(values: list[float], q: float) -> float:
    """최근접 순위 분위수(ms)."""
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(q * len(s) + 0.5) - 1))
    return s[k]


async def timed(n: int, fn, warmup: int = 5) -> list[float]:
    for _ in range(warmup):
        await fn()
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        await fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


async def run(args) -> dict:
    import devstack
    import httpx

    from nova_common import auth, clients
    from nova_common.events import Envelope

    services, broker, gw_app = devstack.build()
    for svc in services.values():
        await svc.startup(start_relay=False)
    admin = {"authorization": "Bearer " + auth.encode({"sub": "U-PROBE", "role": "admin", "name": "측정", "tenant": "T-1"})}
    results: dict[str, dict] = {}
    extra: dict[str, object] = {}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gw_app), base_url="http://gw", timeout=30) as gw:
        async def must(r: httpx.Response) -> httpx.Response:
            if r.status_code >= 400:
                raise RuntimeError(f"측정 요청 실패 {r.request.method} {r.request.url.path}: {r.status_code} {r.text[:200]}")
            return r

        # 1) 활동 500건 항목 상세 — 생성 이벤트 1건 + 보관 이벤트를 소비자 경로로 직접 흘려 활동을 쌓는다
        item = (await must(await gw.post("/v1/sample/items", json={"name": "성능 측정 항목"}, headers=admin))).json()
        await devstack.pump(services, broker)
        from sample.items import T_ARCHIVED

        for _ in range(ACTIVITY_COUNT - 1):
            env = Envelope(type=T_ARCHIVED, source="sample", key=item["id"], tenant="T-1",
                           idempotency_key="probe:" + T_ARCHIVED + ":" + os.urandom(8).hex())
            await broker.deliver(env)
        await broker.drain()
        detail = (await must(await gw.get(f"/v1/sample/items/{item['id']}", headers=admin))).json()
        extra["detail_activity_returned"] = len(detail.get("activity", []))
        extra["detail_bytes"] = len(json.dumps(detail, ensure_ascii=False).encode())

        async def get_detail():
            await must(await gw.get(f"/v1/sample/items/{item['id']}", headers=admin))
        results["항목 상세(활동 500건)"] = {"n": args.detail_n, "ms": await timed(args.detail_n, get_detail)}

        # 2) 프록시 — sample 을 실제 TCP 에코 서버로 돌린다(연결 재사용 여부가 지연에 드러난다)
        port = free_port()
        up = serve(echo_upstream(), port)
        saved = clients._overrides.pop("sample", None)
        old_url = os.environ.get("SVC_SAMPLE_URL")
        os.environ["SVC_SAMPLE_URL"] = f"http://127.0.0.1:{port}"
        try:
            async def get_proxy():
                await must(await gw.get("/v1/sample/items", headers=admin))
            results["프록시(실제 TCP)"] = {"n": args.proxy_n, "ms": await timed(args.proxy_n, get_proxy)}
        finally:
            if hasattr(clients, "aclose_all"):  # 열린 keep-alive 연결을 먼저 닫는다 — 서버가 먼저 내려가면 연결 끊김 경고가 찍힌다
                await clients.aclose_all()
            up.should_exit = True
            if saved is not None:
                clients.override("sample", saved)
            if old_url is None:
                os.environ.pop("SVC_SAMPLE_URL", None)
            else:
                os.environ["SVC_SAMPLE_URL"] = old_url

        # 3) 운영 개요 — 가짜 Prometheus(질의마다 50ms)
        pport = free_port()
        prom = serve(fake_prometheus(), pport)
        os.environ["PROMETHEUS_URL"] = f"http://127.0.0.1:{pport}"
        try:
            async def get_overview():
                r = await must(await gw.get("/v1/ops/monitoring/overview", headers=admin))
                if r.json().get("source") != "prometheus":
                    raise RuntimeError(f"가짜 Prometheus 가 아닌 직접 수집으로 답했습니다: {r.json().get('prometheus_error')}")
            results[f"운영 개요(Prometheus {int(PROM_DELAY_S * 1000)}ms)"] = {"n": args.overview_n, "ms": await timed(args.overview_n, get_overview, warmup=2)}
        finally:
            prom.should_exit = True
            os.environ.pop("PROMETHEUS_URL", None)

        # 4) 메뉴
        async def get_menu():
            await must(await gw.get("/v1/menu", headers=admin))
        results["메뉴"] = {"n": args.menu_n, "ms": await timed(args.menu_n, get_menu)}

    if hasattr(clients, "aclose_all"):  # 공유 클라이언트(T04-6.05)가 있으면 닫는다 — 고치기 전에는 없다
        await clients.aclose_all()
    for svc in services.values():
        await svc.shutdown()
    return {"results": results, "extra": extra}


def main() -> int:
    ap = argparse.ArgumentParser(description="게이트웨이 경로 p50 · p95 측정(읽기 전용 · 출력만)")
    ap.add_argument("--note", default="", help="측정 조건 메모(예: '동시 부하 있음')")
    ap.add_argument("--json", action="store_true", help="표 대신 JSON 한 줄")
    ap.add_argument("--detail-n", type=int, default=100)
    ap.add_argument("--proxy-n", type=int, default=200)
    ap.add_argument("--overview-n", type=int, default=30)
    ap.add_argument("--menu-n", type=int, default=200)
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):  # Windows 파이프는 cp949 — 한국어 표가 깨지지 않게
        sys.stdout.reconfigure(encoding="utf-8")
    import logging

    logging.getLogger("httpx").setLevel(logging.WARNING)  # 요청마다 찍히는 INFO 줄이 표를 가리지 않게
    out = asyncio.run(run(args))
    rows = []
    for name, r in out["results"].items():
        ms = r["ms"]
        rows.append({"측정": name, "횟수": r["n"], "p50_ms": round(statistics.median(ms), 2), "p95_ms": round(pct(ms, 0.95), 2)})
    cond = {"python": platform.python_version(), "os": platform.platform(), "cpu": os.cpu_count(), "note": args.note,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), **out["extra"]}
    if args.json:
        print(json.dumps({"condition": cond, "rows": rows}, ensure_ascii=False))
        return 0
    print("## perf_probe 결과")
    print(f"- 조건: Python {cond['python']} · {cond['os']} · CPU {cond['cpu']} · {cond['at']}" + (f" · {args.note}" if args.note else ""))
    print(f"- 상세 응답의 활동 수 {cond['detail_activity_returned']} · 응답 크기 {cond['detail_bytes']} 바이트")
    print()
    print("| 측정 | 횟수 | p50 (ms) | p95 (ms) |")
    print("|---|---|---|---|")
    for r in rows:
        print(f"| {r['측정']} | {r['횟수']} | {r['p50_ms']} | {r['p95_ms']} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
