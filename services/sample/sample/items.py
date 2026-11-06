"""항목 CRUD + 이벤트 발행/소비 — 새 서비스가 따라 할 예시.

- 목록: 목록 API 계약(page · size · sort · q → items · total)
- 쓰기: 같은 트랜잭션에서 업무 데이터 + 아웃박스 이벤트(svc.emit)
- 소비: @svc.on(topic) — processed_event 로 멱등
- 권한: 게이트웨이가 sample.<행위> 를 검사하고, 서비스는 로그인 여부만 본다
- 자동화 등급: STD-AX-001 L1 — AI 는 초안까지, **모든 쓰기**(등록 · 수정 · 보관 · 보관 해제 · 삭제)는 사람만 `require_human`(ADR-012)
- 테넌트: 게이트웨이 → 미들웨어가 컨텍스트에 심은 값만 쓴다(손으로 나르지 않는다, STD-TENANCY-001 ③)
- 가변점: 이름 정규화는 포트 `sample.normalize_name` — 도메인 팩이 바꿔 끼울 수 있다(STD-DOMAIN-PACK-001)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select

from nova_common import ApiError, Envelope, new_id, packs, principal
from nova_common.context import current_tenant, tenant_filter
from nova_common.db import utcnow
from nova_common.ids import require_uuid7
from nova_common.paging import Page, paginate

from .app import svc
from .models import ITEM_STATUSES, STATUS_ACTIVE, STATUS_ARCHIVED, Item, ItemActivity

router = APIRouter(prefix="/sample")
log = logging.getLogger("sample.items")

T_CREATED = "sample.item.created"
T_UPDATED = "sample.item.updated"
T_ARCHIVED = "sample.item.archived"
T_RESTORED = "sample.item.restored"
ACTIVITY_LIMIT = 50  # 상세에 싣는 활동 상한(REQ-261104-12-8) — 전체 보기 화면은 비목표, 넘치면 activity_truncated
T_DELETED = "sample.item.deleted"  # 바깥 구독자를 위한 사실 통지 — 이 서비스는 구독하지 않는다(활동은 삭제 트랜잭션에서 지운다)


def _not_blank(v: str | None) -> str | None:
    """min_length 는 정규화 전 길이라 공백만 있는 이름을 통과시킨다 — 앞뒤 공백을 뗀 뒤 비면 거부(422)."""
    if v is not None and not v.strip():
        raise ValueError("이름을 입력하세요. 공백만으로는 저장할 수 없습니다")
    return v


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="항목 이름")
    memo: str | None = Field(default=None, max_length=2000)

    _name_not_blank = field_validator("name")(_not_blank)


class ItemPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    memo: str | None = Field(default=None, max_length=2000)

    _name_not_blank = field_validator("name")(_not_blank)


@packs.port("sample.normalize_name")
def normalize_name(name: str) -> str:
    """코어 규칙: 앞뒤 공백만 지운다. 업종마다 다르면 팩이 구현을 바꾼다."""
    return name.strip()


def to_dict(i: Item) -> dict:
    return {"id": i.id, "name": i.name, "memo": i.memo, "status": i.status,
            "created_at": i.created_at.isoformat() + "Z", "updated_at": i.updated_at.isoformat() + "Z"}


_NOT_FOUND = ("item_not_found", "항목을 찾을 수 없습니다. 이미 삭제되었을 수 있습니다")


def _get(s, item_id: str) -> Item:
    # 형식이 틀린 ID 는 조회 전에 끊는다 — 대소문자 무시 정렬(MariaDB)에서 대문자 ID 가 같은 행을 찾지 않게(REQ-261104-11-7)
    require_uuid7(item_id, code=_NOT_FOUND[0], message=_NOT_FOUND[1])
    item = s.get(Item, item_id)
    if item is None or item.tenant_id != current_tenant():  # 다른 테넌트의 항목은 '없는 것'으로
        raise ApiError(404, *_NOT_FOUND)
    return item


@router.get("/items")
def list_items(page: Page = Depends(), status: str | None = None):
    # 모르는 필터 값은 정렬(paginate 의 invalid_sort)과 같은 규칙 — 400 + 허용 값. 빈 목록으로 돌려주면 오타가
    # '항목 없음'처럼 보인다(T03-9.03). 빈 문자열은 필터 없음(화면이 칸을 비운 채 보낼 때)
    if status and status not in ITEM_STATUSES:
        raise ApiError(400, "invalid_status", f"거를 수 없는 상태입니다: {status}", allowed=sorted(ITEM_STATUSES))
    with svc.db.session() as s:
        q = tenant_filter(select(Item), Item)
        if status:
            q = q.where(Item.status == status)
        if page.q:
            q = q.where(Item.name.contains(page.q, autoescape=True))  # % · _ 는 글자 그대로(와일드카드 아님)
        if not page.sort:
            q = q.order_by(Item.created_at.desc())
        return paginate(s, q, page, sortable={"created_at": Item.created_at, "name": Item.name}, to_dict=to_dict)


@router.get("/items/{item_id}")
def get_item(item_id: str):
    with svc.db.session() as s:
        item = _get(s, item_id)
        # 활동도 테넌트로 거른다 — item_id 는 다른 테넌트 활동과 겹칠 수 있다(늦은 이벤트 · 시험 데이터, STD-TENANCY-001 ③)
        # 같은 시각(MariaDB DATETIME 은 초 단위)이면 id(UUIDv7 — 시간순 생성)가 순서를 정한다
        q = tenant_filter(select(ItemActivity), ItemActivity).where(ItemActivity.item_id == item_id)
        # 최신 ACTIVITY_LIMIT 건만 읽는다(하나 더 읽어 넘침을 안다) — 보이는 순서는 예전처럼 오래된 것부터
        newest = s.scalars(q.order_by(ItemActivity.recorded_at.desc(), ItemActivity.id.desc()).limit(ACTIVITY_LIMIT + 1)).all()
        acts = list(reversed(newest[:ACTIVITY_LIMIT]))
        return {**to_dict(item), "activity": [{"kind": a.kind, "recorded_at": a.recorded_at.isoformat() + "Z"} for a in acts],
                "activity_truncated": len(newest) > ACTIVITY_LIMIT}


@router.post("/items", status_code=201)
def create_item(body: ItemIn, request: Request):
    who = principal(request).require_human("항목 등록")
    with svc.db.session() as s:
        item = Item(id=new_id(), tenant_id=current_tenant(), name=packs.get("sample.normalize_name")(body.name), memo=body.memo,
                    created_by=who.user_id, updated_by=who.user_id)
        s.add(item)
        s.flush()
        svc.emit(s, T_CREATED, item.id, {"id": item.id, "name": item.name})  # 테넌트 · 행위자는 봉투가 자동으로
        return to_dict(item)


@router.patch("/items/{item_id}")
def update_item(item_id: str, body: ItemPatch, request: Request):
    who = principal(request).require_human("항목 수정")
    with svc.db.session() as s:
        item = _get(s, item_id)
        if item.status == STATUS_ARCHIVED:
            raise ApiError(409, "item_archived", "보관된 항목은 고칠 수 없습니다. 먼저 보관을 해제하세요")
        if body.name is not None:
            item.name = packs.get("sample.normalize_name")(body.name)
        if body.memo is not None:
            item.memo = body.memo
        item.updated_by, item.updated_at = who.user_id, utcnow()
        svc.emit(s, T_UPDATED, item.id, {"id": item.id, "name": item.name}, idempotency_key=f"sample:{T_UPDATED}:{item.id}:{item.updated_at.isoformat()}")
        return to_dict(item)


@router.post("/items/{item_id}/archive")
def archive_item(item_id: str, request: Request):
    """보관(되돌릴 수 있는 삭제) — 화면은 실행 취소 토스트로 restore 를 부른다."""
    who = principal(request).require_human("항목 보관")
    with svc.db.session() as s:
        item = _get(s, item_id)
        if item.status == STATUS_ARCHIVED:  # 같은 상태로의 전이 — 이벤트 없이 현재 상태 그대로(중복 클릭 · 재시도)
            return to_dict(item)
        item.status, item.updated_by, item.updated_at = STATUS_ARCHIVED, who.user_id, utcnow()
        svc.emit(s, T_ARCHIVED, item.id, {"id": item.id}, idempotency_key=f"sample:{T_ARCHIVED}:{item.id}:{item.updated_at.isoformat()}")
        return to_dict(item)


@router.post("/items/{item_id}/restore")
def restore_item(item_id: str, request: Request):
    who = principal(request).require_human("항목 보관 해제")
    with svc.db.session() as s:
        item = _get(s, item_id)
        if item.status == STATUS_ACTIVE:  # 이미 활성 — 그대로
            return to_dict(item)
        item.status, item.updated_by, item.updated_at = STATUS_ACTIVE, who.user_id, utcnow()
        svc.emit(s, T_RESTORED, item.id, {"id": item.id}, idempotency_key=f"sample:{T_RESTORED}:{item.id}:{item.updated_at.isoformat()}")
        return to_dict(item)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, request: Request):
    """영구 삭제 — 되돌릴 수 없으므로 사람만(STD-AX-001: AI 는 보관까지만). 화면의 기본 경로는 보관 + 실행 취소."""
    principal(request).require_human("항목 삭제")
    with svc.db.session() as s:
        item = _get(s, item_id)
        # 활동은 항목에 딸린 기록 — 같은 트랜잭션에서 함께 지워 고아 활동을 남기지 않는다(자기 DB 라 이벤트를 기다릴 필요 없음)
        s.execute(delete(ItemActivity).where(ItemActivity.item_id == item.id, ItemActivity.tenant_id == item.tenant_id))
        s.delete(item)
        # 삭제는 한 번뿐이라 멱등 키에 시각이 필요 없다
        svc.emit(s, T_DELETED, item.id, {"id": item.id}, idempotency_key=f"sample:{T_DELETED}:{item.id}")


# ------------------------------------------------------------------ 이벤트 소비 (멱등)
@svc.on(T_CREATED)
@svc.on(T_ARCHIVED)
@svc.on(T_RESTORED)
def record_activity(s, env: Envelope):
    # 삭제 뒤 늦게 도착한 이벤트는 건너뛴다 — 고아 활동을 만들지 않고, 처리 기록은 남아 재전달해도 결과가 같다(plan §6 열림)
    # 존재만 본다(행 전체를 읽지 않는다). 테넌트도 맞아야 같은 항목 — 다른 테넌트 항목에 활동을 붙이지 않는다
    tenant_ok = Item.tenant_id == env.tenant if env.tenant is not None else Item.tenant_id.is_(None)
    if s.scalar(select(Item.id).where(Item.id == env.key, tenant_ok)) is None:
        log.info("항목 %s 이 없거나 테넌트가 달라 %s 활동을 건너뜁니다(삭제 뒤 늦은 이벤트)", env.key, env.type)
        return
    # 테넌트는 봉투의 것(발행 시점, STD-TENANCY-001 ④) — 처리 범위(context.scope)와 같은 값이지만 봉투가 원천이다
    s.add(ItemActivity(tenant_id=env.tenant, item_id=env.key, kind=env.type.rsplit(".", 1)[-1], event_id=env.id))
