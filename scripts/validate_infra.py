"""인프라 정적 검증(kustomize/promtool 바이너리가 없는 환경용 대체 검사). lint 가 실행한다.

  uv run python scripts/validate_infra.py

- 모든 YAML 문서 파싱 · kustomization 의 resources/configMapGenerator 파일 존재
- 참조 무결성: envFrom/secretKeyRef/configMap 볼륨이 같은 네임스페이스에 정의돼 있는지
- Prometheus 규칙: groups/rules 구조 · PromQL 괄호 균형 · 사용 메트릭이 코드에 정의된 이름인지
- Grafana 대시보드 JSON 파싱 · uid 중복 없음
"""
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, project  # noqa: E402

from nova_common import catalog  # noqa: E402

errors: list[str] = []
METRICS = set(re.findall(r'"(nova_[a-z_]+)"', (ROOT / "packages/common-py/nova_common/metrics.py").read_text(encoding="utf-8")))
DERIVED = {m + s for m in METRICS for s in ("_bucket", "_count", "_sum")}
RECORDED: set[str] = set()


def load_kustomization(d: Path, seen: set) -> list[dict]:
    d = d.resolve()
    if d in seen:
        return []
    seen.add(d)
    k = yaml.safe_load((d / "kustomization.yaml").read_text(encoding="utf-8"))
    docs = []
    for r in k.get("resources", []):
        p = (d / r)
        if p.is_dir():
            docs += load_kustomization(p, seen)
        elif not p.exists():
            errors.append(f"{d}: resource 없음 {r}")
        else:
            for doc in yaml.safe_load_all(p.read_text(encoding="utf-8")):
                if doc:
                    if k.get("namespace") and "namespace" not in doc.get("metadata", {}) and doc["kind"] not in ("ClusterRole", "ClusterRoleBinding", "Namespace"):
                        doc["metadata"]["namespace"] = k["namespace"]
                    docs.append(doc)
    for g in k.get("configMapGenerator", []):
        for f in g.get("files", []):
            if not (d / f).exists():
                errors.append(f"{d}: configMapGenerator 파일 없음 {f}")
        if g.get("behavior") in ("replace", "merge"):  # 상위 리소스를 덮는 것 — 새 리소스 아님
            continue
        docs.append({"kind": "ConfigMap", "metadata": {"name": g["name"], "namespace": g.get("namespace") or k.get("namespace")}})
    return docs


WORKLOADS = ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob")


def pod_spec(doc: dict) -> dict:
    """워크로드 문서의 파드 사양 — CronJob 은 spec.jobTemplate.spec.template 아래에 있다. 워크로드가 아니면 {}."""
    if doc.get("kind") not in WORKLOADS:
        return {}
    spec = doc.get("spec") or {}
    if doc["kind"] == "CronJob":
        spec = (spec.get("jobTemplate") or {}).get("spec") or {}
    return (spec.get("template") or {}).get("spec") or {}


def check_refs(docs: list[dict], label: str) -> None:
    have = {(d["kind"], d["metadata"].get("namespace"), d["metadata"]["name"]) for d in docs}
    # ExternalSecret 은 target.name(없으면 자기 이름)의 Secret 을 만든다 — 운영 오버레이의 참조 대상
    have |= {("Secret", d["metadata"].get("namespace"), ((d.get("spec") or {}).get("target") or {}).get("name") or d["metadata"]["name"])
             for d in docs if d["kind"] == "ExternalSecret"}
    for d in docs:
        if d["kind"] not in WORKLOADS:
            continue
        ns = d["metadata"].get("namespace")
        spec = pod_spec(d)
        for c in spec.get("containers", []) + spec.get("initContainers", []):
            for ef in c.get("envFrom", []):
                if "configMapRef" in ef and ("ConfigMap", ns, ef["configMapRef"]["name"]) not in have:
                    errors.append(f"[{label}] {d['metadata']['name']}: ConfigMap {ef['configMapRef']['name']} 없음 (ns={ns})")
            for e in c.get("env", []):
                ref = (e.get("valueFrom") or {}).get("secretKeyRef")
                if ref and ("Secret", ns, ref["name"]) not in have:
                    errors.append(f"[{label}] {d['metadata']['name']}: Secret {ref['name']} 없음 (ns={ns})")
        for v in spec.get("volumes", []):
            if "configMap" in v and ("ConfigMap", ns, v["configMap"]["name"]) not in have:
                errors.append(f"[{label}] {d['metadata']['name']}: 볼륨 ConfigMap {v['configMap']['name']} 없음 (ns={ns})")
    names = [(d["kind"], d["metadata"].get("namespace"), d["metadata"]["name"]) for d in docs]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        errors.append(f"[{label}] 중복 리소스 {dup}")


