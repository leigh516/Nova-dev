"""단일 프로세스 개발 스택 — Kafka·네트워크 없이 모든 서비스(nova_common/services.json)를 한 프로세스에서 연결한다.

- 이벤트: 모든 서비스가 하나의 InMemoryBroker 를 공유(컨슈머 그룹 = 서비스 이름 의미 유지)
- 동기 계약 API: nova_common.clients.override 로 ASGI 트랜스포트 연결
- 사용: 통합 테스트(tests/integration) · `python nova.py run`(Kafka 없을 때) · 웹/앱 로컬 개발
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from nova_common import catalog

ROOT = Path(__file__).resolve().parents[1]
NAMES = catalog.names()  # 서비스 목록 단일 원천


def _paths() -> None:
    for n in NAMES:
        p = str(ROOT / "services" / n)
        if p not in sys.path:
            sys.path.insert(0, p)


def load_env_file(path: Path = ROOT / ".env") -> int:
    """저장소 루트 .env(git 제외)의 KEY=VALUE 를 환경 변수 기본값으로 — 이미 설정된 값은 덮어쓰지 않는다. 반환: 읽은 개수."""
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
            n += 1
    return n


def _meta_env() -> None:
    """nova.project.json → 런타임 환경(이미 설정돼 있으면 그대로) — packs → NOVA_PACKS, super_role → NOVA_SUPER_ROLE,
    tz_offset_hours → NOVA_TZ_OFFSET_HOURS. 개발 스택도 생성 매니페스트(configmap · compose)와 같은 원천을 읽는다(R10)."""
    import json as _json

    meta = ROOT / "nova.project.json"
    if meta.exists():
        p = _json.loads(meta.read_text(encoding="utf-8"))
        os.environ.setdefault("NOVA_PACKS", ",".join(p.get("packs", [])))
        # 키가 없는 메타(옛 복제본)면 runtime.py 기본값에 맡긴다 — 빈 값을 심으면 기본값이 가려진다
        for key, env in (("super_role", "NOVA_SUPER_ROLE"), ("tz_offset_hours", "NOVA_TZ_OFFSET_HOURS")):
            if key in p:
                os.environ.setdefault(env, str(p[key]))
    os.environ.setdefault("NOVA_PACKS_ROOT", str(ROOT))


def build(memory_db: bool = True):
    """서비스들을 import 해서 공유 브로커·ASGI 연결을 구성. 반환: (services dict, broker, gw_app)."""
    os.environ.pop("KAFKA_BOOTSTRAP", None)
    _meta_env()
    if not memory_db:
        load_env_file()  # .env — scripts/local_db_setup.py 가 쓴 로컬 MariaDB 접속 정보 등
    if memory_db:
        for n in NAMES:  # 게이트웨이도 processed_event 용 로컬 DB 를 쓴다
            os.environ.setdefault("DATABASE_URL_" + catalog.get(n).env, "sqlite://")
    _paths()
    import httpx

    from nova_common import clients
    from nova_common.events import InMemoryBroker, InMemoryBus

    mods = {n: importlib.import_module(f"{catalog.get(n).package}.main") for n in NAMES}
    broker = InMemoryBroker()
    services = {}
    for name, m in mods.items():
        svc = m.svc
        svc.bus = InMemoryBus(name, broker)
        services[name] = svc
        clients.override(name, httpx.ASGITransport(app=m.app))
    return services, broker, mods[catalog.gateway()].app


async def pump(services: dict, broker, rounds: int = 40) -> int:
    """아웃박스 → 브로커 → 소비 를 더 이상 이벤트가 없을 때까지 반복(결정적 사가 실행). 반환: 전달한 이벤트 수."""
    total = 0
    for _ in range(rounds):
        sent = 0
        for svc in services.values():
            sent += await svc.flush_outbox()
        await broker.drain()
        total += sent
        if sent == 0 and not broker.pending:
            return total
    raise RuntimeError("이벤트 흐름이 끝나지 않았다 — 발행 · 소비가 정해진 횟수 안에 멈추지 않음")
