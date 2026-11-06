"""인프라 생성기 — 서비스 카탈로그 · 프로젝트 메타에서 빠짐없이 만들고, 생성물이 최신이다."""
import gen_dashboards
import gen_k3s
import yaml

from nova_common import catalog
from novalib import project


def test_generated_files_are_current():
    assert gen_k3s.run(check=True) == 0
    assert gen_dashboards.run(check=True) == 0


def test_every_service_has_manifest_and_alert():
    out = {p.name: t for p, t in gen_k3s.generate().items()}
    for n in catalog.names():
        assert f"svc-{n}.yaml" in out
    alert = yaml.safe_load(out["alert_rules.yml"])
    down = next(r for g in alert["groups"] for r in g["rules"] if r.get("alert") == "ServiceDown")
    assert down["expr"] == 'up{job=~"' + "|".join(catalog.names()) + '"} == 0'  # 손으로 쓴 정규식이 서비스를 빠뜨리던 결함 방지


def test_names_come_from_project_meta():
    p = project()
    out = {p_.as_posix().split("infra/")[-1]: t for p_, t in gen_k3s.generate().items()}
    kust = yaml.safe_load(out["k3s/base/kustomization.yaml"])
    assert kust["labels"][0]["pairs"]["app.kubernetes.io/part-of"] == p["slug"]
    assert f"{p['image_registry']}/gateway" in out["k3s/overlays/prod/kustomization.yaml"]
    assert f"api.{p['domain']}" in out["k3s/base/ingress.yaml"]
    for w in p["web_apps"]:
        assert f"web-{w['name']}.yaml" in {k.split('/')[-1] for k in out}


def test_prod_overlay_has_no_dev_secrets():
    out = {p.name: t for p, t in gen_k3s.generate().items() if "prod" in p.parts}
    assert "dev-" not in out["secrets-external.yaml"] and "IDENTIFIED BY" not in out["mariadb-init.sql"]


# ------------------------------------------------------------------ 감사 회귀(I1)
def _out() -> dict[str, str]:
    return {p.as_posix().split("Nova-dev/")[-1]: t for p, t in gen_k3s.generate().items()}


def _find(out: dict[str, str], suffix: str) -> str:
    return next(t for k, t in out.items() if k.endswith(suffix))


def test_helm_template_injects_prod_safety_env():
    """Helm 배포도 k3s 와 같이 JWT_SECRET(시크릿) · NOVA_ENV(기본 prod)를 넣어야 운영 안전장치(fail-closed)가 켜진다."""
    from novalib import ROOT

    tpl = (ROOT / "infra/helm/chart/templates/services.yaml").read_text(encoding="utf-8")
    assert "name: JWT_SECRET" in tpl and "$root.Values.jwtSecret.name" in tpl and "secretKeyRef" in tpl
    assert "name: NOVA_ENV" in tpl and "$root.Values.env" in tpl
    values = yaml.safe_load(_find(_out(), "helm/chart/values.yaml"))
    assert values["env"] == "prod"
    assert values["jwtSecret"] == {"name": f"{project()['slug']}-auth", "key": "jwt-secret"}


def test_k3s_prometheus_has_no_compose_static_targets():
    """k3s Prometheus 에 compose 정적 대상(sample:8000 등)이 있으면 늘 up == 0 → ServiceDown(critical)이 계속 울린다."""
    out = _out()
    k3s = yaml.safe_load(_find(out, "observability/prometheus/prometheus.yml"))
    assert all("static_configs" not in j for j in k3s["scrape_configs"])
    comp = yaml.safe_load(_find(out, "observability/prometheus/prometheus.compose.yml"))
    targets = {t for j in comp["scrape_configs"] for sc in j.get("static_configs", []) for t in sc["targets"]}
    assert {f"{n}:8000" for n in catalog.names()} <= targets
    assert all("kubernetes_sd_configs" not in j for j in comp["scrape_configs"])
    dc = yaml.safe_load(_find(out, "docker-compose.yml"))
    assert "--config.file=/etc/prometheus/prometheus.compose.yml" in dc["services"]["prometheus"]["command"]
    # compose Alertmanager 는 k8s DNS 가 아닌 compose 서비스 이름으로 게이트웨이에 보낸다
    am = yaml.safe_load(_find(out, "observability/alertmanager/alertmanager.compose.yml"))
    assert am["receivers"][0]["webhook_configs"][0]["url"] == f"http://{catalog.gateway()}:8000/internal/alertmanager"
    assert "--config.file=/etc/alertmanager/alertmanager.compose.yml" in dc["services"]["alertmanager"]["command"]


