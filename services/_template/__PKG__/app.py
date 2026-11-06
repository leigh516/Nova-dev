"""__SERVICE__ 골격 — 모듈형 레이아웃: models → app → 기능 모듈 → main (순환 import 방지)."""
from nova_common import create_service

from .models import Base

svc = create_service("__SERVICE__", Base, "__TITLE__ 서비스")
app = svc.app
