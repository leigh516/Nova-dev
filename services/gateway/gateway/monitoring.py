"""운영 모니터링 API — 운영 화면(웹 샘플 앱 /ops)의 백엔드.

1순위 Prometheus(PROMETHEUS_URL, k3s: http://prometheus.observability:9090) · 없거나 장애면 각 서비스
`/metrics`·`/healthz`를 직접 수집해 같은 모양으로 계산한다(직접 수집 폴백). 결과는 5초 캐시해 화면
폴링이 몰려도 서비스에 부담을 주지 않는다(자원 효율).
"""
from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict

import httpx
from prometheus_client.parser import text_string_to_metric_families

from nova_common import catalog, clients

ALL = catalog.names()  # 서비스 목록 단일 원천(nova_common/services.json)
CACHE_TTL = float(os.getenv("GW_MONITOR_CACHE", "5"))

# 알림 규칙 — infra/observability/alert_rules.yml 과 같은 임계값(폴백 모드에서 GW가 직접 평가)
THRESHOLDS = {"error_rate": 0.05, "p95_s": 1.0, "outbox_pending": 100, "consumer_lag": 1000, "dlq": 1,
              "outbox_quarantined": 0}  # 격리 행은 자동 재시도하지 않으므로 1건이라도 경보


PROM_TRANSPORT: httpx.AsyncBaseTransport | None = None  # 테스트가 가짜 Prometheus 를 꽂는 자리(운영은 None = 실제 네트워크)


def prom_url() -> str | None:
    return os.getenv("PROMETHEUS_URL") or None


def prom_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=prom_url(), timeout=3.0, transport=PROM_TRANSPORT)


async def prom(path: str, params: dict, client: httpx.AsyncClient | None = None) -> dict:
    """Prometheus HTTP API 한 번. client 를 주면 그 연결 풀을 쓰고(개요 — 질의 여럿), 없으면 한 번 쓰고 닫는다."""
    if client is None:
        async with prom_client() as c:
            return await prom(path, params, c)
    r = await client.get(path, params=params)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise RuntimeError(body.get("error", "prometheus error"))
    return body["data"]


def _vec(data: dict, key: str = "service") -> dict[str, float]:
    out = {}
    for r in data.get("result", []):
        try:
            out[r["metric"].get(key, "")] = float(r["value"][1])
        except (KeyError, ValueError):
            continue
    return out


# ------------------------------------------------------------------ 직접 수집 폴백
def quantile_from_buckets(buckets: dict[float, float], q: float) -> float | None:
    """누적 히스토그램 버킷(le → count)에서 분위수 근사(Prometheus histogram_quantile 과 같은 선형 보간)."""
    if not buckets:
        return None
    les = sorted(buckets)
    total = buckets[les[-1]]
    if total <= 0:
        return None
    rank = q * total
    prev_le, prev_c = 0.0, 0.0
    for le in les:
        c = buckets[le]
        if c >= rank:
            if le == float("inf"):
                return prev_le
            return prev_le + (le - prev_le) * ((rank - prev_c) / (c - prev_c) if c > prev_c else 0)
        prev_le, prev_c = le, c
    return les[-2] if len(les) > 1 else None


