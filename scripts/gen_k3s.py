#!/usr/bin/env python3
"""인프라 생성기 — 단일 원천 두 개에서 배포 산출물 전부를 만든다.

  원천: packages/common-py/nova_common/services.json (서비스 목록) · nova.project.json (이름 · 레지스트리 · 도메인 · 웹 앱)
  uv run python scripts/gen_k3s.py          # 생성(커밋한다 — 쿠버네티스 쪽은 순수 YAML 로 리뷰)
  uv run python scripts/gen_k3s.py --check  # 생성물이 원천과 어긋나면 실패(lint)
  uv run python scripts/gen_k3s.py --list-secrets  # 첫 배포 전 원격 시크릿 저장소에 채울 키 목록(값 없음 — deploy.md '첫 배포 준비')

산출물(전부 생성 — 손으로 고치지 않는다):
  infra/k3s/base/       namespaces · configmap-common · networkpolicy · secrets-dev · svc-<서비스> · web-<앱> · ingress · mariadb-init.sql · kustomization
  infra/k3s/overlays/   dev/kustomization · prod/{kustomization, delete-dev-secrets, secrets-external, ingress-tls, mariadb-init.sql,
                        alertmanager.yml · alertmanager-data.yaml · db-provision-job.yaml · db-provision.sh ·
                        mariadb-backup.yaml(DB 서비스가 있을 때)}
  infra/helm/chart/     Chart.yaml · values.yaml          (템플릿 templates/ 는 손 관리)
  infra/observability/  kustomization · prometheus/{prometheus.yml(k3s), prometheus.compose.yml(compose), alert_rules.yml} ·
                        alertmanager/{alertmanager.yml(k3s), alertmanager.compose.yml(compose)}
  docker-compose.yml
  web/packages/sdk/src/project.gen.ts   웹 표시 기본값(LOCALE · TIMEZONE) — 환경 변수 NEXT_PUBLIC_* 가 없을 때 sdk 가 쓴다
손으로 관리하는 파일(프로젝트 이름 없음): infra/k3s/base/{kafka,mariadb}.yaml · kafka-topics.txt · prometheus/recording_rules.yml ·
  observability/k8s/* · grafana/provisioning/* · helm/chart/templates/* · infra/docker/*
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, env_name, project, same, write  # noqa: E402

from nova_common import catalog  # noqa: E402

BASE = ROOT / "infra" / "k3s" / "base"
DEV = ROOT / "infra" / "k3s" / "overlays" / "dev"
PROD = ROOT / "infra" / "k3s" / "overlays" / "prod"
HELM = ROOT / "infra" / "helm" / "chart"
OBS = ROOT / "infra" / "observability"
SDK_GEN = ROOT / "web" / "packages" / "sdk" / "src" / "project.gen.ts"
HDR = "# 생성 파일 — scripts/gen_k3s.py (services.json · nova.project.json). 직접 고치지 않는다.\n"
SQL_HDR = "-- 생성 파일 — scripts/gen_k3s.py (services.json). 직접 고치지 않는다.\n"


class Ctx:
    def __init__(self) -> None:
        p = project()
        self.slug: str = p["slug"]
        self.ld: str = p.get("label_domain", f"{self.slug}.dev")
        self.registry: str = p.get("image_registry", f"ghcr.io/example/{self.slug}")
        self.domain: str = p.get("domain", f"{self.slug}.local")
        self.webs: list[dict] = p.get("web_apps", [])
        # 서비스 런타임이 읽는 메타(nova_common.runtime) · 웹 표시 기본값(sdk project.gen.ts) — 원천은 nova.project.json 하나(R10).
        # 기본값을 두지 않는다 — 여기 적으면 코드 기본값과 또 하나의 복제가 된다
        missing = [k for k in ("super_role", "tz_offset_hours", "locale", "timezone") if k not in p]
        if missing:
            raise SystemExit(f"✗ nova.project.json 에 {', '.join(missing)} 가 없다 — 예: super_role \"admin\" · tz_offset_hours 9 · "
                             "locale \"ko-KR\" · timezone \"Asia/Seoul\"")
        self.super_role: str = p["super_role"]
        self.tz_offset_hours = p["tz_offset_hours"]
        self.locale: str = p["locale"]
        self.timezone: str = p["timezone"]
        # 판본 = 운영 이미지 태그 = 되돌아갈 자리. 기본값을 두지 않는다 — 박아 두면 판본과 태그가 다시 어긋난다(REQ-261104-10-6)
        if not str(p.get("version", "")).strip():
            raise SystemExit("✗ nova.project.json 에 version 이 없다 — 마지막 출시 판본(X.Y.Z)을 적는다(release ship 이 기록한다)")
        self.version: str = str(p["version"])
        self.services = catalog.services()
        # 허용 목록 오타는 조용히 '아무도 허용 안 함'(운영에서만 드러나는 차단)이 된다 — 생성 단계에서 멈춘다(plan_REQ_02 §6)
        known = {s.name for s in self.services}
        bad = [f"{s.name} → {f}" for s in self.services for f in s.allow_from if f not in known]
        if bad:
            raise SystemExit(f"✗ services.json k8s.allow_from 에 카탈로그에 없는 서비스: {', '.join(bad)}")
        self.gw = catalog.get(catalog.gateway())
        self.svc_ns = list(dict.fromkeys([self.gw.namespace, *(s.namespace for s in self.services)]))
        self.db_ns = sorted({s.namespace for s in self.services if s.db})
        self.ns = [*self.svc_ns, "infra", "observability"]
        self.cm = f"{self.slug}-common"
        self.auth = f"{self.slug}-auth"
        self.store = f"{self.slug}-secrets"
        self.db_provision = f"{self.slug}-db-provision"  # 운영 DB 계정 프로비저닝 Job 이 읽는 시크릿(infra)

    def db_secret(self, name: str) -> str:
        return f"{self.slug}-db-{name}"

    def image(self, name: str) -> str:
        return f"{self.slug}/{name}"


OUT: dict[Path, str] = {}

# ------------------------------------------------------------------ DB 연결 예산(T07-1.05)
# 파드당 풀 최대 = nova_common/db.py 의 pool_size + max_overflow(tests/test_infra.py 가 대조 — 한쪽만 바꾸면 테스트가 잡는다)
DB_POOL_MAX = 10
# 서비스 풀 밖에서 쓰는 몫 — 운영자 접속 · db-provision Job · 백업 덤프 · MariaDB healthcheck
DB_RESERVED = 10
MARIADB_YAML = BASE / "mariadb.yaml"  # 손 관리 — --max-connections 의 원천


def mariadb_max_connections() -> int:
    m = re.search(r"--max-connections=(\d+)", MARIADB_YAML.read_text(encoding="utf-8"))
    if not m:  # 없으면 서버 기본값(151)이 조용히 쓰인다 — 예산을 셀 수 없으니 멈춘다
        raise SystemExit(f"✗ {MARIADB_YAML.relative_to(ROOT).as_posix()} 에 --max-connections=<수> 가 없다 — DB 연결 예산을 셀 수 없다")
    return int(m[1])


def db_budget(c: "Ctx") -> tuple[int, list[tuple[str, int]]]:
    """운영 최악의 DB 연결 수 — DB 서비스마다 (최대 복제본 + 롤링 maxSurge 1) × 파드당 풀 최대, 더하기 예비분."""
    rows = [(s.name, (max(s.k8s["hpa_max"], s.k8s.get("replicas", 1)) + 1) * DB_POOL_MAX) for s in c.services if s.db]
    return sum(n for _, n in rows) + DB_RESERVED, rows


def check_db_budget(c: "Ctx") -> None:
    """복제본이 다 뜨면 연결이 모자라 새 파드가 기동 · 준비 확인에서 실패한다 — 운영에서야 드러나므로 생성 단계에서 멈춘다."""
    used, rows = db_budget(c)
    limit = mariadb_max_connections()
    if used > limit:
        detail = " · ".join(f"{n} {k}" for n, k in rows)
        raise SystemExit(f"✗ DB 연결 예산 초과: {used} > MariaDB max_connections {limit} — 서비스별 (hpa_max + 1) × 풀 {DB_POOL_MAX}: "
                         f"{detail} · 예비 {DB_RESERVED}. services.json k8s.hpa_max 를 줄이거나 "
                         f"{MARIADB_YAML.relative_to(ROOT).as_posix()} --max-connections 를 늘린다(메모리도 같이 본다)")


def put(path: Path, text: str) -> None:
    OUT[path] = text


def meta_env(c: Ctx, indent: str) -> str:
    """configmap · compose 공통 환경 — 코드 기본값(runtime.py)에 기대지 않고 메타 값을 그대로 싣는다."""
    return (f'{indent}NOVA_SUPER_ROLE: "{c.super_role}"\n'
            f'{indent}NOVA_TZ_OFFSET_HOURS: "{c.tz_offset_hours}"')


# ------------------------------------------------------------------ k3s base
def deployment(c: Ctx, s) -> str:
    env = f"""        env:
        - name: JWT_SECRET
          valueFrom: {{secretKeyRef: {{name: {c.auth}, key: jwt-secret}}}}"""
    if s.db:
        env += f"""
        - name: DATABASE_URL_{s.env}
          valueFrom: {{secretKeyRef: {{name: {c.db_secret(s.name)}, key: url}}}}"""
    tier = s.k8s.get("tier", s.group)
    return HDR + f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {s.name}
  namespace: {s.namespace}
  labels: {{app: {s.name}, {c.ld}/tier: {tier}}}
spec:
  replicas: 1
  revisionHistoryLimit: 3
  selector: {{matchLabels: {{app: {s.name}}}}}
  strategy: {{type: RollingUpdate, rollingUpdate: {{maxSurge: 1, maxUnavailable: 0}}}}
  template:
    metadata:
      labels: {{app: {s.name}, {c.ld}/tier: {tier}}}
      annotations: {{prometheus.io/scrape: "true", prometheus.io/port: "8000", prometheus.io/path: /metrics}}
    spec:
      automountServiceAccountToken: false
      securityContext: {{runAsNonRoot: true, runAsUser: 10001, seccompProfile: {{type: RuntimeDefault}}}}
      terminationGracePeriodSeconds: 30
      containers:
      - name: app
        image: {c.image(s.name)}:dev
        imagePullPolicy: IfNotPresent
        ports: [{{name: http, containerPort: 8000}}]
        envFrom:
        - configMapRef: {{name: {c.cm}}}
{env}
        resources:
          requests: {{cpu: {s.k8s["cpu"]}, memory: {s.k8s["memory"]}}}
          limits: {{memory: {s.k8s["memory_limit"]}}}
        readinessProbe: {{httpGet: {{path: /readyz, port: http}}, periodSeconds: 5, failureThreshold: 3}}
        livenessProbe: {{httpGet: {{path: /healthz, port: http}}, initialDelaySeconds: 15, periodSeconds: 15}}
        startupProbe: {{httpGet: {{path: /healthz, port: http}}, periodSeconds: 2, failureThreshold: 30}}
        securityContext: {{allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {{drop: [ALL]}}}}
        volumeMounts: [{{name: tmp, mountPath: /tmp}}]
      volumes: [{{name: tmp, emptyDir: {{sizeLimit: 64Mi}}}}]
---
apiVersion: v1
kind: Service
metadata:
  name: {s.name}
  namespace: {s.namespace}
spec:
  selector: {{app: {s.name}}}
  ports: [{{name: http, port: 8000, targetPort: http}}]
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {s.name}
  namespace: {s.namespace}
spec:
  scaleTargetRef: {{apiVersion: apps/v1, kind: Deployment, name: {s.name}}}
  minReplicas: 1
  maxReplicas: {s.k8s["hpa_max"]}
  metrics:
  - type: Resource
    resource: {{name: cpu, target: {{type: Utilization, averageUtilization: 70}}}}
  behavior:
    scaleDown: {{stabilizationWindowSeconds: 300}}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {s.name}
  namespace: {s.namespace}
spec:
  maxUnavailable: 1
  selector: {{matchLabels: {{app: {s.name}}}}}
"""


