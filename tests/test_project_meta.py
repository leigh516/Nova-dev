"""프로젝트 메타 단일 원천(REQ-261104-11-5 · R10) — nova.project.json 의 super_role · timezone · locale · 웹 포트가
생성물 · 개발 스택 · 코드 기본값에서 같은 값으로 읽힌다. 복제(코드 기본값 · package.json)는 고칠 파일을 알려 준다."""
from __future__ import annotations

import copy
import json
import os
import re

import devstack
import gen_k3s
import yaml
from novalib import ROOT, project

from nova_common import runtime

SDK_GEN = ROOT / "web" / "packages" / "sdk" / "src" / "project.gen.ts"
RUNTIME = "packages/common-py/nova_common/runtime.py"
GEN_HINT = "python nova.py gen"


def _ts_const(text: str, name: str) -> str | None:
    m = re.search(rf'export const {name} = "([^"]*)";', text)
    return m.group(1) if m else None


def meta_mismatches(meta: dict) -> list[str]:
    """메타와 복제 값이 다른 곳 — 한 줄마다 '무엇: 기대 ≠ 실제 → 고칠 곳'. 빈 목록이면 모두 같다."""
    errs: list[str] = []

    def diff(what: str, want, got, fix: str) -> None:
        if want != got:
            errs.append(f"{what}: nova.project.json {want!r} ≠ {got!r} → {fix}")

    # ① 코드 기본값(환경 변수가 없을 때) — 손으로 적힌 복제라 원천 파일을 고친다
    saved = {k: os.environ.pop(k) for k in ("NOVA_SUPER_ROLE", "NOVA_TZ_OFFSET_HOURS") if k in os.environ}
    try:
        diff("runtime.super_role() 기본값", meta["super_role"], runtime.super_role(), RUNTIME)
        diff("runtime.tz_offset_hours() 기본값", float(meta["tz_offset_hours"]), runtime.tz_offset_hours(), RUNTIME)
    finally:
        os.environ.update(saved)

    # ② sdk 기본값 생성물
    ts = SDK_GEN.read_text(encoding="utf-8") if SDK_GEN.exists() else ""
    diff("project.gen.ts LOCALE", meta["locale"], _ts_const(ts, "LOCALE"), GEN_HINT)
    diff("project.gen.ts TIMEZONE", meta["timezone"], _ts_const(ts, "TIMEZONE"), GEN_HINT)

    # ③ 웹 앱 포트 — package.json(손 관리) · 생성 매니페스트
    base = ROOT / "infra" / "k3s" / "base"
    ingress = (base / "ingress.yaml").read_text(encoding="utf-8")
    for w in meta.get("web_apps", []):
        port, name = w["port"], w["name"]
        pkg_path = f"web/apps/{name}/package.json"
        scripts = json.loads((ROOT / pkg_path).read_text(encoding="utf-8"))["scripts"]
        dev = re.search(r"-p (\d+)", scripts.get("dev", ""))
        diff(f"{pkg_path} scripts.dev 포트", port, int(dev.group(1)) if dev else None, pkg_path)
        start = re.search(r"\$\{PORT:-(\d+)\}", scripts.get("start", ""))
        diff(f"{pkg_path} scripts.start 기본 포트", port, int(start.group(1)) if start else None, pkg_path)
        docs = [d for d in yaml.safe_load_all((base / f"web-{name}.yaml").read_text(encoding="utf-8")) if d]
        dep = next(d for d in docs if d["kind"] == "Deployment")
        svc = next(d for d in docs if d["kind"] == "Service")
        diff(f"web-{name}.yaml containerPort", port, dep["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"], GEN_HINT)
        diff(f"web-{name}.yaml Service port", port, svc["spec"]["ports"][0]["port"], GEN_HINT)
        backend = re.search(rf"name: web-{re.escape(name)}, port: \{{number: (\d+)\}}", ingress)
        diff(f"ingress.yaml web-{name} 포트", port, int(backend.group(1)) if backend else None, GEN_HINT)

    # ④ 생성 매니페스트의 환경 변수
    for d in yaml.safe_load_all((base / "configmap-common.yaml").read_text(encoding="utf-8")):
        if d:
            ns = d["metadata"]["namespace"]
            diff(f"configmap-common({ns}) NOVA_SUPER_ROLE", meta["super_role"], d["data"].get("NOVA_SUPER_ROLE"), GEN_HINT)
            diff(f"configmap-common({ns}) NOVA_TZ_OFFSET_HOURS", str(meta["tz_offset_hours"]), d["data"].get("NOVA_TZ_OFFSET_HOURS"), GEN_HINT)
    env = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["x-svc"]["environment"]
    diff("docker-compose.yml NOVA_SUPER_ROLE", meta["super_role"], env.get("NOVA_SUPER_ROLE"), GEN_HINT)
    diff("docker-compose.yml NOVA_TZ_OFFSET_HOURS", str(meta["tz_offset_hours"]), env.get("NOVA_TZ_OFFSET_HOURS"), GEN_HINT)
    return errs


