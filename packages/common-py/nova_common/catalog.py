"""서비스 카탈로그 — `services.json`(서비스 목록 단일 원천) 읽기.

    from nova_common import catalog
    catalog.names()            # 기동 순서(게이트웨이 마지막)
    catalog.backends()         # 게이트웨이 제외
    catalog.db_services()      # 자기 DB 가 있는 서비스
    catalog.route_for("/sample/items")  # 게이트웨이 라우팅 → "sample"
    python -m nova_common.catalog names|backends|db|ports|routes   # 셸용(공백 구분)
    python -m nova_common.catalog package <서비스>          # 파이썬 패키지 이름(services.json "package" 반영)
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("services.json")


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    group: str
    desc: str
    scope: str
    local_port: int
    k8s: dict = field(default_factory=dict)
    gateway: bool = False
    package_name: str | None = None  # services.json "package" — 표준 모듈과 겹칠 때만(예: platform → platform_svc)
    routes: tuple[str, ...] = ()  # 게이트웨이가 이 서비스로 넘기는 /v1 아래 경로 접두어(예: "/sample")
    perm: str | None = None  # 권한 모듈 이름(권한키 <perm>.<행위> 2단 — docs/conventions/naming.md §3.3). 없으면 서비스 이름
    title: str | None = None  # 사람이 읽는 이름

    @property
    def package(self) -> str:
        """파이썬 패키지 이름(services/<name>/<package>)."""
        return self.package_name or self.name.replace("-", "_")

    @property
    def db_name(self) -> str:
        """DB 스키마·계정 이름 — 패키지 이름과 별개로 항상 서비스 이름 기준."""
        return self.name.replace("-", "_")

    @property
    def env(self) -> str:
        """환경 변수 접미사(SVC_<env>_URL · DATABASE_URL_<env>)."""
        return self.name.upper().replace("-", "_")

    @property
    def db(self) -> bool:
        return bool(self.k8s.get("db"))

    @property
    def namespace(self) -> str:
        return self.k8s.get("namespace", "default")

    @property
    def allow_from(self) -> tuple[str, ...]:
        """이 서비스를 직접 불러도 되는 다른 서비스(k8s.allow_from) — 운영 NetworkPolicy 허용 목록. 비면 게이트웨이만."""
        return tuple(self.k8s.get("allow_from") or ())


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def services() -> tuple[ServiceSpec, ...]:
    data = _raw()
    groups = {g["key"] for g in data["groups"]}
    out = []
    for s in data["services"]:
        s = dict(s)
        if "package" in s:
            s["package_name"] = s.pop("package")
        if "routes" in s:
            s["routes"] = tuple(s["routes"])
        spec = ServiceSpec(**s)
        if spec.group not in groups:
            raise ValueError(f"services.json: {spec.name} 의 group '{spec.group}' 이 groups 에 없음")
        out.append(spec)
    names = [s.name for s in out]
    if len(set(names)) != len(names):
        raise ValueError("services.json: 서비스 이름 중복")
    if sum(s.gateway for s in out) != 1:
        raise ValueError("services.json: gateway 는 정확히 하나")
    return tuple(out)


def groups() -> list[dict]:
    return list(_raw()["groups"])


def get(name: str) -> ServiceSpec:
    for s in services():
        if s.name == name:
            return s
    raise KeyError(name)


def names() -> list[str]:
    return [s.name for s in services()]


def backends() -> list[str]:
    return [s.name for s in services() if not s.gateway]


def gateway() -> str:
    return next(s.name for s in services() if s.gateway)


def db_services() -> list[str]:
    return [s.name for s in services() if s.db]


def routes() -> list[tuple[str, str]]:
    """(경로 접두어, 서비스) — 긴 접두어 먼저(게이트웨이 라우팅 순서)."""
    out = [(p.rstrip("/") or "/", s.name) for s in services() for p in s.routes]
    prefixes = [p for p, _ in out]
    if len(set(prefixes)) != len(prefixes):
        raise ValueError("services.json: routes 접두어 중복")
    return sorted(out, key=lambda x: -len(x[0]))


def route_for(path: str) -> str | None:
    """/v1 를 뗀 경로 → 담당 서비스 이름(없으면 None)."""
    for prefix, svc in routes():
        if path == prefix or path.startswith(prefix + "/"):
            return svc
    return None


def public() -> list[dict]:
    """운영 콘솔용 요약(GW /v1/ops/monitoring/overview 의 catalog)."""
    return [{"name": s.name, "group": s.group, "desc": s.desc, "namespace": s.namespace, "kafka": bool(s.k8s.get("kafka")), "db": s.db, "gateway": s.gateway} for s in services()]


def _main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "names"
    if cmd == "names":
        print(" ".join(names()))
    elif cmd == "backends":
        print(" ".join(backends()))
    elif cmd == "db":
        print(" ".join(db_services()))
    elif cmd == "ports":  # name=port
        print(" ".join(f"{s.name}={s.local_port}" for s in services()))
    elif cmd == "routes":
        print(" ".join(f"{p}={n}" for p, n in routes()))
    elif cmd == "package":  # 서비스 이름 → 파이썬 패키지(셸·Dockerfile)
        print(get(argv[1]).package)
    else:
        print(f"알 수 없는 명령: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