def web(c: Ctx, app: dict) -> str:
    """웹 앱 — probe 3종 · 보안 컨텍스트 · PDB 는 서비스 deployment() 와 같은 값. 경로만 웹 포트의 / (Next 에 /healthz 가 없다).
    readOnlyRootFilesystem 이라 Next 가 실행 중에 쓰는 곳만 emptyDir 로 연다: /tmp(os.tmpdir) · .next/cache(이미지 · fetch 캐시)."""
    n = f"web-{app['name']}"
    cache = f"/web/apps/{app['name']}/.next/cache"  # Dockerfile.web 의 WORKDIR /web + apps/<앱>
    return HDR + f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {n}
  namespace: {c.gw.namespace}
  labels: {{app: {n}, {c.ld}/tier: web}}
spec:
  replicas: 1
  selector: {{matchLabels: {{app: {n}}}}}
  template:
    metadata:
      labels: {{app: {n}, {c.ld}/tier: web}}
    spec:
      automountServiceAccountToken: false
      securityContext: {{runAsNonRoot: true, runAsUser: 1000, seccompProfile: {{type: RuntimeDefault}}}}
      containers:
      - name: web
        image: {c.image(n)}:dev
        ports: [{{name: http, containerPort: {app['port']}}}]
        resources:
          requests: {{cpu: 25m, memory: 96Mi}}
          limits: {{memory: 256Mi}}
        readinessProbe: {{httpGet: {{path: /, port: http}}, periodSeconds: 5, failureThreshold: 3}}
        livenessProbe: {{httpGet: {{path: /, port: http}}, initialDelaySeconds: 15, periodSeconds: 15}}
        startupProbe: {{httpGet: {{path: /, port: http}}, periodSeconds: 2, failureThreshold: 30}}
        securityContext: {{allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {{drop: [ALL]}}}}
        volumeMounts: [{{name: tmp, mountPath: /tmp}}, {{name: next-cache, mountPath: {cache}}}]
      volumes: [{{name: tmp, emptyDir: {{sizeLimit: 64Mi}}}}, {{name: next-cache, emptyDir: {{sizeLimit: 64Mi}}}}]
---
apiVersion: v1
kind: Service
metadata:
  name: {n}
  namespace: {c.gw.namespace}
spec:
  selector: {{app: {n}}}
  ports: [{{name: http, port: {app['port']}, targetPort: http}}]
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {n}
  namespace: {c.gw.namespace}
spec:
  maxUnavailable: 1
  selector: {{matchLabels: {{app: {n}}}}}
"""


def namespaces(c: Ctx) -> str:
    return HDR + "".join(f"""apiVersion: v1
kind: Namespace
metadata:
  name: {n}
  labels: {{{c.ld}/ns: {n}}}
---
""" for n in c.ns)


def configmaps(c: Ctx) -> str:
    urls = "\n".join(f'  SVC_{s.env}_URL: "http://{s.name}.{s.namespace}.svc.cluster.local:8000"' for s in c.services)
    origins = ",".join([f"https://{c.domain}", *(f"https://{w['name']}.{c.domain}" for w in c.webs[1:])])
    out = HDR
    for ns in sorted({s.namespace for s in c.services}):
        out += f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {c.cm}
  namespace: {ns}
data:
  KAFKA_BOOTSTRAP: "kafka.infra.svc.cluster.local:9092"
  OUTBOX_RELAY_INTERVAL: "0.2"
  LOG_LEVEL: "INFO"
  PROMETHEUS_URL: "http://prometheus.observability.svc.cluster.local:9090"
  GW_CORS_ORIGINS: "{origins}"
  NOVA_PACKS: "{",".join(project().get("packs", []))}"
{meta_env(c, '  ')}
{urls}
---
"""
    return out


# 서비스를 직접 부르는 관측 파드(app 라벨 — infra/observability/k8s/*.yaml). 백엔드는 스크레이프만 받고,
# 게이트웨이는 Alertmanager 웹훅(/internal/alertmanager)도 받는다. Grafana 는 Prometheus 만 부르므로 넣지 않는다
OBS_APPS = {"backend": ["prometheus"], "gateway": ["prometheus", "alertmanager"]}
OBS_WHY = {"backend": "Prometheus 스크레이프만", "gateway": "Prometheus 스크레이프 · Alertmanager 웹훅"}


def netpols(c: Ctx) -> str:
    out = HDR
    for ns in c.svc_ns:
        out += f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: {ns}
spec:
  podSelector: {{}}
  policyTypes: [Ingress]
---
"""
    # 서비스 단위 허용(REQ-261104-10-4) — 같은 peer 안 namespaceSelector + podSelector 는 AND: 그 네임스페이스의 그 파드만.
    # 네임스페이스 통째 허용을 두지 않는다 — 허용 목록(k8s.allow_from) 밖 파드의 직접 호출은 운영에서 막힌다
    pod = lambda s: f"    - namespaceSelector: {{matchLabels: {{{c.ld}/ns: {s.namespace}}}}}\n      podSelector: {{matchLabels: {{app: {s.name}}}}}\n"  # noqa: E731
    def obs(kind: str) -> str:  # observability 네임스페이스 통째가 아니라 그 안의 관측 파드만(T07-2.05)
        apps = ", ".join(OBS_APPS[kind])
        return (f"    - namespaceSelector: {{matchLabels: {{{c.ld}/ns: observability}}}}  # {OBS_WHY[kind]}\n"
                f"      podSelector: {{matchExpressions: [{{key: app, operator: In, values: [{apps}]}}]}}\n")
    for s in c.services:
        if s.gateway:
            continue
        peers = pod(c.gw) + "".join(pod(catalog.get(f)) for f in s.allow_from) + obs("backend")
        out += f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-{s.name}
  namespace: {s.namespace}
spec:
  podSelector: {{matchLabels: {{app: {s.name}}}}}
  policyTypes: [Ingress]
  ingress:
  - from:
{peers}    ports: [{{port: 8000}}]
---
"""
    kube = "    - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}  # 인그레스 컨트롤러(Traefik)\n"
    # 게이트웨이 — 인그레스 · 관측만. 웹 파드는 들이지 않는다: 웹 화면은 모두 클라이언트 컴포넌트라 브라우저가 인그레스로 부른다(T02-4.03 확인)
    out += f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-{c.gw.name}
  namespace: {c.gw.namespace}
