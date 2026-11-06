"""플랫폼 baseline — outbox · processed_event 를 add_infra_tables 지금 모양 그대로 만든다.

create_all 로 만든 옛 DB 는 이 리비전으로 stamp 된다(nova_common.migrate). 이 파일은 고치지 않는다 — 바꾸려면 p0002 … 를 더한다.
"""
from alembic import op
import sqlalchemy as sa

revision = "p0001"
down_revision = None
branch_labels = ("platform",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="일련번호"),
        sa.Column("event_id", sa.String(40), nullable=False, comment="이벤트 ID(UUIDv7)"),
        sa.Column("topic", sa.String(120), nullable=False, comment="토픽"),
        sa.Column("key", sa.String(80), nullable=False, comment="파티션 키(집계 ID)"),
        sa.Column("payload", sa.JSON(), nullable=False, comment="봉투 전체(JSON)"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="적재 시각(UTC)"),
        sa.Column("sent_at", sa.DateTime(), nullable=True, comment="발행 시각 — 비면 미발행"),
        sa.Column("attempts", sa.Integer(), nullable=False, comment="발행 시도 횟수"),
        sa.Column("last_error", sa.Text(), nullable=True, comment="마지막 발행 오류"),
        sa.Column("parked", sa.Boolean(), nullable=False, comment="독 메시지 격리(재처리 대기)"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
        sa.UniqueConstraint("event_id", name=op.f("uq_outbox_event_id")),
    )
    op.create_index(op.f("ix_outbox_topic"), "outbox", ["topic"])
    op.create_index(op.f("ix_outbox_sent_at"), "outbox", ["sent_at"])
    op.create_index(op.f("ix_outbox_parked"), "outbox", ["parked"])
    op.create_table(
        "processed_event",
        sa.Column("event_id", sa.String(40), nullable=False, comment="처리한 이벤트 ID"),
        sa.Column("consumer", sa.String(80), nullable=False, comment="소비 서비스"),
        sa.Column("topic", sa.String(120), nullable=False, comment="토픽"),
        sa.Column("ok", sa.Boolean(), nullable=False, comment="처리 성공"),
        sa.Column("at", sa.DateTime(), nullable=False, comment="처리 시각(UTC)"),
        sa.PrimaryKeyConstraint("event_id", "consumer", name=op.f("pk_processed_event")),
    )


def downgrade() -> None:
    op.drop_table("processed_event")
    op.drop_index(op.f("ix_outbox_parked"), table_name="outbox")
    op.drop_index(op.f("ix_outbox_sent_at"), table_name="outbox")
    op.drop_index(op.f("ix_outbox_topic"), table_name="outbox")
    op.drop_table("outbox")