def _fake_gen(monkeypatch, **changes) -> dict:
    meta = copy.deepcopy(project())
    meta.update(changes)
    monkeypatch.setattr(gen_k3s, "project", lambda: meta)
    return {p.relative_to(ROOT).as_posix(): t for p, t in gen_k3s.generate().items()}


# ------------------------------------------------------------------ T03-7.01 configmap · compose
def test_generated_env_carries_meta(monkeypatch):
    out = _fake_gen(monkeypatch, super_role="root", tz_offset_hours=-5)
    for d in yaml.safe_load_all(out["infra/k3s/base/configmap-common.yaml"]):
        if d:
            assert d["data"]["NOVA_SUPER_ROLE"] == "root" and d["data"]["NOVA_TZ_OFFSET_HOURS"] == "-5"
    env = yaml.safe_load(out["docker-compose.yml"])["x-svc"]["environment"]
    assert env["NOVA_SUPER_ROLE"] == "root" and env["NOVA_TZ_OFFSET_HOURS"] == "-5"


# ------------------------------------------------------------------ T03-7.02 devstack
def test_devstack_sets_meta_env(monkeypatch):
    for k in ("NOVA_SUPER_ROLE", "NOVA_TZ_OFFSET_HOURS", "NOVA_PACKS", "NOVA_PACKS_ROOT"):
        monkeypatch.setenv(k, "x")  # 끝나면 원래 상태로 되돌리게 먼저 기록한 뒤 지운다
        monkeypatch.delenv(k)
    devstack._meta_env()
    p = project()
    assert os.environ["NOVA_SUPER_ROLE"] == p["super_role"]
    assert float(os.environ["NOVA_TZ_OFFSET_HOURS"]) == float(p["tz_offset_hours"])
    assert os.environ["NOVA_PACKS"] == ",".join(p.get("packs", []))
    # 이미 설정된 값은 그대로(NOVA_PACKS 와 같은 setdefault)
    monkeypatch.setenv("NOVA_SUPER_ROLE", "root")
    devstack._meta_env()
    assert os.environ["NOVA_SUPER_ROLE"] == "root"


# ------------------------------------------------------------------ T03-7.03 sdk project.gen.ts
def test_sdk_project_gen_from_meta(monkeypatch):
    out = _fake_gen(monkeypatch, locale="en-US", timezone="America/New_York")
    ts = out["web/packages/sdk/src/project.gen.ts"]
    assert ts.startswith("/* 생성 파일 — scripts/gen_k3s.py")
    assert _ts_const(ts, "LOCALE") == "en-US" and _ts_const(ts, "TIMEZONE") == "America/New_York"


def test_sdk_reads_env_literally_then_generated_default():
    """Next 는 process.env.NEXT_PUBLIC_… 를 글자 그대로 쓴 곳만 빌드에 넣는다(T04-9.09) — 동적 참조로 되돌리지 않는다."""
    src = (ROOT / "web" / "packages" / "sdk" / "src" / "index.ts").read_text(encoding="utf-8")
    assert re.search(r"process\.env\.NEXT_PUBLIC_LOCALE \|\| META_LOCALE", src)
    assert re.search(r"process\.env\.NEXT_PUBLIC_TIMEZONE \|\| META_TIMEZONE", src)
    assert 'from "./project.gen"' in src
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("//", "*", "/*")))  # 주석의 설명은 뺀다
    assert "process.env[" not in code
    assert '"ko-KR"' not in src and '"Asia/Seoul"' not in src  # 값 복제가 남지 않는다