spec:
  podSelector: {{matchLabels: {{app: {c.gw.name}}}}}
  policyTypes: [Ingress]
  ingress:
  - from:
{kube}{obs("gateway")}    ports: [{{port: 8000}}]
---
"""
    if c.webs:  # 웹 앱이 없는 프로젝트는 빈 In 목록(무효 선택자)을 만들지 않는다
        webs = ", ".join(f"web-{w['name']}" for w in c.webs)
        ports = ", ".join(f"{{port: {n}}}" for n in sorted({w["port"] for w in c.webs}))  # 앱마다 포트가 다를 수 있다
        out += f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-controller
  namespace: {c.gw.namespace}
spec:
  podSelector: {{matchExpressions: [{{key: app, operator: In, values: [{webs}]}}]}}
  policyTypes: [Ingress]
  ingress:
  - from:
{kube}    ports: [{ports}]
---
"""
    out += f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: kafka-from-services, namespace: infra}}
spec:
  podSelector: {{matchLabels: {{app: kafka}}}}
  policyTypes: [Ingress]
  ingress:
  - from:
    - namespaceSelector: {{matchExpressions: [{{key: {c.ld}/ns, operator: In, values: [{", ".join([*c.svc_ns, "infra"])}]}}]}}
    ports: [{{port: 9092}}, {{port: 9093}}]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: mariadb-from-services, namespace: infra}}
spec:
  podSelector: {{matchLabels: {{app: mariadb}}}}
  policyTypes: [Ingress]
  ingress:
  - from:
    - namespaceSelector: {{matchExpressions: [{{key: {c.ld}/ns, operator: In, values: [{", ".join(c.db_ns or ["infra"])}]}}]}}
    # 같은 peer 안의 두 선택자는 AND — infra 네임스페이스의 계정 Job(운영) · 백업 파드만. infra 의 다른 파드(kafka 등)는 막힌다
    - namespaceSelector: {{matchLabels: {{{c.ld}/ns: infra}}}}
      podSelector: {{matchExpressions: [{{key: app, operator: In, values: [db-provision, mariadb-backup]}}]}}
    ports: [{{port: 3306}}]
"""
    return out


def dev_secrets(c: Ctx) -> str:
    out = HDR + "# 개발용 값. 운영은 overlays/prod 가 이 시크릿을 지우고 ExternalSecret 으로 대체한다(기본 JWT 키면 서비스가 기동 거부)\n"
    for s in c.services:
        if s.db:
            d = s.db_name
            out += f"""apiVersion: v1
kind: Secret
metadata:
  name: {c.db_secret(s.name)}
  namespace: {s.namespace}
type: Opaque
stringData:
  url: "mysql+pymysql://{d}:dev-{d}-pw@mariadb.infra.svc.cluster.local:3306/{d}?charset=utf8mb4"
---
"""
    for ns in sorted({s.namespace for s in c.services}):
        out += f"""apiVersion: v1
kind: Secret
metadata:
  name: {c.auth}
  namespace: {ns}
type: Opaque
stringData:
  jwt-secret: "nova-dev-secret-change-me"
---
"""
    return out


def web_host(c: Ctx, i: int, w: dict) -> str:
    return c.domain if i == 0 else f"{w['name']}.{c.domain}"


def ingresses(c: Ctx) -> list[tuple[str, str, list[str]]]:
    """(이름, 네임스페이스, 호스트 목록) — base ingress() 의 규칙 순서와 같다. 운영 TLS 패치가 같은 목록을 쓴다."""
    return [(c.slug, c.gw.namespace, [f"api.{c.domain}", *(web_host(c, i, w) for i, w in enumerate(c.webs))]),
            ("grafana", "observability", [f"grafana.{c.domain}"])]


def ingress(c: Ctx) -> str:
    gw = f"{{service: {{name: {c.gw.name}, port: {{number: 8000}}}}}}"
    rules = f"""  - host: api.{c.domain}
    http: {{paths: [{{path: /v1, pathType: Prefix, backend: {gw}}}]}}
"""
    for i, w in enumerate(c.webs):
        host = web_host(c, i, w)
        rules += f"""  - host: {host}
    http:
      paths:
      - {{path: /v1, pathType: Prefix, backend: {gw}}}
      - {{path: /, pathType: Prefix, backend: {{service: {{name: web-{w['name']}, port: {{number: {w['port']}}}}}}}}}
"""
    return HDR + f"""# k3s 기본 Traefik. 운영은 overlays/prod 가 TLS · websecure 전용 · HSTS 를 덧붙인다(ingress-tls.yaml) — 개발은 *.{c.domain} 을 hosts 파일에 등록
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {c.slug}
  namespace: {c.gw.namespace}
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web,websecure
spec:
  ingressClassName: traefik
  rules:
{rules}---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grafana
  namespace: observability
spec:
  ingressClassName: traefik
  rules:
  - host: grafana.{c.domain}
    http: {{paths: [{{path: /, pathType: Prefix, backend: {{service: {{name: grafana, port: {{number: 3000}}}}}}}}]}}
"""


def dev_mariadb_init(c: Ctx) -> str:
    dbs = [s.db_name for s in c.services if s.db]
    return (SQL_HDR + "-- 서비스별 스키마 + 전용 계정(자기 스키마에만 권한 — 교차 조인 · 교차 쓰기 불가). 비밀번호는 개발용 고정값.\n"
            "-- 테이블은 각 서비스가 기동 시 마이그레이션(Alembic 플랫폼 + 서비스 분기, ADR-011)으로 만든다. migrations 폴더가 없는 서비스만 create_all.\n"
            + "".join(f"CREATE DATABASE IF NOT EXISTS {d} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n" for d in dbs)
            + "".join(f"CREATE USER IF NOT EXISTS '{d}'@'%' IDENTIFIED BY 'dev-{d}-pw';\n" for d in dbs)
            + "".join(f"GRANT ALL PRIVILEGES ON {d}.* TO '{d}'@'%';\n" for d in dbs)
            + "FLUSH PRIVILEGES;\n")


def base(c: Ctx) -> None:
    put(BASE / "namespaces.yaml", namespaces(c))
    put(BASE / "configmap-common.yaml", configmaps(c))
    put(BASE / "networkpolicy.yaml", netpols(c))
    put(BASE / "secrets-dev.yaml", dev_secrets(c))
    put(BASE / "ingress.yaml", ingress(c))
    put(BASE / "mariadb-init.sql", dev_mariadb_init(c))
    files = ["namespaces.yaml", "configmap-common.yaml", "networkpolicy.yaml", "secrets-dev.yaml"]
    for s in c.services:
        put(BASE / f"svc-{s.name}.yaml", deployment(c, s))
        files.append(f"svc-{s.name}.yaml")
    for w in c.webs:
        put(BASE / f"web-{w['name']}.yaml", web(c, w))
        files.append(f"web-{w['name']}.yaml")
    files += ["kafka.yaml", "mariadb.yaml", "ingress.yaml"]
    put(BASE / "kustomization.yaml", HDR + f"""apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
labels:
- pairs: {{app.kubernetes.io/part-of: {c.slug}, app.kubernetes.io/managed-by: kustomize}}
  includeTemplates: true
resources:
""" + "".join(f"- {f}\n" for f in files) + """configMapGenerator:
- name: kafka-topics
  namespace: infra
  files: [kafka-topics.txt]
- name: mariadb-init
  namespace: infra
  files: [mariadb-init.sql]
generatorOptions:
  disableNameSuffixHash: true
