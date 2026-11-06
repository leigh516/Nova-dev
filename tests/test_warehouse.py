"""자료 창고 · 제품 정본(REQ-261104-02) — 입고 지문 · 부족 항목 · PRD/SPEC 검사 · 출고 파생본 · 드리프트."""
import copy
import json
import shutil
from pathlib import Path

import pytest

import warehouse as wh

ROOT = Path(__file__).resolve().parents[1]
STD = {"STD-TENANCY-001": {"decision": "적용", "reason": "여러 매장"}}

INTAKE = {"version": 1, "files": [], "gaps": [
    {"id": "G-001", "area": "운영", "question": "장애가 나면 누구에게 알려야 하나요?", "why": "알림 대상이 달라진다",
     "status": "열림", "answer": "", "interview": ""}]}

PRD = {
    "version": "0.1", "status": "승인", "approved": {"by": "고객", "date": "2030-01-02"},
    "sources": ["docs/product/intake.json"],
    "product": {"name": "매장 예약", "one_liner": "매장 직원이 예약을 받는다", "background": "전화로 받는다", "why_now": "누락"},
    "goals": ["예약 누락 0"], "non_goals": ["결제"], "anti_goals": ["직원이 두 번 입력"],
    "success_metrics": [{"id": "M-01", "metric": "누락 건수", "target": "월 0건"}],
    "users": [{"id": "U-01", "role": "직원", "description": "매장 직원", "devices": "태블릿"}],
    "features": [{"id": "F-001", "title": "예약 목록", "description": "오늘 예약을 본다", "priority": "필수", "users": ["U-01"],
                  "sources": ["prd/기획서.md#E-001"],
                  "acceptance": [{"id": "F-001-AC1", "criterion": "오늘 예약이 시간순으로 보인다", "test": "자동 테스트"}]}],
    "nfr": [{"id": "N-01", "category": "성능", "requirement": "빠르다", "acceptance": "2초 안(p95)"}],
    "constraints": [], "assumptions": [{"text": "영업시간 하루 단위", "by": "Claude 판단"}], "open_questions": [],
}


def spec_doc():
    s = json.loads((ROOT / "docs/product/_template_spec.json").read_text(encoding="utf-8"))
    s.update(status="승인", approved={"by": "고객", "date": "2030-01-03"}, prd_version="0.1",
             services=[{"name": "booking", "group": "core", "responsibility": "예약", "features": ["F-001"]}],
             data_model=[{"entity": "reservation", "service": "booking", "description": "예약 한 건", "columns": [
                 {"name": "guest_name", "type": "string(100)", "nullable": False, "comment": "손님 이름", "ref": ""},
                 {"name": "customer_id", "type": "ref", "nullable": True, "comment": "고객", "ref": "customer.id"},
                 {"name": "starts_at", "type": "datetime", "nullable": False, "comment": "예약 시각 'KST'", "ref": ""}]}],
             api=[{"id": "API-01", "method": "GET", "path": "/v1/reservations", "service": "booking", "permission": "booking.read",
                   "features": ["F-001"], "request": "paging", "response": "목록", "errors": ["FORBIDDEN"]}],
             events=[{"topic": "booking.reservation.created", "producer": "booking", "consumers": [], "payload": "id"}],
             screens=[{"id": "S-01", "name": "예약 목록", "app": "app", "route": "/reservations", "template": "ListPage", "features": ["F-001"]}],
             test_map=[{"acceptance": "F-001-AC1", "test": "services/booking/tests/test_list.py::test_sorted"}],
             open_questions=[])
    s["foundation"]["adr"] = ["ADR-006"]
    return s


@pytest.fixture
def repo(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "warehouse", docs / "warehouse")
    (docs / "product").mkdir(parents=True)
    monkeypatch.setattr(wh, "WH", docs / "warehouse")
    monkeypatch.setattr(wh, "PRODUCT", docs / "product")
    monkeypatch.setattr(wh, "ROOT", tmp_path)
    monkeypatch.setattr(wh, "project", lambda: {"slug": "shop", "standards": STD})
    return docs


