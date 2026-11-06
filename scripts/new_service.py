#!/usr/bin/env python3
"""새 서비스 만들기 — 템플릿 복사 · 이름 치환 · 서비스 카탈로그 등록 · 토픽 · 권한 · 생성물 갱신.

  python nova.py new-service <이름> --group <gateway|platform|business|capability> --scope <대문자 범위> [--title 한국어이름]
  예) python nova.py new-service order-hub --group business --scope ORDER --title 주문

하는 일:
  1) services/_template → services/<이름>/ (자리표시자 __SERVICE__ · __PKG__ · __TITLE__ · __DOMAIN__ · __ENV__ 치환,
     migrations/ 포함 — env.py · versions/0001_initial.py, 플랫폼 + 서비스 분기 ADR-011)
  2) packages/common-py/nova_common/services.json 에 등록(게이트웨이 앞, 다음 빈 포트, routes ["/<이름>"])
  3) infra/k3s/base/kafka-topics.txt 에 <도메인>.record.created 추가
  4) services/gateway/gateway/rbac.json — user 에 <모듈>.read · <모듈>.create, manager 에 <모듈>.*
  5) 개념 원장(registry/entities.json)에 템플릿 첫 개체 <패키지>_record(표 record) 등재 — 원장이 있으면
  6) 생성물 갱신(gen_k3s · registry sync) — 스크립트가 있으면
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, py, write  # noqa: E402

import naming  # noqa: E402

# 이름 형식은 명명 규약 선언 정본(registry/naming.json)에서 — 정규식을 두 곳에 두지 않는다
NAME = naming.pattern("service")
SCOPE = naming.pattern("scope")
K8S_BY_GROUP = {
    "platform": {"namespace": "core", "tier": "platform", "cpu": "50m", "memory": "128Mi", "memory_limit": "320Mi", "hpa_max": 4, "replicas": 2},
    "business": {"namespace": "core", "tier": "business", "cpu": "50m", "memory": "128Mi", "memory_limit": "320Mi", "hpa_max": 4, "replicas": 1},
    "capability": {"namespace": "capability", "tier": "capability", "cpu": "25m", "memory": "96Mi", "memory_limit": "256Mi", "hpa_max": 3, "replicas": 1},
}


def paths(root: Path) -> dict[str, Path]:
    return {
        "catalog": root / "packages/common-py/nova_common/services.json",
        "template": root / "services/_template",
        "topics": root / "infra/k3s/base/kafka-topics.txt",
        "rbac": root / "services/gateway/gateway/rbac.json",
    }


def create(root: Path, name: str, group: str, scope: str, title: str | None = None, package: str | None = None) -> Path:
    p = paths(root)
    if not NAME.match(name):
        raise SystemExit(f"서비스 이름은 소문자 · 숫자 · 하이픈만(예: order-hub): {name}")
    if not SCOPE.match(scope):
        raise SystemExit(f"범위(scope)는 대문자 · 숫자 2~16자(예: ORDER): {scope}")
    pkg = package or name.replace("-", "_")
    if pkg in sys.stdlib_module_names:
        raise SystemExit(f"패키지 이름 '{pkg}' 이 파이썬 표준 모듈과 겹칩니다 — --package {pkg}_svc 처럼 지정하세요")
    data = json.loads(p["catalog"].read_text(encoding="utf-8"))
    groups = {g["key"] for g in data["groups"]}
    if group not in groups or group == "gateway":
        raise SystemExit(f"그룹은 {sorted(groups - {'gateway'})} 중 하나")
    services = data["services"]
    if any(s["name"] == name for s in services):
        raise SystemExit(f"이미 있는 서비스입니다: {name}")
    if any(s["scope"] == scope for s in services):
        raise SystemExit(f"이미 쓰는 범위(scope)입니다: {scope}")
    dest = root / "services" / name
    if dest.exists():
        raise SystemExit(f"폴더가 이미 있습니다: services/{name}")
    route = f"/{name}"
    if any(route in s.get("routes", []) for s in services):
        raise SystemExit(f"이미 쓰는 경로입니다: {route}")

    # 1) 템플릿 복사 · 치환
    subs = {"__SERVICE__": name, "__PKG__": pkg, "__TITLE__": title or name, "__DOMAIN__": pkg,
            "__ENV__": name.upper().replace("-", "_")}

    def sub(text: str) -> str:
        for k, v in subs.items():
            text = text.replace(k, v)
        return text

    for src in p["template"].rglob("*"):
        if "__pycache__" in src.parts or src.name == "README.md" and src.parent == p["template"]:
            continue
        rel = Path(sub(src.relative_to(p["template"]).as_posix()))
        out = dest / rel
        if src.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            write(out, sub(src.read_text(encoding="utf-8")))

    # 2) 카탈로그 등록 (게이트웨이 앞 = 게이트웨이가 마지막에 기동)
    port = max(s["local_port"] for s in services if not s.get("gateway")) + 1 if len(services) > 1 else 8001
    entry = {"name": name, "title": title or name, "group": group, "desc": f"{title or name}", "scope": scope,
             "local_port": port, "routes": [route],
             "k8s": {**K8S_BY_GROUP[group], "kafka": True, "db": True}}
    if package:
        entry["package"] = package
    gw = next(i for i, s in enumerate(services) if s.get("gateway"))
    services.insert(gw, entry)
    write(p["catalog"], json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    # 3) 토픽
    topic = f"{pkg}.record.created"
    text = p["topics"].read_text(encoding="utf-8")
    if not re.search(rf"^{re.escape(topic)}\s", text, re.M):
        write(p["topics"], text.rstrip("\n") + f"\n{topic} 3 7\n")

    # 4) 권한 표
    if p["rbac"].exists():
        rbac = json.loads(p["rbac"].read_text(encoding="utf-8"))
        roles = rbac["roles"]
        for role, perms in (("user", [f"{name}.read", f"{name}.create"]), ("manager", [f"{name}.*"])):
            if role in roles:
                cur = roles[role]["perms"]
                cur.extend(x for x in perms if x not in cur)
        write(p["rbac"], json.dumps(rbac, ensure_ascii=False, indent=2) + "\n")

    # 5) 개념 원장 — 템플릿 표(record)가 미등재로 lint 를 깨지 않게 등재한다(registry sync 와 같은 자동 단계).
    #    업무 이름으로 바꿀 때는 naming lookup → retire → entity add (안내는 main 의 '다음')
    if (root / naming.ENTITY_LOG).exists() or (root / naming.ENTITIES).exists():
        naming.add_entity(root, f"{pkg}_record", f"{title or name} 기록", name, "record", "core", by="new_service",
                          note="템플릿 첫 개체 — 업무 개체 이름으로 바꾸면 naming retire 후 새 개체를 entity add")
    return dest


def regenerate(root: Path, name: str) -> None:
    for script, args in (("gen_k3s.py", []), ("registry.py", ["sync", "--by", "new_service", "--note", f"서비스 추가: {name}"])):
        path = root / "scripts" / script
        if path.exists():
            subprocess.run([py(), str(path), *args], cwd=root, check=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("--group", required=True)
    ap.add_argument("--scope", required=True)
    ap.add_argument("--title")
    ap.add_argument("--package", help="표준 모듈과 겹칠 때만 (예: platform_svc)")
    ap.add_argument("--no-gen", action="store_true", help="생성물 갱신 생략")
    a = ap.parse_args(argv)
    dest = create(ROOT, a.name, a.group, a.scope, a.title, a.package)
    if not a.no_gen:
        regenerate(ROOT, a.name)
    print(f"✓ services/{a.name} 생성 · 카탈로그 · 토픽 · 권한 등록")
    print("다음:")
    pkg = a.package or a.name.replace("-", "_")
    print("  1) 업무 개체 이름을 정하기 전에 조회: python nova.py naming lookup <개념>   (정확 · 별칭이면 새로 만들지 않는다)")
    print(f"  2) 모델 · 기능 모듈을 업무에 맞게 고친다 ({dest.relative_to(ROOT).as_posix()}) — 표 이름을 바꾸면 개념 원장도:")
    print(f"     python nova.py naming retire {pkg}_record --why <사유> && python nova.py naming entity add <키> --title <한국어> --service {a.name} --table <표> --layer core")
    print(f"  3) python nova.py gen && python nova.py test   (services/{a.name}/tests 포함) && python nova.py lint")
    print("  4) 요구 · 계획 문서에 서비스 추가를 기록하고 커밋")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
