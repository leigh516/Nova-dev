"""샘플 표 구조 정정(REQ-261104-12 P2 · P5) — 활동 기본키 UUIDv7 · 활동 테넌트 칸 · at → recorded_at · 사용자 참조 칸 36자.

리비전 s0002 · 앞 s0001 · 만든 날 2026-11-05

- item_activity.id INTEGER 자동 증가 → VARCHAR(36) UUIDv7(ADR-003). 옛 행은 **옛 정수 순서대로** new_id() 를 받는다 —
  new_id 는 한 프로세스 안에서 단조 증가라 같은 recorded_at 안의 순서(정렬 (recorded_at, id))가 옛 순서와 같다.
- item_activity.tenant_id 신설(STD-TENANCY-001 ①). 옛 행은 대상 항목(item.tenant_id)에서 채운다.
  항목이 이미 지워진 옛 활동(예전 삭제는 활동을 남겼다)은 NULL 로 남는다 — 행을 지우지 않는다(데이터를 조용히 바꾸지 않게).
- item_activity.at → recorded_at(naming column_datetime — '무엇의 시각'). API 응답 키도 recorded_at.
- item_activity.kind comment 에 restored(sample.item.restored 소비 — REQ-261104-12-6).
- item.created_by · updated_by VARCHAR(40) → VARCHAR(36)(ref_column — naming column_ref). 지금 값은 사용자 UUIDv7(36자)이다.
  MariaDB 엄격 모드에서 36자를 넘는 값이 있으면 이 리비전은 실패한다 — 잘라 내지 않는다(그런 값은 사용자 ID 가 아니다, 먼저 확인).
- SQLite 는 batch(표 복사), MariaDB 는 ALTER(MODIFY · CHANGE). 표를 지우고 새로 만들지 않는다(행 보존).

되돌리기(downgrade): 활동 ID 를 (recorded_at, id) 순서의 정수로 되돌리고 recorded_at → at, tenant_id 칸을 뺀다(값은 항목에서 다시 얻을 수 있다).
"""
from alembic import op
import sqlalchemy as sa

from nova_common.ids import new_id

revision = "s0002"
down_revision = "s0001"
branch_labels = None
depends_on = None

TENANT_COMMENT = "테넌트(STD-TENANCY-001)"
KIND_OLD, KIND_NEW = "활동 종류 created|archived", "활동 종류 created|archived|restored"
ID_OLD, ID_NEW = "일련번호", "활동 식별자(UUIDv7)"
AT_COMMENT = "기록 시각(UTC)"
ACTOR_COLS = (("created_by", "만든 사용자"), ("updated_by", "고친 사용자"))


def upgrade() -> None:
    conn = op.get_bind()
    act = sa.table("item_activity", sa.column("id"))
    old_ids = [r[0] for r in conn.execute(sa.select(act.c.id).order_by(act.c.id))]  # 칸 형식을 바꾸기 전에 정수 순서를 읽는다

    with op.batch_alter_table("item_activity") as b:
        b.alter_column("id", existing_type=sa.Integer(), type_=sa.String(36), existing_nullable=False,
                       autoincrement=False, existing_comment=ID_OLD, comment=ID_NEW)
        b.alter_column("at", new_column_name="recorded_at", existing_type=sa.DateTime(), existing_nullable=False,
                       existing_comment=AT_COMMENT)
        b.alter_column("kind", existing_type=sa.String(40), existing_nullable=False, existing_comment=KIND_OLD, comment=KIND_NEW)
        b.add_column(sa.Column("tenant_id", sa.String(40), nullable=True, comment=TENANT_COMMENT))
    op.create_index(op.f("ix_item_activity_tenant_id"), "item_activity", ["tenant_id"])

    act = sa.table("item_activity", sa.column("id", sa.String(36)), sa.column("item_id"), sa.column("tenant_id"))
    for old in old_ids:  # 칸 형식이 바뀐 뒤 값은 '1' · '2' … 문자열 — 옛 순서대로 UUIDv7 을 준다
        conn.execute(act.update().where(act.c.id == str(old)).values(id=new_id()))
    item = sa.table("item", sa.column("id"), sa.column("tenant_id"))
    conn.execute(act.update().values(
        tenant_id=sa.select(item.c.tenant_id).where(item.c.id == act.c.item_id).scalar_subquery()))

    with op.batch_alter_table("item") as b:
        for col, comment in ACTOR_COLS:
            b.alter_column(col, existing_type=sa.String(40), type_=sa.String(36), existing_nullable=True, existing_comment=comment)


def downgrade() -> None:
    with op.batch_alter_table("item") as b:
        for col, comment in ACTOR_COLS:
            b.alter_column(col, existing_type=sa.String(36), type_=sa.String(40), existing_nullable=True, existing_comment=comment)

    conn = op.get_bind()
    act = sa.table("item_activity", sa.column("id", sa.String(36)), sa.column("recorded_at"))
    rows = [r[0] for r in conn.execute(sa.select(act.c.id).order_by(act.c.recorded_at, act.c.id))]
    for n, rid in enumerate(rows, start=1):  # 정수로 되돌릴 때도 보이던 순서를 지킨다
        conn.execute(act.update().where(act.c.id == rid).values(id=str(n)))

    op.drop_index(op.f("ix_item_activity_tenant_id"), table_name="item_activity")
    with op.batch_alter_table("item_activity") as b:
        b.drop_column("tenant_id")
        b.alter_column("kind", existing_type=sa.String(40), existing_nullable=False, existing_comment=KIND_NEW, comment=KIND_OLD)
        b.alter_column("recorded_at", new_column_name="at", existing_type=sa.DateTime(), existing_nullable=False,
                       existing_comment=AT_COMMENT)
        b.alter_column("id", existing_type=sa.String(36), type_=sa.Integer(), existing_nullable=False,
                       autoincrement=True, existing_comment=ID_NEW, comment=ID_OLD)
