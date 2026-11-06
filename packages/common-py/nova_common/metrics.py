"""Prometheus 메트릭 정의 — 모든 서비스가 같은 이름·라벨을 쓰므로 Grafana 대시보드 하나로 전체 서비스를 본다.

라벨 카디널리티를 낮게 유지(route는 템플릿 경로, user/id 라벨 금지)해 Prometheus 메모리를 절약한다.
"""
from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "nova_http_requests_total", "HTTP 요청 수", ["service", "method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "nova_http_request_duration_seconds",
    "HTTP 요청 지연",
    ["service", "method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
HTTP_INFLIGHT = Gauge("nova_http_inflight_requests", "처리 중 요청", ["service"])

EVENTS_PUBLISHED = Counter("nova_events_published_total", "발행 이벤트", ["service", "topic"])
EVENTS_CONSUMED = Counter(
    "nova_events_consumed_total", "소비 이벤트 (result=ok|duplicate|retry|dlq)", ["service", "topic", "result"]
)
EVENT_HANDLER_LATENCY = Histogram(
    "nova_event_handler_duration_seconds",
    "이벤트 핸들러 처리 시간",
    ["service", "topic"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)
EVENT_E2E_LAG = Histogram(
    "nova_event_delivery_lag_seconds",
    "이벤트 발생→소비 지연 (Kafka 경유 전달 지연)",
    ["service", "topic"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 15.0),
)
OUTBOX_PENDING = Gauge("nova_outbox_pending", "발행 대기 아웃박스 이벤트(격리 행 제외)", ["service"])
# 격리(parked) 행 — 자동 재시도하지 않으므로 사람이 보고 재처리해야 한다(python nova.py parked · 알림 OutboxQuarantined)
OUTBOX_QUARANTINED = Gauge("nova_outbox_quarantined", "격리된 아웃박스 이벤트(재처리 대기)", ["service"])
CONSUMER_LAG = Gauge("nova_kafka_consumer_lag", "컨슈머 그룹 lag(메시지)", ["service", "topic", "partition"])

# 비즈니스 · 사가 메트릭 — 프로젝트 업무 메트릭은 각 서비스에서 같은 접두어(nova_)로 정의한다
SAGA_DURATION = Histogram(
    "nova_saga_duration_seconds",
    "사가 소요(시작→종료)",
    ["saga", "outcome"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)
BUSINESS_EVENTS = Counter("nova_business_events_total", "비즈니스 이벤트 카운터", ["service", "kind", "status"])
# 금액 합계 — 통화는 라벨로(단위 접미사를 이름에 넣지 않는다)
BUSINESS_AMOUNT = Counter("nova_business_amount_total", "금액 합계", ["service", "kind", "currency"])
