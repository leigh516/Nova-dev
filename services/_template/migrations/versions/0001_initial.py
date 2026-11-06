"""__SERVICE__ 첫 표 — record(models.Record 그대로). 플랫폼 표(outbox · processed_event)는 플랫폼 분기(p0001)가 만든다.

모델을 업무에 맞게 바꾸면 이 파일을 함께 고친다(아직 배포 전일 때만) — 배포 뒤에는 `python nova.py migrate __SERVICE__ new "<설명>"` 으로 다음 리비전을 더한다.
"""
from alembic import op
import sqlalchemy as sa

revision = "s0001"
down_revision = None
branch_labels = ("service",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "record",
        sa.Column("id", sa.String(36), nullable=False, comment="식별자(UUIDv7)"),
        sa.Column("tenant_id", sa.String(40), nullable=True, comment="테넌트(STD-TENANCY-001)"),
        sa.Column("name", sa.String(100), nullable=False, comment="이름"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="만든 시각(UTC)"),
        sa.Column("created_by", sa.String(36), nullable=True, comment="만든 사용자"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="고친 시각(UTC)"),
        sa.Column("updated_by", sa.String(36), nullable=True, comment="고친 사용자"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record")),
    )
    op.create_index(op.f("ix_record_tenant_id"), "record", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_record_tenant_id"), table_name="record")
    op.drop_table("record")
