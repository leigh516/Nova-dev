"""결함 · 변경요청 원장(issues.py) · 교훈 원장(lessons.py) · 영향 조회(impact.py) — 임시 폴더를 ROOT 로."""
import json

import pytest

import impact
import issues
import lessons

FOUR = dict(repro="1) 목록 화면을 연다 2) 보관을 누른다", expected="항목이 보관된다",
            actual="500 오류 '내부 오류'", env="v0.1.0 / 로컬")


def add(root, title="보관 버튼 500 오류", kind="defect", grade="P1", today="2026-11-04", **kw):
    f = {**FOUR, **kw}
    return issues.add(root, kind=kind, grade=grade, title=title, today=today, **f)


# ───────────────────────── 접수 · 번호
@pytest.mark.parametrize("missing", ["repro", "expected", "actual", "env"])
def test_four_elements_reject_blank(tmp_path, missing):
    with pytest.raises(SystemExit) as e:
        add(tmp_path, **{missing: "   "})
    assert missing in str(e.value)
    assert not (tmp_path / "docs/issues/issues.json").exists()


def test_reject_bad_grade_and_kind(tmp_path):
    with pytest.raises(SystemExit):
        add(tmp_path, grade="긴급")
    with pytest.raises(SystemExit):
        add(tmp_path, kind="bug")
    with pytest.raises(SystemExit):
        add(tmp_path, title=" ")


def test_numbering_per_day(tmp_path):
    a, _ = add(tmp_path)
    b, _ = add(tmp_path, title="로그인 화면 글자 깨짐")
    c, _ = add(tmp_path, title="다른 날 결함", today="2026-11-05")
    assert (a["id"], b["id"], c["id"]) == ("ISS-261104-01", "ISS-261104-02", "ISS-261105-01")
    d = json.loads((tmp_path / "docs/issues/issues.json").read_text(encoding="utf-8"))
    assert [i["id"] for i in d["issues"]] == [a["id"], b["id"], c["id"]]
    assert a["status"] == "open"


def test_similar_open_title_warns_but_accepts(tmp_path):
    add(tmp_path, title="보관 버튼 500 오류")
    it, warns = add(tmp_path, title="목록 보관 버튼 500 오류")
    assert it["id"] == "ISS-261104-02"
    assert warns and "ISS-261104-01" in warns[0]
    _, warns2 = add(tmp_path, title="로그인 화면 글자 깨짐")
    assert warns2 == []


# ───────────────────────── P0 종결 게이트
def test_p0_close_needs_repro_test_and_postmortem(tmp_path):
    it, _ = add(tmp_path, grade="P0")
    with pytest.raises(SystemExit, match="repro-test"):
        issues.set_status(tmp_path, it["id"], "closed")
    with pytest.raises(SystemExit, match="없다"):  # 경로가 실재하지 않는다
        issues.set_status(tmp_path, it["id"], "closed", repro_test="tests/test_x.py::test_a",
                          postmortem="docs/issues/postmortem/pm.md")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_x.py").write_text("def test_a(): pass\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="postmortem"):
        issues.set_status(tmp_path, it["id"], "closed", repro_test="tests/test_x.py::test_a")
    (tmp_path / "docs/issues/postmortem").mkdir(parents=True)
    (tmp_path / "docs/issues/postmortem/pm.md").write_text("# 사후기록\n", encoding="utf-8")
    done = issues.set_status(tmp_path, it["id"], "closed", repro_test="tests/test_x.py::test_a",
                             postmortem="docs/issues/postmortem/pm.md")
    assert done["status"] == "closed"
    assert issues.check(issues.load(tmp_path), tmp_path, view=False) == []


def test_p0_defer_needs_human_approval(tmp_path):
    """L-F10 — P0 결함을 deferred 로 돌려 종결 게이트(재현 테스트 · 사후기록)를 우회하지 못한다.
    재현 불가 · 중복이라 정말 보류할 때는 사람 승인(--approved-by)을 남긴다. 손으로 고친 원장도 check 가 잡는다."""
    it, _ = add(tmp_path, grade="P0")
    with pytest.raises(SystemExit, match="approved-by"):
        issues.set_status(tmp_path, it["id"], "deferred")
    assert issues.load(tmp_path)["issues"][0]["status"] == "open"            # 거부되면 쓰지 않는다
    ok = issues.set_status(tmp_path, it["id"], "deferred", approved_by="한종열", today="2026-11-05")
    assert ok["status"] == "deferred" and ok["approved_by"] == "한종열" and ok["approved_at"] == "2026-11-05"
    hand = {"issues": [{"id": "ISS-261104-01", "kind": "defect", "grade": "P0", "status": "deferred", "title": "y", **FOUR}]}
    assert any("approved-by" in e for e in issues.check(hand, tmp_path, view=False))
    p1, _ = add(tmp_path, grade="P1", title="다른 결함")
    assert issues.set_status(tmp_path, p1["id"], "deferred")["status"] == "deferred"   # P1 이하는 그대로


