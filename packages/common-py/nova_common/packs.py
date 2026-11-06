"""도메인 팩 — 코어는 소켓(포트)을 내고, 업종 팩이 구현을 끼운다(STD-DOMAIN-PACK-001).

코어(서비스)에서 가변점 선언 · 사용:
    from nova_common import packs
    @packs.port("sample.normalize_name")          # 기본 구현 = 코어 규칙
    def normalize_name(name: str) -> str:
        return name.strip()
    packs.get("sample.normalize_name")(body.name)  # 켜진 팩이 있으면 팩 구현, 없으면 기본

팩(packs/<팩>/policies/<서비스 패키지>.py)에서 구현:
    from nova_common.packs import implement
    @implement("sample.normalize_name")
    def normalize(name: str) -> str: ...

켜는 법: 환경 변수 NOVA_PACKS=<팩>,<팩> (nova.project.json "packs" → gen_k3s 가 ConfigMap 에, dev_server 가 환경에)
규칙: 코어는 팩을 import 하지 않는다 · 팩끼리 import 하지 않는다(scripts/packs.py check 가 lint 에서 검사).
"""
from __future__ import annotations

import importlib
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("nova.packs")

_defaults: dict[str, Callable[..., Any]] = {}
_impls: dict[str, tuple[str, Callable[..., Any]]] = {}
_impl_service: dict[str, str] = {}  # 포트 → 그 구현을 불러온 서비스 패키지(verify 가 자기 서비스 것만 본다)
_loaded: set[tuple[str, str]] = set()
_current_pack: str | None = None
_current_service: str | None = None


class PackError(Exception):
    pass


def port(name: str):
    """코어가 가변점(포트)과 기본 구현을 선언한다."""
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        _defaults[name] = fn
        return fn
    return deco


def implement(name: str):
    """팩이 포트를 구현한다 — 같은 포트를 두 팩이 구현하면 실패(어느 쪽인지 모호)."""
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        pack = _current_pack or "?"
        if name in _impls and _impls[name][0] != pack:
            raise PackError(f"포트 {name} 을(를) 팩 {_impls[name][0]} 과 {pack} 이 모두 구현합니다 — 하나만 켜세요")
        _impls[name] = (pack, fn)
        if _current_service:
            _impl_service[name] = _current_service
        return fn
    return deco


def get(name: str) -> Callable[..., Any]:
    if name in _impls:
        return _impls[name][1]
    if name in _defaults:
        return _defaults[name]
    raise PackError(f"선언되지 않은 포트: {name}")


def enabled() -> list[str]:
    return [p.strip() for p in os.getenv("NOVA_PACKS", "").split(",") if p.strip()]


def packs_root() -> Path:
    """packs/ 폴더가 있는 곳 — NOVA_PACKS_ROOT, 없으면 현재 폴더에서 위로 찾는다(서비스 폴더에서 실행해도 저장소 루트)."""
    env = os.getenv("NOVA_PACKS_ROOT")
    if env:
        return Path(env)
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / "packs").is_dir():
            return d
    return here


def load(service_package: str) -> list[str]:
    """켜진 팩의 policies/<서비스 패키지>.py 를 불러온다(서비스 기동 시). 불러온 팩 이름을 돌려준다.
    켜진 팩이 없으면 실패한다(조용히 건너뛰면 업종 규칙이 빠진 채 운영된다)."""
    global _current_pack, _current_service
    done = []
    root = packs_root()
    for pack in enabled():
        key = (pack, service_package)
        if key in _loaded:
            continue
        if not (root / "packs" / pack / "pack.json").exists():
            raise PackError(f"켜진 도메인 팩 '{pack}' 을(를) 찾을 수 없습니다: {root / 'packs' / pack} (NOVA_PACKS · NOVA_PACKS_ROOT 확인)")
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        if (root / "packs" / pack / "policies" / f"{service_package}.py").exists():
            _current_pack, _current_service = pack, service_package
            try:
                importlib.import_module(f"packs.{pack}.policies.{service_package}")
                done.append(pack)
            finally:
                _current_pack, _current_service = None, None
        _loaded.add(key)
    if done:
        log.info("도메인 팩 적용 %s → %s", service_package, done)
    return done


def verify(service_package: str) -> None:
    """이 서비스용으로 불러온 팩이 선언되지 않은 포트를 구현했으면 실패(포트 이름 오타가 조용히 무시되는 것 방지).

    포트 선언(@port)은 코어 모듈을 import 할 때 채워지므로 load() 안에서 바로 검사하면 선언 모듈보다 먼저
    불릴 때 오탐이 난다. 서비스는 모든 라우터 모듈을 import 한 뒤 기동(Service.startup → load_packs)하므로
    그 자리에서 load() 다음에 부른다. 다른 서비스 패키지용 구현은 보지 않는다(한 프로세스 여러 서비스 — 개발 서버)."""
    unknown = sorted(n for n, svc in _impl_service.items() if svc == service_package and n not in _defaults)
    if unknown:
        where = ", ".join(f"{n}(팩 {_impls[n][0]})" for n in unknown)
        raise PackError(
            f"선언되지 않은 포트를 구현한 팩이 있습니다: {where} — 포트 이름 오타인지 확인하세요 "
            f"(선언된 포트: {', '.join(sorted(_defaults)) or '없음'})"
        )


def active() -> dict[str, str]:
    """포트 → 구현 출처(팩 이름 또는 'core') — 운영 확인 · 테스트용."""
    return {n: (_impls[n][0] if n in _impls else "core") for n in sorted({*_defaults, *_impls})}


def reset() -> None:
    """테스트용 — 팩 구현과 로드 기록을 비운다(코어 기본 구현은 남긴다)."""
    _impls.clear()
    _impl_service.clear()
    _loaded.clear()
