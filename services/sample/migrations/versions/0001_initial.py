"""sample baseline — item · item_activity 를 models.py 지금 모양 그대로 만든다(create_all 시절 DB 는 이 리비전으로 stamp).

플랫폼 표(outbox · processed_event)는 플랫폼 분기(p0001)가 만든다. 이 파일은 고치지 않는다 — 바꾸려면 `python nova.py migrate sample new "<설명>"`.
"""
from alembic import op
import sqlalchemy as sa

revision = "s0001"
down_revision = None
branch_labels = ("service",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item",
        sa.Column("id", sa.String(36), nullable=False, comment="항목 식별자(UUIDv7)"),
        sa.Column("tenant_id", sa.String(40), nullable=True, comment="테넌트(STD-TENANCY-001)"),
        sa.Column("name", sa.String(100), nullable=False, comment="항목 이름"),
        sa.Column("memo", sa.Text(), nullable=True, comment="메모"),
        sa.Column("status", sa.String(20), nullable=False, comment="상태 active|archived"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="만든 시각(UTC)"),
        sa.Column("created_by", sa.String(40), nullable=True, comment="만든 사용자"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="고친 시각(UTC)"),
        sa.Column("updated_by", sa.String(40), nullable=True, comment="고친 사용자"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item")),
    )
    op.create_index(op.f("ix_item_tenant_id"), "item", ["tenant_id"])
    op.create_index(op.f("ix_item_status"), "item", ["status"])
    op.create_table(
        "item_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="일련번호"),
        sa.Column("item_id", sa.String(36), nullable=False, comment="대상 항목(item.id)"),
        sa.Column("kind", sa.String(40), nullable=False, comment="활동 종류 created|archived"),
        sa.Column("event_id", sa.String(36), nullable=False, comment="원인 이벤트 ID(멱등 추적)"),
        sa.Column("at", sa.DateTime(), nullable=False, comment="기록 시각(UTC)"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_activity")),
    )
    op.create_index(op.f("ix_item_activity_item_id"), "item_activity", ["item_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_item_activity_item_id"), table_name="item_activity")
    op.drop_table("item_activity")
    op.drop_index(op.f("ix_item_status"), table_name="item")
    op.drop_index(op.f("ix_item_tenant_id"), table_name="item")
    op.drop_table("item")