""")


# ------------------------------------------------------------------ overlays
EXTRA_SECRETS = [("mariadb-root", "infra", ["password"]), ("grafana-admin", "observability", ["user", "password"])]
# 운영에만 있는 시크릿 — 개발 base 에 같은 이름이 없으므로 delete-dev-secrets 에 넣지 않는다(없는 리소스 삭제 → kustomize 실패)
PROD_ONLY_SECRETS = [("alertmanager-receivers", "observability", ["oncall-url"])]
# 운영 알림 수신처(R2) — oncall URL 은 시크릿 파일에서 읽는다(url_file, Alertmanager 0.26+). 생성물에 URL 글자를 두지 않는다
ONCALL_URL_FILE = "/etc/alertmanager/receivers/oncall-url"
AM_DATA = {"storage": "1Gi"}  # 침묵 · 발송 기록(nflog) — 작다. 재시작 뒤 침묵이 풀려 알림이 다시 쏟아지지 않게 PVC 로
# 운영 게이트웨이가 믿는 프록시 홉 수(P-5) — k3s Traefik 하나만 앞에 있다. 앞에 클라우드 L7 LB 를 더 두면 2.
# k3s prod 공통 ConfigMap 과 Helm values 가 같이 쓴다(개발 base 는 넣지 않는다 = 기본 0, XFF 무시)
TRUSTED_HOPS = "1"


# 운영 DB 계정 프로비저닝 스크립트의 고정부 — 비밀번호 글자는 없다(프로비저닝 시크릿을 envFrom 으로 받아 printenv 로 읽는다)
DB_PROVISION_HEAD = r"""#!/bin/bash
# 운영 DB 서비스 계정 프로비저닝(db-provision Job) — 서비스마다 스키마 · 계정 · 비밀번호 동기화 · 자기 스키마 권한.
# 멱등: IF NOT EXISTS · ALTER USER 라 다시 돌면 계정은 그대로, 비밀번호는 지금 시크릿 값으로 맞춘다(교체 절차).
# 비밀번호는 이 파일에 없다 — 프로비저닝 시크릿(키 <db>-password)과 root 비밀번호(MYSQL_PWD ← mariadb-root)는 환경 변수로만 받는다.
set -euo pipefail
HOST="${DB_HOST:-mariadb.infra.svc.cluster.local}"
q="'"
b='\'
sql_str() {  # SQL 문자열 리터럴 안에 넣을 수 있게 \ 와 ' 를 겹쳐 쓴다
  local s="${1//"$b"/"$b$b"}"
  printf '%s' "${s//"$q"/"$q$q"}"
}
secret() {  # 키에 '-' 가 있어 $이름 으로 읽지 못한다 — printenv 로 읽고, 없거나 비면 멈춘다(빈 비밀번호 계정을 만들지 않는다)
  local v
  if ! v="$(printenv "$1")" || [ -z "$v" ]; then
    echo "✗ 프로비저닝 시크릿 키 $1 없음 — ExternalSecret @SECRET@ 동기화를 확인한다" >&2
    exit 1
  fi
  sql_str "$v"
}
for i in $(seq 1 30); do  # MariaDB 기동 대기(최대 60초) — 그 뒤 실패는 Job backoffLimit 이 다시 돌린다
  if mariadb-admin --protocol=tcp -h "$HOST" -u root ping >/dev/null 2>&1; then break; fi
  if [ "$i" = 30 ]; then echo "✗ MariaDB($HOST) 응답 없음" >&2; exit 1; fi
  sleep 2
done
"""

DB_PROVISION_EACH = """
# @DB@
PW_@DB@="$(secret @DB@-password)"
mariadb --protocol=tcp -h "$HOST" -u root <<SQL
CREATE DATABASE IF NOT EXISTS @DB@ CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '@DB@'@'%' IDENTIFIED BY '${PW_@DB@}';
ALTER USER '@DB@'@'%' IDENTIFIED BY '${PW_@DB@}';
GRANT ALL PRIVILEGES ON @DB@.* TO '@DB@'@'%';
FLUSH PRIVILEGES;
SQL
echo "✓ @DB@ 계정 · 권한"
"""


def db_provision_sh(c: Ctx, dbs: list) -> str:
    sh = DB_PROVISION_HEAD.replace("@SECRET@", c.db_provision)
    sh = sh.replace("#!/bin/bash\n", "#!/bin/bash\n" + HDR, 1)
    return sh + "".join(DB_PROVISION_EACH.replace("@DB@", s.db_name) for s in dbs)


def db_provision_job(c: Ctx) -> str:
    return HDR + f"""# 운영 DB 서비스 계정 프로비저닝 — 스크립트는 db-provision.sh(ConfigMap db-provision). 끝나고 10분 뒤 지워진다:
# 다시 apply 하면 새 Job 이 만들어져(불변 필드 오류 없음) 계정을 확인하고 비밀번호를 동기화한다
apiVersion: batch/v1
kind: Job
metadata:
  name: db-provision
  namespace: infra
  labels: {{app: db-provision}}
spec:
  backoffLimit: 6
  ttlSecondsAfterFinished: 600
  template:
    metadata:
      labels: {{app: db-provision}}
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext: {{runAsNonRoot: true, runAsUser: 999, runAsGroup: 999, seccompProfile: {{type: RuntimeDefault}}}}
      containers:
      - name: provision
        image: mariadb:11.4
        command: [bash, /scripts/db-provision.sh]
        env:
        - {{name: MYSQL_PWD, valueFrom: {{secretKeyRef: {{name: mariadb-root, key: password}}}}}}
        - {{name: DB_HOST, value: mariadb.infra.svc.cluster.local}}
        envFrom:
        - secretRef: {{name: {c.db_provision}}}
        resources:
          requests: {{cpu: 10m, memory: 32Mi}}
          limits: {{memory: 128Mi}}
        securityContext: {{allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {{drop: [ALL]}}}}
        volumeMounts:
        - {{name: script, mountPath: /scripts, readOnly: true}}
        - {{name: tmp, mountPath: /tmp}}
      volumes:
      - {{name: script, configMap: {{name: db-provision}}}}
      - {{name: tmp, emptyDir: {{sizeLimit: 16Mi}}}}
"""


# 운영 MariaDB 일일 덤프(P-1 A · P-2 A — plan_REQ_02 §11.9). 일정 · 보관일 · 용량의 원천은 여기 하나, 시간대는 nova.project.json timezone
# alert_hold_hours: 실패 경보의 유지 시간 — 하루 일정 + 여유 2시간. 다음 정기 백업이 성공하면 그 전에 풀고, 또 실패하면 다시 보내 늘린다
BACKUP = {"schedule": "0 3 * * *", "keep_days": 7, "storage": "10Gi", "alert_hold_hours": 26}
# 백업 실패 경보(T07-2.06)는 Alertmanager API 로 직접 보낸다 — kube-state-metrics · Pushgateway 를 더하지 않는다(의존성 추가 없음)
AM_SVC = ("alertmanager.observability.svc.cluster.local", "9093")  # infra/observability/k8s/alertmanager.yaml Service

# 덤프 스크립트 — 비밀번호 글자는 없다(root 비밀번호는 MYSQL_PWD ← mariadb-root). 쓰다 만 파일이 보관본으로 보이지 않게 .partial → mv.
# 실패(ERR)하면 경보를 보내고 원래 종료 코드로 끝낸다(Job 은 그대로 Failed). 성공하면 같은 경보를 해제한다(endsAt = 지금).
# mariadb 이미지에 curl · wget 이 없어 bash /dev/tcp 로 HTTP/1.0 POST 한다. 본문 길이는 바이트(wc -c) — 요약이 한국어다
BACKUP_SH = """set -euo pipefail
am_alert() {  # $1 = firing | resolved
  local now end body resp
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  end="$now"
  if [ "$1" = firing ]; then end="$(date -u -d '+@HOLD@ hours' +%Y-%m-%dT%H:%M:%SZ)"; fi
  body='[{"labels":{"alertname":"MariaDBBackupFailed","severity":"critical","service":"mariadb-backup","namespace":"infra"},"annotations":{"summary":"MariaDB 일일 백업 실패","runbook":"kubectl -n infra logs job/<최근 Job> — deploy.md 백업 · 복원"},"startsAt":"'"$now"'","endsAt":"'"$end"'"}]'
  exec 3<>"/dev/tcp/$AM_HOST/$AM_PORT" || return 1
  printf 'POST /api/v2/alerts HTTP/1.0\\r\\nHost: %s\\r\\nContent-Type: application/json\\r\\nContent-Length: %s\\r\\n\\r\\n%s' "$AM_HOST" "$(printf '%s' "$body" | wc -c)" "$body" >&3
  IFS= read -r resp <&3 || resp=""
  exec 3<&-
  case "$resp" in
    "HTTP/"*" 200"*) echo "✓ 경보 $1 전송" ;;
    *) echo "✗ Alertmanager 응답: ${resp:-없음}" >&2; return 1 ;;
  esac
}
trap 'rc=$?; am_alert firing || echo "✗ 백업 실패 경보를 보내지 못했다 — Job Failed 로만 남는다" >&2; exit "$rc"' ERR
f="/backup/mariadb-$(date +%Y%m%d-%H%M%S).sql.gz"
mariadb-dump --protocol=tcp -h "$DB_HOST" -u root --single-transaction --databases @DBS@ | gzip > "$f.partial"
mv "$f.partial" "$f"
echo "✓ 백업 $f ($(du -h "$f" | cut -f1))"
find /backup -maxdepth 1 -name 'mariadb-*.sql.gz*' -mmin +@MIN@ -print -delete
# 해제 전송 실패는 경고로만 둔다 — 백업은 이미 성공했고, 경보는 endsAt(@HOLD@시간)에 저절로 풀린다
am_alert resolved || echo "△ 경보 해제를 보내지 못했다(백업은 성공)" >&2
"""


def mariadb_backup(c: Ctx, dbs: list) -> str:
    tz = project().get("timezone")
    if not tz:  # 기본값을 박으면 운영 서버 시간대와 일정이 조용히 어긋난다
        raise SystemExit("✗ nova.project.json 에 timezone 이 없다 — 백업 일정의 시간대(예: Asia/Seoul)를 적는다")
    sh = (BACKUP_SH.replace("@DBS@", " ".join(s.db_name for s in dbs)).replace("@MIN@", str(BACKUP["keep_days"] * 24 * 60))
          .replace("@HOLD@", str(BACKUP["alert_hold_hours"])))
    script = "".join(f"              {line}\n" for line in sh.splitlines())  # args 블록 스칼라(|) 들여쓰기
    return HDR + f"""# 운영 MariaDB 일일 백업 — 덤프 파일은 같은 노드의 PVC mariadb-backup 에 {BACKUP['keep_days']}일 보관.
