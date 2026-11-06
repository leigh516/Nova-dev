"""에이전트 · 스킬 정의 검사(scripts/claude_check.py) — 규칙마다 잘못된 정의를 실제로 잡는지, 지금 저장소가 통과하는지."""
from pathlib import Path

import claude_check as cc

ROOT = Path(__file__).resolve().parents[1]

GOOD_AGENT = """---
name: {name}
description: 저장소 코드와 문서를 넓게 조사해야 할 때 부른다 — 결론과 근거만 짧게 돌려주고 원자료는 메인 컨텍스트에 싣지 않는다.
tools: {tools}
---

# {name} — 조사

## 언제 나를 부르나
- 조사가 필요할 때. 이어서 [규칙](../../../docs/rules.md) 을 본다

## 따르는 규칙
- [규칙](../../../docs/rules.md)

## 수행 절차
1. 읽는다
2. 잰다

## 반환 형식
- 핵심 답 · 실측 · 근거(`파일:줄`) · 미해결(없으면 '없음')

## 하지 않는 것
- `docs_new.py` · `git_record.py` · `git commit` · `git push` 는 하지 않는다(main 이 한다)

## 실패·불확실 처리
- 모르면 판정 불가로 남긴다
"""


def guess_folder(name: str) -> str:
    """시험용 — 이름으로 폴더를 고른다(실제 편제와 같은 규칙)."""
    if name.endswith("-specialist"):
        return "domain"
    if name.endswith(("-auditor", "-reviewer", "-tester", "-guardian")) or name in ("tester", "verifier"):
        return "quality"
    if name.endswith("-writer"):
        return "docs"
    return "research"


QUICK = "\n" + cc.QUICK_HEADING + "\n| 상황 | 에이전트 |\n|---|---|\n"


def make_repo(tmp: Path, name: str = "researcher", tools: str = "Read, Grep, Glob, Bash", body: str | None = None,
              folder: str | None = None) -> Path:
    (tmp / "docs").mkdir(parents=True, exist_ok=True)
    (tmp / "docs" / "rules.md").write_text("# 규칙\n", encoding="utf-8")
    ag = tmp / ".claude" / "agents"
    d = ag / (folder if folder is not None else guess_folder(name))
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(body or GOOD_AGENT.format(name=name, tools=tools), encoding="utf-8")
    cmd = tmp / ".claude" / "commands"
    cmd.mkdir(parents=True, exist_ok=True)
    (cmd / "intake.md").write_text(f"# /intake\n1. `{name}` 에이전트에게 맡긴다\n", encoding="utf-8")
    (ag / "README.md").write_text("# 에이전트\n" + QUICK + "\n## 편제표\n" + cc.ROSTER_START + "\n" + cc.ROSTER_END + "\n", encoding="utf-8")
    cc.write_readme(tmp)
    return tmp


def errs(root: Path) -> list[str]:
    return cc.check(root)[0]


def has(rule: str, root: Path) -> bool:
    return any(e.startswith(rule + " ") for e in errs(root))


def test_good_repo_passes(tmp_path):
    root = make_repo(tmp_path)
    assert errs(root) == []


def test_A1_unknown_frontmatter_key(tmp_path):
    body = GOOD_AGENT.format(name="researcher", tools="Read, Bash").replace("tools:", "color: blue\ntools:")
    assert has("A1", make_repo(tmp_path, body=body))


def test_A1_missing_required_key(tmp_path):
    body = GOOD_AGENT.format(name="researcher", tools="Read, Bash").replace("tools: Read, Bash\n", "")
    assert has("A1", make_repo(tmp_path, body=body))


def test_A2_name_must_match_stem(tmp_path):
    body = GOOD_AGENT.format(name="other-name", tools="Read, Bash")
    assert has("A2", make_repo(tmp_path, name="researcher", body=body))


