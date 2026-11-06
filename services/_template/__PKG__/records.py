"""__TITLE__ 기능 모듈 — 목록 · 등록 + 이벤트 발행. 기능이 늘면 모듈을 나누고 main.py 에 등록한다.

- 테넌트: 미들웨어가 컨텍스트에 심은 값만 쓴다 — tenant_filter · current_tenant(손으로 나르지 않는다, STD-TENANCY-001 ③)
- 자동화 등급 L1(STD-AX-001 기본값) — AI 는 초안까지, 저장은 사람. L1 의 모든 쓰기(POST · PUT · PATCH · DELETE)는
  `principal(request).require_human("<작업>")` 으로 AI 실행을 막는다(ADR-012 — 감시 테스트 tests/test_ax_guard.py 가 확인)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from nova_common import ApiError, new_id, principal
from nova_common.context import current_tenant, tenant_filter
from nova_common.ids import require_uuid7
from nova_common.paging import Page, paginate

from .app import svc
from .models import Record

router = APIRouter(prefix="/__SERVICE__")

T_CREATED = "__DOMAIN__.record.created"


class RecordIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        """min_length 는 정규화 전 길이 — 공백만 있으면 빈 이름이 저장되므로 거부(422)."""
        if not v.strip():
            raise ValueError("이름을 입력하세요. 공백만으로는 저장할 수 없습니다")
        return v


def to_dict(r: Record) -> dict:
    return {"id": r.id, "name": r.name, "created_at": r.created_at.isoformat() + "Z"}


@router.get("/records")
def list_records(page: Page = Depends()):
    with svc.db.session() as s:
        q = tenant_filter(select(Record), Record)
        if page.q:
            q = q.where(Record.name.contains(page.q, autoescape=True))  # % · _ 는 글자 그대로
        if not page.sort:
            q = q.order_by(Record.created_at.desc())
        return paginate(s, q, page, sortable={"created_at": Record.created_at, "name": Record.name}, to_dict=to_dict)


@router.get("/records/{record_id}")
def get_record(record_id: str):
    # 형식이 틀린 ID 는 조회 전에 끊는다 — 대소문자 무시 정렬(MariaDB)에서 대문자 ID 가 같은 행을 찾지 않게
    require_uuid7(record_id, code="record_not_found", message="항목을 찾을 수 없습니다")
    with svc.db.session() as s:
        r = s.get(Record, record_id)
        if r is None or r.tenant_id != current_tenant():  # 다른 테넌트의 것은 '없는 것'으로
            raise ApiError(404, "record_not_found", "항목을 찾을 수 없습니다")
        return to_dict(r)


@router.post("/records", status_code=201)
def create_record(body: RecordIn, request: Request):
    who = principal(request).require_human("기록 등록")
    with svc.db.session() as s:
        r = Record(id=new_id(), tenant_id=current_tenant(), name=body.name.strip(), created_by=who.user_id, updated_by=who.user_id)
        s.add(r)
        s.flush()
        svc.emit(s, T_CREATED, r.id, {"id": r.id, "name": r.name})
        return to_dict(r)