# 노드 밖 복사 · 복원 순서는 docs/conventions/deploy.md §백업 · 복원. 실패한 Job 은 지우지 않고 남기고, 실패하면 Alertmanager 에
# critical 경보 MariaDBBackupFailed 를 직접 보낸다(성공하면 해제). 일정 자체가 안 돈 경우는 경보가 없다 — '매일 확인'으로 본다
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mariadb-backup
  namespace: infra
  labels: {{app: mariadb-backup}}
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: local-path
  resources: {{requests: {{storage: {BACKUP['storage']}}}}}
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mariadb-backup
  namespace: infra
  labels: {{app: mariadb-backup}}
spec:
  schedule: "{BACKUP['schedule']}"
  timeZone: {tz}
  concurrencyPolicy: Forbid
  startingDeadlineSeconds: 3600
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        metadata:
          labels: {{app: mariadb-backup}}
        spec:
          restartPolicy: Never
          automountServiceAccountToken: false
          securityContext: {{runAsNonRoot: true, runAsUser: 999, runAsGroup: 999, fsGroup: 999, seccompProfile: {{type: RuntimeDefault}}}}
          containers:
          - name: backup
            image: mariadb:11.4
            command: [bash, -c]
            args:
            - |
{script}            env:
            - {{name: MYSQL_PWD, valueFrom: {{secretKeyRef: {{name: mariadb-root, key: password}}}}}}
            - {{name: DB_HOST, value: mariadb.infra.svc.cluster.local}}
            - {{name: TZ, value: {tz}}}
            - {{name: AM_HOST, value: {AM_SVC[0]}}}
            - {{name: AM_PORT, value: "{AM_SVC[1]}"}}
            resources:
              requests: {{cpu: 50m, memory: 64Mi}}
              limits: {{memory: 256Mi}}
            securityContext: {{allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {{drop: [ALL]}}}}
            volumeMounts:
            - {{name: backup, mountPath: /backup}}
            - {{name: tmp, mountPath: /tmp}}
          volumes:
          - {{name: backup, persistentVolumeClaim: {{claimName: mariadb-backup}}}}
          - {{name: tmp, emptyDir: {{sizeLimit: 16Mi}}}}
"""


def prod_secrets(c: Ctx) -> list[tuple[str, str, list[str]]]:
    """개발 base 에도 있는 시크릿(이름, 네임스페이스, 키) — 운영은 지우고 ExternalSecret 으로 대체한다."""
    out = [(c.db_secret(s.name), s.namespace, ["password"]) for s in c.services if s.db]
    out += [(c.auth, ns, ["jwt-secret"]) for ns in sorted({s.namespace for s in c.services})]
    return out + EXTRA_SECRETS


def remote_key(c: Ctx, name: str, ns: str) -> str:
    return f"{c.slug}/prod/{ns}/{name}"


def list_secrets() -> list[tuple[str, str, str]]:
    """운영 ExternalSecret 이 원격 저장소에서 읽는 (원격 키, property, 받는 시크릿) — 첫 배포 전에 저장소에 채울 목록(T07-2.07).
    DB 계정 프로비저닝 시크릿은 서비스 DB 시크릿과 같은 원격 키를 다시 읽으므로 한 번만 낸다."""
    c = Ctx()
    rows: dict[tuple[str, str], str] = {}
    for n, ns, keys in [*prod_secrets(c), *PROD_ONLY_SECRETS]:
        for k in keys:
            rows.setdefault((remote_key(c, n, ns), k), f"{ns}/{n}")
    return [(key, prop, used) for (key, prop), used in rows.items()]


# 운영 HSTS(T07-2.04) — 1년 · 하위 도메인 포함. preload 는 넣지 않는다: 목록 등록은 되돌리기 어려운 외부 공개라 사람이 정한다
HSTS = {"stsSeconds": 31536000, "stsIncludeSubdomains": True, "forceSTSHeader": True}


def prod_tls(c: Ctx) -> tuple[str, str]:
    """운영 인그레스 TLS — (ingress-tls.yaml 본문, kustomization 패치). 인증서 시크릿 · cert-manager ClusterIssuer 는
    nova.project.json tls{secret, cluster_issuer} 에서. 없으면 시크릿은 자리표시 <slug>-tls, issuer 주석은 넣지 않는다
    (없는 issuer 이름을 적으면 인증서가 조용히 안 나온다 — 첫 배포 준비는 deploy.md)."""
    tls = project().get("tls") or {}
    secret = tls.get("secret") or f"{c.slug}-tls"
    issuer = tls.get("cluster_issuer")
    if issuer:
        note = f"# 인증서: cert-manager ClusterIssuer {issuer} 가 인그레스마다 시크릿 {secret} 를 만든다(nova.project.json tls)\n"
    else:
        note = (f"# 자리표시: nova.project.json 에 tls 가 없다 — 인증서 시크릿 {secret} 를 인그레스 네임스페이스마다 직접 넣거나\n"
                "# tls.cluster_issuer(cert-manager)를 적고 python nova.py gen. 절차는 docs/conventions/deploy.md '첫 배포 준비'\n")
    hsts = ", ".join(f"{k}: {str(v).lower() if isinstance(v, bool) else v}" for k, v in HSTS.items())
    body = HDR + note + "# Traefik 은 기본으로 다른 네임스페이스의 미들웨어를 쓰지 못한다 — 인그레스가 있는 네임스페이스마다 하나씩\n"
    patches = ""
    for ns in dict.fromkeys(ns for _, ns, _ in ingresses(c)):
        body += f"""apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata: {{name: hsts, namespace: {ns}}}
spec:
  headers: {{{hsts}}}
---
"""
    for name, ns, hosts in ingresses(c):
        ann = (f"        traefik.ingress.kubernetes.io/router.entrypoints: websecure\n"
               f'        traefik.ingress.kubernetes.io/router.tls: "true"\n'
               f"        traefik.ingress.kubernetes.io/router.middlewares: {ns}-hsts@kubernetescrd\n")
        if issuer:
            ann += f"        cert-manager.io/cluster-issuer: {issuer}\n"
        patches += f"""- target: {{kind: Ingress, name: {name}}}
  # 운영은 HTTPS 만(websecure) · 모든 호스트 TLS · HSTS — http(web) 진입은 Traefik 전역 리다이렉트로(deploy.md 첫 배포 준비)
  patch: |-
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: {name}
      namespace: {ns}
      annotations:
{ann}    spec:
      tls:
      - hosts: [{", ".join(hosts)}]
        secretName: {secret}
"""
    return body, patches


def overlays(c: Ctx) -> None:
    put(DEV / "kustomization.yaml", HDR + f"""# 개발(단일 노드 k3s): 레플리카 1, HPA 상한 2 — 노트북 · 소형 VM 에서 전체가 뜨도록
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources: [../../base, ../../../observability]
patches:
- target: {{kind: HorizontalPodAutoscaler}}
  patch: |-
    - {{op: replace, path: /spec/maxReplicas, value: 2}}
""")
    dbs = [s for s in c.services if s.db]
    secrets = prod_secrets(c)
    put(PROD / "delete-dev-secrets.yaml", HDR + "".join(
        f"$patch: delete\napiVersion: v1\nkind: Secret\nmetadata: {{name: {n}, namespace: {ns}}}\n---\n" for n, ns, _ in secrets))

    def remote(n: str, ns: str) -> str:
        return remote_key(c, n, ns)

    # DB 비밀번호 원천은 원격 property password 하나(P-4 A) — 서비스 쪽 url 은 ESO 템플릿이 조립한다(같은 값을 두 번 넣지 않게).
    # urlquery: 비밀번호에 @ · / · : 가 있어도 url 이 깨지지 않게 퍼센트 인코딩한다(SQLAlchemy 가 되돌려 읽는다)
    tpl = {c.db_secret(s.name): f"mysql+pymysql://{s.db_name}:{{{{ .password | urlquery }}}}@mariadb.infra.svc.cluster.local:3306/"
                                f"{s.db_name}?charset=utf8mb4" for s in dbs}
    ext = HDR + f"# 비밀값은 저장소에 두지 않는다 — ClusterSecretStore({c.store}: Vault · 클라우드 Secret Manager 등)에서 동기화\n"
    for n, ns, keys in [*secrets, *PROD_ONLY_SECRETS]:
        data = "".join(f"  - {{secretKey: {k}, remoteRef: {{key: {remote(n, ns)}, property: {k}}}}}\n" for k in keys)
        target = f"{{name: {n}, creationPolicy: Owner}}"
        if n in tpl:
            target = f"""
    name: {n}
    creationPolicy: Owner
    template:
      engineVersion: v2
      data: {{url: "{tpl[n]}"}}"""
        ext += f"""apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata: {{name: {n}, namespace: {ns}}}
spec:
  refreshInterval: 1h
  secretStoreRef: {{kind: ClusterSecretStore, name: {c.store}}}
  target: {target}
  data:
{data}---
"""
    if dbs:
        # DB 계정 프로비저닝 Job(infra)이 읽는 시크릿 — 다른 네임스페이스의 서비스 시크릿은 읽을 수 없어 같은 원격 키를 한 번 더 받는다.
        # 개발 base 에 같은 이름의 시크릿이 없으므로 delete-dev-secrets 에 넣지 않는다(없는 리소스 삭제 → kustomize 실패)
        data = "".join(f"  - {{secretKey: {s.db_name}-password, remoteRef: {{key: {remote(c.db_secret(s.name), s.namespace)}, "
                       f"property: password}}}}\n" for s in dbs)
        ext += f"""apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata: {{name: {c.db_provision}, namespace: infra}}
