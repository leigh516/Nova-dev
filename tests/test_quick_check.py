"""빠른 검사(quick_check) — 바뀐 파일 · 단계 task 에서 돌릴 테스트 · lint 단계를 고르는 규칙 (REQ-261104-17-1)."""
import quick_check as q


def test_changed_test_file_is_selected_itself():
    assert "tests/test_goals.py" in q.select_tests(["tests/test_goals.py"])


def test_script_change_selects_tests_that_import_it():
    # goals.py 를 import 하는 테스트가 골라져야 한다(실제 저장소 파일로 확인)
    picked = q.select_tests(["scripts/goals.py"])
    assert "tests/test_audit_r1_fixes.py" in picked


def test_service_change_selects_that_service_tests():
    picked = q.select_tests(["services/sample/sample/items.py"])
    assert "services/sample/tests" in picked


def test_docs_only_change_selects_no_tests_but_docs_lint():
    assert q.select_tests(["docs/plans/README.md"]) == []
    assert "docs_index" in q.select_lint(["docs/plans/README.md"])


def test_lint_mapping_by_area():
    assert "gen_tokens" in q.select_lint(["design/tokens/brand.tokens.json"])
    assert "claude_check" in q.select_lint([".claude/commands/task-run.md"])
    assert "gen_k3s" in q.select_lint(["packages/common-py/nova_common/services.json"])


def test_stage_tests_read_from_tasks_section():
    text = (
        "## 1단계 · 앞\n- [ ] T09-1.01 일 (tests/test_a.py::test_x 통과)\n"
        "## 2단계 · 뒤\n- [ ] T09-2.01 일 (`tests/test_b.py::test_y` · services/sample/tests/test_m.py 통과)\n"
        "  - 파일: 테스트 `packages/common-py/tests/test_c.py`\n"
        "## 3단계 · 다음\n- [ ] T09-3.01 (tests/test_z.py)\n"
    )
    assert q.stage_tests(text, 2) == [
        "tests/test_b.py::test_y", "services/sample/tests/test_m.py", "packages/common-py/tests/test_c.py"]


def test_group_by_run_root():
    groups = q.group_by_root(["tests/test_a.py", "services/sample/tests", "services/sample/tests/test_m.py::t",
                              "packages/common-py/tests/test_c.py"])
    # 공통 라이브러리 테스트는 저장소 테스트와 한 프로세스에서 섞으면 전역 상태(서비스 연결 대체 · 포트)가 엉킨다
    # — 전체 test 와 같은 경계로 따로 돌린다(2026-11-04 quick 첫 실측에서 통합 테스트 5건 실패로 드러남)
    assert groups["."] == ["tests/test_a.py"]
    assert groups["packages/common-py"] == ["packages/common-py/tests/test_c.py"]
    assert groups["services/sample"] == ["tests"]


def test_template_service_change_goes_to_new_service_test():
    """_template 은 자리표시(__PKG__)가 든 원본 — 그 폴더에서 돌리지 않고 템플릿으로 만들어 보는 테스트로."""
    picked = q.select_tests(["services/_template/__PKG__/models.py", "services/_template/tests/test_migrations.py"])
    assert picked == ["tests/test_new_service.py"]


def test_folder_already_selected_drops_its_children():
    groups = q.group_by_root(["services/sample/tests/test_m.py", "services/sample/tests", "tests/test_a.py"])
    assert groups["services/sample"] == ["tests"]


def test_whole_file_selected_drops_its_single_tests():
    groups = q.group_by_root(["tests/test_a.py", "tests/test_a.py::test_x", "tests/test_b.py::test_y"])
    assert groups["."] == ["tests/test_a.py", "tests/test_b.py::test_y"]


GOOD = (
    "## 1단계 · 끝난 단계\n- [x] T09-1.01 옛 일 (tests/test_a.py 통과)\n  - [x] 커밋 `feat: 옛 형식`\n"
    "## 2단계 · 새 단계\n- [ ] T09-2.01 일 (tests/test_b.py::test_y 통과)\n"
    "  - [ ] 실패 테스트 작성 → `uv run pytest tests/test_b.py::test_y` 실패 확인\n  - [ ] 최소 구현 → 같은 명령 통과 확인\n"
    "- [ ] T09-2.02 문서 고치기 (문서 검사 통과)\n\n"
    "**단계 관문**: `python nova.py quick --stage T09-2` → 전체 `python nova.py check` → 커밋 묶음 · 푸시\n"
    "## 작업 중 발견 (단계와 별개)\n- [ ] 🆕 T09-9.01 무엇 (재현 · 기대)\n"
)


