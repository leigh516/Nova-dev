"""생성물 원장 핵심 규칙 — 순수 함수 단위 테스트 + 스캐너 설정."""
import pytest
import registry as R


def art(kind, scope, name, loc="x.py"):
    return R.Artifact(kind=kind, scope=scope, name=name, loc=loc)


def sync(state, events, scanned, **kw):
    new = R.plan_sync(state, scanned, by="test", at="2026-11-03T00:00:00Z", start_seq=len(events) + 1, refs_of=kw.get("refs_of", lambda a: []))
    events = events + new
    return R.replay(events), events, new


def test_create_assigns_sequential_ids_per_kind_and_scope():
    state, events, new = sync({}, [], [art("TBL", "CORE", "user"), art("TBL", "CORE", "payment"), art("TBL", "ROOMS", "room")])
    ids = sorted(state)
    assert ids == ["TBL-CORE-0001", "TBL-CORE-0002", "TBL-ROOMS-0001"]
    assert [e["action"] for e in new] == ["create"] * 3 and [e["seq"] for e in new] == [1, 2, 3]
    assert state["TBL-CORE-0001"]["status"] == "active"


def test_sync_is_idempotent_and_detects_moves_as_update():
    scanned = [art("TBL", "CORE", "user", "a.py")]
    state, events, _ = sync({}, [], scanned)
    state, events, new = sync(state, events, scanned)
    assert new == []
    state, events, new = sync(state, events, [art("TBL", "CORE", "user", "b.py")])
    assert [e["action"] for e in new] == ["update"] and state["TBL-CORE-0001"]["loc"] == "b.py"


def test_missing_artifact_is_deleted_with_refs_and_number_not_reused():
    state, events, _ = sync({}, [], [art("SCR", "WCUS", "/a"), art("SCR", "WCUS", "/b")])
    state, events, new = sync(state, events, [art("SCR", "WCUS", "/a")], refs_of=lambda a: ["web/apps/app/app/layout.tsx"])
    d = state["SCR-WCUS-0002"]
    assert new[0]["action"] == "delete" and d["status"] == "deleted" and d["refs"] == ["web/apps/app/app/layout.tsx"]
    state, events, _ = sync(state, events, [art("SCR", "WCUS", "/a"), art("SCR", "WCUS", "/c")])
    assert "SCR-WCUS-0003" in state  # 삭제된 0002 번호는 재사용하지 않음


def test_recreating_a_deleted_name_is_refused_until_restore():
    state, events, _ = sync({}, [], [art("TBL", "MKT", "hold")])
    state, events, _ = sync(state, events, [])
    with pytest.raises(R.RegistryError, match="restore TBL-MKT-0001"):
        sync(state, events, [art("TBL", "MKT", "hold")])
    events = events + [R.event("restore", state["TBL-MKT-0001"], by="test", at="t", seq=len(events) + 1, note="다시 사용")]
    state = R.replay(events)
    assert state["TBL-MKT-0001"]["status"] == "active"
    _, _, new = sync(state, events, [art("TBL", "MKT", "hold")])
    assert new == []


def test_duplicate_active_names_in_scan_are_refused():
    with pytest.raises(R.RegistryError, match="중복"):
        sync({}, [], [art("API", "CORE", "GET /me"), art("API", "CORE", "GET /me", "other.py")])


def test_check_detects_snapshot_drift_and_unregistered():
    state, events, _ = sync({}, [], [art("EVT", "KAFKA", "a.b.c")])
    assert R.check(events, state, [art("EVT", "KAFKA", "a.b.c")]) == []
    errs = R.check(events, {**state, "EVT-KAFKA-0001": {**state["EVT-KAFKA-0001"], "name": "x"}}, [art("EVT", "KAFKA", "a.b.c")])
    assert any("스냅샷" in e for e in errs)
    errs = R.check(events, state, [art("EVT", "KAFKA", "a.b.c"), art("EVT", "KAFKA", "new.topic.x")])
    assert any("미등록" in e for e in errs)


def test_rename_keeps_id_and_history():
    state, events, _ = sync({}, [], [art("CMP", "UI", "Stat")])
    events = events + [R.event("rename", {**state["CMP-UI-0001"], "name": "StatCard"}, by="t", at="t", seq=len(events) + 1, note="규약 이름")]
    state = R.replay(events)
    assert state["CMP-UI-0001"]["name"] == "StatCard" and state["CMP-UI-0001"]["versions"] == 2


def test_moving_between_services_links_old_to_new_with_replaced_by():
    """서비스 분리 · 통합: 같은 종류 · 이름이 한 서비스에서 사라지고 다른 서비스에 생기면 옛 ID → 새 ID 연결."""
    state, events, _ = sync({}, [], [art("TBL", "CORE", "user_account"), art("TBL", "CORE", "payment")])
    state, events, new = sync(state, events, [art("TBL", "IAM", "user_account"), art("TBL", "CORE", "payment")])
    old, moved = state["TBL-CORE-0001"], state["TBL-IAM-0001"]
    assert old["status"] == "deleted" and old["replaced_by"] == "TBL-IAM-0001"
    assert moved["status"] == "active" and state["TBL-CORE-0002"]["status"] == "active"
    # 같은 이름이 여러 곳에 새로 생기면 어느 쪽인지 모르므로 연결하지 않는다
    state, events, _ = sync({}, [], [art("API", "CORE", "GET /x")])
    state, events, _ = sync(state, events, [art("API", "IAM", "GET /x"), art("API", "DEAL", "GET /x")])
    assert state["API-CORE-0001"]["replaced_by"] is None


def test_repo_registry_is_consistent():
    assert R.check(R.load_events(), R.replay(R.load_events()), R.scan()) == []


def test_scan_uses_router_prefix_and_infra_tables():
    names = {(a.kind, a.scope, a.name) for a in R.scan()}
    assert ("API", "SAMPLE", "GET /sample/items") in names  # APIRouter(prefix="/sample") + "/items"
    assert ("TBL", "SAMPLE", "outbox") in names and ("TBL", "SAMPLE", "item") in names
    assert ("EVT", "KAFKA", "sample.item.created") in names


def test_kinds_and_id_pattern_come_from_config():
    assert set(R.KIND_LABEL) >= {"SVC", "TBL", "API", "EVT", "SCR", "CMP"}
    assert R.ID_RE.match("TBL-SAMPLE-0001") and not R.ID_RE.match("XYZ-A-0001")


def test_unknown_scanner_type_is_error():
    with pytest.raises(R.RegistryError):
        R.scan({"kinds": {}, "scanners": [{"kind": "X", "type": "nope"}]})