spec:
  refreshInterval: 1h
  secretStoreRef: {{kind: ClusterSecretStore, name: {c.store}}}
  target: {{name: {c.db_provision}, creationPolicy: Owner}}
  data:
{data}---
"""
    put(PROD / "secrets-external.yaml", ext)
    accounts = ("서비스 계정 · 권한은 db-provision Job 이 만든다(db-provision.sh — 비밀번호는 시크릿 " + c.db_provision + ")"
                if dbs else "DB 서비스가 없어 계정을 만들지 않는다")
    put(PROD / "mariadb-init.sql", SQL_HDR + f"-- 운영: 스키마만 만든다(ConfigMap 에 비밀번호 금지). {accounts}\n"
        + "".join(f"CREATE DATABASE IF NOT EXISTS {s.db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n" for s in c.services if s.db))
    put(PROD / "alertmanager.yml", alertmanager_cfg(c, prod=True))
    put(PROD / "alertmanager-data.yaml", HDR + f"""# 운영 Alertmanager 저장소 — 침묵 · 발송 기록이 재시작 뒤에도 남는다(base 는 emptyDir)
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {{name: alertmanager-data, namespace: observability, labels: {{app: alertmanager}}}}
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: local-path
  resources: {{requests: {{storage: {AM_DATA['storage']}}}}}
""")
    tls_body, tls_patches = prod_tls(c)
    put(PROD / "ingress-tls.yaml", tls_body)
    resources = ["../../base", "../../../observability", "secrets-external.yaml", "alertmanager-data.yaml", "ingress-tls.yaml"]
    prov_cm = ""
    if dbs:  # DB 서비스가 없는 프로젝트는 Job · 스크립트를 만들지 않는다(빈 시크릿 · 빈 스크립트 금지)
        put(PROD / "db-provision.sh", db_provision_sh(c, dbs))
        put(PROD / "db-provision-job.yaml", db_provision_job(c))
        resources.append("db-provision-job.yaml")
        put(PROD / "mariadb-backup.yaml", mariadb_backup(c, dbs))
        resources.append("mariadb-backup.yaml")
        prov_cm = "- {name: db-provision, namespace: infra, files: [db-provision.sh]}\n"
    core = "|".join(s.name for s in c.services if s.k8s.get("replicas", 1) >= 2) or c.gw.name
    images = "".join(f'- {{name: {c.image(n)}, newName: {c.registry}/{n}, newTag: "{c.version}"}}\n'
                     for n in [*catalog.names(), *(f"web-{w['name']}" for w in c.webs)])
    put(PROD / "kustomization.yaml", HDR + f"""# 운영: 핵심 경로(services.json replicas ≥ 2) 최소 2 레플리카 + PDB, Kafka 3 브로커(RF 3, min.insync 2)
# 비밀값: 개발 시크릿을 지우고 ExternalSecret(ClusterSecretStore {c.store})으로 대체
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources: [{", ".join(resources)}]
configMapGenerator:
- {{name: mariadb-init, namespace: infra, behavior: replace, files: [mariadb-init.sql]}}
- {{name: alertmanager-config, namespace: observability, behavior: replace, files: [alertmanager.yml]}}
{prov_cm}generatorOptions: {{disableNameSuffixHash: true}}
patches:
- path: delete-dev-secrets.yaml
- target: {{kind: ConfigMap, name: {c.cm}}}
  # GW_TRUSTED_HOPS: 게이트웨이 앞 프록시가 Traefik 하나뿐(P-5) — XFF 오른쪽 {TRUSTED_HOPS}홉을 클라이언트 IP 로 믿는다(레이트리밋 키).
  # 앞에 L7 LB 를 더 두면 늘려야 한다 — 적으면 모두 LB IP 로 묶이고, 많으면 클라이언트가 위조한 IP 를 믿는다
  patch: |-
    - {{op: add, path: /data/NOVA_ENV, value: prod}}
    - {{op: add, path: /data/GW_TRUSTED_HOPS, value: "{TRUSTED_HOPS}"}}
- target: {{kind: Deployment, name: grafana}}
  # 운영 Grafana: 익명 열람 · iframe 임베딩을 끈다(개발 base 는 켬). 이름으로 병합 — env 순서에 기대지 않는다
  patch: |-
    apiVersion: apps/v1
    kind: Deployment
    metadata: {{name: grafana, namespace: observability}}
    spec:
      template:
        spec:
          containers:
          - name: grafana
            env:
            - {{name: GF_AUTH_ANONYMOUS_ENABLED, value: "false"}}
            - {{name: GF_SECURITY_ALLOW_EMBEDDING, value: "false"}}
- target: {{kind: Deployment, name: alertmanager}}
  # 운영 Alertmanager: 수신처 시크릿은 optional — 아직 없어도 기동하고 게이트웨이 수신은 산다(oncall 만 발송 오류).
  # data 는 emptyDir 대신 PVC(emptyDir: null 로 지워야 볼륨 소스가 둘이 되지 않는다)
  patch: |-
    apiVersion: apps/v1
    kind: Deployment
    metadata: {{name: alertmanager, namespace: observability}}
    spec:
      template:
        spec:
          containers:
          - name: alertmanager
            volumeMounts:
            - {{name: receivers, mountPath: {ONCALL_URL_FILE.rsplit('/', 1)[0]}, readOnly: true}}
          volumes:
          - {{name: data, emptyDir: null, persistentVolumeClaim: {{claimName: alertmanager-data}}}}
          - {{name: receivers, secret: {{secretName: alertmanager-receivers, optional: true}}}}
- target: {{kind: HorizontalPodAutoscaler, name: "{core}"}}
  patch: |-
    - {{op: replace, path: /spec/minReplicas, value: 2}}
- target: {{kind: Deployment, name: "{core}"}}
  patch: |-
    - {{op: replace, path: /spec/replicas, value: 2}}
- target: {{kind: StatefulSet, name: kafka}}
  patch: |-
    - {{op: replace, path: /spec/replicas, value: 3}}
    - {{op: replace, path: /spec/template/spec/containers/0/env/1/value, value: "3"}}
    - {{op: replace, path: /spec/template/spec/containers/0/env/3/value, value: "-Xms512m -Xmx1g"}}
    - {{op: replace, path: /spec/template/spec/containers/0/resources, value: {{requests: {{cpu: 250m, memory: 1Gi}}, limits: {{memory: 1536Mi}}}}}}
- target: {{kind: Deployment, name: "web-.*"}}
  patch: |-
    - {{op: replace, path: /spec/replicas, value: 2}}
{tls_patches}images:
{images}""")


# ------------------------------------------------------------------ helm
def helm(c: Ctx) -> None:
    p = project()
    put(HELM / "Chart.yaml", HDR + f"""apiVersion: v2
name: {c.slug}
description: {p.get("name", c.slug)} 서비스 umbrella 차트(ArgoCD 대비). 인프라(Kafka · MariaDB · 관측)는 Kustomize base 를 사용
type: application
version: {c.version}
appVersion: "{c.version}"
""")
    w = max(len(s.name) for s in c.services) + 1

    # 서비스 단위 NetworkPolicy 입력 — k3s netpols() 와 같은 peer(게이트웨이 → allow_from 순). 게이트웨이는 파드 peer 없이
    # 인그레스 컨트롤러 · 관측만 받는다(templates/networkpolicy.yaml 이 gateway 표시로 가른다)
    def ingress_from(s) -> str:
        if s.gateway:
            return "[]"
        peers = [c.gw, *(catalog.get(f) for f in s.allow_from)]
        return "[" + ", ".join(f"{{namespace: {p.namespace}, app: {p.name}}}" for p in peers) + "]"

    body = "".join(
        f"  {(s.name + ':').ljust(w)} {{namespace: {s.namespace}, replicas: {s.k8s['replicas']}, hpaMax: {s.k8s['hpa_max']}, "
        f"cpu: {s.k8s['cpu']}, memory: {s.k8s['memory']}, memoryLimit: {s.k8s['memory_limit']}, db: {str(s.db).lower()}, "
        f"{'gateway: true, ' if s.gateway else ''}ingressFrom: {ingress_from(s)}, "
        f"observedBy: [{', '.join(OBS_APPS['gateway' if s.gateway else 'backend'])}]}}\n"
        for s in c.services)
    put(HELM / "values.yaml", HDR + f"""project: {c.slug}
