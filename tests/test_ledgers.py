"""대장 4종(ADR-004) — 코드에서 파생 · 정합 검사 · 생성물 최신."""
import json
import shutil

import ledgers
import pytest


def test_repo_ledgers_current_and_consistent():
    assert ledgers.main(check=True) == 0


def test_db_dictionary_from_models_with_meaning():
    rows = ledgers.scan_db()
    item = {r["column"]: r for r in rows if r["table"] == "item"}
    assert item["id"]["type"] == "VARCHAR(36)" and "PK" in item["id"]["flags"] and item["id"]["meaning"]
    assert {r["table"] for r in rows if r["common"]} == {"outbox", "processed_event"}


def test_permissions_follow_routes_and_overrides():
    perms, roles, errors = ledgers.scan_permissions(ledgers.scan_apis())
    by = {p["key"]: p for p in perms}
    assert errors == []
    assert "POST /sample/items/{item_id}/archive" in by["sample.update"]["apis"]  # override: POST 지만 update
    assert by["sample.delete"]["roles"] == ["manager", "admin"]
    assert "guest" in by["sample.read"]["roles"]


def test_events_resolve_constants():
    events, errors = ledgers.scan_events()
    e = {x["topic"]: x for x in events}
    assert errors == []
    assert e["sample.item.created"]["publishers"] == ["sample"] and e["sample.item.created"]["subscribers"] == ["sample"]
    assert "name" in e["sample.item.created"]["payload"]


def test_screens_map_api_to_tables():
    apis, db = ledgers.scan_apis(), ledgers.scan_db()
    screens, errors = ledgers.scan_screens(apis, db)
    s = {x["route"]: x for x in screens}
    assert errors == []
    assert s["/items"]["name"] == "항목 목록" and s["/items"]["status"] == "완료"
    assert "DELETE /sample/items/{item_id}" in s["/items"]["apis"] and "item" in s["/items"]["tables"]
    assert s["/ops"]["apis"] == ["GET /ops/monitoring/overview"]


def test_menu_with_unknown_permission_is_error(tmp_path, monkeypatch):
    gw = tmp_path / "gw"
    shutil.copytree(ledgers.GW, gw, ignore=shutil.ignore_patterns("__pycache__"))
    menu = json.loads((gw / "menu.json").read_text(encoding="utf-8"))
    menu["items"].append({"key": "x", "label": "엑스", "path": "/x", "channels": ["web"], "perm": "nothing.read"})
    (gw / "menu.json").write_text(json.dumps(menu, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ledgers, "GW", gw)
    _, _, errors = ledgers.scan_permissions(ledgers.scan_apis())
    assert any("nothing.read" in e for e in errors)


@pytest.mark.parametrize("path,probe,ok", [("/sample/items/{item_id}", "/sample/items/x", True), ("/sample/items", "/sample/items/x", False)])
def test_path_regex(path, probe, ok):
    assert bool(ledgers.path_regex(path).match(probe)) is ok


def test_on_pattern_reads_keyword_args():
    """@svc.on(토픽, broadcast=True) 도 구독으로 읽는다(T03-5.09) — 못 읽으면 대장에서 게이트웨이 구독자가 사라진다."""
    texts = ['@svc.on("platform.rbac.changed", broadcast=True)', "@svc.on(T_CREATED)", '@svc.on( "a.b.c" )']
    assert [m.group(1) or m.group(2) for t in texts for m in ledgers.ON.finditer(t)] == ["platform.rbac.changed", "T_CREATED", "a.b.c"]
