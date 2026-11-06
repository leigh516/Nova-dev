"""요구 체크리스트(REQ-261104-03) — 트리 · 자동 채움 근거 · 폼 생성 · md 계층 · 저장 번호 · intake 가져오기."""
import copy
import json
import shutil
from pathlib import Path

import pytest

import checklist as ck
import warehouse as wh

ROOT = Path(__file__).resolve().parents[1]
INTAKE = {"version": 1, "gaps": [], "files": [{
    "path": "prd/기획.md", "category": "prd", "sha256": "-", "size": 1, "status": "분석됨", "analyzed": "2030-01-01", "summary": "기획",
    "findings": [{"id": "E-001", "area": "목적 · 배경", "kind": "사실", "text": "엑셀로 받는다", "quote": "엑셀"}]}]}
# 킷 목록 고정구 — 형식은 design/tokens/kits/catalog.json(REQ-261106-04-1)과 같다. 견본은 px 숫자 · 토큰 단계 이름 둘 다 받는다
CATALOG = {"kits": [
    {"id": "nova", "label": "Nova 기본", "desc": "검사를 통과한 기본 값", "tokens": None,
     "preview": {"hex": "#4F5BD5", "radius": 10, "gap": 8, "dark": False}, "gaps": [], "status": "기본"},
    {"id": "newtype", "label": "newtype — 초록 콘솔", "desc": "초록 관제 콘솔", "tokens": "newtype.tokens.json",
     "preview": {"hex": "#1F9D55", "radius": 4, "gap": 12, "dark": True}, "gaps": ["popover", "daterange"], "status": "채택 가능"},
    {"id": "dim", "label": "흐린 킷", "desc": "대비 미달 시험용", "tokens": "dim.tokens.json",
     "preview": {"hex": "#CCCCCC", "radius": "md", "gap": "2", "dark": False}, "gaps": [], "status": "채택 가능"}]}
KIT_CALLS: list[str] = []