def test_A3_description_english_or_short_or_no_trigger(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    old = base.split("\n")[2]
    for bad in ("description: Researches the codebase when needed and returns a summary to the main agent only.",
                "description: 조사할 때 부른다",
                "description: 저장소 코드와 문서를 넓게 조사하고 결론과 근거만 짧게 돌려주며 원자료는 메인 컨텍스트에 싣지 않는 역할이다.",
                "description: 저장소 코드와 문서를 넓게 조사해야 할 때 부른다 — use proactively. 결론과 근거만 돌려준다."):
        root = make_repo(tmp_path / str(abs(hash(bad))), body=base.replace(old, bad))
        assert has("A3", root), bad


def test_A4_unknown_tool(tmp_path):
    assert has("A4", make_repo(tmp_path, tools="Read, Grepp, Bash"))


def test_A5_judge_cannot_write(tmp_path):
    root = make_repo(tmp_path, name="security-auditor", tools="Read, Grep, Bash, Edit")
    assert has("A5", root)
    # 폴더 정책 — planning/ 은 이름과 상관없이 읽기 전용
    root2 = make_repo(tmp_path / "b", name="task-planner", tools="Read, Write, Bash", folder="planning")
    assert has("A5", root2)


def test_A6_judge_needs_bash(tmp_path):
    assert has("A6", make_repo(tmp_path, name="code-reviewer", tools="Read, Grep"))


def test_A6_A5_not_applied_to_writer(tmp_path):
    root = make_repo(tmp_path, name="doc-writer", tools="Read, Write, Edit")
    assert not has("A5", root) and not has("A6", root)


def test_A7_section_order(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    swapped = base.replace("## 수행 절차", "## 임시").replace("## 따르는 규칙", "## 수행 절차").replace("## 임시", "## 따르는 규칙")
    assert has("A7", make_repo(tmp_path, body=swapped))
    missing = base.replace("## 실패·불확실 처리", "## 기타")
    assert has("A7", make_repo(tmp_path / "b", body=missing))


def test_A8_return_four_parts(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    assert has("A8", make_repo(tmp_path, body=base.replace(" · 미해결(없으면 '없음')", "")))


def test_A9_forbidden_command_outside_dont_section(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    for cmd in ("git_record.py", "registry.py sync", "masterplan adopt", "release ship", "git push"):
        bad = base.replace("2. 잰다", f"2. `{cmd}` 를 돌린다")
        assert has("A9", make_repo(tmp_path / cmd.replace(" ", "_"), body=bad)), cmd
    # '하지 않는 것' 절 안은 허용 — 좋은 정의가 이미 거기 적는다
    assert not has("A9", make_repo(tmp_path / "ok", body=base))


def test_A10_broken_link_and_unknown_command(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    assert has("A10", make_repo(tmp_path, body=base.replace("../../../docs/rules.md)", "../../../docs/nope.md)", 1)))
    assert has("A10", make_repo(tmp_path / "b", body=base.replace("1. 읽는다", "1. `/nope-command` 를 부른다")))
    # 있는 명령은 통과
    ok = base.replace("1. 읽는다", "1. `/intake` 뒤 `/issue` 로 남긴다")
    root = make_repo(tmp_path / "c", body=ok)
    (root / ".claude" / "commands" / "issue.md").write_text("# /issue\n결함 접수\n", encoding="utf-8")
    assert not has("A10", root)


def test_A11_command_calls_undefined_agent(tmp_path):
    root = make_repo(tmp_path)
    (root / ".claude" / "commands" / "debug.md").write_text("# /debug\n`ghost-agent` 에이전트에 맡긴다\n", encoding="utf-8")
    assert has("A11", root)


def test_A11_unused_agent_is_warning_only(tmp_path):
    root = make_repo(tmp_path)
    (root / ".claude" / "commands" / "intake.md").write_text("# /intake\n직접 읽는다\n", encoding="utf-8")
    cc.write_readme(root)
    e, w = cc.check(root)
    assert e == [] and any("researcher" in x for x in w)


def test_A12_roster_must_match(tmp_path):
    root = make_repo(tmp_path)
    readme = root / ".claude" / "agents" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("| 조사 |", "| 판정 |"), encoding="utf-8")
    assert has("A12", root)
    cc.write_readme(root)
    assert not has("A12", root)


def test_A13_color_literal(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    assert has("A13", make_repo(tmp_path, body=base.replace("2. 잰다", "2. 색은 #1a2b3c 로")))


def test_A14_user_called_nova(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    assert has("A14", make_repo(tmp_path, body=base.replace("2. 잰다", "2. 우선순위는 Nova 가 정한다")))


def test_A15_model_value(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    assert has("A15", make_repo(tmp_path, body=base.replace("tools:", "model: gpt\ntools:")))
    assert not has("A15", make_repo(tmp_path / "b", body=base.replace("tools:", "model: sonnet\ntools:")))


# ───────────────────────── 스킬
SKILL = """---
name: {name}
description: 화면 한 벌을 조립할 때 쓴다 — 템플릿 호출과 데이터 정의만으로 끝낸다.
{extra}---

# {name}

정본: `docs/rules.md` · [참고](references/ref.md)
{body}
"""


def make_skill(root: Path, name: str = "nova-x", extra: str = "", body: str = "", ref: str = "# 참고\n한글\n") -> Path:
    d = root / ".claude" / "skills" / name
    (d / "references").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(SKILL.format(name=name, extra=extra, body=body), encoding="utf-8")
    (d / "references" / "ref.md").write_text(ref, encoding="utf-8")
    return root


def skill_has(rule: str, root: Path) -> bool:
    return any(e.startswith(rule + " ") for e in cc.skill_errors(root))


def test_skill_good(tmp_path):
    root = make_skill(make_repo(tmp_path))
    assert cc.skill_errors(root) == []


def test_S1_name_must_match_folder(tmp_path):
    root = make_repo(tmp_path)
    make_skill(root, name="nova-x")
    p = root / ".claude" / "skills" / "nova-x" / "SKILL.md"
    p.write_text(p.read_text(encoding="utf-8").replace("name: nova-x", "name: nova-y"), encoding="utf-8")
    assert skill_has("S1", root)


def test_S2_canon_skill_bans_values(tmp_path):
    for bad in ("버튼 색은 #ffcc00", "여백 16px", "대비 4.5:1 이상"):
        root = make_skill(make_repo(tmp_path / str(abs(hash(bad)))), extra="canon: design-system\n", body=bad)
        assert skill_has("S2", root), bad
    # 같은 줄 allowlist-canon 사유가 있으면 허용
    root = make_skill(make_repo(tmp_path / "ok"), extra="canon: design-system\n",
                      body="대비 4.5:1 이상 <!-- allowlist-canon: WCAG 기준 인용 -->")
    assert not skill_has("S2", root)
    # canon 선언이 없으면 검사하지 않는다
    assert not skill_has("S2", make_skill(make_repo(tmp_path / "free"), body="여백 16px"))
    # references 도 검사한다
    root = make_skill(make_repo(tmp_path / "ref"), extra="canon: design-system\n", ref="# 참고\n여백 8px\n")
    assert skill_has("S2", root)


def test_S3_paths_and_links_exist(tmp_path):
    assert skill_has("S3", make_skill(make_repo(tmp_path), body="그리고 `scripts/nope.py` 를 본다"))
    assert skill_has("S3", make_skill(make_repo(tmp_path / "b"), body="[없는](references/none.md)"))
    # 자리표시 · 와일드카드는 건너뛴다
    ok = "`docs/plans/<REQ>/x.html` · `docs/registry/*.md` · `docs/plans/drafts/master_plan_vX.Y-draft.md`"
    assert not skill_has("S3", make_skill(make_repo(tmp_path / "c"), body=ok))
    # 템플릿이 있는 산출물(`_template_<이름>`)은 생길 파일로 본다
    root = make_repo(tmp_path / "d")
    (root / "docs" / "product").mkdir(parents=True)
    (root / "docs" / "product" / "_template_prd.json").write_text("{}", encoding="utf-8")
    assert not skill_has("S3", make_skill(root, body="`docs/product/prd.json`"))


def test_S4_md_without_hangul(tmp_path):
    root = make_skill(make_repo(tmp_path), ref="# Reference\nEnglish only\n")
    assert skill_has("S4", root)


# ───────────────────────── 지금 저장소
def test_repo_passes():
    e, _w = cc.check(ROOT)
    assert e == [], "\n".join(e)


def test_repo_core_roster_by_folder():
    agents = cc.load_agents(ROOT)
    # 폴더형 편제(ADR-010) — 핵심 42개(psg05 역할 40 + Nova docs-auditor · ops-auditor) + 도메인 팩마다 하나씩
    core = [a for a in agents if a.folder != "domain"]
    assert len(core) == 42
    assert {a.folder for a in core} == set(cc.FOLDERS) - {"domain"}
    assert all(a.folder == "domain" for a in agents if a.name.endswith(cc.DOMAIN_SUFFIX))
    readme = (ROOT / ".claude" / "agents" / "README.md").read_text(encoding="utf-8")
    for a in agents:
        assert f"`{a.name}`" in readme


def test_A17_domain_agent_needs_its_pack_and_is_read_only(tmp_path):
    """도메인 에이전트(<팩>-specialist) — 짝 팩이 없으면 실패, 있으면 통과, 판정자라 쓰기 도구는 실패."""
    root = make_repo(tmp_path, name="shop-specialist")
    assert has("A17", root)
    (root / "packs" / "shop").mkdir(parents=True)
    (root / "packs" / "shop" / "pack.json").write_text('{"name": "shop"}', encoding="utf-8")
    assert not has("A17", root)
    # 명령이 이름으로 부르지 않아도 경고하지 않는다(명령은 '<팩>-specialist' 로 부른다)
    assert not any("shop-specialist" in w for w in cc.check(root)[1])
    root2 = make_repo(tmp_path / "w", name="shop-specialist", tools="Read, Write, Bash")
    assert has("A5", root2)
    # domain/ 밖의 -specialist · domain/ 안의 다른 이름은 실패
    assert has("A17", make_repo(tmp_path / "x", name="shop-specialist", folder="quality"))
    assert has("A17", make_repo(tmp_path / "y", name="researcher", folder="domain"))


def test_pack_template_renders_valid_agent(tmp_path):
    """packs/_template/agent.md 틀로 만든 에이전트가 모든 규칙을 통과한다(틀이 낡으면 여기서 잡는다)."""
    tpl = (ROOT / "packs" / "_template" / "agent.md").read_text(encoding="utf-8")
    body = tpl.replace("__AGENT__", "shop-specialist").replace("__PACK__", "shop").replace("__TITLE__", "쇼핑")
    root = make_repo(tmp_path, name="shop-specialist", body=body)
    for rel in ("CLAUDE.md", "docs/std/STD-DOMAIN-PACK-001.md", "docs/conventions/naming.md",
                "docs/conventions/ux-heuristics.md", "docs/conventions/glossary.md"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("# 문서\n", encoding="utf-8")
    for c in ("req-analyze", "plan-new", "task-run", "review-request", "req-interview"):
        (root / ".claude" / "commands" / f"{c}.md").write_text(f"# /{c}\n", encoding="utf-8")
    (root / "packs" / "shop").mkdir(parents=True)
    (root / "packs" / "shop" / "pack.json").write_text('{"name": "shop"}', encoding="utf-8")
    cc.write_readme(root)
    assert errs(root) == []


def test_A17_underscore_pack_maps_to_hyphen_agent(tmp_path):
    """팩 이름의 밑줄은 에이전트 이름에서 하이픈(demo_x → demo-x-specialist) — 실제 new-pack 에서 걸렸던 자리."""
    root = make_repo(tmp_path, name="demo-x-specialist")
    (root / "packs" / "demo_x").mkdir(parents=True)
    (root / "packs" / "demo_x" / "pack.json").write_text('{"name": "demo_x"}', encoding="utf-8")
    assert not has("A17", root) and not has("A2", root)


def test_A18_definition_must_live_in_a_known_folder(tmp_path):
    assert has("A18", make_repo(tmp_path, folder=""))              # 루트에 정의
    assert has("A18", make_repo(tmp_path / "b", folder="misc"))    # 정해지지 않은 폴더


def test_A2_duplicate_name_across_folders(tmp_path):
    root = make_repo(tmp_path)
    d = root / ".claude" / "agents" / "planning"
    d.mkdir(parents=True)
    (d / "researcher.md").write_text(GOOD_AGENT.format(name="researcher", tools="Read, Bash"), encoding="utf-8")
    cc.write_readme(root)
    assert any(e.startswith("A2 이름 중복") for e in errs(root))


def test_ops_writers_only(tmp_path):
    ok = make_repo(tmp_path, name="release-manager", tools="Read, Write, Edit, Bash", folder="ops")
    assert not has("A5", ok)
    bad = make_repo(tmp_path / "b", name="change-manager", tools="Read, Write, Bash", folder="ops")
    assert has("A5", bad)


def test_A16_group_line_is_rejected(tmp_path):
    base = GOOD_AGENT.format(name="researcher", tools="Read, Bash")
    assert has("A16", make_repo(tmp_path, body=base.replace("## 언제 나를 부르나", "> 묶음: 조사\n\n## 언제 나를 부르나")))


def test_A11_retired_name_and_skill_calls(tmp_path):
    root = make_repo(tmp_path)
    (root / ".claude" / "commands" / "debug.md").write_text("# /debug\n`synthesizer` 에이전트에 맡긴다\n", encoding="utf-8")
    assert any("폐지된" in e for e in errs(root))
    # 스킬 SKILL.md 의 호출도 센다 — 명령이 안 불러도 경고가 없다
    root2 = make_repo(tmp_path / "s")
    (root2 / ".claude" / "commands" / "intake.md").write_text("# /intake\n직접 읽는다\n", encoding="utf-8")
    sk = root2 / ".claude" / "skills" / "demo"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: demo\ndescription: 시험 스킬이다\n---\n# 시험\n`researcher` 에이전트에 맡긴다\n", encoding="utf-8")
    cc.write_readme(root2)
    e, w = cc.check(root2)
    assert e == [] and not any("researcher" in x for x in w)


def test_A19_quick_table(tmp_path):
    root = make_repo(tmp_path)
    readme = root / ".claude" / "agents" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("|---|---|\n", "|---|---|\n| 조사 | `ghost-researcher` |\n", 1), encoding="utf-8")
    assert has("A19", root)
    readme.write_text(readme.read_text(encoding="utf-8").replace(cc.QUICK_HEADING, "## 다른 제목"), encoding="utf-8")
    assert has("A19", root)
