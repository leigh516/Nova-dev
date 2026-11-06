"""${message}

리비전 ${up_revision} · 앞 ${down_revision | comma,n} · 만든 날 ${create_date}
downgrade 를 반드시 채운다(되돌리기 경로 — ADR-011). 칸에는 comment=(DB 사전의 '의미')를 단다.
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