@pytest.fixture
def repo(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "docs" / "warehouse", tmp_path / "warehouse")
    (tmp_path / "product").mkdir()
    for p in (tmp_path / "warehouse/inbound/checklist").glob("checklist_*"):
        p.unlink()
    for cat, exts in ck.MOCKUP_DIRS.items():   # 저장소에 들어온 실제 목업 · 캡처는 비운다 — 새 프로젝트처럼 빈 입고에서 시작
        for p in (tmp_path / "warehouse/inbound" / cat).rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                p.unlink()
    monkeypatch.setattr(wh, "WH", tmp_path / "warehouse")
    monkeypatch.setattr(wh, "PRODUCT", tmp_path / "product")
    monkeypatch.setattr(wh, "ROOT", tmp_path)
    (tmp_path / "product/intake.json").write_text(json.dumps(INTAKE, ensure_ascii=False), encoding="utf-8")
    # 킷 목록 · 프로젝트 메타는 고정구 — 저장소 실제 catalog.json · nova.project.json 을 읽거나 바꾸지 않는다
    kd = tmp_path / "kits"
    kd.mkdir()
    (kd / "catalog.json").write_text(json.dumps(CATALOG, ensure_ascii=False), encoding="utf-8")
    (kd / "newtype.tokens.json").write_text("{}", encoding="utf-8")
    (kd / "dim.tokens.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ck, "KITS_CATALOG", kd / "catalog.json")
    (tmp_path / "nova.project.json").write_text(json.dumps({"name": "시험", "design": {"kit": "nova"}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(ck, "PROJECT_JSON", tmp_path / "nova.project.json")
    KIT_CALLS.clear()

    def fake_kit_use(kid):   # kits.use 대역 — 대비 미달 킷(dim)은 거절, 나머지는 kits.use 처럼 design 을 통째로 기록
        KIT_CALLS.append(kid)
        if kid == "dim":
            return False, "킷 dim 대비 · 분리 검사 미달 1건 — line 1.53:1"
        meta = json.loads((tmp_path / "nova.project.json").read_text(encoding="utf-8"))
        meta["design"] = {"kit": kid, "date": "2030-01-02", "by": "시험", "source": "checklist"}
        (tmp_path / "nova.project.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True, f"✓ 킷 {kid}"
    monkeypatch.setattr(ck, "run_kit_use", fake_kit_use)
    return tmp_path


def doc(answers, status="complete", rev=1, updated="2030-01-02T10:00:00", file=""):
    return {"form": "nova-checklist", "tree_version": "1", "status": status, "revision": rev, "created": "2030-01-02",
            "updated": updated, "file": file, "lv": 1, "answers": answers}


def a(value, state="customer"):
    return {"value": value, "other": "", "note": "", "state": state, "evidence": []}


def test_repo_checklist_is_valid():
    assert ck.check_tree(ck.tree()) == []
    assert ck.check() == []


def test_tree_rules():
    t = {"version": "1", "sections": [{"id": "s", "title": "섹션", "questions": [
        {"id": "s.a", "q": "질문", "type": "one", "area": "기능", "lv": 1, "options": [{"id": "x", "label": "X"}]},
        {"id": "t.b", "q": "", "type": "text", "area": "없는영역", "lv": 4}]}]}
    errs = "\n".join(ck.check_tree(t))
    for m in ("보기가 2개 이상", "섹션 ID 's.'", "area", "lv", "질문 문구"):
        assert m in errs, m


def test_prefill_needs_evidence(repo):
    t = ck.tree()
    ok = {"what.kind": {"value": "replace", "evidence": ["E-001"]}}
    assert ck.check_answers(ok, t, "p", prefill=True) == []
    bad = {"what.kind": {"value": "replace"}, "what.domain": {"value": "없는보기", "evidence": ["E-001"]}, "x.y": {"value": "1"}}
    errs = "\n".join(ck.check_answers(bad, t, "p", prefill=True))
    assert "근거" in errs and "없는 보기" in errs and "트리에 없는 질문 x.y" in errs
    (repo / "product/checklist_prefill.json").write_text(json.dumps({"answers": {"what.kind": {"value": "new", "evidence": ["E-999"]}}}), encoding="utf-8")
    assert ck.main(["build"]) == 0                                                 # 근거 번호의 존재는 build 가 아니라 check 가 본다
    assert any("없는 근거 E-999" in e for e in ck.check())


def test_build_embeds_prefill_evidence_and_tokens(repo):
    (repo / "product/checklist_prefill.json").write_text(json.dumps({"answers": {"what.kind": {"value": "replace", "evidence": ["E-001"]}}}), encoding="utf-8")
    assert ck.main(["build"]) == 0
    html = ck.form_path().read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "--color-action-primary:" in html and "엑셀로 받는다" in html
    assert "<script src" not in html and "/*__DATA__*/" not in html
    assert ck.check() == []
    (repo / "product/checklist_prefill.json").write_text(json.dumps({"answers": {}}), encoding="utf-8")
    assert any("checklist.html" in e for e in ck.check())  # 원천이 바뀌면 폼이 낡음


def test_md_hierarchy_and_visibility(repo):
    ans = {"users.who": a(["customer"]), "users.customer.signup": a("both"), "users.count": a("_unknown", "unknown"),
           "what.kind": a("new"), "what.replace.current": a(["paper"])}   # 부모(replace)가 아니므로 보이지 않는다
    md = ck.render_md(doc(ans), ck.tree(), "checklist_20300102_01")
    assert md.startswith("---\nform: nova-checklist") and "status: complete" in md
    assert "- 누가 쓰나요? (여러 개 선택) → **외부 고객**" in md
    assert "  - 고객 회원가입이 필요한가요? → **둘 다**" in md
    assert "지금은 무엇으로 하고 있나요?" not in md
    assert "사용자는 대략 몇 명인가요? → **건너뜀 · 나중에**" in md
    assert "STD-TENANCY-001" not in md.split("## 표준 판정 후보")[1]           # users.orgs 를 답하지 않았다
    md2 = ck.render_md(doc({**ans, "users.orgs": a("multi")}), ck.tree(), "checklist_20300102_01")
    assert "- STD-TENANCY-001: 여러 조직이 각자 쓴다" in md2.split("## 표준 판정 후보")[1]


def test_save_numbering_and_overwrite(repo):
    n1 = ck.save_doc(doc({"basic.name": a("매장")}, status="draft"))
    assert ck.FILE_RE.match(n1) and n1.endswith("_01")
    assert (ck.ck_dir() / f"{n1}.md").exists()
    n2 = ck.save_doc(doc({"basic.name": a("매장 2")}, status="draft", file=n1))   # 같은 세션 → 덮는다
    assert n2 == n1 and len(list(ck.ck_dir().glob("checklist_*.json"))) == 1
    n3 = ck.save_doc(doc({}, status="draft"))                                      # 새 세션 → 다음 번호
    assert n3.endswith("_02")
    with pytest.raises(ValueError):
        ck.save_doc(doc({"what.kind": a("없는보기")}))
    assert ck.main(["build"]) == 0
    assert ck.check() == []


def test_import_complete_only_and_idempotent(repo):
    ck.save_doc(doc({"basic.name": a("매장")}, status="draft"))
    assert ck.import_to_intake() == ("", 0, 0)                                     # 작성중은 반영 안 함
    p = ck.ck_dir() / "checklist_20300102_05.json"
    p.write_text(json.dumps(doc({"basic.name": a("매장"), "users.who": a(["staff"]), "users.count": a("_unknown", "unknown"),
                                 "what.kind": a("replace", "prefill")}), ensure_ascii=False), encoding="utf-8")
    rel, nf, ng = ck.import_to_intake()
    assert rel == "checklist/checklist_20300102_05.json" and nf == 2
    intake = wh.load("intake")
    texts = [g["question"] for g in intake["gaps"]]
    assert "사용자는 대략 몇 명인가요?" in texts and "어떤 일인가요?" in texts          # 모름 · 확인 전 → 부족 항목
    prd = next(f for f in intake["files"] if f["path"] == "prd/기획.md")
    assert prd["findings"][0]["id"] == "E-001"                                     # 다른 자료의 발견은 그대로
    mine = next(f for f in intake["files"] if f["path"] == rel)
    assert [e["id"] for e in mine["findings"]] == ["E-002", "E-003"]               # 번호는 이어서
    again = ck.import_to_intake()
    assert again == (rel, nf, ng) and len(wh.load("intake")["gaps"]) == len(intake["gaps"])   # 멱등
    assert wh.check_intake(wh.load("intake")) == []


def test_generated_files_are_not_inbound_material(repo):
    assert ck.main(["build"]) == 0
    ck.save_doc(doc({"basic.name": a("매장")}))
    seen = wh.inbound_files()
    assert "checklist/checklist.html" not in seen and not any(k.endswith(".md") for k in seen)
    assert any(k.endswith(".json") for k in seen)


def test_tree_v2_has_explanations_and_tech():
    """설명 · 기술 결정 · 원본 질의 반영(REQ-261104-04)."""
    t = ck.tree()
    qs, _, _ = ck.index(t)
    assert [lv["label"] for lv in t["levels"]] == ["기본", "자세히", "전문가"]
    feeds = {q["feeds"] for q in qs.values() if q.get("feeds")}
    for f in ("foundation.stack.frontend", "foundation.stack.backend", "foundation.stack.mobile", "foundation.architecture.style",
              "foundation.architecture.deploy", "foundation.database.engine", "foundation.database.migration",
              "standards.STD-TENANCY-001", "standards.STD-AX-001", "standards.STD-DOMAIN-PACK-001"):
        assert f in feeds, f
    cross = {q["feeds"].split(".", 2)[2] for q in qs.values() if q.get("feeds", "").startswith("foundation.crosscutting.")}
    assert cross == set(wh.CROSSCUT)                                               # 공통 기능 11종 = /foundation 매트릭스
    assert sum(1 for q in qs.values() if q.get("help")) >= 40 and len(t["glossary"]) >= 30
    sids = {s["id"] for s in t["sections"]}
    for sid in ("goal", "done", "auth", "design", "tech", "cross", "dev", "naming", "rules", "sec", "plan", "ops"):
        assert sid in sids, sid                                                    # 원본 섹션(목표 · 끝나는 자리 · 인증 · 디자인 · 개발 환경 · 이름 · 경계 · 보안 · 거버넌스 · 출하)


def test_rows_answers_and_skipped_sections(repo):
    t = ck.tree()
    good = {"scope.items": a([{"name": "예약 목록", "priority": "must"}])}
    assert ck.check_answers(good, t, "d") == []
    bad = {"scope.items": a([{"name": "x", "priority": "없음"}]), "scope.first": a([{"x": 1}])}
    errs = "\n".join(ck.check_answers(bad, t, "d"))
    assert "없는 보기 '없음'" in errs and "scope.first" in errs
    d = doc({"scope.items": a([{"name": "예약 목록", "priority": "must"}]), "tech.frontend": a("next")}, status="complete")
    d["skipped_sections"] = ["ai"]
    d["lv"] = 1                                                                    # 기본 단계로 낮춰도 답한 자세히 질문은 남는다
    md = ck.render_md(d, t, "checklist_20300102_01")
    assert "예약 목록 · 필수" in md and "## 건너뛴 섹션" in md and "- AI 기능" in md
    assert "`foundation.stack.frontend` — 화면(웹)은 무엇으로 만들까요? → Next.js + React" in md
    p = ck.ck_dir() / "checklist_20300102_07.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    ck.import_to_intake()
    gaps = wh.load("intake")["gaps"]
    assert any(g["question"] == "AI 기능을 쓰나요?" and "섹션을 건너뜀" in g["why"] for g in gaps)


def test_badges_must_be_explained():
    t = copy.deepcopy(ck.tree())
    t["sections"][0]["questions"][1]["options"][0]["rec"] = "뜻 없는 배지"
    assert any("badges" in e for e in ck.check_tree(t))


def test_color_question_and_design_md(repo):
    """디자인 — 색 견본 · 직접 지정 · 대비 계산 · md 디자인 결정 절(REQ-261104-05)."""
    t = ck.tree()
    assert round(ck.contrast("#FFFFFF", "#000000"), 1) == 21.0 and round(ck.contrast("#4F5BD5", "#FFFFFF"), 1) >= 4.5
    ok = {"design.color.main": a({"hex": "#2563EB", "preset": "blue", "text_hex": "#2563EB"})}
    assert ck.check_answers(ok, t, "d") == []
    bad = {"design.color.main": a({"hex": "파랑", "preset": ""}), "design.color.accent": a({"hex": "#FFFFFF", "preset": "없음"})}
    errs = "\n".join(ck.check_answers(bad, t, "d"))
    assert "#RRGGBB" in errs and "없는 견본" in errs
    d = doc({"design.color.main": a({"hex": "#FFD400", "preset": "", "text_hex": "#8A7300"}), "design.radius": a("round")})
    md = ck.render_md(d, t, "checklist_20300102_01")
    assert "## 디자인 결정" in md and "직접 지정 #FFD400 (흰 배경 글자 대비 1.4:1, 글자용 #8A7300 4.6:1)" in md
    qs, _, _ = ck.index(t)
    kinds = {o["preview"]["kind"] for q in qs.values() for o in q.get("options", []) if o.get("preview")}
    assert {"radius", "density", "font", "layout", "list", "text"} <= kinds


def test_gallery_ids_match_form_and_mockups(repo):
    """Nova 보기 갤러리 · 목업 채택표(REQ-261104-06) — 폼과 검사의 카드 ID 가 같고, 목업 목록이 입고와 맞는다."""
    import re as _re
    tpl = (ck.FORM_DIR / "template.html").read_text(encoding="utf-8")
    form_ids = set(_re.findall(r'\{ id: "([a-z]+)", t: "', tpl))
    assert form_ids == ck.GALLERY_IDS
    qs, _, _ = ck.index(ck.tree())
    assert {o["gallery"] for q in qs.values() for o in q.get("options", []) if o.get("gallery")} <= ck.GALLERY_IDS
    (ck.wh.WH / "inbound/html-mockup/mockup_예약.html").write_text("<h1>예약</h1>", encoding="utf-8")
    (ck.wh.WH / "inbound/screenshot/현행_목록.png").write_bytes(b"\x89PNG")
    assert ck.sync_mockups() == 2
    pre = json.loads(ck.prefill_path().read_text(encoding="utf-8"))
    assert [m["file"] for m in pre["mockups"]] == ["html-mockup/mockup_예약.html", "screenshot/현행_목록.png"]
    good = {"mockup.list": a({"html-mockup/mockup_예약.html": {"level": "all", "note": "전부"}})}
    assert ck.check_answers(good, ck.tree(), "d") == []
    assert ck.check_answers({"mockup.list": a({"x.html": {"level": "다"}})}, ck.tree(), "d")
    md = ck.render_md(doc({"mockup.have": a("yes"), **good}), ck.tree(), "checklist_20300102_01")
    assert "html-mockup/mockup_예약.html: 그대로 채택(전부)" in md
    (ck.wh.WH / "inbound/screenshot/현행_목록.png").unlink()
    assert ck.main(["build"]) == 0                                                 # build 는 만들고, 입고와 어긋남은 check 가 잡는다
    assert any("입고에 없는 파일" in e for e in ck.check())


def test_one_choice_rejects_list_value():
    """회귀 — 한 개 고르는 질문에 목록 값을 넣으면 오류(예전엔 list 가 `in opt` 에서 TypeError 또는 통과)."""
    errs = ck.check_answers({"what.kind": a(["new"])}, ck.tree(), "d")
    assert errs and "what.kind" in errs[0]
    assert ck.check_answers({"what.kind": a(["x"])}, ck.tree(), "d")


UI_INDEX = ROOT / "web" / "packages" / "ui" / "src" / "index.ts"
PARTS_USE_IDS = {"shell", "list", "form", "detail", "login", "confirm", "toast", "badge", "stat", "empty", "controls", "shortcut", "theme"}


def ui_exports() -> tuple[set, set]:
    """`@nova/ui` 내보내기 → (모든 값 이름, 화면 부품 이름).

    화면 부품 = 컴포넌트 · 템플릿(대문자로 시작하는 이름). 대상 밖: 타입(`type X`) · 훅(`use*`) ·
    공급자(`Providers`) · 서식 함수(`fmt*`) · 상수(`DEFAULT_SHORTCUTS` 같은 대문자 이름)."""
    import re as _re
    src = UI_INDEX.read_text(encoding="utf-8")
    names = set()
    for block in _re.findall(r"export\s*\{([^}]*)\}", src):
        for n in (x.strip() for x in block.split(",")):
            if n and not n.startswith("type "):
                names.add(n.split(" as ")[-1].strip())
    screen = {n for n in names if n[0].isupper() and not n.isupper() and n != "Providers"}
    return names, screen


def test_parts_match_ui_exports():
    """E3(REQ-261104-18-1) — `parts.use` 선택지의 부품 대응(`parts`)과 `@nova/ui` 내보내기가 빠짐없이 맞는다."""
    names, screen = ui_exports()
    assert len(screen) >= 30                                                      # 읽기가 깨져 빈 목록으로 통과하는 것을 막는다
    qs, _, _ = ck.index(ck.tree())
    opts = qs["parts.use"]["options"]
    assert PARTS_USE_IDS <= {o["id"] for o in opts}                               # 이미 받은 답이 ID 로 이어진다
    covered, errs = set(), []
    for o in opts:
        if not o.get("parts"):
            errs.append(f"{o['id']}: 부품 대응 칸(parts)이 없다")
        for p in o.get("parts", []):
            if p not in names:
                errs.append(f"{o['id']}: '{p}' 는 @nova/ui 내보내기에 없다")
            covered.add(p)
        if not o.get("group"):
            errs.append(f"{o['id']}: 분류(group)가 없다")
    errs += [f"@nova/ui 부품 '{p}' 를 덮는 선택지가 없다" for p in sorted(screen - covered)]
    assert errs == []
    assert {o["group"] for o in opts} >= {"틀", "버튼", "입력", "목록", "표시", "피드백", "차트", "도움말"}


# ───────────────────────── 표준 디자인 킷(REQ-261106-04-2)
def test_kit_question_options_come_from_catalog(repo):
    """보기는 tree.json 에 손으로 복제하지 않고 catalog.json 에서 채운다 — nova 가 Nova 기본 · 견본은 style(토큰 단계)."""
    raw = json.loads((ck.FORM_DIR / "tree.json").read_text(encoding="utf-8"))
    rq = next(q for s in raw["sections"] if s["id"] == "design" for q in s["questions"] if q["id"] == "design.kit")
    assert "options" not in rq and rq["options_from"] == "kits" and rq["feeds"] == "design.kit" and rq["type"] == "one"
    design = next(s for s in ck.tree()["sections"] if s["id"] == "design")
    assert design["questions"][0]["id"] == "design.kit"                            # 디자인 섹션 맨 앞
    q = design["questions"][0]
    assert [o["id"] for o in q["options"]] == ["nova", "newtype", "dim"]
    nova, newtype = q["options"][0], q["options"][1]
    assert nova["rec"] == "Nova 기본" and "rec" not in newtype
    assert newtype["preview"] == {"kind": "style", "value": "newtype", "hex": "#1F9D55", "radius": "sm", "gap": "3", "dark": True,
                                  "px": {"radius": 4.0, "gap": 12.0}}             # px 숫자 → 가장 가까운 토큰 단계
    assert "부품 2개" in newtype["warn"]
    qs, _, _ = ck.index(ck.tree())
    assert "kit" in {o["id"] for o in qs["design.source"]["options"]}            # 디자인 출처에 '표준 디자인 킷'
    assert ck.check_tree(ck.tree()) == []
    assert ck.main(["build"]) == 0 and '"newtype"' in ck.form_path().read_text(encoding="utf-8")


def test_kit_catalog_checks(repo):
    """catalog 이 없거나 · 갭이 parts.need 보기가 아니거나 · 토큰 파일이 없으면 check_tree 가 잡는다."""
    bad = copy.deepcopy(CATALOG)
    bad["kits"][1]["gaps"] = ["없는부품"]
    bad["kits"][2]["tokens"] = "없음.tokens.json"
    ck.KITS_CATALOG.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    errs = "\n".join(ck.check_tree(ck.tree()))
    assert "'없는부품' 는 parts.need" in errs and "없음.tokens.json" in errs
    ck.KITS_CATALOG.unlink()
    assert "킷 목록이 없거나 비었다" in "\n".join(ck.check_tree(ck.tree()))


def test_kit_md_line(repo):
    name = ck.save_doc(doc({"design.kit": a("newtype")}, status="draft"))
    md = (ck.ck_dir() / f"{name}.md").read_text(encoding="utf-8")
    line = next(x for x in md.splitlines() if "킷 결정" in x)
    assert "newtype — 초록 콘솔 (`newtype`)" in line and "작은 말풍선 창(팝오버), 기간 선택" in line
    assert "제출(완료) 뒤" in line and "/foundation 5단계에서 확인하고 필요하면 `python nova.py kit use <id>` 로 다시 설정" in line
    md2 = ck.render_md(doc({"design.kit": a("newtype")}), ck.tree(), "x")
    assert "체크리스트로 설정됨" in md2


def test_import_sets_kit_and_records_source(repo):
    p = ck.ck_dir() / "checklist_20300102_01.json"
    p.write_text(json.dumps(doc({"design.kit": a("newtype")}), ensure_ascii=False), encoding="utf-8")
    rel, nf, ng = ck.import_to_intake()
    meta = json.loads(ck.PROJECT_JSON.read_text(encoding="utf-8"))
    assert meta["design"] == {"kit": "newtype", "date": "2030-01-02", "by": "시험", "source": "checklist",
                              "origin": "checklist:checklist_20300102_01.json#design.kit"}
    assert KIT_CALLS == ["newtype"] and ck.LAST_KIT["ok"]
    intake = wh.load("intake")
    mine = next(f for f in intake["files"] if f["path"] == rel)
    assert any("표준 디자인 킷" in e["text"] and "체크리스트로 설정됨" in e["text"] for e in mine["findings"])
    assert "/foundation 5단계에서 확인" in mine["summary"]
    kit_gaps = [g for g in intake["gaps"] if g["origin"].startswith(f"{rel}#design.kit:")]
    assert sorted(g["origin"].rsplit(":", 1)[1] for g in kit_gaps) == ["daterange", "popover"]   # 킷 갭 → 부족 항목
    assert all(g["status"] == "열림" and g["why"] == "표준 디자인 킷 newtype 의 부품 갭(🗺)" for g in kit_gaps)
    assert ck.import_to_intake() == (rel, nf, ng) and len(wh.load("intake")["gaps"]) == len(intake["gaps"])   # 멱등
    assert wh.check_intake(wh.load("intake")) == []


def test_import_does_not_set_rejected_or_unknown_kit(repo):
    p = ck.ck_dir() / "checklist_20300102_01.json"
    p.write_text(json.dumps(doc({"design.kit": a("dim")}), ensure_ascii=False), encoding="utf-8")
    ck.import_to_intake()
    assert json.loads(ck.PROJECT_JSON.read_text(encoding="utf-8"))["design"] == {"kit": "nova"}   # 대비 미달 → 설정 안 함
    gap = next(g for g in wh.load("intake")["gaps"] if g["origin"].endswith("#design.kit:설정"))
    assert "설정하지 못함" in gap["why"] and "검사 미달" in gap["why"]
    p.write_text(json.dumps(doc({"design.kit": a("gone")}, updated="2030-01-03T00:00:00"), ensure_ascii=False), encoding="utf-8")
    KIT_CALLS.clear()
    ck.import_to_intake()
    assert KIT_CALLS == []                                                         # 목록에 없는 킷은 부르지도 않는다
    gap = next(g for g in wh.load("intake")["gaps"] if g["origin"].endswith("#design.kit:설정"))
    assert "킷 목록(catalog.json)에 없어" in gap["why"]
    p.write_text(json.dumps(doc({"design.kit": a("newtype", "prefill")}, updated="2030-01-04T00:00:00"), ensure_ascii=False), encoding="utf-8")
    KIT_CALLS.clear()
    ck.import_to_intake()
    assert KIT_CALLS == [] and ck.LAST_KIT is None                                 # 확인 전 답은 설정하지 않는다
