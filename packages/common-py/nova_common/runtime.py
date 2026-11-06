"""실행 환경 — 개발 기능 기본값과 운영 안전장치.

NOVA_ENV=prod 이면 등록된 개발 기능(예: 인증번호 응답 노출 · 데모 계정 시드 · 모의 소셜 로그인)의 기본값이 꺼지고,
기본 JWT 비밀키나 켜진 개발 기능이 하나라도 있으면 서비스가 기동하지 않는다(fail-closed).
값은 호출할 때마다 읽는다(테스트 · 재설정 반영).

서비스는 자기 개발 기능을 등록한다:
    from nova_common.runtime import register_dev_feature, dev_feature
    register_dev_feature("SAMPLE_DEMO_SEED", "데모 데이터 시드")
    if dev_feature("SAMPLE_DEMO_SEED"): ...
"""
from __future__ import annotations

import os

DEFAULT_JWT_SECRET = "nova-dev-secret-change-me"
# 운영에서 반드시 꺼져 있어야 하는 개발 기능 (이름 → 설명). 서비스가 register_dev_feature 로 채운다
DEV_FEATURES: dict[str, str] = {
    "NOVA_DEMO": "데모 계정 · 데모 비밀번호 시드",
}


def register_dev_feature(name: str, description: str) -> str:
    """운영에서 꺼져 있어야 하는 개발 기능을 등록한다. 이름을 돌려준다."""
    DEV_FEATURES[name] = description
    return name


def env() -> str:
    return os.getenv("NOVA_ENV", "dev").lower()


def is_prod() -> bool:
    return env() == "prod"


def dev_feature(name: str) -> bool:
    """개발 기능 켜짐 여부 — 명시값이 우선, 없으면 운영은 꺼짐 · 그 외는 켜짐."""
    v = os.getenv(name)
    if v is not None:
        return v.strip().lower() in ("1", "true", "yes", "on")
    return not is_prod()


def jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or DEFAULT_JWT_SECRET


def super_role() -> str:
    """모든 역할 검사를 통과하는 최상위 역할 이름 (기본 admin)."""
    return os.getenv("NOVA_SUPER_ROLE", "admin")


def tz_offset_hours() -> float:
    """화면 · 업무 '벽시계' 시간대 오프셋 (기본 9 = Asia/Seoul)."""
    return float(os.getenv("NOVA_TZ_OFFSET_HOURS", "9"))


def sqlite_allowed() -> bool:
    """운영에서도 sqlite 를 쓰겠다고 명시했는가(NOVA_ALLOW_SQLITE=1 — 단일 노드 시연 등)."""
    return os.getenv("NOVA_ALLOW_SQLITE", "").strip().lower() in ("1", "true", "yes", "on")


def prod_safety_errors(*, db_url: str | None = None, in_memory_bus: bool = False) -> list[str]:
    """운영(NOVA_ENV=prod)에서 기동을 막아야 할 사유 목록.

    db_url: 업무 표가 있는 서비스의 DB URL(없으면 DB 검사 생략 — 게이트웨이처럼 상태 없는 서비스).
    in_memory_bus: 이벤트를 주고받는 서비스가 메모리 버스(KAFKA_BOOTSTRAP 미설정)인가.
    """
    if not is_prod():
        return []
    errs = []
    secret = os.getenv("JWT_SECRET")
    if not secret or secret == DEFAULT_JWT_SECRET or len(secret) < 32:
        errs.append("JWT_SECRET 이 없거나 기본값 · 32자 미만입니다 (외부 시크릿으로 주입)")
    for name, what in DEV_FEATURES.items():
        if dev_feature(name):
            errs.append(f"{name}=1 — {what} 기능이 운영에서 켜져 있습니다")
    if db_url and db_url.startswith("sqlite") and not sqlite_allowed():
        errs.append("DATABASE_URL 이 없어 sqlite 를 씁니다 — 운영 DB(MariaDB) 주소를 주입하세요 (일부러 쓰면 NOVA_ALLOW_SQLITE=1)")
    if in_memory_bus:
        errs.append("KAFKA_BOOTSTRAP 이 없어 메모리 버스를 씁니다 — 서비스 간 이벤트가 전달되지 않습니다")
    return errs


def assert_prod_safe(service: str, *, db_url: str | None = None, in_memory_bus: bool = False) -> None:
    errs = prod_safety_errors(db_url=db_url, in_memory_bus=in_memory_bus)
    if errs:
        raise RuntimeError(f"[{service}] 운영 안전장치: 기동 거부 — " + " / ".join(errs))
