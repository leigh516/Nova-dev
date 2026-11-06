"""목록 API 계약 — `?page=1&size=20&sort=-created_at&q=...` → `{"items", "total", "page", "size"}`.

    from nova_common.paging import Page, paginate

    @router.get("/items")
    def list_items(page: Page = Depends()):
        with svc.db.session() as s:
            q = select(Item)
            if page.q:
                q = q.where(Item.name.contains(page.q, autoescape=True))  # % · _ 를 글자 그대로
            return paginate(s, q, page, sortable={"created_at": Item.created_at, "name": Item.name},
                            to_dict=lambda i: {"id": i.id, "name": i.name})
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .service import ApiError

MAX_SIZE = 100
MAX_PAGE = 100_000  # 이보다 깊은 쪽은 검색 · 정렬로 좁힌다(거대한 offset 은 DB 오류 · 전체 스캔)


@dataclass
class Page:
    page: int = Query(1, ge=1, le=MAX_PAGE, description="1부터 · 최대 100000")
    size: int = Query(20, ge=1, le=MAX_SIZE, description="기본 20 · 최대 100")
    sort: str | None = Query(None, description="필드명, 내림차순은 -필드명 (예: -created_at)")
    q: str | None = Query(None, description="검색어")


def paginate(
    session: Session,
    query: Select,
    page: Page,
    *,
    sortable: dict[str, Any] | None = None,
    to_dict: Callable[[Any], dict] | None = None,
) -> dict:
    """query 에 정렬 · offset · limit 을 적용하고 total 을 함께 돌려준다.

    sortable: 허용 정렬 필드 → 컬럼. 목록에 없는 sort 는 400(임의 컬럼 정렬 · 주입 방지).
    """
    if page.sort:
        key = page.sort.lstrip("-")
        col = (sortable or {}).get(key)
        if col is None:
            raise ApiError(400, "invalid_sort", f"정렬할 수 없는 항목입니다: {key}",
                           allowed=sorted((sortable or {}).keys()))
        query = query.order_by(col.desc() if page.sort.startswith("-") else col.asc())
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = session.scalars(query.offset((page.page - 1) * page.size).limit(page.size)).all()
    items = [to_dict(r) for r in rows] if to_dict else list(rows)
    return {"items": items, "total": total, "page": page.page, "size": page.size}