def put(repo, name, data):
    (repo / "product" / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_repo_warehouse_is_valid():
    assert wh.check() == []


def test_scan_tracks_new_changed_removed(repo):
    f = repo / "warehouse/inbound/prd/기획서.md"
    f.write_text("# 기획\n예약을 받는다", encoding="utf-8")
    assert wh.scan(write=True)["새로"] == ["prd/기획서.md"]
    d = wh.load("intake")
    assert d["files"][0]["status"] == "미분석" and d["files"][0]["category"] == "prd"
    assert wh.scan(write=True) == {"새로": [], "바뀜": [], "사라짐": []}
    f.write_text("# 기획 v2", encoding="utf-8")
    assert wh.scan(write=True)["바뀜"] == ["prd/기획서.md"]
    assert wh.load("intake")["files"][0]["status"] == "재분석 필요"
    f.unlink()
    assert wh.scan(write=True)["사라짐"] == ["prd/기획서.md"]
    assert wh.load("intake")["files"][0]["status"] == "삭제됨"


def test_gaps_lists_empty_areas_and_open_items(repo):
    d = copy.deepcopy(INTAKE)
    d["files"] = [{"path": "prd/a.md", "category": "prd", "sha256": "x", "size": 1, "status": "분석됨", "analyzed": "2030-01-01",
                   "summary": "요약", "findings": [{"id": "E-001", "area": "기능", "kind": "요구", "text": "목록", "quote": "목록"}]}]
    empty, open_ = wh.gaps(d)
    assert "기능" not in empty and "운영" in empty and [g["id"] for g in open_] == ["G-001"]
    d["gaps"][0].update(status="답함", answer="점장에게 문자")
    empty, open_ = wh.gaps(d)
    assert "운영" not in empty and open_ == []  # 인터뷰로 답한 것도 근거다


def test_full_flow_out_and_drift(repo):
    put(repo, "intake", INTAKE)
    put(repo, "prd", PRD)
    put(repo, "spec", spec_doc())
    assert wh.check_prd(PRD) == [] and wh.check_spec(spec_doc(), PRD) == []
    assert wh.out() == [] and wh.check() == []
    o = repo / "warehouse/outbound"
    for rel in ("prd/prd.md", "prd/prd.html", "prd/prd.json", "spec/spec.md", "spec/spec.html", "spec/spec.json",
                "db-sql/schema.sql", "db-sql/rollback.sql", "checklist/gaps.md", "checklist/acceptance.md",
                "etc/intake_report.md", "html-mockup/analysis_html-mockup.md"):
        assert (o / rel).exists(), rel
    sql = (o / "db-sql/schema.sql").read_text(encoding="utf-8")
    assert "`id` CHAR(36) NOT NULL COMMENT 'UUIDv7" in sql and "`tenant_id` VARCHAR(40)" in sql
    assert "CREATE DATABASE IF NOT EXISTS `shop_booking`" in sql and "COMMENT '예약 시각 ''KST'''" in sql
    assert "DROP TABLE IF EXISTS `reservation`" in (o / "db-sql/rollback.sql").read_text(encoding="utf-8")
    html = (o / "prd/prd.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "<table>" in html and "<script" not in html
    assert "장애가 나면" in (o / "checklist/gaps.md").read_text(encoding="utf-8")
    assert "F-001-AC1" in (o / "checklist/acceptance.md").read_text(encoding="utf-8")
    # 출고본을 손으로 고치면 드리프트
    (o / "prd/prd.md").write_text("손으로 고침", encoding="utf-8")
    assert any("드리프트" in e for e in wh.check())
    wh.out()
    # 정본이 사라지면 그 생성물도 지운다
    (repo / "product/spec.json").unlink()
    assert any("원천이 없는 생성물" in e for e in wh.out(check=True))
    wh.out()
    assert not (o / "spec/spec.md").exists() and not (o / "db-sql/schema.sql").exists()
    assert (o / "spec/README.md").exists()


def test_outbound_css_uses_tokens():
    """출고 HTML 색은 디자인 토큰에서 — :root 에 --color-*(라이트 · 다크) 선언, 규칙 본문은 var(--color-…) 만(plan_REQ_04 T04-5.08 · R15)."""
    import re

    import gen_tokens as gt
    tree = gt.load()
    css = wh.css()
    surface = tree["semantic"]["color"]["bg"]["surface"]
    assert f"--color-bg-surface:{gt.value_of(tree, surface, 'light')}" in css
    assert "prefers-color-scheme:dark" in css and f"--color-bg-surface:{gt.value_of(tree, surface, 'dark')}" in css
    rules = re.sub(r":root\{[^{}]*\}", "", css)           # 토큰 선언을 뺀 나머지 = 규칙 본문
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", rules), rules
    assert "var(--color-text-primary)" in rules and "var(--bg)" not in rules
    assert css in wh.md_to_html("# 제목\n", "제목")


def test_check_detects_token_change(repo, monkeypatch):
    """토큰 원천의 색이 바뀌면 출고 HTML 이 낡은 것이 되고 check 가 드리프트로 잡는다(plan_REQ_04 T04-5.09 · R15)."""
    import copy as _copy

    import gen_tokens as gt
    put(repo, "prd", PRD)
    assert wh.out() == [] and wh.check() == []
    tree = _copy.deepcopy(gt.load())
    surface = tree["semantic"]["color"]["bg"]["surface"]
    old = gt.value_of(tree, surface, "light")
    tree["semantic"]["color"]["bg"]["surface"] = {"$type": "color", "$value": "#123456"}
    assert gt.value_of(tree, tree["semantic"]["color"]["bg"]["surface"], "light") != old
    monkeypatch.setattr(gt, "load", lambda path=gt.SRC: tree)
    errs = wh.check()
    assert any("드리프트" in e and "prd.html" in e for e in errs), errs
    wh.out()                                              # 다시 만들면 녹색
    assert wh.check() == []
    assert "--color-bg-surface:#123456" in (repo / "warehouse/outbound/prd/prd.html").read_text(encoding="utf-8")


def test_prd_rules(repo):
    bad = copy.deepcopy(PRD)
    bad["approved"] = {"by": "", "date": ""}
    bad["features"][0]["acceptance"] = []
    bad["features"][0]["users"] = ["U-09"]
    bad["features"][0]["sources"] = []
    errs = "\n".join(wh.check_prd(bad))
    for msg in ("승인 관문", "수용 기준", "없는 사용자 U-09", "sources"):
        assert msg in errs, msg


def test_spec_rules(repo):
    s = spec_doc()
    s["prd_version"] = "0.0"
    s["foundation"]["crosscutting"] = s["foundation"]["crosscutting"][:-1]  # 하나 빠짐
    s["data_model"][0]["columns"].append({"name": "id", "type": "uuid", "comment": ""})
    s["api"][0]["permission"] = "read"
    s["test_map"] = []
    errs = "\n".join(wh.check_spec(s, PRD))
    for msg in ("prd_version", "파일 · 첨부", "자동", "type 'uuid'", "comment", "<모듈>.<행위>", "테스트 맵에 없는 수용 기준"):
        assert msg in errs, msg


def test_symmetry(repo):
    (repo / "warehouse/inbound/new-kind").mkdir()
    shutil.rmtree(repo / "warehouse/outbound/etc")
    errs = "\n".join(wh.check_symmetry())
    assert "outbound/etc 없음" in errs and "inbound/new-kind" in errs