image: {{registry: {c.registry}, tag: "{c.version}", pullPolicy: IfNotPresent}}
kafkaBootstrap: kafka.infra.svc.cluster.local:9092
prometheusUrl: http://prometheus.observability.svc.cluster.local:9090
# 운영 안전장치(k3s overlays/prod 와 같다): NOVA_ENV=prod 면 기본 JWT 키 · 켜진 개발 기능이 있을 때 서비스가 기동 거부
env: prod
jwtSecret: {{name: {c.auth}, key: jwt-secret}}  # 서비스 네임스페이스마다 미리 만든다(ExternalSecret 등) — 차트는 비밀값을 만들지 않는다
packs: "{",".join(p.get("packs", []))}"
corsOrigins: "{",".join([f"https://{c.domain}", *(f"https://{w['name']}.{c.domain}" for w in c.webs[1:])])}"
# 게이트웨이가 믿는 프록시 홉 수(P-5) — 1 = 앞에 인그레스 컨트롤러 하나. 앞에 L7 LB 를 더 두면 2. 비우면 0(XFF 무시)
trustedHops: "{TRUSTED_HOPS}"
# 서비스 단위 NetworkPolicy(k3s base networkpolicy.yaml 과 같은 정책) — 서비스는 게이트웨이가 붙인 x-user-id · x-role 을 믿으므로
# 끄면 아무 파드나 그 헤더로 서비스를 직접 부를 수 있다. 차트는 네임스페이스를 만들지 않으므로 자동 라벨 kubernetes.io/metadata.name 으로 고른다
networkPolicy:
  enabled: true
  namespaces: [{", ".join(c.svc_ns)}]  # 기본 거부(default-deny-ingress)를 둘 서비스 네임스페이스
  ingressNamespace: kube-system        # 인그레스 컨트롤러(Traefik) — 게이트웨이만 받는다
  observabilityNamespace: observability  # 그 안에서 서비스별 observedBy 파드(app 라벨)만 들인다 — 네임스페이스 통째 허용 없음
# 서비스 목록 하나로 Deployment · Service · HPA · PDB · NetworkPolicy 렌더(ingressFrom = 직접 호출을 받을 파드, services.json k8s.allow_from ·
# observedBy = 이 서비스를 부르는 관측 파드 — 백엔드는 prometheus, 게이트웨이는 + alertmanager)
services:
{body}""")


# ------------------------------------------------------------------ 관측
THRESHOLDS = {"error_rate": 0.05, "p95_s": 1.0, "outbox_pending": 100, "consumer_lag": 1000,
              "outbox_quarantined": 0}  # 게이트웨이 monitoring.THRESHOLDS 와 같게(tests/test_infra.py 가 대조)


def alertmanager_cfg(c: Ctx, prod: bool = False, compose: bool = False) -> str:
    """알림 라우팅 — critical 은 즉시, warning 은 묶어서. 개발(k3s · compose)은 게이트웨이 하나,
    운영은 게이트웨이 + oncall(url_file) 두 곳에 같은 알림을 보낸다(한 곳이 죽어도 알림이 사라지지 않게)."""
    if compose:
        url, where = f"http://{c.gw.name}:8000/internal/alertmanager", "docker-compose"
    else:
        url = f"http://{c.gw.name}.{c.gw.namespace}.svc.cluster.local:8000/internal/alertmanager  # 클러스터 내부 전용(인그레스 미노출)"
        where = "k3s 운영" if prod else "k3s"
    crit = "group_wait: 10s, repeat_interval: 30m"
    if prod:
        note = ("# 수신처 두 곳 — gateway(클러스터 내부) + oncall(시크릿 alertmanager-receivers 의 oncall-url 파일).\n"
                "# critical · warning 모두 두 곳으로(continue: true). severity 가 없는 알림은 기본 수신처 gateway 로만 간다\n")
        routes = (f"  - {{matchers: ['severity=\"critical\"'], receiver: gateway, {crit}, continue: true}}\n"
                  f"  - {{matchers: ['severity=\"critical\"'], receiver: oncall, {crit}}}\n"
                  "  - {matchers: ['severity=\"warning\"'], receiver: gateway, continue: true}\n"
                  "  - {matchers: ['severity=\"warning\"'], receiver: oncall}\n")
        extra = f"- name: oncall\n  webhook_configs:\n  - url_file: {ONCALL_URL_FILE}\n    send_resolved: true\n"
    else:
        note = "# 수신처는 게이트웨이 웹훅 하나뿐이다 — 운영은 overlays/prod/alertmanager.yml 이 oncall 을 더해 대신한다\n"
        routes = f"  - {{matchers: ['severity=\"critical\"'], receiver: gateway, {crit}}}\n"
        extra = ""
    return HDR + f"""# 알림 라우팅({where}) — critical 은 즉시, warning 은 묶어서.
{note}route:
  receiver: gateway
  group_by: [alertname, service]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
{routes}receivers:
- name: gateway
  webhook_configs:
  - url: {url}
    send_resolved: true
{extra}"""


def observability(c: Ctx) -> None:
    names = catalog.names()
    static = "".join(f'  - {{targets: ["{n}:8000"], labels: {{job: {n}}}}}\n' for n in names)
    common = f"""# 자원 효율: 스크레이프 15s, 고카디널리티 라벨(route 외 경로) 금지 규약
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels: {{cluster: {c.slug}}}
rule_files:
- /etc/prometheus/*rules*.yml   # recording_rules(손) · alert_rules(생성) · business_rules(손, 프로젝트 업무)
alerting:
  alertmanagers:
  - static_configs: [{{targets: ["alertmanager:9093"]}}]
scrape_configs:
"""
    # compose 정적 대상(sample:8000 …)은 k3s 설정에 넣지 않는다 — k3s 에서는 늘 up == 0 이라 ServiceDown(critical)이 계속 울린다
    put(OBS / "prometheus" / "prometheus.compose.yml", HDR + "# Prometheus — docker-compose 용: 정적 대상(job 라벨 = 서비스 이름). k3s 는 prometheus.yml\n"
        + common + f"""- job_name: compose
  static_configs:
{static}""")
    put(OBS / "prometheus" / "prometheus.yml", HDR + "# Prometheus — k3s 용: 파드 어노테이션(prometheus.io/scrape) 기반 SD. compose 는 prometheus.compose.yml\n"
        + common + f"""- job_name: pods
  kubernetes_sd_configs: [{{role: pod, namespaces: {{names: [{", ".join(c.svc_ns)}]}}}}]
  relabel_configs:
  - {{source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape], action: keep, regex: "true"}}
  - {{source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port], action: replace, regex: '([^:]+)(?::\\d+)?;(\\d+)', replacement: '$1:$2', target_label: __address__}}
  - {{source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path], action: replace, target_label: __metrics_path__, regex: (.+)}}
  - {{source_labels: [__meta_kubernetes_pod_label_app], target_label: job}}
  - {{source_labels: [__meta_kubernetes_namespace], target_label: namespace}}
  - {{source_labels: [__meta_kubernetes_pod_name], target_label: pod}}
""")
    jobs = "|".join(names)
    t = THRESHOLDS
    put(OBS / "prometheus" / "alert_rules.yml", HDR + f"""# 임계값은 게이트웨이 monitoring.THRESHOLDS 와 같다(Prometheus 가 없을 때 게이트웨이 직접 수집도 같은 판단)
# 프로젝트 업무 기록 · 알림 규칙은 손 관리 파일 prometheus/business_rules.yml 에 쓴다(rule_files 가 *rules*.yml 을 모두 읽는다)
groups:
- name: platform-slo
  rules:
  - alert: ServiceDown
    expr: up{{job=~"{jobs}"}} == 0
    for: 1m
    labels: {{severity: critical}}
    annotations: {{summary: "{{{{ $labels.job }}}} 응답 없음", runbook: "서비스 다운 — 파드 · 로그 · 최근 배포 확인"}}
  - alert: HighErrorRate
    expr: service:http_errors:ratio5m > {t["error_rate"]}
    for: 5m
    labels: {{severity: warning}}
    annotations: {{summary: "{{{{ $labels.service }}}} 5xx {{{{ $value | humanizePercentage }}}}"}}
  - alert: HighLatencyP95
    expr: service:http_latency_seconds:p95_5m > {t["p95_s"]}
    for: 10m
    labels: {{severity: warning}}
    annotations: {{summary: "{{{{ $labels.service }}}} p95 {{{{ $value | humanizeDuration }}}}"}}
  - alert: GatewayLatencyBudget
    expr: service:http_latency_seconds:p95_5m{{service="{c.gw.name}"}} > 0.3
    for: 10m
    labels: {{severity: warning}}
    annotations: {{summary: "게이트웨이 p95 300ms 초과 (SLO)"}}
- name: platform-events
  rules:
  - alert: OutboxBacklog
    expr: sum by (service) (nova_outbox_pending) > {t["outbox_pending"]}
    for: 5m
    labels: {{severity: warning}}
    annotations: {{summary: "{{{{ $labels.service }}}} 미발행 아웃박스 {{{{ $value }}}}건 — Kafka 연결 확인"}}
  - alert: OutboxQuarantined
    expr: max by (service) (nova_outbox_quarantined) > {t["outbox_quarantined"]}
    for: 5m
    labels: {{severity: warning}}
    annotations: {{summary: "{{{{ $labels.service }}}} 격리된 아웃박스 {{{{ $value }}}}건", runbook: "자동 재시도하지 않는다 — 원인 수정 후 python nova.py parked <서비스> list · requeue"}}
  - alert: KafkaConsumerLag
    expr: service:kafka_consumer_lag:sum > {t["consumer_lag"]}
    for: 5m
    labels: {{severity: warning}}
    annotations: {{summary: "{{{{ $labels.service }}}} 컨슈머 lag {{{{ $value }}}}"}}
  - alert: EventsToDLQ
    expr: sum by (service, topic) (increase(nova_events_consumed_total{{result="dlq"}}[15m])) > 0
    labels: {{severity: warning}}
    annotations: {{summary: "{{{{ $labels.service }}}} {{{{ $labels.topic }}}} DLQ 이동 발생 — 원인 수정 후 재처리"}}
""")
    put(OBS / "alertmanager" / "alertmanager.yml", alertmanager_cfg(c))
    put(OBS / "alertmanager" / "alertmanager.compose.yml", alertmanager_cfg(c, compose=True))
    dashboards = sorted(p.name for p in (OBS / "grafana" / "dashboards").glob("*.json"))
    prom_files = sorted({"prometheus.yml", "alert_rules.yml", *(p.name for p in (OBS / "prometheus").glob("*rules*.yml"))})
    put(OBS / "kustomization.yaml", HDR + f"""# 관측 스택(k3s): Prometheus(+RBAC) · Alertmanager · Grafana(프로비저닝) — 설정 파일은 이 디렉터리의 원본을 ConfigMap 으로
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: observability
resources: [k8s/prometheus.yaml, k8s/grafana.yaml, k8s/alertmanager.yaml]
configMapGenerator:
- name: prometheus-config
  files: [{", ".join(f"prometheus/{f}" for f in prom_files)}]
- name: grafana-datasources
  files: [grafana/provisioning/datasources/prometheus.yml]
- name: grafana-dashboard-provider
  files: [grafana/provisioning/dashboards/platform.yml]
- name: grafana-dashboards
  files: [{", ".join(f"grafana/dashboards/{d}" for d in dashboards)}]
- name: alertmanager-config
  files: [alertmanager/alertmanager.yml]
""")


# ------------------------------------------------------------------ docker-compose
def compose(c: Ctx) -> None:
    urls = "".join(f"    SVC_{env_name(n)}_URL: http://{n}:8000\n" for n in catalog.backends())
    svcs = ""
    for s in c.services:
        svcs += f"  {s.name}:\n    <<: *svc\n    build: {{context: ., dockerfile: infra/docker/Dockerfile.service, args: {{SERVICE: {s.name}}}}}\n"
        if s.db:
            d = s.db_name
            svcs += f'    environment: {{<<: *env, DATABASE_URL_{s.env}: "mysql+pymysql://{d}:dev-{d}-pw@mariadb:3306/{d}?charset=utf8mb4"}}\n'
        if s.gateway:
            svcs += '    ports: ["8080:8000"]\n'
    put(ROOT / "docker-compose.yml", HDR + f"""# 개발 전체 스택: docker compose up -d --build   (게이트웨이 http://localhost:8080/v1 · Grafana http://localhost:3300 · Prometheus :9090)
name: {c.slug}
x-svc: &svc
  build: {{context: ., dockerfile: infra/docker/Dockerfile.service}}
  restart: unless-stopped
  environment: &env
    KAFKA_BOOTSTRAP: kafka:9092
    PROMETHEUS_URL: http://prometheus:9090
    NOVA_PACKS: "{",".join(project().get("packs", []))}"
{meta_env(c, '    ')}
{urls}  depends_on:
    kafka-topics: {{condition: service_completed_successfully}}
    mariadb: {{condition: service_healthy}}
  mem_limit: 320m

services:
  kafka:
    image: apache/kafka:3.9.1
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_HEAP_OPTS: -Xms256m -Xmx384m
    volumes: [kafka-data:/var/lib/kafka/data]
    mem_limit: 768m
    healthcheck: {{test: ["CMD-SHELL", "/opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1"], interval: 5s, retries: 30}}
  kafka-topics:
    image: apache/kafka:3.9.1
    depends_on: {{kafka: {{condition: service_healthy}}}}
    volumes: [./infra/k3s/base/kafka-topics.txt:/topics.txt:ro]
    entrypoint: ["/bin/bash", "-c"]
    command:
    - |
      grep -v '^#' /topics.txt | while read t p d; do
        [ -z "$$t" ] && continue
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic $$t --partitions $$p --config retention.ms=$$((d*86400000))
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic $$t.dlq --partitions 1
      done
  mariadb:
    image: mariadb:11.4
    environment: {{MARIADB_ROOT_PASSWORD: dev-root-pw}}
    command: [--innodb-buffer-pool-size=128M, --performance-schema=OFF, --character-set-server=utf8mb4, --collation-server=utf8mb4_unicode_ci]
    volumes: [maria-data:/var/lib/mysql, ./infra/k3s/base/mariadb-init.sql:/docker-entrypoint-initdb.d/init.sql:ro]
    healthcheck: {{test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"], interval: 5s, retries: 30}}
    mem_limit: 512m

{svcs}
  prometheus:
    image: prom/prometheus:v2.55.1
    command: [--config.file=/etc/prometheus/prometheus.compose.yml, --storage.tsdb.retention.time=3d, --web.enable-lifecycle]
    volumes: [./infra/observability/prometheus:/etc/prometheus:ro]
    ports: ["9090:9090"]
    mem_limit: 512m
  alertmanager:
    image: prom/alertmanager:v0.28.1
    volumes: [./infra/observability/alertmanager:/etc/alertmanager:ro]
    command: [--config.file=/etc/alertmanager/alertmanager.compose.yml]
    mem_limit: 96m
  grafana:
    image: grafana/grafana:11.3.0
    environment:
      PROMETHEUS_URL: http://prometheus:9090
      GF_SECURITY_ADMIN_PASSWORD: grafana-dev-pw
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_SECURITY_ALLOW_EMBEDDING: "true"
      GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH: /var/lib/grafana/dashboards/platform-overview.json
    volumes:
    - ./infra/observability/grafana/provisioning:/etc/grafana/provisioning:ro
    - ./infra/observability/grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports: ["3300:3000"]
    mem_limit: 256m

volumes: {{kafka-data: {{}}, maria-data: {{}}}}
""")


def sdk_meta(c: Ctx) -> None:
    """웹 sdk 의 표시 기본값. 값만 내보낸다 — 환경 변수는 sdk 가 process.env.NEXT_PUBLIC_… 를 글자 그대로 읽는다
    (Next 는 글자 그대로 쓴 참조만 빌드에 넣는다 · T04-9.09). json.dumps 로 따옴표 · 역슬래시를 안전하게 넣는다."""
    put(SDK_GEN, f"""/* 생성 파일 — scripts/gen_k3s.py (원천: nova.project.json). 직접 고치지 않는다. */
