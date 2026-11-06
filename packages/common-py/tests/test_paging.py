"""목록 API 계약 — 정렬 허용 목록 · 페이지 분할 · total."""
import pytest
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from nova_common import ApiError
from nova_common.paging import Page, paginate


class Base(DeclarativeBase):
    pass


class Row(Base):
    __tablename__ = "row"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(10))


@pytest.fixture
def session():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all([Row(id=i, name=f"n{i:02d}") for i in range(1, 46)])
        s.commit()
        yield s


def test_paginate_pages_and_total(session):
    out = paginate(session, select(Row), Page(page=3, size=20, sort="-id", q=None),
                   sortable={"id": Row.id}, to_dict=lambda r: r.id)
    assert out["total"] == 45 and out["page"] == 3 and out["size"] == 20
    assert out["items"] == [5, 4, 3, 2, 1]


def test_paginate_rejects_unknown_sort(session):
    with pytest.raises(ApiError) as e:
        paginate(session, select(Row), Page(page=1, size=20, sort="password", q=None), sortable={"id": Row.id})
    assert e.value.status == 400 and e.value.code == "invalid_sort"