def check_promql(expr: str, where: str) -> None:
    if expr.count("(") != expr.count(")") or expr.count("{") != expr.count("}") or expr.count("[") != expr.count("]"):
        errors.append(f"{where}: 괄호 불균형 {expr}")
    for m in re.findall(r"\b(nova_[a-z_]+)", expr):
        if m not in METRICS and m not in DERIVED:
            errors.append(f"{where}: 정의되지 않은 메트릭 {m}")
    for m in re.findall(r"\b([a-z_]+:[a-z_0-9]+:[a-z_0-9]+)\b", expr):
        if m not in RECORDED:
            errors.append(f"{where}: 정의되지 않은 recording rule {m}")


DEV_SECRET_MARKERS = re.compile(r"nova-dev-secret|dev-[a-z_]+-pw|dev-root-pw|grafana-dev-pw")


def kubectl() -> str | None:
    import os
    import shutil

    docker = Path("C:/Program Files/Docker/Docker/resources/bin/kubectl.exe")
    for c in (os.getenv("KUBECTL"), shutil.which("kubectl"), str(docker)):
        if c and Path(c).exists():
            return c
    return None


def check_prod_render() -> None:
    """운영 렌더(kubectl kustomize) 배포 게이트 — 개발 비밀값 · 가변 이미지 태그 · NOVA_ENV 누락이면 실패."""
    import subprocess

    k = kubectl()
    if not k:
        print("- kubectl 없음 — 운영 렌더 검사 건너뜀(KUBECTL 환경 변수로 지정 가능)")
        return
    out = subprocess.run([k, "kustomize", str(ROOT / "infra/k3s/overlays/prod")], capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        errors.append(f"[prod] kustomize 실패: {out.stderr[:300]}")
        return
    docs = [d for d in yaml.safe_load_all(out.stdout) if d]
    check_prod_docs(docs)
    errors.extend(check_prod_env(docs))
    # 정적 로드는 패치($patch: delete 등)를 모른다 — 렌더 결과에서만 빠진 것을 더한다(같은 오류는 두 번 적지 않는다)
    errors.extend(f"{e} (렌더 결과)" for e in check_prod_readiness(docs) if e not in errors)
    print(f"운영 렌더 검사: {len(docs)} 리소스 · {readiness_line(docs)}")


def check_prod_docs(docs: list[dict]) -> None:
    """운영 렌더 결과 문서 검사(kubectl 없이도 시험할 수 있게 렌더와 나눔)."""
    for d in docs:
        name = f"{d['kind']}/{d['metadata'].get('namespace', '-')}/{d['metadata']['name']}"
        if d["kind"] == "Secret":
            errors.append(f"[prod] 평문 Secret 금지(ExternalSecret 사용): {name}")
        if DEV_SECRET_MARKERS.search(yaml.safe_dump(d)):
            errors.append(f"[prod] 개발용 비밀값 문자열: {name}")
        spec = pod_spec(d)
        for c in spec.get("containers", []) + spec.get("initContainers", []):
            img = c.get("image", "")
            if img.endswith((":dev", ":latest")) or ":" not in img.split("/")[-1]:
                errors.append(f"[prod] 가변 이미지 태그 금지: {name} → {img}")
    # 가용성: 웹·핵심 경로(services.json replicas ≥ 2)는 운영에서 2 레플리카 이상
    need = {s.name for s in catalog.services() if s.k8s.get("replicas", 1) >= 2}
    for d in docs:
        n = d["metadata"]["name"]
        if d["kind"] == "Deployment" and (n in need or n.startswith("web-")) and (d["spec"].get("replicas") or 1) < 2:
            errors.append(f"[prod] 레플리카 2 미만: Deployment/{n}")
    cm_name = f"{project()['slug']}-common"
    cms = [d for d in docs if d["kind"] == "ConfigMap" and d["metadata"]["name"] == cm_name]
    if not cms or any((d.get("data") or {}).get("NOVA_ENV") != "prod" for d in cms):
        errors.append(f"[prod] {cm_name} 에 NOVA_ENV=prod 가 없음")
    # 운영 Grafana 는 익명 열람 · 임베딩을 끈다(인그레스 grafana.<도메인> 으로 바깥에 열린다)
    for d in docs:
        if d["kind"] == "Deployment" and d["metadata"]["name"] == "grafana":
            for c in d["spec"]["template"]["spec"]["containers"]:
                env = {e["name"]: e.get("value") for e in c.get("env", [])}
                for k in ("GF_AUTH_ANONYMOUS_ENABLED", "GF_SECURITY_ALLOW_EMBEDDING"):
                    if env.get(k, "false") != "false":
                        errors.append(f"[prod] Grafana {k}={env.get(k)} — 운영에서는 false 여야 함")


def check_prod_env(docs: list[dict]) -> list[str]:
    """운영 렌더에서 서비스 Deployment 마다 컨테이너의 NOVA_ENV 가 prod 로 풀리는지(T07-2.02 — B7).
    env 가 envFrom 을 이긴다(쿠버네티스 규칙). NOVA_ENV 가 없으면 서비스는 dev 로 떠 개발 로그인 · 기본 키 검사가 꺼진다."""
    errs: list[str] = []
    cms = {(d["metadata"].get("namespace"), d["metadata"]["name"]): (d.get("data") or {}) for d in docs if d["kind"] == "ConfigMap"}
    deps = {d["metadata"]["name"]: d for d in docs if d["kind"] == "Deployment"}
    for n in catalog.names():
        d = deps.get(n)
        if not d:
            errs.append(f"[prod] Deployment/{n} 이 운영 렌더에 없음 — NOVA_ENV 를 확인할 수 없다")
            continue
        ns = d["metadata"].get("namespace")
        for c in pod_spec(d).get("containers", []):
            val = None
            for ef in c.get("envFrom", []):  # 나중 envFrom 이 앞의 것을 덮는다
                ref = (ef.get("configMapRef") or {}).get("name")
                if ref and "NOVA_ENV" in cms.get((ns, ref), {}):
                    val = cms[(ns, ref)]["NOVA_ENV"]
            for e in c.get("env", []):
                if e.get("name") == "NOVA_ENV":
                    val = e.get("value")
            if val != "prod":
                errs.append(f"[prod] Deployment/{ns}/{n} 컨테이너 {c.get('name')}: NOVA_ENV={val!r} — prod 여야 한다(기동 안전장치가 꺼진다)")
    return errs


def check_prod_env_patch(kust: dict) -> list[str]:
    """kubectl 없이 보는 정적 검사 — 운영 kustomization 이 공통 ConfigMap 에 NOVA_ENV=prod 를 넣는 패치를 가졌는가."""
    cm = f"{project()['slug']}-common"
    for p in kust.get("patches") or []:
        t = p.get("target") or {}
        if t.get("kind") == "ConfigMap" and t.get("name") == cm and isinstance(p.get("patch"), str):
            ops = yaml.safe_load(p["patch"]) or []
            if isinstance(ops, list) and {"op": "add", "path": "/data/NOVA_ENV", "value": "prod"} in ops:
                return []
    return [f"[prod] overlays/prod/kustomization.yaml 에 {cm} NOVA_ENV=prod 패치가 없음 — 운영 서비스가 dev 로 뜬다"]


def readiness_namespaces() -> set[str]:
    """PDB 를 요구하는 네임스페이스 — 카탈로그 서비스의 네임스페이스 + 웹 앱 네임스페이스(게이트웨이와 같은 곳, gen_k3s.web).
    observability 는 넣지 않는다(T02-8.04): E3 의 PDB 는 서비스 PDB 이고, grafana · alertmanager 는 레플리카 1개라
    PDB(minAvailable 1)를 걸면 그 파드를 옮길 수 없어 노드 비우기(drain)가 멈춘다. 가용성보다 운영 작업이 막히는 비용이 크다."""
    return {s.namespace for s in catalog.services()} | {catalog.get(catalog.gateway()).namespace}


def _readiness(docs: list[dict]) -> tuple[list[str], dict[str, int]]:
    """운영 준비 판정 — 오류 문자열과 숫자(DB 계정 Job 수 · 정책 있음/필요 · PDB 있음/필요)를 함께 낸다."""
    errs: list[str] = []
    meta = lambda d: d.get("metadata") or {}  # noqa: E731
    jobs = sum(1 for d in docs if d["kind"] == "Job" and
               ((meta(d).get("labels") or {}).get("app") == "db-provision" or meta(d).get("name") == "db-provision"))
    if catalog.db_services() and not jobs:
        errs.append("[운영 준비] DB 계정 Job(app: db-provision) 없음 — 운영 DB 서비스 계정 · 권한을 만들 수단이 없다")
    pols = {(meta(d).get("namespace"), ((d.get("spec") or {}).get("podSelector") or {}).get("matchLabels", {}).get("app"))
            for d in docs if d["kind"] == "NetworkPolicy"}
    pol_ok = 0
    for n in catalog.backends():
        ns = catalog.get(n).namespace
        if (ns, n) in pols:
            pol_ok += 1
        else:
            errs.append(f"[운영 준비] 서비스 단위 NetworkPolicy 없음: {ns}/{n} (podSelector app: {n})")
    pdbs = [(meta(d).get("namespace"), ((d.get("spec") or {}).get("selector") or {}).get("matchLabels") or {})
            for d in docs if d["kind"] == "PodDisruptionBudget"]
    scope = readiness_namespaces()
    pdb_need = pdb_ok = 0
    for d in docs:
        ns = meta(d).get("namespace")
        if d["kind"] != "Deployment" or ns not in scope:
            continue
        pdb_need += 1
        labels = (((d.get("spec") or {}).get("template") or {}).get("metadata") or {}).get("labels") or {}
        # 빈 matchLabels 는 네임스페이스 전체를 고른다 — 특정 Deployment 의 PDB 로 치지 않는다
        if any(pns == ns and ml and all(labels.get(k) == v for k, v in ml.items()) for pns, ml in pdbs):
            pdb_ok += 1
        else:
            errs.append(f"[운영 준비] PDB 없음: Deployment/{ns}/{meta(d).get('name')} — 노드 비우기 때 한꺼번에 내려간다")
    return errs, {"jobs": jobs, "pol_ok": pol_ok, "pol_need": len(catalog.backends()), "pdb_ok": pdb_ok, "pdb_need": pdb_need}


def check_prod_readiness(docs: list[dict]) -> list[str]:
    """운영 준비(REQ-261104-10 E3) — DB 서비스가 있으면 계정 프로비저닝 Job, 백엔드 서비스마다 자기 파드를 고르는 NetworkPolicy,
    서비스 · 웹 네임스페이스의 Deployment 마다 그 파드를 고르는 PDB. 빠진 것을 오류 문자열로 돌려준다."""
    return _readiness(docs)[0]


def readiness_line(docs: list[dict]) -> str:
    """lint 출력 한 줄 — 분자(있음)/분모(필요)를 함께 찍어, 빠지면 숫자로 보이게 한다."""
    c = _readiness(docs)[1]
    return f"운영 준비: DB 계정 Job {c['jobs']} · 서비스 정책 {c['pol_ok']}/{c['pol_need']} · PDB {c['pdb_ok']}/{c['pdb_need']}"


def helm_bin() -> str | None:
    import os
    import shutil

    for c in (os.getenv("HELM"), shutil.which("helm")):
        if c and Path(c).exists():
            return c
    return None


def check_helm_render() -> None:
    """Helm 차트 렌더(helm template) — 모든 서비스 컨테이너에 NOVA_ENV=prod · JWT_SECRET(secretKeyRef)가 있어야 한다."""
    import subprocess

    h = helm_bin()
    if not h:
        print("- helm 없음 — Helm 렌더 검사 건너뜀(HELM 환경 변수로 지정 가능). 템플릿 텍스트 검사는 tests/test_infra.py")
        return
    out = subprocess.run([h, "template", "nova-check", str(ROOT / "infra/helm/chart")], capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        errors.append(f"[helm] helm template 실패: {out.stderr[:300]}")
        return
    docs = [d for d in yaml.safe_load_all(out.stdout) if d]
    n = 0
    for d in docs:
        if d.get("kind") != "Deployment":
            continue
        n += 1
        for c in d["spec"]["template"]["spec"]["containers"]:
            env = {e["name"]: e for e in c.get("env", [])}
            if (env.get("NOVA_ENV") or {}).get("value") != "prod":
                errors.append(f"[helm] {d['metadata']['name']}: NOVA_ENV=prod 없음")
            if not ((env.get("JWT_SECRET") or {}).get("valueFrom") or {}).get("secretKeyRef"):
                errors.append(f"[helm] {d['metadata']['name']}: JWT_SECRET secretKeyRef 없음")
    # 서비스 단위 NetworkPolicy — 서비스마다 allow-<서비스>, 백엔드는 게이트웨이 파드부터 들인다(k3s base 와 같은 정책)
    pols = {(d["metadata"]["namespace"], d["metadata"]["name"]): d for d in docs if d.get("kind") == "NetworkPolicy"}
    gw = catalog.get(catalog.gateway())
    for s in catalog.services():
        pol = pols.get((s.namespace, f"allow-{s.name}"))
        if not pol:
            errors.append(f"[helm] NetworkPolicy {s.namespace}/allow-{s.name} 없음")
            continue
        peers = [(p.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name"),
                  p.get("podSelector", {}).get("matchLabels", {}).get("app")) for r in pol["spec"].get("ingress") or [] for p in r["from"]]
        want = [] if s.gateway else [(gw.namespace, gw.name), *((catalog.get(f).namespace, f) for f in s.allow_from)]
        if [p for p in peers if p[1]] != want:
            errors.append(f"[helm] {s.namespace}/allow-{s.name}: 허용 파드가 게이트웨이 · allow_from 과 다름 {peers}")
        # 관측 peer(T07-2.05) — 파드 선택자 없이 네임스페이스만 고르는 peer 는 네임스페이스 통째 허용이다
        if [p for r in pol["spec"].get("ingress") or [] for p in r["from"] if "podSelector" not in p
                and p.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name") != "kube-system"]:
            errors.append(f"[helm] {s.namespace}/allow-{s.name}: 파드 선택자 없는 네임스페이스 통째 허용이 있음")
    for ns in dict.fromkeys(s.namespace for s in catalog.services()):
        if (ns, "default-deny-ingress") not in pols:
            errors.append(f"[helm] NetworkPolicy {ns}/default-deny-ingress 없음")
    print(f"Helm 렌더 검사: Deployment {n}개 · NetworkPolicy {len(pols)}개")


def check_generated() -> None:
    """단일 원천 → 생성물이 최신인지(gen_k3s · gen_dashboards --check)."""
    import os
    import subprocess

    for script in ("gen_k3s.py", "gen_dashboards.py"):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--check"], capture_output=True, text=True,
                           encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if r.returncode:
            errors.append(f"{script} --check 실패: " + (r.stderr or r.stdout).strip())
        else:
            print(r.stdout.strip())


def main() -> int:
    check_generated()
    for f in sorted((ROOT / "infra").rglob("*.y*ml")):
        if "templates" in f.parts:  # Helm Go 템플릿은 YAML이 아님
            continue
        try:
            list(yaml.safe_load_all(f.read_text(encoding="utf-8")))
        except yaml.YAMLError as e:
            errors.append(f"{f}: YAML 오류 {e}")
    for ov in ("dev", "prod"):
        docs = load_kustomization(ROOT / f"infra/k3s/overlays/{ov}", set())
        check_refs(docs, ov)
        print(f"overlay {ov}: {len(docs)} 리소스")
        if ov == "prod":
            # 운영 준비(E3)는 정적 로드로 판정한다 — kubectl 없는 PC · 새 프로젝트에서도 건너뛰지 않는다.
            # kubectl 이 있으면 check_prod_render 가 패치가 반영된 렌더 결과로 한 번 더 본다.
            errors.extend(check_prod_readiness(docs))
            print(readiness_line(docs))
            # NOVA_ENV=prod 패치(T07-2.02) — 정적 로드는 패치를 적용하지 않으므로 패치 존재를 본다. 렌더 결과는 check_prod_render
            errors.extend(check_prod_env_patch(yaml.safe_load(
                (ROOT / "infra/k3s/overlays/prod/kustomization.yaml").read_text(encoding="utf-8"))))
    check_prod_render()
    check_helm_render()
    rules_dir = ROOT / "infra/observability/prometheus"
    rec = yaml.safe_load((rules_dir / "recording_rules.yml").read_text(encoding="utf-8"))
    RECORDED.update(r["record"] for g in rec["groups"] for r in g["rules"])
    rule_files = sorted(p.name for p in rules_dir.glob("*rules*.yml"))
    for fn in rule_files:  # 업무 규칙 파일의 기록 규칙도 대시보드 · 알림에서 쓸 수 있다
        for g in yaml.safe_load((rules_dir / fn).read_text(encoding="utf-8"))["groups"] or []:
            RECORDED.update(r["record"] for r in g["rules"] if "record" in r)
    n = 0
    for fn in rule_files:
        for g in yaml.safe_load((rules_dir / fn).read_text(encoding="utf-8"))["groups"] or []:
            for r in g["rules"]:
                if not (("record" in r) ^ ("alert" in r)) or "expr" not in r:
                    errors.append(f"{fn}: 규칙 구조 오류 {r}")
                check_promql(r["expr"], f"{fn}:{r.get('record') or r.get('alert')}")
                n += 1
    print(f"Prometheus 규칙 {n}개")
    uids = set()
    for f in sorted((ROOT / "infra/observability/grafana/dashboards").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d["uid"] in uids:
            errors.append(f"{f}: uid 중복")
        uids.add(d["uid"])
        for p in d["panels"]:
            for t in p.get("targets", []):
                check_promql(t["expr"], f"{f.name}:{p['title']}")
    print(f"대시보드 {len(uids)}개")
    for e in errors:
        print("✗", e)
    if not errors:
        print("✓ 인프라 검증 통과")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
