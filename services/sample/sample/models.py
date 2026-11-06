"""sample 서비스 ORM 모델 — 이 서비스 DB 만 소유한다(다른 서비스 표 조회 금지)."""
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nova_common.db import NovaBase, utcnow
from nova_common.context import tenant_column
from nova_common.ids import id_column, ref_column


class Base(NovaBase):  # 제약 이름 규칙 · 서비스마다 자기 MetaData(ADR-011)
    pass


# 항목 상태 — 이 서비스 안의 단일 원천. 상태 전이(items.py)와 목록 필터 검사(모르는 값은 400)가 함께 읽는다.
# 코드를 바꾸지 않고 늘리는 운영 코드값이 아니라 이 서비스의 상태 기계라서 설정 API 가 아닌 모델에 둔다(backend.md §2)
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
ITEM_STATUSES = (STATUS_ACTIVE, STATUS_ARCHIVED)


class Item(Base):
    """예시 개체 — 이름 · 상태(ITEM_STATUSES) · 감사 컬럼."""

    __tablename__ = "item"
    id: Mapped[str] = id_column(comment="항목 식별자(UUIDv7)")  # ADR-003
    tenant_id: Mapped[str | None] = tenant_column()  # STD-TENANCY-001 ① (M1 공유 스키마)
    name: Mapped[str] = mapped_column(String(100), comment="항목 이름")
    memo: Mapped[str | None] = mapped_column(Text, nullable=True, comment="메모")
    status: Mapped[str] = mapped_column(String(20), default=STATUS_ACTIVE, index=True, comment="상태 active|archived")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, comment="만든 시각(UTC)")
    # 사용자 참조 칸 — 손으로 String(40) 을 쓰지 않고 ref_column(UUIDv7 36자). 조회 조건이 아니라 색인은 두지 않는다(naming column_ref)
    created_by: Mapped[str | None] = ref_column(nullable=True, index=False, comment="만든 사용자")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, comment="고친 시각(UTC)")
    updated_by: Mapped[str | None] = ref_column(nullable=True, index=False, comment="고친 사용자")


class ItemActivity(Base):
    """이벤트 소비 예시 — sample.item.* 를 받아 활동 기록을 남긴다(멱등: 같은 이벤트는 한 번만)."""

    __tablename__ = "item_activity"
    id: Mapped[str] = id_column(comment="활동 식별자(UUIDv7)")  # ADR-003 — 같은 시각 활동의 순서도 이 값이 정한다(시간순 생성)
    tenant_id: Mapped[str | None] = tenant_column()  # STD-TENANCY-001 ① — 소비자가 봉투 tenant(④)를 저장한다
    item_id: Mapped[str] = ref_column(comment="대상 항목(item.id)")
    kind: Mapped[str] = mapped_column(String(40), comment="활동 종류 created|archived|restored")
    event_id: Mapped[str] = ref_column(index=False, comment="원인 이벤트 ID(멱등 추적)")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, comment="기록 시각(UTC)")
