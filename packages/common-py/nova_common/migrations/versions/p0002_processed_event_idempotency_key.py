"""[Expand] 처리 기록에 중복 제거 키 — processed_event.idempotency_key(NULL 허용) + UNIQUE(consumer, idempotency_key).

ADR-012 P1: 소비 중복 판정을 (consumer, idempotency_key) 로 옮기기 위한 칸. 옛 행은 칸이 비어 있고(NULL 은 UNIQUE 에 걸리지 않는다)
event_id 로 대체 판정한다. NOT NULL 로 조이는 Contract 는 다음 판본(보관 기간 14일 뒤 빈 행 0 일 때).
SQLite 는 제약을 ALTER 로 더하지 못해 batch(표 복사)로 한다 — MariaDB 는 그대로 ALTER.
"""
from alembic import op
import sqlalchemy as sa

revision = "p0002"
down_revision = "p0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("processed_event") as b:
        b.add_column(sa.Column("idempotency_key", sa.String(200), nullable=True, comment="중복 제거 키(봉투 idempotency_key)"))
        b.create_unique_constraint(op.f("uq_processed_event_consumer_idempotency_key"), ["consumer", "idempotency_key"])


def downgrade() -> None:
    with op.batch_alter_table("processed_event") as b:
        b.drop_constraint(op.f("uq_processed_event_consumer_idempotency_key"), type_="unique")
        b.drop_column("idempotency_key")