# ------------------------------------------------------------------ T03-7.04 웹 포트
def test_web_port_from_meta(monkeypatch):
    webs = [dict(w, port=3100) for w in project()["web_apps"]]
    out = _fake_gen(monkeypatch, web_apps=webs)
    w = webs[0]["name"]
    docs = [d for d in yaml.safe_load_all(out[f"infra/k3s/base/web-{w}.yaml"]) if d]
    dep = next(d for d in docs if d["kind"] == "Deployment")
    svc = next(d for d in docs if d["kind"] == "Service")
    assert dep["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"] == 3100
    assert svc["spec"]["ports"][0]["port"] == 3100
    assert f"name: web-{w}, port: {{number: 3100}}" in out["infra/k3s/base/ingress.yaml"]
    pol = next(d for d in yaml.safe_load_all(out["infra/k3s/base/networkpolicy.yaml"])
               if d and d["metadata"]["name"] == "allow-ingress-controller")
    assert pol["spec"]["ingress"][0]["ports"] == [{"port": 3100}]
    # grafana 3000 은 웹 포트가 아니다 — 그대로
    assert "name: grafana, port: {number: 3000}" in out["infra/k3s/base/ingress.yaml"]
    assert '"3300:3000"' in out["docker-compose.yml"]


def test_netpol_lists_every_web_port(monkeypatch):
    base = project()["web_apps"][0]
    out = _fake_gen(monkeypatch, web_apps=[dict(base, name="app", port=3000), dict(base, name="admin", port=3200),
                                           dict(base, name="ops", port=3000)])
    pol = next(d for d in yaml.safe_load_all(out["infra/k3s/base/networkpolicy.yaml"])
               if d and d["metadata"]["name"] == "allow-ingress-controller")
    assert pol["spec"]["ingress"][0]["ports"] == [{"port": 3000}, {"port": 3200}]


# ------------------------------------------------------------------ T03-7.05 복제 검사
def test_replicas_match_project_meta():
    errs = meta_mismatches(project())
    assert not errs, "nova.project.json 과 다른 복제:\n  " + "\n  ".join(errs)


def test_replica_check_names_file_to_fix():
    meta = copy.deepcopy(project())
    meta.update(super_role="root", tz_offset_hours=-5, locale="en-US", timezone="America/New_York",
                web_apps=[dict(w, port=3100) for w in meta["web_apps"]])
    errs = "\n".join(meta_mismatches(meta))
    assert f"runtime.super_role() 기본값: nova.project.json 'root' ≠ 'admin' → {RUNTIME}" in errs
    assert f"runtime.tz_offset_hours() 기본값: nova.project.json -5.0 ≠ 9.0 → {RUNTIME}" in errs
    assert f"project.gen.ts LOCALE: nova.project.json 'en-US' ≠ 'ko-KR' → {GEN_HINT}" in errs
    app = meta["web_apps"][0]["name"]
    assert f"web/apps/{app}/package.json scripts.dev 포트: nova.project.json 3100 ≠ 3000 → web/apps/{app}/package.json" in errs
    assert f"web-{app}.yaml containerPort: nova.project.json 3100 ≠ 3000 → {GEN_HINT}" in errs
    assert "docker-compose.yml NOVA_SUPER_ROLE: nova.project.json 'root' ≠ 'admin'" in errs


def test_missing_meta_key_fails_with_hint(monkeypatch):
    """옛 복제본 메타에 키가 없으면 KeyError 가 아니라 무엇을 적을지 알려 주고 멈춘다(기본값을 두면 또 하나의 복제)."""
    import pytest

    meta = {k: v for k, v in project().items() if k != "locale"}
    monkeypatch.setattr(gen_k3s, "project", lambda: meta)
    with pytest.raises(SystemExit, match="locale"):
        gen_k3s.generate()
