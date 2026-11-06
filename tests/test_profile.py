"""규모 프로파일(lite · product · platform) — 선언 · 판정 · 바꾸기 이력 · 추천 · 병렬 게이트 연결 (REQ-261104-17-5)."""
import datetime as dt

import project_profile as pf

DAY = dt.date(2026, 11, 4)
GOOD = {"profile": {"value": "platform", "why": "공통개발플랫폼 자신 — 모든 절차 · 봉인", "date": "2026-11-04", "history": []}}


def test_repo_declares_platform_with_reason():
    """Nova 자신은 platform 으로 선언되어 있고 이유가 있다(REQ-17 종료 조건 E4)."""
    meta = pf.load_meta()
    assert pf.check(meta) == []
    assert meta["profile"]["value"] == "platform"


def test_check_rejects_missing_unknown_and_empty_reason():
    assert any("profile" in e for e in pf.check({}))
    assert any("lite · product · platform" in e for e in pf.check({"profile": {**GOOD["profile"], "value": "solo"}}))
    assert any("이유" in e for e in pf.check({"profile": {**GOOD["profile"], "why": " "}}))
    assert any("날짜" in e for e in pf.check({"profile": {**GOOD["profile"], "date": "어제"}}))


def test_set_keeps_history_and_requires_reason():
    meta = pf.set_profile(GOOD, "product", "복제본 기본 — 착수 전체 · 공통 영역 뒤 병렬", DAY)
    p = meta["profile"]
    assert p["value"] == "product" and p["date"] == "2026-11-04"
    assert p["history"] == [{"value": "platform", "why": GOOD["profile"]["why"], "date": "2026-11-04"}]
    assert pf.check(meta) == []
    import pytest
    with pytest.raises(SystemExit, match="이유"):
        pf.set_profile(GOOD, "lite", "", DAY)


def test_rules_differ_by_profile_but_safety_never_drops():
    lite, product, platform = (pf.rules(v) for v in ("lite", "product", "platform"))
    assert lite["parallel"] is False and product["parallel"] is True
    assert lite["sdd"] == "light" and product["sdd"] == "full"
    # 승인 관문 · 안전 검사 · 기록 하한은 어느 프로파일에서도 빠지지 않는다
    for r in (lite, product, platform):
        assert r["approval_gate"] and r["safety_checks"] and r["record_floor"]


def test_suggest_small_project_is_lite():
    value, reasons = pf.suggest(backend_services=1, web_apps=1, packs=0, is_platform=False)
    assert value == "lite" and reasons
    assert pf.suggest(backend_services=4, web_apps=2, packs=1, is_platform=False)[0] == "product"
    assert pf.suggest(backend_services=1, web_apps=1, packs=0, is_platform=True)[0] == "platform"


def test_parallel_gate_closed_for_lite(tmp_path, monkeypatch):
    import parallel
    monkeypatch.setattr(pf, "load_meta", lambda root=None: {"profile": {**GOOD["profile"], "value": "lite"}})
    why, _ = parallel.gate(tmp_path / "없는-마스터플랜.md")
    assert any("lite" in w for w in why)