def test_prod_overlay_disables_grafana_anonymous_and_embedding():
    kust = yaml.safe_load(_find(_out(), "k3s/overlays/prod/kustomization.yaml"))
    p = next(x for x in kust["patches"] if (x.get("target") or {}).get("name") == "grafana")
    patch = yaml.safe_load(p["patch"])
    env = {e["name"]: e["value"] for e in patch["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert env["GF_AUTH_ANONYMOUS_ENABLED"] == "false" and env["GF_SECURITY_ALLOW_EMBEDDING"] == "false"


def test_generated_comments_do_not_claim_missing_automation():
    """없는 프로비저닝 Job · Secret 주입을 있다고 쓰지 않는다 — 있으면 있다고, 없으면 없다고 쓴다(T02-2.06)."""
    out = _out()
    sql = _find(out, "k3s/overlays/prod/mariadb-init.sql")
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    has_job = "db-provision-job.yaml" in kust["resources"] and any(k.endswith("overlays/prod/db-provision-job.yaml") for k in out)
    assert has_job == bool(catalog.db_services())
    assert ("db-provision Job 이 만든다" in sql) == has_job
    assert "후속 과제" not in sql and "수동으로 만든다" not in sql
    assert "운영 시 Secret 으로 주입" not in _find(out, "observability/alertmanager/alertmanager.yml")


# ------------------------------------------------------------------ REQ-261104-10 · 판본 버전 원천(T02-1.01 · 1.02)
def test_missing_version_fails(monkeypatch):
    """nova.project.json 에 version 이 없으면 생성기가 멈춘다 — 기본값을 박으면 '판본 ≠ 이미지 태그' 결함이 다시 생긴다."""
    meta = {k: v for k, v in project().items() if k != "version"}
    monkeypatch.setattr(gen_k3s, "project", lambda: meta)
    import pytest

    with pytest.raises(SystemExit, match="version"):
        gen_k3s.Ctx()


def test_image_tag_comes_from_project_version(monkeypatch):
    """운영 이미지 newTag · Helm Chart version/appVersion · values image.tag 가 모두 meta version 을 따른다."""
    from novalib import ROOT

    meta = {**project(), "version": "9.8.7"}
    monkeypatch.setattr(gen_k3s, "project", lambda: meta)
    out = _out()
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    assert kust["images"] and {i["newTag"] for i in kust["images"]} == {"9.8.7"}
    chart = yaml.safe_load(_find(out, "helm/chart/Chart.yaml"))
    assert str(chart["version"]) == "9.8.7" and chart["appVersion"] == "9.8.7"
    assert yaml.safe_load(_find(out, "helm/chart/values.yaml"))["image"]["tag"] == "9.8.7"
    assert '"0.1.0"' not in (ROOT / "scripts/gen_k3s.py").read_text(encoding="utf-8")  # 고정 판본 글자가 남지 않는다


# ------------------------------------------------------------------ REQ-261104-10 · 검증기 확장(T02-1.05)
def _cronjob(image: str, secret: str, cm: str) -> dict:
    pod = {"containers": [{"name": "c", "image": image, "envFrom": [{"configMapRef": {"name": cm}}],
                           "env": [{"name": "P", "valueFrom": {"secretKeyRef": {"name": secret, "key": "password"}}}]}]}
    return {"kind": "CronJob", "metadata": {"name": "backup", "namespace": "infra"},
            "spec": {"schedule": "0 3 * * *", "jobTemplate": {"spec": {"template": {"spec": pod}}}}}


def test_validator_reads_cronjob_and_external_secret(monkeypatch):
    """CronJob 은 spec.jobTemplate.spec.template 아래에 파드가 있다 — 참조 · 이미지 검사가 빠지면 안 된다.
    ExternalSecret 의 target.name 은 그 이름의 Secret 을 만든다 — 참조 대상으로 인정한다."""
    import validate_infra as vi

    cj = _cronjob("mariadb:latest", "root-pw", "backup-cfg")
    assert vi.pod_spec(cj)["containers"][0]["image"] == "mariadb:latest"
    assert vi.pod_spec({"kind": "Service", "metadata": {"name": "x"}, "spec": {}}) == {}
    ext = {"kind": "ExternalSecret", "metadata": {"name": "es", "namespace": "infra"},
           "spec": {"target": {"name": "root-pw"}}}
    monkeypatch.setattr(vi, "errors", [])
    vi.check_refs([cj, ext], "t")
    assert vi.errors == ["[t] backup: ConfigMap backup-cfg 없음 (ns=infra)"]  # Secret 은 ExternalSecret 이 만든다 — 통과
    monkeypatch.setattr(vi, "errors", [])
    vi.check_refs([cj], "t")
    assert any("Secret root-pw 없음" in e for e in vi.errors)  # CronJob 참조도 본다
    monkeypatch.setattr(vi, "errors", [])
    vi.check_prod_docs([cj])
    assert any("가변 이미지 태그" in e and "mariadb:latest" in e for e in vi.errors)


# ------------------------------------------------------------------ REQ-261104-10 · 운영 준비 검사(T02-1.06 — 연결은 T02-7.01)
def _ready_docs() -> list[dict]:
    """카탈로그 기준으로 '다 갖춘' 합성 운영 문서 — DB 계정 Job · 백엔드마다 정책 · Deployment 마다 PDB."""
    docs: list[dict] = [{"kind": "Job", "metadata": {"name": "db-provision", "namespace": "infra", "labels": {"app": "db-provision"}}}]
    for n in catalog.names():
        s = catalog.get(n)
        tpl = {"metadata": {"labels": {"app": n, "x/tier": "core"}}, "spec": {"containers": []}}
        docs.append({"kind": "Deployment", "metadata": {"name": n, "namespace": s.namespace}, "spec": {"template": tpl}})
        docs.append({"kind": "PodDisruptionBudget", "metadata": {"name": n, "namespace": s.namespace},
                     "spec": {"selector": {"matchLabels": {"app": n}}}})
    for n in catalog.backends():
        s = catalog.get(n)
        docs.append({"kind": "NetworkPolicy", "metadata": {"name": f"allow-{n}", "namespace": s.namespace},
                     "spec": {"podSelector": {"matchLabels": {"app": n}}}})
    return docs


def test_prod_readiness_check_flags_missing():
    """운영 첫날 사고를 막는 장치(계정 Job · 서비스 단위 정책 · PDB)가 빠지면 무엇이 빠졌는지 한국어로 짚는다."""
    import validate_infra as vi

    assert vi.check_prod_readiness(_ready_docs()) == []
    backend = catalog.backends()[0]
    gone = [d for d in _ready_docs() if not (d["kind"] in ("Job", "NetworkPolicy") or
                                             (d["kind"] == "PodDisruptionBudget" and d["metadata"]["name"] == backend))]
    errs = vi.check_prod_readiness(gone)
    joined = "\n".join(errs)
    assert "DB 계정 Job" in joined
    assert all(f"NetworkPolicy" in joined and n in joined for n in catalog.backends())
    assert any("PDB" in e and f"Deployment/{catalog.get(backend).namespace}/{backend}" in e for e in errs)
    # 이름이 같아도 다른 네임스페이스의 정책은 쳐 주지 않는다
    wrong_ns = [{**d, "metadata": {**d["metadata"], "namespace": "elsewhere"}} if d["kind"] == "NetworkPolicy" else d
                for d in _ready_docs()]
    assert any("NetworkPolicy" in e for e in vi.check_prod_readiness(wrong_ns))


def test_prod_readiness_pdb_scope_is_service_namespaces():
    """PDB 요구는 서비스 · 웹 네임스페이스만(T02-8.04) — observability 는 레플리카 1개라 PDB 를 걸면 노드 비우기를 막는다.
    observability Deployment 에 PDB 가 없어도 통과하고, 서비스 PDB 가 빠지면 여전히 실패한다."""
    import validate_infra as vi

    tpl = {"metadata": {"labels": {"app": "grafana"}}, "spec": {"containers": []}}
    obs = [{"kind": "Deployment", "metadata": {"name": n, "namespace": "observability"},
            "spec": {"template": {**tpl, "metadata": {"labels": {"app": n}}}}} for n in ("grafana", "alertmanager")]
    assert vi.check_prod_readiness(_ready_docs() + obs) == []
    gw = catalog.gateway()
    no_gw_pdb = [d for d in _ready_docs() + obs if not (d["kind"] == "PodDisruptionBudget" and d["metadata"]["name"] == gw)]
    errs = vi.check_prod_readiness(no_gw_pdb)
    assert errs == [f"[운영 준비] PDB 없음: Deployment/{catalog.get(gw).namespace}/{gw} — 노드 비우기 때 한꺼번에 내려간다"]


def test_prod_readiness_passes_on_generated():
    """생성된 운영 오버레이(정적 로드 — kubectl 없이도)가 운영 준비를 모두 갖추고, validate_infra 가 그 수를 한 줄로 찍는다(E3)."""
    import validate_infra as vi
    from novalib import ROOT

    docs = vi.load_kustomization(ROOT / "infra/k3s/overlays/prod", set())
    assert vi.check_prod_readiness(docs) == []
    line = vi.readiness_line(docs)
    jobs = sum(1 for d in docs if d["kind"] == "Job" and d["metadata"]["name"] == "db-provision")
    nb = len(catalog.backends())
    deps = [d for d in docs if d["kind"] == "Deployment" and d["metadata"]["namespace"] in vi.readiness_namespaces()]
    assert deps and line == f"운영 준비: DB 계정 Job {jobs} · 서비스 정책 {nb}/{nb} · PDB {len(deps)}/{len(deps)}"
    assert jobs == (1 if catalog.db_services() else 0)
    # 빠지면 분자가 줄어 보인다 — 숫자가 늘 같은 값을 찍는 장식이 아니다
    gone = [d for d in docs if d["kind"] != "PodDisruptionBudget"]
    assert vi.readiness_line(gone).endswith(f"PDB 0/{len(deps)}")


def test_dev_server_exposes_only_gateway_and_metrics():
    """dev_server 는 서비스 앱 전체를 /svc/<name> 에 마운트하지 않는다(게이트웨이 인증 · 권한 우회 방지)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import dev_server

    assert dev_server.DEFAULT_HOST == "127.0.0.1"

    class FakeSvc:
        def __init__(self, app):
            self.app = app

    sample = FastAPI()
    sample.get("/metrics")(lambda: "nova_metric 1")
    sample.get("/sample/items")(lambda: {"items": ["비밀"]})
    gw = FastAPI()
    gw.post("/internal/alertmanager")(lambda: {"ok": True})
    gw.get("/v1/ping")(lambda: {"ok": True})
    services = {n: FakeSvc(sample if n != catalog.gateway() else gw) for n in catalog.names()}
    root = dev_server.build_root(services, gw)
    backend = next(n for n in catalog.names() if n != catalog.gateway())

    local = TestClient(root)
    assert local.get(f"/svc/{backend}/sample/items").status_code == 404
    assert local.get(f"/svc/{backend}/metrics").status_code == 200
    assert local.get("/v1/ping").status_code == 200
    assert local.post("/internal/alertmanager").status_code == 200  # 이 PC(루프백)에서는 허용
    remote = TestClient(root, client=("203.0.113.7", 50000))
    assert remote.post("/internal/alertmanager").status_code == 404  # 바깥 주소에서는 막는다
    assert remote.get("/v1/ping").status_code == 200


# ------------------------------------------------------------------ REQ-261104-10 · R1 운영 DB 계정(T02-2.01 ~ 2.06)
def _with_extra_db_service(monkeypatch) -> list:
    """카탈로그에 하이픈 이름의 DB 서비스를 하나 더한다 — '서비스 목록에서 자동 포함'과 db_name 변환을 함께 본다."""
    import dataclasses

    real = catalog.services()
    proto = next(s for s in real if s.db)
    extra = dataclasses.replace(proto, name="ledger-x", routes=(), local_port=proto.local_port + 90)
    monkeypatch.setattr(catalog, "services", lambda: (*real, extra))
    return [s for s in catalog.services() if s.db]


def _docs(text: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(text) if d]


def test_prod_db_secret_single_password_source(monkeypatch):
    """운영 DB 비밀번호의 원천은 원격 property password 하나 — 서비스 쪽 url 은 템플릿으로 조립하고(P-4 A),
    infra 쪽 프로비저닝 시크릿은 같은 원격 키를 서비스마다 <db>-password 로 받는다."""
    dbs = _with_extra_db_service(monkeypatch)
    slug = project()["slug"]
    out = _out()
    ext = _find(out, "k3s/overlays/prod/secrets-external.yaml")
    es = {(d["metadata"]["namespace"], d["metadata"]["name"]): d for d in _docs(ext)}
    for s in dbs:
        d = es[(s.namespace, f"{slug}-db-{s.name}")]
        assert [(x["secretKey"], x["remoteRef"]["property"]) for x in d["spec"]["data"]] == [("password", "password")]
        url = d["spec"]["target"]["template"]["data"]["url"]
        assert url.startswith(f"mysql+pymysql://{s.db_name}:")
        assert f"@mariadb.infra.svc.cluster.local:3306/{s.db_name}?charset=utf8mb4" in url
        assert "{{" in url and ".password" in url  # 값은 템플릿이 채운다 — 글자로 박지 않는다
    assert "dev-" not in ext and "-pw" not in ext
    # T02-2.02 — infra 프로비저닝 시크릿: 서비스 시크릿과 같은 원격 키 · property
    prov = es[("infra", f"{slug}-db-provision")]
    got = {x["secretKey"]: x["remoteRef"] for x in prov["spec"]["data"]}
    assert set(got) == {f"{s.db_name}-password" for s in dbs}
    for s in dbs:
        assert got[f"{s.db_name}-password"] == {"key": f"{slug}/prod/{s.namespace}/{slug}-db-{s.name}", "property": "password"}
    # 개발 시크릿이 없는 이름은 지우기 패치에 넣지 않는다(없는 리소스 삭제 → kustomize 실패)
    deleted = {d["metadata"]["name"] for d in _docs(_find(out, "k3s/overlays/prod/delete-dev-secrets.yaml"))}
    assert f"{slug}-db-provision" not in deleted
    assert {f"{slug}-db-{s.name}" for s in dbs} <= deleted


def test_prod_has_db_provision_job_for_every_db_service(monkeypatch):
    """DB 서비스마다 계정 · 비밀번호 동기화 · 권한을 만드는 멱등 스크립트와 그것을 돌리는 Job — 비밀번호 글자는 생성물에 없다."""
    import re

    dbs = _with_extra_db_service(monkeypatch)
    slug = project()["slug"]
    out = _out()
    # T02-2.03 — 스크립트
    sh = _find(out, "k3s/overlays/prod/db-provision.sh")
    for s in dbs:
        d = s.db_name
        assert f"CREATE USER IF NOT EXISTS '{d}'@'%'" in sh
        assert f"ALTER USER '{d}'@'%' IDENTIFIED BY" in sh
        assert f"GRANT ALL PRIVILEGES ON {d}.* TO '{d}'@'%'" in sh
        assert f"{d}-password" in sh  # 프로비저닝 시크릿 키(envFrom)에서 읽는다
    assert re.findall(r"IDENTIFIED BY '([^']*)'", sh) and all(v.startswith("$") for v in re.findall(r"IDENTIFIED BY '([^']*)'", sh))
    assert "dev-" not in sh and "-pw" not in sh
    # T02-2.04 — Job · kustomization
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    assert "db-provision-job.yaml" in kust["resources"]
    gens = {g["name"]: g for g in kust["configMapGenerator"]}
    assert gens["db-provision"]["files"] == ["db-provision.sh"] and gens["db-provision"]["namespace"] == "infra"
    job = _docs(_find(out, "k3s/overlays/prod/db-provision-job.yaml"))[0]
    assert job["kind"] == "Job" and job["metadata"]["namespace"] == "infra"
    assert job["metadata"]["labels"]["app"] == "db-provision"
    assert job["spec"]["backoffLimit"] == 6 and job["spec"]["ttlSecondsAfterFinished"] == 600  # 다시 apply 해도 불변 필드 오류 없음
    tpl = job["spec"]["template"]
    assert tpl["metadata"]["labels"]["app"] == "db-provision"  # mariadb 정책이 파드 라벨로 고른다
    pod = tpl["spec"]
    assert pod["restartPolicy"] in ("Never", "OnFailure") and pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsNonRoot"] is True
    (ctr,) = pod["containers"]
    assert ctr["image"] == "mariadb:11.4"
    assert ctr["securityContext"] == {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}}
    refs = [(e.get("valueFrom") or {}).get("secretKeyRef") for e in ctr["env"]]
    assert {"name": "mariadb-root", "key": "password"} in refs
    assert {"secretRef": {"name": f"{slug}-db-provision"}} in ctr["envFrom"]
    vols = {v["name"]: v for v in pod["volumes"]}
    assert any((v.get("configMap") or {}).get("name") == "db-provision" for v in vols.values())
    assert "db-provision.sh" in " ".join(ctr["command"] + ctr.get("args", []))


def test_mariadb_policy_admits_provision_and_backup():
    """mariadb 수신 정책 — DB 서비스 네임스페이스에 더해 infra 의 계정 Job · 백업 파드만(같은 peer 안 네임스페이스 AND 파드 라벨)."""
    ld = project().get("label_domain", f"{project()['slug']}.dev")
    pol = next(d for d in _docs(_find(_out(), "k3s/base/networkpolicy.yaml")) if d["metadata"]["name"] == "mariadb-from-services")
    assert pol["metadata"]["namespace"] == "infra" and pol["spec"]["podSelector"] == {"matchLabels": {"app": "mariadb"}}
    peers = [p for rule in pol["spec"]["ingress"] for p in rule["from"]]
    infra_pods = [p for p in peers if "podSelector" in p]
    assert len(infra_pods) == 1
    (p,) = infra_pods
    assert p["namespaceSelector"] == {"matchLabels": {f"{ld}/ns": "infra"}}  # 다른 네임스페이스의 같은 라벨 파드는 안 된다
    assert p["podSelector"] == {"matchExpressions": [{"key": "app", "operator": "In", "values": ["db-provision", "mariadb-backup"]}]}
    # 네임스페이스 통째로 여는 peer 는 DB 서비스 네임스페이스 하나뿐 — infra 전체(kafka 등)는 열지 않는다
    db_ns = sorted({s.namespace for s in catalog.services() if s.db})
    assert [q for q in peers if "podSelector" not in q] == [
        {"namespaceSelector": {"matchExpressions": [{"key": f"{ld}/ns", "operator": "In", "values": db_ns}]}}]
    assert all(rule["ports"] == [{"port": 3306}] for rule in pol["spec"]["ingress"])


# ------------------------------------------------------------------ REQ-261104-10 · R3 운영 MariaDB 백업(T02-3.02)
def test_prod_backup_cronjob(monkeypatch):
    """운영 MariaDB 일일 덤프 — PVC(local-path) + CronJob. 일정 · 보관일은 상수 BACKUP 하나, 시간대는 nova.project.json,
    대상 DB 는 카탈로그의 DB 서비스 전부(새 서비스도 자동 포함). 비밀번호 글자는 생성물에 없다."""
    import validate_infra as vi

    dbs = _with_extra_db_service(monkeypatch)
    p = project()
    out = _out()
    docs = _docs(_find(out, "k3s/overlays/prod/mariadb-backup.yaml"))
    by_kind = {d["kind"]: d for d in docs}
    assert set(by_kind) == {"PersistentVolumeClaim", "CronJob"}
    pvc, cj = by_kind["PersistentVolumeClaim"], by_kind["CronJob"]
    assert pvc["metadata"] == {"name": "mariadb-backup", "namespace": "infra", "labels": {"app": "mariadb-backup"}}
    assert pvc["spec"]["storageClassName"] == "local-path" and pvc["spec"]["accessModes"] == ["ReadWriteOnce"]
    # 일정 · 보관일 원천은 상수 하나
    assert gen_k3s.BACKUP["schedule"] == "0 3 * * *" and gen_k3s.BACKUP["keep_days"] == 7
    assert cj["metadata"]["namespace"] == "infra" and cj["metadata"]["labels"]["app"] == "mariadb-backup"
    spec = cj["spec"]
    assert spec["schedule"] == gen_k3s.BACKUP["schedule"] and spec["timeZone"] == p["timezone"]
    assert spec["concurrencyPolicy"] == "Forbid"
    tpl = spec["jobTemplate"]["spec"]["template"]
    assert tpl["metadata"]["labels"]["app"] == "mariadb-backup"  # mariadb-from-services 정책이 이 라벨로 들인다
    pod = vi.pod_spec(cj)
    assert pod["automountServiceAccountToken"] is False and pod["securityContext"]["runAsNonRoot"] is True
    (ctr,) = pod["containers"]
    assert ctr["image"] == "mariadb:11.4"
    assert ctr["securityContext"] == {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}}
    assert {"name": "mariadb-root", "key": "password"} in [(e.get("valueFrom") or {}).get("secretKeyRef") for e in ctr["env"]]
    assert {"name": "TZ", "value": p["timezone"]} in ctr["env"]  # 파일 이름의 날짜도 일정과 같은 시간대
    claim = [v["persistentVolumeClaim"]["claimName"] for v in pod["volumes"] if "persistentVolumeClaim" in v]
    assert claim == ["mariadb-backup"]
    sh = " ".join(ctr["command"] + ctr.get("args", []))
    assert "mariadb-dump" in sh and "--single-transaction" in sh
    assert "--databases " + " ".join(s.db_name for s in dbs) in sh
    assert "| gzip" in sh and "pipefail" in sh  # 덤프가 실패하면 gzip 이 성공해도 Job 실패
    assert f"-mmin +{7 * 24 * 60}" in sh and "-delete" in sh  # 보관 7일 지난 파일 삭제
    assert "dev-" not in _find(out, "k3s/overlays/prod/mariadb-backup.yaml") and "IDENTIFIED" not in sh
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    assert "mariadb-backup.yaml" in kust["resources"]
    # 운영 렌더 검사기(T02-1.05)로 이미지 · 참조 확인 — mariadb-root 는 ExternalSecret 이 만든다
    monkeypatch.setattr(vi, "errors", [])
    vi.check_prod_docs(docs)
    vi.check_refs([*docs, *_docs(_find(out, "k3s/overlays/prod/secrets-external.yaml"))], "t")
    assert [e for e in vi.errors if "mariadb-backup" in e] == []  # 렌더 전체용 검사(NOVA_ENV ConfigMap)는 이 부분 문서와 무관


def test_prod_backup_absent_without_db_services(monkeypatch):
    """DB 서비스가 없는 프로젝트는 백업을 만들지 않는다(빈 --databases 금지) — 시작 초안 · 새 프로젝트에서도 초록."""
    real = catalog.services()
    monkeypatch.setattr(catalog, "services", lambda: tuple(s for s in real if not s.db))
    out = _out()
    assert not any(k.endswith("mariadb-backup.yaml") for k in out)
    assert "mariadb-backup.yaml" not in yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))["resources"]


def test_deploy_doc_backup_restore():
    """deploy.md §백업 · 복원(T02-3.03) — 일정 · 보관일이 상수 BACKUP 과 같고, 복원 순서(0 레플리카 → 복원 → 계정 Job → 레플리카 복구 →
    readyz)가 지켜지며, 노드 밖 복사 · DB 전체 단위 · 개인정보 주의가 있고, 비밀값이 없다."""
    import re

    import validate_infra as vi
    from novalib import ROOT

    doc = (ROOT / "docs/conventions/deploy.md").read_text(encoding="utf-8")
    sec = doc.split("## 백업 · 복원", 1)[1]
    hh, mm = gen_k3s.BACKUP["schedule"].split()[1], gen_k3s.BACKUP["schedule"].split()[0]
    assert f"매일 {int(hh):02d}:{int(mm):02d}" in sec and f"{gen_k3s.BACKUP['keep_days']}일" in sec
    assert "timezone" in sec and "mariadb-backup" in sec
    for must in ("노드 밖 복사", "DB 전체", "M1", "개인정보"):
        assert must in sec, must
    steps = ["--replicas=0", "DROP DATABASE", "job/db-provision", "rollout status", "/readyz"]
    pos = [sec.find(s) for s in steps]
    assert -1 not in pos and pos == sorted(pos), dict(zip(steps, pos))
    assert not vi.DEV_SECRET_MARKERS.search(doc) and "IDENTIFIED BY" not in doc
    assert not re.search(r"(?i)password\s*[:=]\s*['\"]?\w", doc)  # 비밀번호 실값을 적지 않는다(환경 변수 참조만)


# ------------------------------------------------------------------ REQ-261104-10 · R4 서비스 단위 NetworkPolicy(T02-4.02 ~ 4.04)
def _netpols() -> list[dict]:
    return [d for d in _docs(_find(_out(), "k3s/base/networkpolicy.yaml")) if d["kind"] == "NetworkPolicy"]


def _pod_peer(ld: str, ns: str, app: str) -> dict:
    # 같은 from 원소 안의 두 선택자는 AND — 그 네임스페이스의 그 파드만
    return {"namespaceSelector": {"matchLabels": {f"{ld}/ns": ns}}, "podSelector": {"matchLabels": {"app": app}}}


def _with_allowlisted_backend(monkeypatch, allow_from: list[str]) -> None:
    """다른 네임스페이스에 allow_from 을 가진 백엔드를 하나 더한다 — '카탈로그 전부를 돈다'와 교차 네임스페이스 peer 를 함께 본다."""
    import dataclasses

    real = catalog.services()
    proto = next(s for s in real if not s.gateway)
    extra = dataclasses.replace(proto, name="ledger-x", routes=(), local_port=proto.local_port + 90,
                                k8s={**proto.k8s, "namespace": "ledger-ns", "db": False, "allow_from": allow_from})
    monkeypatch.setattr(catalog, "services", lambda: (*real, extra))


def test_backend_policy_admits_only_gateway_and_allowlist(monkeypatch):
    """백엔드는 게이트웨이 파드 · allow_from 서비스 파드 · observability 만 받는다(네임스페이스 통째 허용 없음).
    게이트웨이는 kube-system(인그레스) · observability, 웹은 kube-system 만 — 웹 SSR 은 게이트웨이를 부르지 않는다(모든 화면이 "use client")."""
    import validate_infra as vi

    _with_allowlisted_backend(monkeypatch, [catalog.backends()[0]])
    ld = project().get("label_domain", f"{project()['slug']}.dev")
    gw = catalog.get(catalog.gateway())
    pols = _netpols()
    by = {(p["metadata"]["namespace"], p["metadata"]["name"]): p for p in pols}
    assert not any(p["metadata"]["name"] == "allow-services-and-observability" for p in pols)
    obs = {"namespaceSelector": {"matchLabels": {f"{ld}/ns": "observability"}},
           "podSelector": {"matchExpressions": [{"key": "app", "operator": "In", "values": ["prometheus"]}]}}  # T07-2.05
    obs_gw = {**obs, "podSelector": {"matchExpressions": [{"key": "app", "operator": "In", "values": ["prometheus", "alertmanager"]}]}}
    for n in catalog.backends():
        s = catalog.get(n)
        pol = by[(s.namespace, f"allow-{n}")]
        assert pol["spec"]["podSelector"] == {"matchLabels": {"app": n}} and pol["spec"]["policyTypes"] == ["Ingress"]
        (rule,) = pol["spec"]["ingress"]
        assert rule["ports"] == [{"port": 8000}]
        allowed = [_pod_peer(ld, catalog.get(f).namespace, f) for f in s.allow_from]
        assert rule["from"] == [_pod_peer(ld, gw.namespace, gw.name), *allowed, obs]
    extra = by[("ledger-ns", "allow-ledger-x")]["spec"]["ingress"][0]["from"]
    assert _pod_peer(ld, catalog.get(catalog.backends()[0]).namespace, catalog.backends()[0]) in extra
    # 서비스 네임스페이스에서 모든 파드를 고르는 정책은 기본 거부뿐(규칙 없음)
    svc_ns = {s.namespace for s in catalog.services()}
    for p in pols:
        if p["metadata"]["namespace"] in svc_ns and p["spec"]["podSelector"] == {}:
            assert p["metadata"]["name"] == "default-deny-ingress" and not p["spec"].get("ingress")
    # 게이트웨이 · 웹
    kube = {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}
    gpol = by[(gw.namespace, f"allow-{gw.name}")]
    assert gpol["spec"]["podSelector"] == {"matchLabels": {"app": gw.name}}
    (grule,) = gpol["spec"]["ingress"]
    assert grule["from"] == [kube, obs_gw] and grule["ports"] == [{"port": 8000}]
    webs = [f"web-{w['name']}" for w in project().get("web_apps", [])]
    if webs:
        wpol = by[(gw.namespace, "allow-ingress-controller")]
        assert wpol["spec"]["podSelector"] == {"matchExpressions": [{"key": "app", "operator": "In", "values": webs}]}
        (wrule,) = wpol["spec"]["ingress"]
        assert wrule["from"] == [kube] and wrule["ports"] == [{"port": 3000}]
    # 웹 파드를 출처로 들이는 peer 는 어디에도 없다
    assert not any(set((peer.get("podSelector") or {}).get("matchLabels", {}).values()) & set(webs)
                   for p in pols for r in p["spec"].get("ingress") or [] for peer in r["from"])
    # 운영 준비 검사(E3)의 '서비스 단위 정책' 항목이 생성물로 채워진다
    assert not [e for e in vi.check_prod_readiness(pols) if "NetworkPolicy" in e]


HELM_NETPOL_LINES = (
    # 서비스 네임스페이스마다 기본 거부 — k3s base 의 default-deny-ingress 와 같은 이름 · 같은 뜻
    "{{- range $ns := $np.namespaces }}",
    "metadata: {name: default-deny-ingress, namespace: {{ $ns }}}",
    "podSelector: {}",
    # 서비스 단위 허용 — 그 서비스 파드만 고르고 8000 만 연다
    "metadata: {name: allow-{{ $name }}, namespace: {{ $s.namespace }}}",
    "podSelector: {matchLabels: {app: {{ $name }}}}",
    "policyTypes: [Ingress]",
    "ports: [{port: 8000}]",
    # 게이트웨이만 인그레스 컨트롤러 네임스페이스를 들인다
    "{{- if $s.gateway }}",
    "- namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: {{ $np.ingressNamespace }}}}",
    # 허용 peer 는 네임스페이스 AND 파드(같은 원소 안 두 선택자) — 네임스페이스 통째 허용이 아니다
    "{{- range $p := $s.ingressFrom }}",
    "- namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: {{ $p.namespace }}}}",
    "podSelector: {matchLabels: {app: {{ $p.app }}}}",
    "- namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: {{ $np.observabilityNamespace }}}}",
    "podSelector: {matchExpressions: [{key: app, operator: In, values: {{ toJson $s.observedBy }}}]}",  # T07-2.05
)


def test_helm_chart_has_same_service_netpols(monkeypatch):
    """Helm 차트도 k3s base 와 같은 서비스 단위 NetworkPolicy 를 가진다(보안 감사 치명 — 정책이 없으면 아무 파드나
    x-role: admin 헤더로 서비스를 직접 부를 수 있다). 정책 입력은 values(생성물 — services.json allow_from)에서만 오고,
    값이 k3s 생성 정책의 peer 와 하나하나 같아야 한다. helm 이 없는 PC 에서도 잡도록 텍스트 · 구조로 본다
    (helm 이 있으면 validate_infra.check_helm_render 가 렌더 결과로 한 번 더 본다)."""
    from novalib import ROOT

    _with_allowlisted_backend(monkeypatch, [catalog.backends()[0]])  # 교차 네임스페이스 allow_from 하나를 더해 본다
    ld = project().get("label_domain", f"{project()['slug']}.dev")
    out = _out()
    values = yaml.safe_load(_find(out, "helm/chart/values.yaml"))
    np = values.get("networkPolicy")
    assert np, "Helm values 에 networkPolicy 입력 없음"
    gw = catalog.get(catalog.gateway())
    assert np["enabled"] is True
    assert np["namespaces"] == list(dict.fromkeys([gw.namespace, *(s.namespace for s in catalog.services())]))
    assert np["ingressNamespace"] == "kube-system" and np["observabilityNamespace"] == "observability"
    by = {(p["metadata"]["namespace"], p["metadata"]["name"]): p for p in _netpols()}
    for s in catalog.services():
        v = values["services"][s.name]
        assert bool(v.get("gateway")) == s.gateway
        k3s_from = by[(s.namespace, f"allow-{s.name}")]["spec"]["ingress"][0]["from"]
        pods = [{"namespace": p["namespaceSelector"]["matchLabels"][f"{ld}/ns"], "app": p["podSelector"]["matchLabels"]["app"]}
                for p in k3s_from if "matchLabels" in p.get("podSelector", {})]  # 관측 peer(matchExpressions)는 observedBy 로 따로 본다
        assert v["ingressFrom"] == pods, f"{s.name}: Helm 허용 peer 가 k3s 정책과 다름"
        if not s.gateway:
            assert pods[0] == {"namespace": gw.namespace, "app": gw.name}  # 백엔드는 게이트웨이부터
    assert values["services"]["ledger-x"]["ingressFrom"][1] == {
        "namespace": catalog.get(catalog.backends()[0]).namespace, "app": catalog.backends()[0]}
    # 템플릿(손 관리) — 위 값을 그리는 줄이 있다. 켜고 끄는 스위치는 values 의 enabled 하나
    tpl_path = ROOT / "infra/helm/chart/templates/networkpolicy.yaml"
    assert tpl_path.exists(), "Helm 차트에 NetworkPolicy 템플릿 없음"
    tpl = tpl_path.read_text(encoding="utf-8")
    lines = {ln.strip() for ln in tpl.splitlines()}
    for want in HELM_NETPOL_LINES:
        assert want in lines, f"Helm NetworkPolicy 템플릿에 줄이 없음: {want}"
    assert tpl.count("kind: NetworkPolicy") == 2 and "{{- if $np.enabled }}" in lines
    assert "ingress:" in lines and "- from:" in lines


def test_netpols_without_web_apps(monkeypatch):
    """웹 앱이 없는 새 프로젝트 — 웹 정책(빈 In 목록 = 무효 선택자)을 만들지 않고, kafka · mariadb · 게이트웨이 정책은 그대로 남는다."""
    meta = {**project(), "web_apps": []}
    monkeypatch.setattr(gen_k3s, "project", lambda: meta)
    text = gen_k3s.netpols(gen_k3s.Ctx())
    names = {d["metadata"]["name"] for d in _docs(text)}
    assert "allow-ingress-controller" not in names
    assert {"kafka-from-services", "mariadb-from-services", f"allow-{catalog.gateway()}"} <= names


def test_unknown_allow_from_fails(monkeypatch):
    """allow_from 오타가 조용히 '아무도 허용 안 함'이 되지 않게 — 카탈로그에 없는 이름이면 생성기가 멈춘다(plan §6 닫힘)."""
    import pytest

    _with_allowlisted_backend(monkeypatch, ["no-such-svc"])
    with pytest.raises(SystemExit, match="no-such-svc"):
        gen_k3s.generate()


def test_prod_alertmanager_two_receivers_and_volume():
    """운영 알림(REQ-10-2) — 수신처 두 곳(게이트웨이 + oncall), critical · warning 모두 두 곳으로(continue: true).
    oncall URL 은 시크릿 파일(url_file)에서 읽고 생성물에는 글자가 없다. 수신처 시크릿은 optional 마운트(없어도 기동),
    침묵 · 발송 기록(data)은 PVC 에 남겨 재시작 뒤에도 유지한다."""
    import shutil
    import subprocess

    import validate_infra as vi
    from novalib import ROOT

    slug = project()["slug"]
    out = _out()
    gw_url = f"http://{catalog.gateway()}.{catalog.get(catalog.gateway()).namespace}.svc.cluster.local:8000/internal/alertmanager"
    am = yaml.safe_load(_find(out, "k3s/overlays/prod/alertmanager.yml"))
    recv = {r["name"]: r["webhook_configs"] for r in am["receivers"]}
    assert set(recv) == {"gateway", "oncall"}
    assert recv["gateway"] == [{"url": gw_url, "send_resolved": True}]
    assert recv["oncall"] == [{"url_file": "/etc/alertmanager/receivers/oncall-url", "send_resolved": True}]
    assert am["route"]["receiver"] == "gateway"
    for sev in ("critical", "warning"):
        hits = [r for r in am["route"]["routes"] if r["matchers"] == [f'severity="{sev}"']]
        assert [r["receiver"] for r in hits] == ["gateway", "oncall"], sev
        assert hits[0].get("continue") is True, sev  # 첫 수신처에서 멈추지 않고 oncall 까지 간다
    # 오버레이: 설정 교체 · PVC 리소스 · 수신처 ExternalSecret(개발 시크릿이 없으니 지우기 패치에는 넣지 않는다)
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    assert {"name": "alertmanager-config", "namespace": "observability", "behavior": "replace",
            "files": ["alertmanager.yml"]} in kust["configMapGenerator"]
    assert "alertmanager-data.yaml" in kust["resources"]
    (pvc,) = _docs(_find(out, "k3s/overlays/prod/alertmanager-data.yaml"))
    assert pvc["kind"] == "PersistentVolumeClaim"
    assert pvc["metadata"]["name"] == "alertmanager-data" and pvc["metadata"]["namespace"] == "observability"
    assert pvc["spec"]["accessModes"] == ["ReadWriteOnce"] and pvc["spec"]["storageClassName"] == "local-path"
    es = {(d["metadata"]["namespace"], d["metadata"]["name"]): d for d in _docs(_find(out, "k3s/overlays/prod/secrets-external.yaml"))}
    rec = es[("observability", "alertmanager-receivers")]
    assert [(x["secretKey"], x["remoteRef"]) for x in rec["spec"]["data"]] == [
        ("oncall-url", {"key": f"{slug}/prod/observability/alertmanager-receivers", "property": "oncall-url"})]
    deleted = {d["metadata"]["name"] for d in _docs(_find(out, "k3s/overlays/prod/delete-dev-secrets.yaml"))}
    assert "alertmanager-receivers" not in deleted
    assert "http" not in _find(out, "k3s/overlays/prod/secrets-external.yaml").split("alertmanager-receivers", 1)[1]
    # 실제 렌더로 패치가 먹었는지 — 볼륨 소스가 둘이 되거나(emptyDir 잔존) 마운트가 빠지면 여기서 잡힌다
    k = vi.kubectl() or shutil.which("kubectl")
    if not k:
        return  # kubectl 없는 환경 — 생성물 단언까지만(운영 렌더는 lint 의 check_prod_render 가 맡는다)
    r = subprocess.run([k, "kustomize", str(ROOT / "infra/k3s/overlays/prod")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[:500]
    docs = _docs(r.stdout)
    (dep,) = [d for d in docs if d["kind"] == "Deployment" and d["metadata"]["name"] == "alertmanager"]
    assert dep["metadata"]["namespace"] == "observability"
    vols = {v["name"]: v for v in vi.pod_spec(dep)["volumes"]}
    assert vols["data"] == {"name": "data", "persistentVolumeClaim": {"claimName": "alertmanager-data"}}
    assert vols["receivers"]["secret"] == {"secretName": "alertmanager-receivers", "optional": True}
    (ctr,) = vi.pod_spec(dep)["containers"]
    mounts = {m["name"]: m for m in ctr["volumeMounts"]}
    assert mounts["receivers"]["mountPath"] == "/etc/alertmanager/receivers" and mounts["receivers"]["readOnly"] is True
    assert mounts["config"]["mountPath"] == "/etc/alertmanager" and mounts["data"]["mountPath"] == "/alertmanager"
    cm = next(d for d in docs if d["kind"] == "ConfigMap" and d["metadata"]["name"].startswith("alertmanager-config"))
    assert yaml.safe_load(cm["data"]["alertmanager.yml"]) == am  # base 의 게이트웨이 하나짜리 설정을 운영 설정이 대신한다
    assert any(d["kind"] == "PersistentVolumeClaim" and d["metadata"]["name"] == "alertmanager-data" for d in docs)


def test_outbox_quarantined_alert_rule():
    """격리 행(T03-4.04 nova_outbox_quarantined)은 자동 재시도하지 않으므로 1건이라도 5분 남으면 warning(REQ-261104-11-3).
    임계값은 생성기와 게이트웨이 직접 수집 경보가 같은 값을 써야 Prometheus 유무로 판단이 갈리지 않는다."""
    import ast

    from novalib import ROOT

    # 키는 끝부분으로 찾는다 — `_out()` 은 'Nova-dev/' 로 잘라 키를 만들어, 복제본(다른 폴더 이름)에서는 절대 경로가 된다
    alert = yaml.safe_load(_find(_out(), "observability/prometheus/alert_rules.yml"))
    rules = {r["alert"]: r for g in alert["groups"] for r in g["rules"] if "alert" in r}
    q = rules["OutboxQuarantined"]
    assert q["expr"] == "max by (service) (nova_outbox_quarantined) > 0"
    assert q["for"] == "5m" and q["labels"] == {"severity": "warning"}
    assert "nova.py parked" in q["annotations"]["summary"] + q["annotations"].get("runbook", "")
    src = (ROOT / "services/gateway/gateway/monitoring.py").read_text(encoding="utf-8")
    gw = next(ast.literal_eval(n.value) for n in ast.parse(src).body
              if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "THRESHOLDS")
    assert gen_k3s.THRESHOLDS["outbox_quarantined"] == gw["outbox_quarantined"] == 0
    shared = set(gen_k3s.THRESHOLDS) & set(gw)
    assert {k: gen_k3s.THRESHOLDS[k] for k in shared} == {k: gw[k] for k in shared}


# ------------------------------------------------------------------ REQ-261104-10 · R5 웹 · Helm 운영 기본값 · npm ci + R17 신뢰 홉(T02-6.02 ~ 6.06)
def _svc_container_and_pod() -> tuple[dict, dict]:
    """기준값 — base 서비스 Deployment(svc-<게이트웨이>). 웹 · Helm 은 이 값에 맞춘다(값을 따로 만들지 않는다)."""
    import validate_infra as vi

    dep = next(d for d in _docs(_find(_out(), f"k3s/base/svc-{catalog.gateway()}.yaml")) if d["kind"] == "Deployment")
    pod = vi.pod_spec(dep)
    return pod["containers"][0], pod


def test_web_has_probes_security_and_pdb():
    """웹 Deployment 도 서비스와 같은 probe 3종 · seccomp · 컨테이너 보안 컨텍스트 · PDB 를 가진다.
    readOnlyRootFilesystem 이라 Next 가 쓰는 /tmp · .next/cache 는 emptyDir 로 연다(P-6 실기동 확인은 별도)."""
    import validate_infra as vi

    sc, spod = _svc_container_and_pod()
    out = _out()
    for w in project().get("web_apps", []):
        n = f"web-{w['name']}"
        docs = _docs(_find(out, f"k3s/base/{n}.yaml"))
        dep = next(d for d in docs if d["kind"] == "Deployment")
        pod = vi.pod_spec(dep)
        (ctr,) = pod["containers"]
        assert pod["securityContext"]["seccompProfile"] == spod["securityContext"]["seccompProfile"] == {"type": "RuntimeDefault"}
        assert pod["securityContext"]["runAsNonRoot"] is True
        assert ctr["securityContext"] == sc["securityContext"]
        assert ctr["securityContext"]["readOnlyRootFilesystem"] is True
        # probe 는 웹 포트(http=3000)의 / — 4단계 NetworkPolicy 가 웹 파드에 여는 포트와 같다
        assert ctr["ports"] == [{"name": "http", "containerPort": 3000}]
        for kind in ("startupProbe", "livenessProbe", "readinessProbe"):
            p = ctr[kind]
            assert p["httpGet"] == {"path": "/", "port": "http"}, kind
            assert {k: v for k, v in p.items() if k != "httpGet"} == {k: v for k, v in sc[kind].items() if k != "httpGet"}, kind
        mounts = {m["mountPath"]: m["name"] for m in ctr["volumeMounts"]}
        assert set(mounts) == {"/tmp", f"/web/apps/{w['name']}/.next/cache"}
        vols = {v["name"]: v for v in pod["volumes"]}
        assert set(vols) == set(mounts.values()) and all("emptyDir" in v for v in vols.values())
        pdb = next(d for d in docs if d["kind"] == "PodDisruptionBudget")
        assert pdb["metadata"] == {"name": n, "namespace": dep["metadata"]["namespace"]}
        assert pdb["spec"] == {"maxUnavailable": 1, "selector": {"matchLabels": {"app": n}}}
        # 운영 준비 검사(E3)의 'PDB 없음: Deployment/<ns>/web-…' 항목이 생성물로 채워진다
        assert not [e for e in vi.check_prod_readiness(docs) if n in e]


def test_helm_template_matches_k3s_hardening():
    """Helm 템플릿(손 관리)도 k3s 서비스 Deployment 와 같은 probe 3종 · 보안 컨텍스트 · /tmp emptyDir · PDB 를 가진다.
    helm 없는 환경에서도 잡도록 k3s 생성물의 줄을 템플릿에서 그대로 찾는다(값이 갈라지면 실패)."""
    import re

    from novalib import ROOT

    tpl = (ROOT / "infra/helm/chart/templates/services.yaml").read_text(encoding="utf-8")
    lines = {ln.strip() for ln in tpl.splitlines()}
    svc = _find(_out(), f"k3s/base/svc-{catalog.gateway()}.yaml").splitlines()
    for key in ("readinessProbe:", "livenessProbe:", "startupProbe:", "volumeMounts:", "volumes:"):
        (want,) = [ln.strip() for ln in svc if ln.strip().startswith(key)]
        assert want in lines, f"Helm 템플릿에 k3s 와 같은 줄이 없음: {want}"
    # 보안 컨텍스트 두 줄(파드 · 컨테이너) 모두
    for want in [ln.strip() for ln in svc if ln.strip().startswith("securityContext:")]:
        assert want in lines, f"Helm 템플릿에 k3s 와 같은 줄이 없음: {want}"
    assert "failureThreshold: 3" in next(ln for ln in lines if ln.startswith("readinessProbe:"))
    # 서비스마다 PDB — 같은 선택자(app: <이름>) · maxUnavailable 1
    pdb = tpl.split("kind: PodDisruptionBudget", 1)
    assert len(pdb) == 2, "Helm 템플릿에 PodDisruptionBudget 없음"
    body = pdb[1].split("---", 1)[0]
    assert "maxUnavailable: 1" in body and re.search(r"selector: \{matchLabels: \{app: \{\{ \$name \}\}\}\}", body)
    # 서비스 range 안에 있다(밖이면 서비스마다가 아니라 한 번만 렌더된다)
    assert tpl.index("{{- range $name, $s := .Values.services }}") < tpl.index("kind: PodDisruptionBudget") < tpl.rindex("{{- end }}")


def test_web_dockerfile_uses_npm_ci_only():
    """웹 이미지는 잠금 파일 그대로만 설치한다 — `npm install` 대체 경로가 있으면 잠금 파일이 없거나 어긋날 때
    조용히 다른 의존성 판본으로 빌드된다. 잠금 파일 COPY 도 필수(`*` 글롭은 없어도 통과시킨다)."""
    import re

    from novalib import ROOT

    # 지시문만 본다(주석은 왜 바꿨는지 설명하느라 옛 명령을 적을 수 있다)
    code = [ln for ln in (ROOT / "infra/docker/Dockerfile.web").read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    installs = [ln for ln in code if re.search(r"\bnpm (ci|install|i)\b", ln)]
    assert installs == ["RUN npm ci --workspaces --include-workspace-root"], installs
    copies = [ln for ln in code if ln.startswith("COPY") and "package.json" in ln]
    assert any(re.search(r"(^|\s)web/package-lock\.json(\s|$)", ln) for ln in copies), copies
    assert not any("package-lock.json*" in ln for ln in code)
    assert (ROOT / "web/package-lock.json").is_file()  # 필수 COPY 의 원천이 저장소에 있다


def test_prod_sets_trusted_hops():
    """운영은 Traefik 하나 뒤에 게이트웨이가 있다(P-5 = 1) — X-Forwarded-For 의 오른쪽 1홉을 클라이언트 IP 로 믿는다.
    개발 base 는 넣지 않는다(기본 0 = XFF 무시, 위조 방지). 값이 틀리면 레이트리밋이 위조를 허용하거나 모두 같은 IP 가 된다."""
    import shutil
    import subprocess

    import validate_infra as vi
    from novalib import ROOT

    out = _out()
    cm = f"{project()['slug']}-common"
    assert "GW_TRUSTED_HOPS" not in _find(out, "k3s/base/configmap-common.yaml")
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    (patch,) = [p for p in kust["patches"] if (p.get("target") or {}).get("kind") == "ConfigMap"
                and p["target"].get("name") == cm]
    ops = yaml.safe_load(patch["patch"])
    assert {"op": "add", "path": "/data/GW_TRUSTED_HOPS", "value": "1"} in ops
    # 값의 뜻을 패치 바로 위 주석에 남긴다(1 이 '프록시 Traefik 하나'라는 전제임을 다음 사람이 알게)
    block = _find(out, "k3s/overlays/prod/kustomization.yaml").split(f"name: {cm}}}", 1)[1].split("patch: |-", 1)[0]
    assert "GW_TRUSTED_HOPS" in block and "Traefik" in block
    k = vi.kubectl() or shutil.which("kubectl")
    if k:  # 실제 렌더 — 게이트웨이 네임스페이스의 공통 ConfigMap 에 문자열 "1" 로 들어간다
        r = subprocess.run([k, "kustomize", str(ROOT / "infra/k3s/overlays/prod")], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr[:500]
        gw_ns = catalog.get(catalog.gateway()).namespace
        (gcm,) = [d for d in _docs(r.stdout) if d["kind"] == "ConfigMap" and d["metadata"]["name"] == cm
                  and d["metadata"]["namespace"] == gw_ns]
        assert gcm["data"]["GW_TRUSTED_HOPS"] == "1"
    # Helm(T02-6.06) — values 의 trustedHops(문자열 "1")를 템플릿이 env GW_TRUSTED_HOPS 로 넣는다
    values = yaml.safe_load(_find(out, "helm/chart/values.yaml"))
    assert values["trustedHops"] == "1"
    tpl = (ROOT / "infra/helm/chart/templates/services.yaml").read_text(encoding="utf-8")
    assert "- {name: GW_TRUSTED_HOPS, value: {{ $root.Values.trustedHops | default \"0\" | quote }}}" in tpl


def test_alertmanager_image_has_url_file_fix():
    """Alertmanager v0.27.0 은 url_file 웹훅이 2xx 아닌 응답을 받으면 프로세스 전체가 panic 한다(prometheus/alertmanager#3798,
    0.28.0 수정). 운영 oncall 수신처가 url_file 을 쓰므로 개발 · 운영 모든 이미지가 0.28.0 이상이어야 한다(T02-8.05 · 사용자 결정 (A))."""
    import re

    from novalib import ROOT

    out = _out()
    sources = {
        "compose(생성물)": _find(out, "docker-compose.yml"),
        "k8s(손 관리)": (ROOT / "infra/observability/k8s/alertmanager.yaml").read_text(encoding="utf-8"),
    }
    for where, text in sources.items():
        tags = re.findall(r"prom/alertmanager:v(\d+)\.(\d+)\.(\d+)", text)
        assert tags, f"{where}: Alertmanager 이미지가 없다"
        for t in tags:
            assert tuple(map(int, t)) >= (0, 28, 0), f"{where}: v{'.'.join(t)} — url_file panic 결함(#3798)이 있는 판본"


# ------------------------------------------------------------------ REQ-261105-05 · plan_REQ_07 1 · 2단계(운영 기본값)
def _with_db_service(monkeypatch, **k8s) -> None:
    """DB 서비스 하나를 더한다 — k8s 값(hpa_max 등)을 바꿔 연결 예산을 시험한다."""
    import dataclasses

    real = catalog.services()
    proto = next(s for s in real if s.db)
    extra = dataclasses.replace(proto, name="ledger-x", routes=(), local_port=proto.local_port + 90, k8s={**proto.k8s, **k8s})
    monkeypatch.setattr(catalog, "services", lambda: (*real, extra))


def test_db_pool_constant_matches_common_db():
    """생성기의 파드당 풀 최대(DB_POOL_MAX)는 nova_common/db.py 의 pool_size + max_overflow 와 같아야 한다 —
    한쪽만 바뀌면 연결 예산이 실제와 어긋난다(THRESHOLDS 와 같은 대조 방식)."""
    import re

    from novalib import ROOT

    src = (ROOT / "packages/common-py/nova_common/db.py").read_text(encoding="utf-8")
    m = re.search(r"pool_size=(\d+),\s*max_overflow=(\d+)", src)
    assert m, "db.py 에서 pool_size · max_overflow 를 찾지 못했다 — 형식이 바뀌었으면 DB_POOL_MAX 대조를 같이 고친다"
    assert gen_k3s.DB_POOL_MAX == int(m[1]) + int(m[2])


def test_db_connection_budget_within_mariadb_limit(monkeypatch):
    """T07-1.05 — (서비스별 최대 복제본 + 롤링 1) × 풀 최대 + 예비분 합이 MariaDB max_connections 를 넘으면 생성 실패."""
    import pytest

    c = gen_k3s.Ctx()
    limit = gen_k3s.mariadb_max_connections()
    assert limit > 0
    used, rows = gen_k3s.db_budget(c)
    want = sum((max(s.k8s["hpa_max"], s.k8s.get("replicas", 1)) + 1) * gen_k3s.DB_POOL_MAX for s in catalog.services() if s.db)
    assert used == want + gen_k3s.DB_RESERVED and used <= limit
    assert {n for n, _ in rows} == {s.name for s in catalog.services() if s.db}
    # 넘치게 하면 생성이 멈추고 이유에 서비스 이름 · 상한 · 고칠 곳이 나온다
    _with_db_service(monkeypatch, hpa_max=limit)
    with pytest.raises(SystemExit) as e:
        gen_k3s.generate()
    msg = str(e.value)
    assert "max_connections" in msg and "ledger-x" in msg and str(limit) in msg and "hpa_max" in msg


def test_db_connection_budget_without_db_services(monkeypatch):
    """DB 서비스가 없는 새 프로젝트 — 예산은 예비분뿐이고 생성은 초록."""
    real = catalog.services()
    monkeypatch.setattr(catalog, "services", lambda: tuple(s for s in real if not s.db))
    used, rows = gen_k3s.db_budget(gen_k3s.Ctx())
    assert rows == [] and used == gen_k3s.DB_RESERVED
    gen_k3s.generate()


def _prod_render_like() -> list[dict]:
    """kubectl 없이 운영 렌더를 흉내 낸다 — base 서비스 Deployment + 공통 ConfigMap 에 prod 패치(NOVA_ENV)를 적용."""
    out = _out()
    docs = [d for n in catalog.names() for d in _docs(_find(out, f"k3s/base/svc-{n}.yaml"))]
    cms = _docs(_find(out, "k3s/base/configmap-common.yaml"))
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    cm = f"{project()['slug']}-common"
    for p in kust["patches"]:
        if (p.get("target") or {}).get("kind") == "ConfigMap" and p["target"].get("name") == cm:
            for op in yaml.safe_load(p["patch"]):
                for d in cms:
                    d["data"][op["path"].rsplit("/", 1)[1]] = op["value"]
    return [*docs, *cms]


def test_prod_env_required_per_service_deployment():
    """T07-2.02 — 운영 렌더에서 서비스 Deployment 마다 NOVA_ENV 가 prod 로 풀려야 한다(env 가 envFrom 을 이긴다).
    ConfigMap 하나만 보던 검사는 Deployment 가 그 ConfigMap 을 안 읽거나 env 로 dev 를 덮는 경우를 놓친다."""
    import copy

    import validate_infra as vi

    good = _prod_render_like()
    assert vi.check_prod_env(good) == []
    # ConfigMap 에 NOVA_ENV 가 없으면 서비스마다 실패
    bare = copy.deepcopy(good)
    for d in bare:
        if d["kind"] == "ConfigMap":
            d["data"].pop("NOVA_ENV")
    errs = vi.check_prod_env(bare)
    assert len(errs) == len(catalog.names()) and all("NOVA_ENV" in e for e in errs)
    # env 로 dev 를 덮으면 실패
    over = copy.deepcopy(good)
    dep = next(d for d in over if d["kind"] == "Deployment")
    dep["spec"]["template"]["spec"]["containers"][0]["env"].append({"name": "NOVA_ENV", "value": "dev"})
    assert [e for e in vi.check_prod_env(over) if dep["metadata"]["name"] in e]
    # Deployment 가 빠져도 실패(서비스가 렌더에서 사라짐)
    gone = [d for d in good if not (d["kind"] == "Deployment" and d["metadata"]["name"] == catalog.gateway())]
    assert [e for e in vi.check_prod_env(gone) if catalog.gateway() in e]


def test_prod_env_static_patch_check(monkeypatch):
    """kubectl 이 없는 PC · 새 프로젝트에서도 운영 오버레이에 NOVA_ENV=prod 패치가 있는지 정적으로 본다.
    개발 base · compose 에는 넣지 않는다 — 로컬 python nova.py run · compose 는 그대로 dev(§11.2 검토 초점)."""
    import validate_infra as vi
    from novalib import ROOT

    out = _out()
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    assert vi.check_prod_env_patch(kust) == []
    for p in kust["patches"]:
        if (p.get("target") or {}).get("kind") == "ConfigMap":
            p["patch"] = p["patch"].replace("NOVA_ENV", "NOVA_ENVX")
    assert vi.check_prod_env_patch(kust)
    assert "NOVA_ENV" not in _find(out, "k3s/base/configmap-common.yaml")
    assert "NOVA_ENV" not in _find(out, "docker-compose.yml")
    for f in ("scripts/dev_server.py", "scripts/run_local.sh", "scripts/devstack.py"):  # python nova.py run 의 실행기 — NOVA_ENV 없음 = dev
        assert "NOVA_ENV" not in (ROOT / f).read_text(encoding="utf-8"), f
    # validate_infra main 이 정적 검사를 부른다(kubectl 이 없어도 건너뛰지 않음)
    src = (ROOT / "scripts/validate_infra.py").read_text(encoding="utf-8")
    assert "check_prod_env_patch(" in src.split("def main", 1)[1] and "check_prod_env(" in src.split("def check_prod_render", 1)[1]


def _prod_ingress_parts(out: dict[str, str]) -> tuple[dict, list[dict]]:
    kust = yaml.safe_load(_find(out, "k3s/overlays/prod/kustomization.yaml"))
    return kust, _docs(_find(out, "k3s/overlays/prod/ingress-tls.yaml"))


def test_prod_ingress_tls_https_only_hsts(monkeypatch):
    """T07-2.04 — 운영 인그레스는 TLS(모든 호스트) · websecure 만 · HSTS 미들웨어. 인증서 시크릿 · issuer 는
    nova.project.json tls 에서, 없으면 자리표시(<slug>-tls · issuer 주석 없음)로 — 새 프로젝트 첫날도 초록."""
    import shutil
    import subprocess

    import validate_infra as vi
    from novalib import ROOT

    p = project()
    slug, domain = p["slug"], p["domain"]
    gw = catalog.get(catalog.gateway())
    out = _out()
    kust, mws = _prod_ingress_parts(out)
    assert "ingress-tls.yaml" in kust["resources"]
    # HSTS 미들웨어 — 인그레스가 있는 네임스페이스마다(Traefik 은 기본으로 다른 네임스페이스의 미들웨어를 못 쓴다)
    by_ns = {d["metadata"]["namespace"]: d for d in mws if d["kind"] == "Middleware"}
    assert set(by_ns) == {gw.namespace, "observability"}
    for d in by_ns.values():
        assert d["apiVersion"] == "traefik.io/v1alpha1" and d["metadata"]["name"] == "hsts"
        h = d["spec"]["headers"]
        assert h["stsSeconds"] >= 31536000 and h["stsIncludeSubdomains"] is True and h["forceSTSHeader"] is True
    # 인그레스 패치 — 호스트 전부를 TLS 로, websecure 만, 미들웨어 연결
    base_ing = {d["metadata"]["name"]: d for d in _docs(_find(out, "k3s/base/ingress.yaml"))}
    pats = {(pt["target"]["kind"], pt["target"]["name"]): yaml.safe_load(pt["patch"]) for pt in kust["patches"]
            if (pt.get("target") or {}).get("kind") == "Ingress"}
    assert set(pats) == {("Ingress", n) for n in base_ing}
    for n, b in base_ing.items():
        pt = pats[("Ingress", n)]
        ns = b["metadata"]["namespace"]
        ann = pt["metadata"]["annotations"]
        assert ann["traefik.ingress.kubernetes.io/router.entrypoints"] == "websecure"
        assert ann["traefik.ingress.kubernetes.io/router.middlewares"] == f"{ns}-hsts@kubernetescrd"
        assert ann["traefik.ingress.kubernetes.io/router.tls"] == "true"
        assert "cert-manager.io/cluster-issuer" not in ann  # issuer 가 없으면 넣지 않는다(없는 issuer 는 인증서 발급 실패로 숨는다)
        (tls,) = pt["spec"]["tls"]
        assert tls["hosts"] == [r["host"] for r in b["spec"]["rules"]] and tls["secretName"] == f"{slug}-tls"
    assert f"api.{domain}" in pats[("Ingress", slug)]["spec"]["tls"][0]["hosts"]
    assert "nova.project.json" in _find(out, "k3s/overlays/prod/ingress-tls.yaml")  # 자리표시 안내
    # 개발 base 는 그대로(http 도 받음)
    assert "router.entrypoints: web,websecure" in _find(out, "k3s/base/ingress.yaml")
    # 메타에 tls 가 있으면 그 값을 쓴다
    meta = {**p, "tls": {"secret": "acme-cert", "cluster_issuer": "letsencrypt-prod"}}
    monkeypatch.setattr(gen_k3s, "project", lambda: meta)
    kust2, _ = _prod_ingress_parts(_out())
    for pt in kust2["patches"]:
        if (pt.get("target") or {}).get("kind") == "Ingress":
            body = yaml.safe_load(pt["patch"])
            assert body["metadata"]["annotations"]["cert-manager.io/cluster-issuer"] == "letsencrypt-prod"
            assert body["spec"]["tls"][0]["secretName"] == "acme-cert"
    monkeypatch.undo()
    k = vi.kubectl() or shutil.which("kubectl")
    if k:  # 실제 렌더 — 패치가 base 인그레스에 붙는다
        r = subprocess.run([k, "kustomize", str(ROOT / "infra/k3s/overlays/prod")], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr[:500]
        ings = [d for d in _docs(r.stdout) if d["kind"] == "Ingress"]
        assert ings and all(d["spec"].get("tls") and
                            d["metadata"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] == "websecure" for d in ings)
        assert sum(1 for d in _docs(r.stdout) if d["kind"] == "Middleware") == 2


def _obs_peer(ld: str, apps: list[str]) -> dict:
    return {"namespaceSelector": {"matchLabels": {f"{ld}/ns": "observability"}},
            "podSelector": {"matchExpressions": [{"key": "app", "operator": "In", "values": apps}]}}


def test_observability_peer_narrowed_to_prometheus_alertmanager(monkeypatch):
    """T07-2.05 — observability 네임스페이스 통째가 아니라 그 안의 파드만: 백엔드는 Prometheus(스크레이프)만,
    게이트웨이는 Prometheus + Alertmanager(웹훅). Grafana 등 다른 관측 파드는 서비스를 직접 부르지 못한다."""
    from novalib import ROOT

    _with_allowlisted_backend(monkeypatch, [catalog.backends()[0]])
    ld = project().get("label_domain", f"{project()['slug']}.dev")
    by = {(p["metadata"]["namespace"], p["metadata"]["name"]): p for p in _netpols()}
    for s in catalog.services():
        frm = by[(s.namespace, f"allow-{s.name}")]["spec"]["ingress"][0]["from"]
        want = gen_k3s.OBS_APPS["gateway" if s.gateway else "backend"]
        assert frm[-1] == _obs_peer(ld, want)
        assert not [p for p in frm if p.get("namespaceSelector", {}).get("matchLabels", {}).get(f"{ld}/ns") == "observability"
                    and "podSelector" not in p], f"{s.name}: observability 통째 허용이 남아 있다"
    assert gen_k3s.OBS_APPS == {"backend": ["prometheus"], "gateway": ["prometheus", "alertmanager"]}
    # 그 라벨을 가진 파드가 관측 매니페스트(손 관리)에 실제로 있다 — 이름이 바뀌면 스크레이프가 조용히 막힌다
    labels = set()
    for f in ("prometheus.yaml", "alertmanager.yaml"):
        for d in _docs((ROOT / "infra/observability/k8s" / f).read_text(encoding="utf-8")):
            if d["kind"] in ("Deployment", "StatefulSet"):
                labels.add(d["spec"]["template"]["metadata"]["labels"]["app"])
    assert {"prometheus", "alertmanager"} <= labels
    # Helm — 서비스마다 observedBy(생성물)를 템플릿이 같은 peer 로 그린다
    values = yaml.safe_load(_find(_out(), "helm/chart/values.yaml"))
    for s in catalog.services():
        assert values["services"][s.name]["observedBy"] == gen_k3s.OBS_APPS["gateway" if s.gateway else "backend"]
    tpl = {ln.strip() for ln in (ROOT / "infra/helm/chart/templates/networkpolicy.yaml").read_text(encoding="utf-8").splitlines()}
    assert "podSelector: {matchExpressions: [{key: app, operator: In, values: {{ toJson $s.observedBy }}}]}" in tpl


def test_backup_failure_alert_without_new_components():
    """T07-2.06 — kube-state-metrics · Pushgateway 없이: 백업 스크립트가 실패하면(ERR) Alertmanager API(/api/v2/alerts)로
    critical 경보를 직접 보내고, 성공하면 같은 경보를 해제(endsAt=지금)한다. 이미지에 curl 이 없어 bash /dev/tcp 로 보낸다.
    경보 전송 실패가 백업 결과(종료 코드)를 바꾸지 않는다."""
    out = _out()
    (cj,) = [d for d in _docs(_find(out, "k3s/overlays/prod/mariadb-backup.yaml")) if d["kind"] == "CronJob"]
    (ctr,) = cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"]
    sh = ctr["args"][0]
    assert "/api/v2/alerts" in sh and "/dev/tcp/" in sh
    assert '"alertname":"MariaDBBackupFailed"' in sh and '"severity":"critical"' in sh
    assert "trap " in sh and " ERR" in sh  # 실패 경로
    assert sh.rstrip().splitlines()[-1].startswith("am_alert resolved")  # 성공 경로의 마지막 = 해제
    assert "exit \"$rc\"" in sh  # 경보를 보낸 뒤 원래 종료 코드로 끝낸다(삼키지 않음)
    env = {e["name"]: e.get("value") for e in ctr["env"]}
    assert env["AM_HOST"] == "alertmanager.observability.svc.cluster.local" and env["AM_PORT"] == "9093"
    # 생성 주석이 '알림 없음'이라고 거짓말하지 않는다
    assert "알림 없음" not in _find(out, "k3s/overlays/prod/mariadb-backup.yaml")


def test_list_secrets_matches_external_secrets(capsys):
    """T07-2.07 — gen_k3s --list-secrets 는 운영 ExternalSecret 이 읽는 원격 키 · property 를 빠짐없이 한 줄씩 낸다."""
    import sys as _sys

    out = _out()
    want = set()
    for d in _docs(_find(out, "k3s/overlays/prod/secrets-external.yaml")):
        for x in d["spec"]["data"]:
            want.add((x["remoteRef"]["key"], x["remoteRef"]["property"]))
    rows = gen_k3s.list_secrets()
    assert {(r[0], r[1]) for r in rows} == want and len(rows) == len(want)
    assert gen_k3s.main(["--list-secrets"]) == 0
    text = capsys.readouterr().out
    assert f"{project()['slug']}-secrets" in text  # ClusterSecretStore 이름
    for key, prop in want:
        assert any(key in ln and prop in ln for ln in text.splitlines()), key
    assert "dev-" not in text
    _sys.stdout.flush()


def test_deploy_doc_first_deploy_section():
    """T07-2.07 — deploy.md '첫 배포 준비' 절: 시크릿 저장소 · 원격 키 목록 명령 · TLS · DNS · 레지스트리 권한."""
    from novalib import ROOT

    doc = (ROOT / "docs/conventions/deploy.md").read_text(encoding="utf-8")
    assert "## 첫 배포 준비" in doc
    sec = doc.split("## 첫 배포 준비", 1)[1].split("\n## ", 1)[0]
    for must in ("ClusterSecretStore", "--list-secrets", "TLS", "DNS", "레지스트리", "imagePullSecrets", "nova.project.json"):
        assert must in sec, must
