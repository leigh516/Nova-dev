#!/usr/bin/env python3
"""Grafana 대시보드 JSON 생성기 — 플랫폼 공통 2종(서비스 개요 RED · Kafka 이벤트).

  uv run python scripts/gen_dashboards.py          # infra/observability/grafana/dashboards/platform-*.json
  uv run python scripts/gen_dashboards.py --check  # 서비스 카탈로그와 어긋나면 실패(lint)
프로젝트 업무 대시보드는 같은 Dash 빌더로 이 파일 아래에 추가하거나, Grafana 에서 만든 JSON 을 dashboards/ 에 둔다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import project, same, write  # noqa: E402

from nova_common import catalog  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "infra" / "observability" / "grafana" / "dashboards"
RESULT: dict[Path, str] = {}
DS = {"type": "prometheus", "uid": "prometheus"}
# 상태 색(성공 · 주의 · 위험 · 정보 · 강조)
C = {"ok": "#2BB673", "warn": "#E8A33D", "bad": "#E8505B", "info": "#3BA3E8", "brand": "#4F5BD5"}


class Dash:
    def __init__(self, uid, title, tags, desc):
        self.d = {
            "uid": uid, "title": title, "tags": ["platform", *tags], "description": desc, "timezone": "browser", "schemaVersion": 39,
            "refresh": "15s", "time": {"from": "now-1h", "to": "now"}, "editable": True, "graphTooltip": 1, "panels": [],
            "templating": {"list": []}, "annotations": {"list": []},
        }
        self.y = 0
        self.id = 1

    def var_service(self):
        self.d["templating"]["list"].append({
            "name": "service", "label": "서비스", "type": "query", "datasource": DS, "query": "label_values(nova_http_requests_total, service)",
            "includeAll": True, "multi": True, "current": {"text": "All", "value": "$__all"}, "refresh": 2,
        })
        return self

    def row(self, title):
        self.d["panels"].append({"id": self.id, "type": "row", "title": title, "collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": self.y}})
        self.id += 1
        self.y += 1
        return self

    def stats(self, items, h=4):
        w = 24 // len(items)
        for i, (title, expr, unit, color, thresholds) in enumerate(items):
            steps = [{"color": color, "value": None}] + [{"color": c, "value": v} for v, c in (thresholds or [])]
            self.d["panels"].append({
                "id": self.id, "type": "stat", "title": title, "datasource": DS, "gridPos": {"h": h, "w": w, "x": i * w, "y": self.y},
                "targets": [{"refId": "A", "expr": expr, "datasource": DS}],
                "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": steps}}, "overrides": []},
                "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "background", "graphMode": "area", "textMode": "auto"},
            })
            self.id += 1
        self.y += h
        return self

    def ts(self, title, targets, unit="short", w=12, x=0, h=8, stack=False, newline=True):
        self.d["panels"].append({
            "id": self.id, "type": "timeseries", "title": title, "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": self.y},
            "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": lf, "datasource": DS} for i, (e, lf) in enumerate(targets)],
            "fieldConfig": {"defaults": {"unit": unit, "custom": {"lineWidth": 2, "fillOpacity": 18, "gradientMode": "opacity", "stacking": {"mode": "normal" if stack else "none"}}}, "overrides": []},
            "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]}, "tooltip": {"mode": "multi"}},
        })
        self.id += 1
        if newline:
            self.y += h
        return self

    def pair(self, a, b):
        self.ts(*a[:2], **{**a[2], "w": 12, "x": 0, "newline": False})
        self.ts(*b[:2], **{**b[2], "w": 12, "x": 12, "newline": True})
        return self

    def table(self, title, expr, h=8):
        self.d["panels"].append({
            "id": self.id, "type": "table", "title": title, "datasource": DS, "gridPos": {"h": h, "w": 24, "x": 0, "y": self.y},
            "targets": [{"refId": "A", "expr": expr, "format": "table", "instant": True, "datasource": DS}],
            "transformations": [{"id": "organize", "options": {"excludeByName": {"Time": True}}}],
        })
        self.id += 1
        self.y += h
        return self

    def save(self, name):
        RESULT[OUT / name] = json.dumps(self.d, ensure_ascii=False, indent=1) + "\n"


SV = 'service=~"$service"'


def main():
    name = project().get("name", "Platform")
    jobs = "|".join(catalog.names())
    gw = catalog.gateway()
    ns = "|".join(dict.fromkeys(s.namespace for s in catalog.services()))
    n = len(catalog.names())
    (Dash("platform-overview", f"{name} · 서비스 개요 (RED)", ["red"], "서비스별 요청률 · 오류율 · 지연 · 자원").var_service()
     .stats([
        ("가동 서비스", f'count(up{{job=~"{jobs}"}} == 1)', "none", C["ok"], [(0, C["bad"]), (n, C["ok"])]),
        ("전체 RPS", "sum(service:http_requests:rate1m)", "reqps", C["brand"], None),
        ("최대 5xx 비율", "max(service:http_errors:ratio5m)", "percentunit", C["ok"], [(0.01, C["warn"]), (0.05, C["bad"])]),
        ("게이트웨이 p95", f'service:http_latency_seconds:p95_5m{{service="{gw}"}}', "s", C["ok"], [(0.3, C["warn"]), (1, C["bad"])]),
        ("활성 알림", 'count(ALERTS{alertstate="firing"}) or vector(0)', "none", C["ok"], [(1, C["bad"])]),
     ])
     .row("요청")
     .pair(("요청률(RPS)", [(f"sum by (service) (rate(nova_http_requests_total{{{SV}}}[1m]))", "{{service}}")], {"unit": "reqps"}),
           ("5xx 오류율", [(f"service:http_errors:ratio5m{{{SV}}}", "{{service}}")], {"unit": "percentunit"}))
     .pair(("지연 p95", [(f"service:http_latency_seconds:p95_5m{{{SV}}}", "{{service}}")], {"unit": "s"}),
           ("처리 중 요청", [(f"sum by (service) (nova_http_inflight_requests{{{SV}}})", "{{service}}")], {}))
     .table("느린 라우트 Top (p95)", 'topk(10, histogram_quantile(0.95, sum by (service, route, le) (rate(nova_http_request_duration_seconds_bucket[5m]))))')
     .row("자원")
     .pair(("CPU (코어)", [(f'sum by (pod) (rate(container_cpu_usage_seconds_total{{namespace=~"{ns}",container!=""}}[5m]))', "{{pod}}")], {}),
           ("메모리", [(f'sum by (pod) (container_memory_working_set_bytes{{namespace=~"{ns}",container!=""}})', "{{pod}}")], {"unit": "bytes"}))
     ).save("platform-overview.json")

    (Dash("platform-events", f"{name} · Kafka 이벤트", ["kafka"], "아웃박스 → Kafka → 멱등 소비 파이프라인 · lag · DLQ")
     .stats([
        ("발행/초", "sum(topic:events_published:rate5m)", "ops", C["brand"], None),
        ("미발행 아웃박스", "sum(nova_outbox_pending)", "none", C["ok"], [(50, C["warn"]), (100, C["bad"])]),
        ("컨슈머 lag", "sum(nova_kafka_consumer_lag)", "none", C["ok"], [(100, C["warn"]), (1000, C["bad"])]),
        ("DLQ (1h)", 'sum(increase(nova_events_consumed_total{result="dlq"}[1h])) or vector(0)', "none", C["ok"], [(1, C["bad"])]),
        ("중복 차단 (1h)", 'sum(increase(nova_events_consumed_total{result="duplicate"}[1h])) or vector(0)', "none", C["info"], None),
     ])
     .pair(("토픽별 발행률", [("topic:events_published:rate5m", "{{topic}}")], {"unit": "ops", "stack": True}),
           ("서비스별 소비 결과", [('sum by (service, result) (service_topic:events_consumed:rate5m)', "{{service}} · {{result}}")], {"unit": "ops"}))
     .pair(("컨슈머 lag (파티션 합)", [("service:kafka_consumer_lag:sum", "{{service}}")], {}),
           ("이벤트 전달 지연 p95", [("service:event_delivery_lag_seconds:p95_5m", "{{service}}")], {"unit": "s"}))
     .pair(("아웃박스 대기", [("sum by (service) (nova_outbox_pending)", "{{service}}")], {}),
           ("핸들러 처리 시간 p95", [("histogram_quantile(0.95, sum by (service, le) (rate(nova_event_handler_duration_seconds_bucket[5m])))", "{{service}}")], {"unit": "s"}))
     ).save("platform-events.json")
    return RESULT


def run(check: bool) -> int:
    RESULT.clear()
    main()
    stale = [p for p, t in RESULT.items() if not same(p, t)]
    if check:
        if stale:
            print("✗ 대시보드가 원천과 다릅니다 — uv run python scripts/gen_dashboards.py 실행 후 커밋:", *[p.name for p in stale], sep="\n  ", file=sys.stderr)
            return 1
        print(f"✓ 대시보드 최신: {len(RESULT)}개")
        return 0
    for p in stale:
        write(p, RESULT[p])
    print(f"✓ 대시보드 생성: {len(RESULT)}개 (변경 {len(stale)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(run("--check" in sys.argv[1:]))
