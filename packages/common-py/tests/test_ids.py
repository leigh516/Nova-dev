"""UUIDv7 (RFC 9562) — 형식 · 버전 · 변형 · 단조 증가 · 시각 추출 · 문자열 정렬 = 시간 정렬."""
import uuid
from datetime import datetime, timedelta, timezone

from nova_common import ids
from nova_common.events import Envelope


def test_version_and_variant():
    u = ids.uuid7()
    assert u.version == 7 and u.variant == uuid.RFC_4122
    s = ids.new_id()
    assert len(s) == ids.UUID_LEN == 36 and s == s.lower() and ids.is_uuid7(s)


def test_strictly_increasing_even_within_same_millisecond():
    many = [ids.new_id() for _ in range(20000)]  # 같은 ms 에 수천 개 → 카운터로 순서 유지
    assert many == sorted(many) and len(set(many)) == len(many)


def test_embedded_time():
    t = ids.uuid7_time(ids.new_id())
    assert abs(t - datetime.now(timezone.utc)) < timedelta(seconds=5)


def test_rejects_non_v7():
    assert not ids.is_uuid7(str(uuid.uuid4()))
    assert not ids.is_uuid7("IT-01J000")
    try:
        ids.uuid7_time(str(uuid.uuid4()))
        raise AssertionError("v4 를 받으면 안 된다")
    except ValueError:
        pass


def test_event_ids_are_uuid7():
    assert ids.is_uuid7(Envelope(type="a.b.c", source="s", key="k", idempotency_key="i", data={}).id)


def test_require_uuid7_404_envelope():
    """경로 ID 형식 검사(REQ-261104-11-7) — UUIDv7 정규형(소문자 36자)이 아니면 DB 조회 전에 404 봉투."""
    import pytest
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import DeclarativeBase

    from nova_common.service import ApiError, Service

    good = ids.new_id()
    assert ids.require_uuid7(good) == good
    bad_values = ("abc", good.upper(), good.replace("-", ""), str(uuid.uuid4()), "", f" {good}")
    for bad in bad_values:
        with pytest.raises(ApiError) as e:
            ids.require_uuid7(bad)
        assert (e.value.status, e.value.code, e.value.message) == (404, "not_found", "찾는 항목이 없습니다"), bad
    with pytest.raises(ApiError) as e:
        ids.require_uuid7("abc", code="item_not_found", message="항목을 찾을 수 없습니다")
    assert (e.value.code, e.value.message) == ("item_not_found", "항목을 찾을 수 없습니다")

    # 서비스 오류 처리기를 거치면 표준 봉투 {error:{code,message}} 로 나간다
    class Base(DeclarativeBase):
        pass

    svc = Service("idcheck", Base, "형식 검사", db_url="sqlite://")

    @svc.app.get("/things/{thing_id}")
    def get_thing(thing_id: str):
        return {"id": ids.require_uuid7(thing_id)}

    with TestClient(svc.app) as c:
        r = c.get("/things/abc")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
        assert c.get(f"/things/{good}").json() == {"id": good}