/** 표시 형식 기본값 — 환경 변수(NEXT_PUBLIC_LOCALE · NEXT_PUBLIC_TIMEZONE)가 없을 때 쓴다. */
export const LOCALE = {json.dumps(c.locale, ensure_ascii=False)};
export const TIMEZONE = {json.dumps(c.timezone, ensure_ascii=False)};
""")


def generate() -> dict[Path, str]:
    OUT.clear()
    c = Ctx()
    check_db_budget(c)
    base(c)
    overlays(c)
    helm(c)
    observability(c)
    compose(c)
    sdk_meta(c)
    return OUT


def run(check: bool) -> int:
    generate()
    stale = [p for p, t in OUT.items() if not same(p, t)]
    # 사라진 서비스 · 웹의 옛 생성물(svc-*.yaml · web-*.yaml)
    keep = {p.name for p in OUT if p.parent == BASE}
    orphans = [p for p in [*BASE.glob("svc-*.yaml"), *BASE.glob("web-*.yaml")] if p.name not in keep]
    # DB 서비스가 모두 빠지면 운영 계정 Job · 스크립트 · 백업도 옛 생성물이다
    orphans += [p for p in (PROD / "db-provision.sh", PROD / "db-provision-job.yaml", PROD / "mariadb-backup.yaml")
                if p.exists() and p not in OUT]
    if check:
        if stale or orphans:
            print("✗ 생성물이 원천(services.json · nova.project.json)과 다릅니다 — uv run python scripts/gen_k3s.py 실행 후 커밋:",
                  *[p.relative_to(ROOT).as_posix() for p in [*stale, *orphans]], sep="\n  ", file=sys.stderr)
            return 1
        print(f"✓ 인프라 생성물 최신: {len(OUT)}개 파일")
        return 0
    for p in stale:
        write(p, OUT[p])
    for p in orphans:
        p.unlink()
    print(f"✓ 생성: {len(OUT)}개 파일 (변경 {len(stale)} · 삭제 {len(orphans)})")
    return 0


def main(argv: list[str]) -> int:
    if "--list-secrets" in argv:
        rows = list_secrets()
        print(f"# 원격 시크릿 저장소(ClusterSecretStore {Ctx().store})에 채울 키 — 원격 키 · property · 받는 시크릿(네임스페이스/이름). 값은 적지 않는다")
        w = max(len(k) for k, _, _ in rows)
        for key, prop, used in rows:
            print(f"{key.ljust(w)}  {prop:<12} → {used}")
        return 0
    return run("--check" in argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