def test_p1_closes_without_postmortem(tmp_path):
    it, _ = add(tmp_path, grade="P1")
    assert issues.set_status(tmp_path, it["id"], "closed")["status"] == "closed"


def test_unknown_id_and_status(tmp_path):
    it, _ = add(tmp_path)
    with pytest.raises(SystemExit):
        issues.set_status(tmp_path, "ISS-261104-99", "triaged")
    with pytest.raises(SystemExit):
        issues.set_status(tmp_path, it["id"], "done")


# ───────────────────────── change 승인 게이트
def test_change_approval_gates(tmp_path):
    it, _ = add(tmp_path, kind="change", grade="P2", title="항목 목록에 상태 필터 추가")
    cid = it["id"]
    assert issues.set_status(tmp_path, cid, "triaged")["status"] == "triaged"  # 승인 전 단계는 통과
    with pytest.raises(SystemExit, match="impact"):
        issues.set_status(tmp_path, cid, "in_progress", level="L2", approved_by="한종열")
    with pytest.raises(SystemExit, match="approved-by"):
        issues.set_status(tmp_path, cid, "in_progress", impact="1) 대상 …", level="L2")
    with pytest.raises(SystemExit, match="level"):
        issues.set_status(tmp_path, cid, "in_progress", impact="1) 대상 …", approved_by="한종열")
    with pytest.raises(SystemExit, match="ADR"):
        issues.set_status(tmp_path, cid, "in_progress", impact="1) 대상 …", level="L3", approved_by="한종열")
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "docs/adr/ADR-099-x.md").write_text("# 결정\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="ADR"):
        issues.set_status(tmp_path, cid, "in_progress", impact="1) 대상 …", level="L3",
                          approved_by="한종열", adr="docs/adr/ADR-000-없음.md")
    ok = issues.set_status(tmp_path, cid, "in_progress", impact="1) 대상 …", level="L3",
                           approved_by="한종열", adr="docs/adr/ADR-099-x.md")
    assert ok["status"] == "in_progress" and ok["approved_by"] == "한종열"
    assert issues.check(issues.load(tmp_path), tmp_path, view=False) == []


def test_failed_set_does_not_write(tmp_path):
    it, _ = add(tmp_path, kind="change", grade="P2")
    with pytest.raises(SystemExit):
        issues.set_status(tmp_path, it["id"], "in_progress", impact="영향")
    assert issues.load(tmp_path)["issues"][0]["status"] == "open"
    assert "impact" not in issues.load(tmp_path)["issues"][0] or not issues.load(tmp_path)["issues"][0]["impact"]


# ───────────────────────── check · render
def test_check_missing_file_is_ok(tmp_path):
    assert issues.check(issues.load(tmp_path), tmp_path) == []


def test_check_catches_hand_edits(tmp_path):
    bad = {"issues": [
        {"id": "ISS-1", "kind": "defect", "grade": "P9", "status": "open", "title": "x",
         "repro": "", "expected": "e", "actual": "a", "env": "v"},
        {"id": "ISS-261104-01", "kind": "defect", "grade": "P0", "status": "closed", "title": "y",
         **FOUR},
        {"id": "ISS-261104-02", "kind": "change", "grade": "P2", "status": "verifying", "title": "z",
         **FOUR},
    ]}
    errs = issues.check(bad, tmp_path, view=False)
    text = "\n".join(errs)
    for frag in ("ISS-1", "P9", "repro", "repro-test", "impact", "approved-by"):
        assert frag in text, frag


def test_render_view_and_sync_check(tmp_path):
    add(tmp_path, title="보관 버튼 500 오류")
    errs = issues.check(issues.load(tmp_path), tmp_path)
    assert any("render" in e for e in errs)  # 보기가 원장과 다르다
    issues.render(tmp_path)
    view = (tmp_path / "docs/issues/README.md").read_text(encoding="utf-8")
    assert "생성물 — scripts/issues.py render" in view
    assert "ISS-261104-01" in view and "보관 버튼 500 오류" in view
    assert issues.check(issues.load(tmp_path), tmp_path) == []
    # 설명 절은 보존하고 표 절만 바꾼다
    p = tmp_path / "docs/issues/README.md"
    p.write_text(view.replace("# 결함 · 변경요청", "# 결함 · 변경요청\n\n사람이 쓴 설명 한 줄"), encoding="utf-8")
    add(tmp_path, title="로그인 화면 글자 깨짐")
    issues.render(tmp_path)
    view2 = p.read_text(encoding="utf-8")
    assert "사람이 쓴 설명 한 줄" in view2 and "ISS-261104-02" in view2


def test_cli_add_and_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(issues, "ROOT", tmp_path)
    rc = issues.main(["add", "--kind", "defect", "--grade", "P2", "--title", "제목 하나",
                      "--repro", FOUR["repro"], "--expected", FOUR["expected"],
                      "--actual", FOUR["actual"], "--env", FOUR["env"]])
    assert rc == 0
    assert issues.main(["list", "--open"]) == 0
    out = capsys.readouterr().out
    assert "ISS-" in out and "제목 하나" in out
    assert issues.main(["check"]) == 0  # add 가 보기도 함께 다시 만든다


# ───────────────────────── 교훈 원장
LESSON_HEAD = "# 교훈 원장\n\n설명\n\n## 교훈\n"


def lessons_file(tmp_path, body):
    p = tmp_path / "docs/memo/lessons.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(LESSON_HEAD + body, encoding="utf-8")
    return p


def test_lessons_add_requires_ref(tmp_path):
    lessons_file(tmp_path, "")
    with pytest.raises(SystemExit):
        lessons.add(tmp_path, "트리거", "규칙", ref="어제 일")
    with pytest.raises(SystemExit):
        lessons.add(tmp_path, " ", "규칙", ref="REQ-261103-05")
    line = lessons.add(tmp_path, "긴 작업 뒤 영어로 미끄러짐", "문장마다 한국어 확인", ref="REQ-261103-05",
                       today="2026-11-04")
    assert line == "- [2026-11-04] 긴 작업 뒤 영어로 미끄러짐 → **문장마다 한국어 확인.** (근거: REQ-261103-05)"
    assert lessons.check(tmp_path) == []


@pytest.mark.parametrize("ref", ["REQ-261103-05", "ISS-261104-01", "history_261104_12", "review_261104_01", "ADR-008"])
def test_lessons_ref_formats(tmp_path, ref):
    lessons_file(tmp_path, "")
    lessons.add(tmp_path, f"트리거 {ref}", "규칙", ref=ref)
    assert lessons.check(tmp_path) == []


def test_lessons_check_format_and_promotion(tmp_path):
    lessons_file(tmp_path, "- 형식이 틀린 줄\n"
                           "- [2026-11-04] 트리거 → **규칙.** (근거: 어제)\n")
    errs = lessons.check(tmp_path)
    assert len(errs) == 2
    lessons_file(tmp_path, "- [2026-11-04] 같은 트리거 → **규칙 하나.** (근거: REQ-261103-05)\n"
                           "- [2026-11-05] 같은 트리거 → **규칙 둘.** (근거: ISS-261105-01)\n")
    assert any("승급 후보" in e for e in lessons.check(tmp_path))
    lessons_file(tmp_path, "- [2026-11-04] 같은 트리거 → **규칙 하나.** (근거: REQ-261103-05)\n"
                           "- [2026-11-05] 같은 트리거 → **규칙 둘.** (근거: ISS-261105-01) (승급 후보)\n")
    assert lessons.check(tmp_path) == []


def test_lessons_add_marks_promotion(tmp_path):
    lessons_file(tmp_path, "- [2026-11-04] 같은 트리거 → **규칙 하나.** (근거: REQ-261103-05)\n")
    line = lessons.add(tmp_path, "같은 트리거", "규칙 둘", ref="ISS-261105-01", today="2026-11-05")
    assert line.endswith("(승급 후보)")
    assert lessons.check(tmp_path) == []


def test_lessons_find(tmp_path):
    lessons_file(tmp_path, "- [2026-11-04] heredoc 줄바꿈 → **Edit 도구로.** (근거: history_261104_12)\n")
    assert len(lessons.find(tmp_path, "HEREDOC")) == 1
    assert lessons.find(tmp_path, "없는말") == []


def test_repo_lessons_ok():
    """저장소의 실제 교훈 원장이 형식을 지킨다."""
    assert lessons.check() == []


# ───────────────────────── 영향 조회
def test_impact_five_lines(tmp_path):
    reg = tmp_path / "docs/registry"
    reg.mkdir(parents=True)
    (reg / "screens.md").write_text("| 화면ID | 이름 | 사용 표 |\n|---|---|---|\n| SCR-WAPP-0005 | 항목 목록 | item |\n", encoding="utf-8")
    (reg / "db-dictionary.md").write_text("| 표 | 컬럼 |\n|---|---|\n| item | name |\n| member | name |\n", encoding="utf-8")
    (reg / "permissions.md").write_text("| 권한 |\n|---|\n| sample.read |\n", encoding="utf-8")
    (reg / "events.md").write_text("| 이벤트 |\n|---|\n| sample.item.created |\n", encoding="utf-8")
    svc = tmp_path / "packages/common-py/nova_common"
    svc.mkdir(parents=True)
    (svc / "services.json").write_text(json.dumps({"services": [{"name": "sample", "title": "샘플"}]}), encoding="utf-8")
    lines = impact.report(impact.analyze(["item"], root=tmp_path))
    text = "\n".join(lines)
    for head in ("1) 대상", "2) 직접", "3) 간접", "4) 등급", "5) 갱신"):
        assert sum(1 for l in lines if l.strip().startswith(head)) == 1, head
    assert "SCR-WAPP-0005" in text and "판정은 사람 몫" in text
    assert "L1~L2" in text or "L2~L3" in text
    # 아무 데도 없으면 L1
    none = "\n".join(impact.report(impact.analyze(["zzz없는말"], root=tmp_path)))
    assert "4) 등급 힌트: L1 " in none


def test_impact_cli_requires_keyword(capsys):
    with pytest.raises(SystemExit):
        impact.main([])
