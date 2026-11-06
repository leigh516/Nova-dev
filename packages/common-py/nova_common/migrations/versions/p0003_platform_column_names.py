"""플랫폼 표 칸 이름을 명명 규약에 맞춘다(ADR-012 D3) — outbox.parked → is_parked · processed_event.ok → is_ok · processed_event.at → processed_at.

- 플랫폼 표는 nova_common 만 읽고 쓰므로(서비스 코드는 칸을 직접 쓰지 않는다) 코드와 한 판본에서 함께 바꾼다.
- SQLite 는 batch(표 복사)로 바꾼다. 옛 create_all DB 의 **이름 없는** UNIQUE(outbox.event_id)는 naming_convention 을 주지 않으면
  이름 없이 그대로 옮겨진다(중복은 막히지만 모델의 uq_outbox_event_id 와 이름이 달라 drift 1건). 그래서 naming_convention 을 주어
  표 복사 때 규칙 이름을 붙인다(테스트 test_p0003_legacy_db_keeps_values_and_unnamed_unique 가 지킨다).
- MariaDB 는 CHANGE COLUMN 이라 타입 · NULL · comment 를 다시 적어야 해서 existing_* 를 모두 준다.
- 인덱스 이름(ix_outbox_parked)은 칸 이름에서 나오므로 지우고 새 이름(ix_outbox_is_parked)으로 다시 만든다.
"""
from alembic import op
import sqlalchemy as sa

from nova_common.db import NAMING_CONVENTION

revision = "p0003"
down_revision = "p0002"
branch_labels = None
depends_on = None

# (표, 옛 이름, 새 이름, 타입, comment)
RENAMES = (
    ("outbox", "parked", "is_parked", sa.Boolean(), "독 메시지 격리(재처리 대기)"),
    ("processed_event", "ok", "is_ok", sa.Boolean(), "처리 성공"),
    ("processed_event", "at", "processed_at", sa.DateTime(), "처리 시각(UTC)"),
)


def _rename(old_to_new: bool) -> None:
    for table in ("outbox", "processed_event"):
        # naming_convention: SQLite 표 복사 때 반사된 이름 없는 제약(옛 DB 의 UNIQUE(event_id))에 규칙 이름을 붙인다
        # → 옛 DB 도 새 DB 와 같은 uq_outbox_event_id 가 되어 모델과 차이 0. MariaDB 는 표 복사를 하지 않아 영향 없다
        with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as b:
            for t, old, new, type_, comment in RENAMES:
                if t != table:
                    continue
                src, dst = (old, new) if old_to_new else (new, old)
                b.alter_column(src, new_column_name=dst, existing_type=type_, existing_nullable=False, existing_comment=comment)


def upgrade() -> None:
    op.drop_index(op.f("ix_outbox_parked"), table_name="outbox")
    _rename(True)
    op.create_index(op.f("ix_outbox_is_parked"), "outbox", ["is_parked"])


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_is_parked"), table_name="outbox")
    _rename(False)
    op.create_index(op.f("ix_outbox_parked"), "outbox", ["parked"])