class Scraper:
    def __init__(self):
        self.prev: dict[str, tuple[float, float, float, dict]] = {}  # svc → (t, requests, errors, buckets)
        self.cache: tuple[float, dict] | None = None

    async def scrape(self, svc: str) -> dict:
        t0 = time.perf_counter()
        st: dict = {"service": svc, "up": False}
        try:
            c = clients.pooled(svc)  # 프록시와 같은 연결 풀(T04-6.06) — 닫지 않는다
            h = await c.get("/healthz", timeout=2.0)
            m = await c.get("/metrics", timeout=2.0)
            st["up"] = h.status_code == 200
            st["version"] = h.json().get("version") if st["up"] else None
            st["uptime_s"] = h.json().get("uptime_s") if st["up"] else None
            text = m.text
        except Exception as e:  # 다운
            st["error"] = type(e).__name__
            return st
        st["scrape_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        req = err = inflight = pending = quarantined = lag = 0.0
        buckets: dict[float, float] = defaultdict(float)
        consumed: dict[str, float] = defaultdict(float)
        published: dict[str, float] = defaultdict(float)
        topics: dict[str, dict] = defaultdict(lambda: {"published": 0.0, "consumed": 0.0, "dlq": 0.0})
        business: dict[str, float] = defaultdict(float)
        amount: dict[str, float] = defaultdict(float)
        for fam in text_string_to_metric_families(text):
            for s in fam.samples:
                lb = s.labels
                if lb.get("service") != svc:  # 단일 프로세스 개발 모드에서는 레지스트리를 공유하므로 서비스 라벨로 거른다
                    continue
                n = s.name
                if n == "nova_http_requests_total":
                    req += s.value
                    if lb.get("status", "").startswith("5"):
                        err += s.value
                elif n == "nova_http_request_duration_seconds_bucket":
                    buckets[float(lb["le"])] += s.value
                elif n == "nova_http_inflight_requests":
                    inflight += s.value
                elif n == "nova_outbox_pending":
                    pending += s.value
                elif n == "nova_outbox_quarantined":
                    quarantined += s.value
                elif n == "nova_kafka_consumer_lag":
                    lag += s.value
                elif n == "nova_events_consumed_total":
                    consumed[lb.get("result", "")] += s.value
                    topics[lb.get("topic", "")]["consumed" if lb.get("result") == "ok" else ("dlq" if lb.get("result") == "dlq" else "consumed")] += s.value if lb.get("result") in ("ok", "dlq") else 0
                elif n == "nova_events_published_total":
                    published[lb.get("topic", "")] += s.value
                    topics[lb.get("topic", "")]["published"] += s.value
                elif n == "nova_business_events_total":
                    business[f"{lb.get('kind')}.{lb.get('status')}"] += s.value
                elif n == "nova_business_amount_total":
                    amount[f"{lb.get('kind', '')}:{lb.get('currency', '')}"] += s.value
        now = time.monotonic()
        prev = self.prev.get(svc)
        rps = err_rate = None
        p95_buckets = dict(buckets)
        if prev:
            dt = max(1e-3, now - prev[0])
            d_req, d_err = req - prev[1], err - prev[2]
            rps = round(d_req / dt, 2)
            err_rate = round(d_err / d_req, 4) if d_req > 0 else 0.0
            delta = {le: c - prev[3].get(le, 0.0) for le, c in buckets.items()}
            if delta and max(delta.values()) > 0:
                p95_buckets = delta
        self.prev[svc] = (now, req, err, dict(buckets))
        p95 = quantile_from_buckets(p95_buckets, 0.95)
        st.update(
            requests_total=req, errors_total=err, rps=rps if rps is not None else 0.0,
            error_rate=err_rate if err_rate is not None else (round(err / req, 4) if req else 0.0),
            p95_ms=round(p95 * 1000, 1) if p95 is not None else None, inflight=inflight,
            outbox_pending=pending, outbox_quarantined=quarantined, consumer_lag=lag, events={"consumed": dict(consumed), "published": sum(published.values())},
            topics={k: v for k, v in topics.items() if k}, business=dict(business), amount=dict(amount),
        )
        return st

    async def overview(self) -> dict:
        if self.cache and time.monotonic() - self.cache[0] < CACHE_TTL:
            return self.cache[1]
        rows = await asyncio.gather(*(self.scrape(s) for s in ALL))
        topics: dict[str, dict] = defaultdict(lambda: {"published": 0.0, "consumed": 0.0, "dlq": 0.0})
        business: dict[str, float] = defaultdict(float)
        amount: dict[str, float] = defaultdict(float)
        for r in rows:
            for t, v in (r.pop("topics", None) or {}).items():
                for k in v:
                    topics[t][k] += v[k]
            for k, v in (r.pop("business", None) or {}).items():
                business[k] += v
            for k, v in (r.pop("amount", None) or {}).items():
                amount[k] += v
        out = {
            "source": "direct", "generated_at": time.time(), "services": rows,
            "topics": [{"topic": k, **v} for k, v in sorted(topics.items())],
            "business": dict(business), "amount": dict(amount), "catalog": catalog.public(), "groups": catalog.groups(),
        }
        out["alerts"] = evaluate_alerts(out)
        out["summary"] = summarize(out)
        self.cache = (time.monotonic(), out)
        return out


scraper = Scraper()


def evaluate_alerts(ov: dict) -> list[dict]:
    a = []
    for s in ov["services"]:
        name = s["service"]
        if not s.get("up"):
            a.append({"name": "ServiceDown", "severity": "critical", "service": name, "summary": f"{name} 응답 없음"})
            continue
        if (s.get("error_rate") or 0) > THRESHOLDS["error_rate"]:
            a.append({"name": "HighErrorRate", "severity": "warning", "service": name, "summary": f"5xx 비율 {s['error_rate'] * 100:.1f}%"})
        if (s.get("p95_ms") or 0) > THRESHOLDS["p95_s"] * 1000:
            a.append({"name": "HighLatencyP95", "severity": "warning", "service": name, "summary": f"p95 {s['p95_ms']:.0f}ms"})
        if (s.get("outbox_pending") or 0) > THRESHOLDS["outbox_pending"]:
            a.append({"name": "OutboxBacklog", "severity": "warning", "service": name, "summary": f"미발행 아웃박스 {s['outbox_pending']:.0f}건"})
        if (s.get("outbox_quarantined") or 0) > THRESHOLDS["outbox_quarantined"]:
            a.append({"name": "OutboxQuarantined", "severity": "warning", "service": name,
                      "summary": f"격리된 아웃박스 {s['outbox_quarantined']:.0f}건 — 원인 수정 후 python nova.py parked 로 재처리"})
        if (s.get("consumer_lag") or 0) > THRESHOLDS["consumer_lag"]:
            a.append({"name": "KafkaConsumerLag", "severity": "warning", "service": name, "summary": f"컨슈머 lag {s['consumer_lag']:.0f}"})
        if (s.get("events", {}).get("consumed", {}).get("dlq") or 0) >= THRESHOLDS["dlq"]:
            a.append({"name": "EventsToDLQ", "severity": "warning", "service": name, "summary": f"DLQ 이동 {s['events']['consumed']['dlq']:.0f}건"})
    return a


def summarize(ov: dict) -> dict:
    ups = [s for s in ov["services"] if s.get("up")]
    return {
        "services_up": len(ups), "services_total": len(ov["services"]),
        "rps": round(sum(s.get("rps") or 0 for s in ups), 2),
        "error_rate": round(max([s.get("error_rate") or 0 for s in ups] or [0]), 4),
        "p95_ms_max": max([s.get("p95_ms") or 0 for s in ups] or [0]),
        "outbox_pending": sum(s.get("outbox_pending") or 0 for s in ups),
        "consumer_lag": sum(s.get("consumer_lag") or 0 for s in ups),
        "alerts": len(ov.get("alerts", [])),
        "health": "critical" if any(x["severity"] == "critical" for x in ov.get("alerts", [])) else ("warning" if ov.get("alerts") else "ok"),
    }


# ------------------------------------------------------------------ Prometheus 모드
PROM_Q = {
    "rps": 'sum by (service) (rate(nova_http_requests_total[1m]))',
    "error_rate": 'sum by (service) (rate(nova_http_requests_total{status=~"5.."}[5m])) / clamp_min(sum by (service) (rate(nova_http_requests_total[5m])), 1e-9)',
    "p95": 'histogram_quantile(0.95, sum by (service, le) (rate(nova_http_request_duration_seconds_bucket[5m])))',
    "inflight": 'sum by (service) (nova_http_inflight_requests)',
    "outbox": 'sum by (service) (nova_outbox_pending)',
    "quarantined": 'max by (service) (nova_outbox_quarantined)',  # 레플리카마다 같은 DB 행 수를 내므로 합이 아니라 최댓값(alert_rules 와 같다)
    "lag": 'sum by (service) (nova_kafka_consumer_lag)',
    "dlq": 'sum by (service) (nova_events_consumed_total{result="dlq"})',
    "consumed": 'sum by (service) (nova_events_consumed_total{result="ok"})',
    "requests": 'sum by (service) (nova_http_requests_total)',
}


# 서비스별이 아닌 개요 질의 — PROM_Q 와 함께 한꺼번에 낸다(T04-6.07)
PROM_EXTRA = {
    "topics_pub": "sum by (topic) (nova_events_published_total)",
    "topics_dlq": 'sum by (topic) (nova_events_consumed_total{result="dlq"})',
    "topics_ok": 'sum by (topic) (nova_events_consumed_total{result="ok"})',
    "biz": "sum by (kind, status) (nova_business_events_total)",
    "amt": "sum by (kind, currency) (nova_business_amount_total)",
}


async def prom_overview() -> dict:
    # 질의 16개(서비스별 10 + up 1 + 토픽 · 업무 5)를 클라이언트 하나로 동시에 — 지연이 질의 수만큼 쌓이지 않고 가장 느린 하나만큼.
    # 실패 의미는 그대로: 하나라도 실패하면 gather 가 그 예외를 올리고 overview() 가 직접 수집으로 폴백한다(계획 §6)
    queries = {**{"svc:" + k: q for k, q in PROM_Q.items()}, "up": 'up{job=~"' + "|".join(ALL) + '"}', **PROM_EXTRA}
    async with prom_client() as c:
        res = dict(zip(queries, await asyncio.gather(*(prom("/api/v1/query", {"query": q}, c) for q in queries.values()))))
    v = {k: _vec(res["svc:" + k]) for k in PROM_Q}
    up = _vec(res["up"], "job")
    topics_pub = res["topics_pub"]
    topics_dlq = _vec(res["topics_dlq"], "topic")
    topics_ok = _vec(res["topics_ok"], "topic")
    biz, amt = res["biz"], res["amt"]
    rows = []
    for s in ALL:
        is_up = up.get(s, 0) >= 1
        p95 = v["p95"].get(s)
        rows.append({
            "service": s, "up": is_up, "rps": round(v["rps"].get(s, 0.0), 2), "error_rate": round(v["error_rate"].get(s, 0.0), 4),
            "p95_ms": round(p95 * 1000, 1) if p95 is not None and p95 == p95 else None, "inflight": v["inflight"].get(s, 0.0),
            "outbox_pending": v["outbox"].get(s, 0.0), "outbox_quarantined": v["quarantined"].get(s, 0.0), "consumer_lag": v["lag"].get(s, 0.0), "requests_total": v["requests"].get(s, 0.0),
            "events": {"consumed": {"ok": v["consumed"].get(s, 0.0), "dlq": v["dlq"].get(s, 0.0)}},
        })
    out = {
        "source": "prometheus", "generated_at": time.time(), "services": rows,
        "topics": [{"topic": t, "published": float(r["value"][1]), "consumed": topics_ok.get(t, 0.0), "dlq": topics_dlq.get(t, 0.0)} for t, r in ((x["metric"].get("topic", ""), x) for x in topics_pub.get("result", []))],
        "business": {f"{r['metric'].get('kind')}.{r['metric'].get('status')}": float(r["value"][1]) for r in biz.get("result", [])},
        "amount": {f"{r['metric'].get('kind')}:{r['metric'].get('currency')}": float(r["value"][1]) for r in amt.get("result", [])},
        "catalog": catalog.public(), "groups": catalog.groups(),
    }
    out["alerts"] = evaluate_alerts(out)
    out["summary"] = summarize(out)
    return out


async def overview() -> dict:
    if prom_url():
        try:
            return await prom_overview()
        except Exception as e:  # Prometheus 장애 → 직접 수집
            ov = await scraper.overview()
            return {**ov, "source": "direct", "prometheus_error": f"{type(e).__name__}: {e}"[:200]}
    return await scraper.overview()
