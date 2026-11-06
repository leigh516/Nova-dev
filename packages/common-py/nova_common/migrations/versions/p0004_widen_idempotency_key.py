"""처리 기록 중복 제거 키 칸 넓히기 — processed_event.idempotency_key VARCHAR(200) → VARCHAR(320).

기본 키 `{source}:{topic}:{key}:{event_id}` 의 최대 길이는 소비자 80 + 토픽 120 + 키 80 + UUID 36 + 구분자 3 = 319 다.
200 이면 MariaDB 엄격 모드에서 'Data too long' 으로 그 이벤트가 DLQ 로 간다(T03-9.04 · 사용자 결정 2026-11-04 (A)).
UNIQUE(consumer, idempotency_key) 는 utf8mb4 기준 (80 + 320) × 4 = 1,600 바이트로 InnoDB 인덱스 상한 3,072 안이다.
SQLite 는 칸 형식을 ALTER 하지 못해 batch(표 복사)로 한다 — MariaDB 는 그대로 ALTER(MODIFY).
되돌리기(downgrade)는 200 보다 긴 값이 있으면 MariaDB 에서 실패한다 — 값을 잘라 내지 않는다(조용히 데이터를 바꾸지 않게).
"""
from alembic import op
import sqlalchemy as sa

revision = "p0004"
down_revision = "p0003"
branch_labels = None
depends_on = None

COMMENT = "중복 제거 키(봉투 idempotency_key)"


def upgrade() -> None:
    with op.batch_alter_table("processed_event") as b:
        b.alter_column("idempotency_key", existing_type=sa.String(200), type_=sa.String(320),
                       existing_nullable=True, existing_comment=COMMENT)


def downgrade() -> None:
    with op.batch_alter_table("processed_event") as b:
        b.alter_column("idempotency_key", existing_type=sa.String(320), type_=sa.String(200),
                       existing_nullable=True, existing_comment=COMMENT)