def test_tasks_check_accepts_stage_gate_format():
    assert q.check_tasks(GOOD, "t.md") == []


def test_tasks_check_requires_stage_gate_for_code_stage():
    text = GOOD.replace("**단계 관문**", "단계 끝")
    errs = q.check_tasks(text, "t.md")
    assert any("2단계" in e and "단계 관문" in e for e in errs)


def test_tasks_check_rejects_commit_subline_in_open_task():
    text = GOOD.replace("  - [ ] 최소 구현 → 같은 명령 통과 확인\n",
                        "  - [ ] 최소 구현 → 같은 명령 통과 확인\n  - [ ] 커밋 `feat: x` · `git_record.py`\n")
    assert any("T09-2.01" in e and "커밋" in e for e in q.check_tasks(text, "t.md"))


def test_tasks_check_requires_test_path_for_tdd_task():
    text = GOOD.replace("(tests/test_b.py::test_y 통과)", "(통과)").replace(
        "`uv run pytest tests/test_b.py::test_y`", "`uv run pytest`")
    assert any("T09-2.01" in e and "테스트 경로" in e for e in q.check_tasks(text, "t.md"))


def test_tasks_check_accepts_bare_test_name():
    """경로 없이 함수 이름만 적어도 된다 — 관문이 테스트 폴더에서 def 를 찾아 경로로 바꾼다."""
    text = GOOD.replace("(tests/test_b.py::test_y 통과)", "(test_quick_named_only 통과)").replace(
        "`uv run pytest tests/test_b.py::test_y`", "`uv run pytest`")
    assert q.check_tasks(text, "t.md") == []


def test_stage_tests_resolve_bare_names_to_paths():
    text = "## 1단계 · 이름만\n- [ ] T09-1.01 일 (test_whole_file_selected_drops_its_single_tests 통과)\n"
    assert q.stage_tests(text, 1) == ["tests/test_quick_check.py::test_whole_file_selected_drops_its_single_tests"]


def test_tasks_check_rejects_inline_commit_in_open_task():
    text = GOOD.replace("  - [ ] 최소 구현 → 같은 명령 통과 확인\n", "  - [ ] 최소 구현 → 통과 · [ ] 커밋\n")
    assert any("T09-2.01" in e and "커밋" in e for e in q.check_tasks(text, "t.md"))


def test_tasks_check_accepts_kmp_test_names():
    """코틀린 테스트(…Test.kt · kmp-test)도 테스트 표기다 — pytest 관문이 모으지 않을 뿐 형식 위반은 아니다."""
    text = GOOD.replace("(tests/test_b.py::test_y 통과)", "(BackStackTest.kt 통과)").replace(
        "`uv run pytest tests/test_b.py::test_y`", "`gradlew`")
    assert q.check_tasks(text, "t.md") == []


def test_basetemp_is_unique_per_process():
    """여러 세션 · 담당이 동시에 quick 을 돌리면 같은 임시 폴더를 서로 지운다(2026-11-04 실측 — WinError 32).
    폴더 이름에 프로세스 번호를 넣는다."""
    import os
    a = q.basetemp(0)
    assert str(os.getpid()) in a.name and a.parent.name == ".pytest_tmp"
    assert q.basetemp(0) != q.basetemp(1)


def test_data_file_change_selects_owner_script_tests():
    """데이터 원천(naming.json · 토큰 · services.json …)을 바꾸면 그것을 읽는 스크립트의 테스트도 고른다
    — 2026-11-04 naming.json 예외 추가가 quick 을 통과하고 전체 test 에서야 test_naming 7건으로 드러남."""
    assert "tests/test_naming.py" in q.select_tests(["registry/naming.json"])
    assert "tests/test_ledgers.py" in q.select_tests(["registry/ledgers.json"])
    assert any("test_catalog" in t for t in q.select_tests(["packages/common-py/nova_common/services.json"]))


def test_root_conftest_does_not_select_whole_repo():
    """루트 conftest.py 가 바뀌었다고 저장소 전체(`.`)를 한 pytest 로 돌리면 이름이 같은 테스트 파일(test_migrations.py 셋)이
    부딪힌다(2026-11-04 import file mismatch). 루트 conftest 는 그것을 지키는 테스트로 보낸다."""
    picked = q.select_tests(["conftest.py"])
    assert "." not in picked and "" not in picked
    assert "tests/test_pytest_tmp.py" in picked
    assert q.select_tests(["tests/conftest.py"]) == ["tests"]
