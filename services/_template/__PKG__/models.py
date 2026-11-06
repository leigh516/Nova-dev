"""__SERVICE__ 서비스 ORM 모델 — 이 서비스 DB 만 소유한다(다른 서비스 표 조회 금지)."""
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from nova_common.context import tenant_column
from nova_common.db import NovaBase, utcnow
from nova_common.ids import id_column, ref_column


class Base(NovaBase):  # 제약 이름 규칙 · 서비스마다 자기 MetaData(ADR-011)
    pass


class Record(Base):
    """첫 개체 — 이름을 업무에 맞게 바꾸고 컬럼을 채운다(바꾸면 registry sync)."""

    __tablename__ = "record"  # 단수 snake 개체 이름(서비스 DB 가 따로라 도메인 접두 없음 — docs/conventions/naming.md §3.1)
    id: Mapped[str] = id_column(comment="식별자(UUIDv7)")  # ADR-003 — 칸마다 comment 가 DB 사전의 '의미'
    tenant_id: Mapped[str | None] = tenant_column()  # STD-TENANCY-001 ① — 테넌트 칸은 헬퍼로(손으로 선언하지 않는다)
    name: Mapped[str] = mapped_column(String(100), comment="이름")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, comment="만든 시각(UTC)")
    # 다른 개체(사용자)를 가리키는 칸은 ref_column — 손으로 String(n) 을 쓰지 않는다(naming column_ref: _id · _by → VARCHAR(36))
    created_by: Mapped[str | None] = ref_column(nullable=True, index=False, comment="만든 사용자")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, comment="고친 시각(UTC)")
    updated_by: Mapped[str | None] = ref_column(nullable=True, index=False, comment="고친 사용자")
