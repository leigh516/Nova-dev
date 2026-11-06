"""도구 호출 훅 묶음(.claude/hooks/nova_hooks.py — REQ-261105-07).

막는 것은 둘뿐(비밀 읽기는 settings 의 permissions.deny, 저장소 파일에 셸로 쓰기는 pretool 판정)이고,
나머지(되돌림 · SOUL 편집 · 호출 기록 · 컨텍스트 임계 · 스냅샷 · 인계 주입)는 경고 · 기록만 한다.
거짓 거부(정상 명령이 막히는 것)가 이 훅의 가장 비싼 실패라 통과 사례를 거부 사례만큼 단언한다."""
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "nova_hooks.py"
spec = importlib.util.spec_from_file_location("nova_hooks", HOOK)
nh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nh)

R = "F:/project-nuri/Nova-dev"   # 판정 함수는 문자열만 본다 — 실제 폴더가 없어도 된다
SCRATCH = "C:/Users/han/AppData/Local/Temp/claude/bfc97f/b3e6/scratchpad"


def act(cmd, tool="Bash", cwd=R):
    v = nh.shell_write_verdict(cmd, cwd, R, tool)
    return v["action"] if v else None


# ---- 셸로 저장소 파일 쓰기(REQ-261105-07-2) — 거부 ----
@pytest.mark.parametrize("cmd", [
    "cat > docs/a.md <<'EOF'\n내용\nEOF",
    "cat <<EOF > scripts/x.py\nprint(1)\nEOF",
    "echo hi >> README.md",
    "printf x | tee docs/plans/tasks/tasks_REQ_07.md",
    "printf x | tee -a docs/a.md > /dev/null",
    "python -c \"open('docs/a.md','w').write('x')\"",
    "uv run python -c \"p='docs/a.md'; open(p, 'w').write('x')\"",
    "python - <<'EOF' < /dev/null\nfrom pathlib import Path\nPath('docs/a.md').write_text('x')\nEOF",
    "echo x > F:/project-nuri/Nova-dev/docs/a.md",
    "echo x > /f/project-nuri/Nova-dev/docs/a.md",
    "echo x > 'F:\\project-nuri\\Nova-dev\\docs\\a b.md'",
    "cd docs && echo x > a.md",
])
def test_denies_shell_write_into_repo(cmd):
    assert act(cmd) == "deny", cmd


@pytest.mark.parametrize("cmd", [
    "Set-Content -Path docs/a.md -Value x",
    "'x' | Out-File docs\\a.md -Encoding utf8",
    "Add-Content README.md 'x'",
    "[IO.File]::WriteAllText('F:/project-nuri/Nova-dev/docs/a.md', 'x')",
    "echo x > docs/a.md",
])
def test_denies_powershell_write_into_repo(cmd):
    assert act(cmd, tool="PowerShell") == "deny", cmd


# ---- 통과(오늘 이 저장소에서 정상으로 쓰인 명령) ----
@pytest.mark.parametrize("cmd", [
    "git status",
    "git commit -F - <<'EOF'\nfix(훅): sed -i 로 고친 것을 > docs/a.md 처럼 적은 본문\nEOF",
    "git commit -m \"$(cat <<'EOF'\n본문 > docs/a.md\nEOF\n)\"",
    "ls > /dev/null 2>&1",
    "uv run pytest tests/test_nova_hooks.py -q 2>&1 | tail -5",
    "python nova.py quick 2>&1",
    "echo x > \"$TEMP/a.txt\"",
    "echo x > $TMP/a.txt",
    f"cat > {SCRATCH}/a.py <<'EOF'\nopen('docs/a.md','w')\nEOF",
    f"cat > 'C:\\Users\\han\\AppData\\Local\\Temp\\claude\\x\\scratchpad\\b.py' <<'EOF'\nx\nEOF",
    "sed -n 1,20p docs/a.md",
    "grep -n \"a > b.md\" docs/a.md",
    "awk '$1 > 3' docs/a.txt",
    "python -c \"import json; print(json.load(open('nova.project.json'))['name'])\"",
    "python -c \"print(open('docs/a.md', encoding='utf-8').read()[:100])\"",
    "python nova.py issue add --observe \"sed -i 로 > docs/a.md 덮음\"",
    "echo x > .pytest_tmp/log.txt",
    "echo x > .git/COMMIT_MSG_TMP",
    "dir > nul",
    "[ 3 -gt 2 ] && echo ok",
    "for f in docs/*.md; do wc -l \"$f\"; done",
    "cd C:/Users/han/elsewhere && echo x > a.txt",
    "git diff --stat > /dev/null; git log --oneline -3",
    "cat docs/a.md | grep -c x <<< 'y'",
    "",
])
def test_passes_normal_commands(cmd):
    assert act(cmd) is None, cmd


def test_passes_powershell_reads():
    assert act("Get-Content docs/a.md | Select-Object -First 5", tool="PowerShell") is None
    assert act("git status > $null", tool="PowerShell") is None


def test_escape_hatch_turns_deny_into_warn():
    assert act("NOVA_SHELL_WRITE=1 echo x > docs/a.md") == "warn"


def test_sed_in_place_on_repo_file_is_warning_not_deny():
    v = nh.shell_write_verdict("sed -i 's/- \\[ \\]/- [x]/' docs/plans/tasks/tasks_REQ_07.md", R, R, "Bash")
    assert v["action"] == "warn" and "Edit" in v["message"]
    assert act(f"sed -i 's/a/b/' {SCRATCH}/x.txt") is None   # 저장소 밖은 말하지 않는다


def test_deny_message_says_what_and_alternative_in_korean():
    v = nh.shell_write_verdict("echo hi >> README.md", R, R, "Bash")
    assert "README.md" in v["message"] and "Edit" in v["message"] and "Write" in v["message"]
    assert "스크래치" in v["message"] and nh.HANGUL.search(v["message"])


# ---- 되돌림 경고(REQ-261105-07-3) ----
DIRTY = ["docs/a.md", "scripts/b.py", "docs/sub/c.md"]


@pytest.mark.parametrize("cmd,hit", [
    ("git checkout -- docs/a.md", ["docs/a.md"]),
    ("git checkout HEAD -- docs/", ["docs/a.md", "docs/sub/c.md"]),
    ("git checkout .", DIRTY),
    ("git restore scripts/b.py", ["scripts/b.py"]),
    ("git reset --hard HEAD", DIRTY),
    ("git status && git checkout -- docs/*.md", ["docs/a.md"]),
])
def test_revert_hits_dirty_files(cmd, hit):
    assert nh.revert_hits(cmd, DIRTY, "") == hit


@pytest.mark.parametrize("cmd", [
    "git checkout main", "git checkout -b feat/x", "git restore --staged docs/a.md",
    "git checkout -- README.md", "git reset HEAD~1", "git status",
])
def test_revert_ignores_safe_commands(cmd):
    assert nh.revert_hits(cmd, DIRTY, "") == []


def test_revert_respects_subdir_cwd():
    assert nh.revert_hits("git checkout -- a.md", DIRTY, "docs") == ["docs/a.md"]


def test_parse_porcelain_z():
    out = " M docs/a.md\0?? new.txt\0R  new/name.py\0old/name.py\0MM scripts/b.py\0"
    assert nh.parse_porcelain_z(out) == ["docs/a.md", "new/name.py", "scripts/b.py"]


# ---- 훅 실행(subprocess) 도우미 ----
def run_hook(event, payload, root, env=None):
    e = {**os.environ, "CLAUDE_PROJECT_DIR": str(root), **(env or {})}
    raw = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    r = subprocess.run([sys.executable, str(HOOK), event], input=raw, capture_output=True, text=True,
                       encoding="utf-8", env=e, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


def jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_pretool_denies_shell_write_end_to_end(tmp_path):
    out = run_hook("pretool", {"tool_name": "Bash", "cwd": str(tmp_path),
                               "tool_input": {"command": "echo x > docs/a.md", "description": "파일 쓰기"}}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "docs/a.md" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_pretool_passes_git_status_silently(tmp_path):
    assert run_hook("pretool", {"tool_name": "Bash", "cwd": str(tmp_path),
                                "tool_input": {"command": "git status", "description": "상태 보기"}}, tmp_path) is None


def test_pretool_keeps_persona_check(tmp_path):
    """기존 persona_guard --pretool 의미 유지 — 영어 도구 설명은 같은 프로세스에서 거부된다."""
    out = run_hook("pretool", {"tool_name": "Bash", "cwd": str(tmp_path),
                               "tool_input": {"command": "git status", "description": "Now running the tests and then commit."}},
                   tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert nh.PERSONA.PRETOOL_MARK in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_pretool_sed_warns_without_deny(tmp_path):
    out = run_hook("pretool", {"tool_name": "Bash", "cwd": str(tmp_path),
                               "tool_input": {"command": "sed -i 's/a/b/' docs/a.md", "description": "치환"}}, tmp_path)
    assert "permissionDecision" not in out["hookSpecificOutput"]
    assert "Edit" in out["hookSpecificOutput"]["additionalContext"]


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


def test_pretool_revert_warns_and_logs(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "--allow-empty", "-m", "첫")
    (tmp_path / "a.txt").write_text("원본", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "둘")
    (tmp_path / "a.txt").write_text("미커밋 수정", encoding="utf-8")
    out = run_hook("pretool", {"tool_name": "Bash", "cwd": str(tmp_path), "session_id": "s1",
                               "tool_input": {"command": "git checkout -- a.txt", "description": "되돌리기"}}, tmp_path)
    ctx = out["hookSpecificOutput"]
    assert "permissionDecision" not in ctx and "a.txt" in ctx["additionalContext"]
    rec = jsonl(tmp_path / ".claude/state/revert_events.jsonl")
    assert rec[-1]["hit"] == ["a.txt"] and rec[-1]["command"] == "git checkout -- a.txt"


# ---- 기록: SOUL 편집 · 에이전트 · 스킬 · 명령(REQ-261105-07-4 · 5) ----
def test_posttool_logs_soul_edit_only(tmp_path):
    run_hook("posttool", {"tool_name": "Edit", "session_id": "s1",
                          "tool_input": {"file_path": str(tmp_path / ".claude" / "soul" / "STYLE.md")}}, tmp_path)
    run_hook("posttool", {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "docs/a.md")}}, tmp_path)
    rec = jsonl(tmp_path / ".claude/state/soul_edits.jsonl")
    assert len(rec) == 1 and rec[0]["file"] == ".claude/soul/STYLE.md" and rec[0]["tool"] == "Edit"


def test_posttool_logs_agent_and_skill(tmp_path):
    run_hook("posttool", {"tool_name": "Agent", "session_id": "s1",
                          "tool_input": {"subagent_type": "devops-engineer", "description": "훅 구현", "prompt": "긴 지시"}}, tmp_path)
    run_hook("posttool", {"tool_name": "Skill", "tool_input": {"skill": "nova-screen"}}, tmp_path)
    a = jsonl(tmp_path / ".claude/state/agent_runs.jsonl")
    assert a[0]["subagent_type"] == "devops-engineer" and a[0]["description"] == "훅 구현" and "prompt" not in a[0]
    s = jsonl(tmp_path / ".claude/state/skill_usage.jsonl")
    assert s[0]["kind"] == "skill" and s[0]["name"] == "nova-screen"


def test_prompt_logs_slash_command_only(tmp_path):
    run_hook("prompt", {"prompt": "/session-end 마무리해 주세요", "session_id": "s1"}, tmp_path)
    run_hook("prompt", {"prompt": "그냥 질문입니다 /path/는 명령이 아님", "session_id": "s1"}, tmp_path)
    s = jsonl(tmp_path / ".claude/state/skill_usage.jsonl")
    assert [(x["kind"], x["name"]) for x in s] == [("command", "session-end")]


def test_usage_summary_counts_recent_days():
    now = datetime(2026, 11, 5, 12, 0, 0)
    old = (now - timedelta(days=30)).isoformat(timespec="seconds")
    recs = {"agent": [{"ts": now.isoformat(), "subagent_type": "x"}, {"ts": old, "subagent_type": "x"}],
            "skill": [{"ts": now.isoformat(), "kind": "command", "name": "task-run"},
                      {"ts": now.isoformat(), "kind": "command", "name": "task-run"},
                      {"ts": now.isoformat(), "kind": "skill", "name": "nova-screen"}]}
    s = nh.summarize_usage(recs, days=7, now=now)
    assert s == {"명령": {"task-run": 2}, "스킬": {"nova-screen": 1}, "에이전트": {"x": 1}}


# ---- 호출 기록 원장(REQ-261105-08-3) — 기계 로컬 기록을 회차마다 커밋되는 JSONL 로 ----
def _state(root, agents=(), skills=()):
    st = root / ".claude/state"
    st.mkdir(parents=True, exist_ok=True)
    (st / "agent_runs.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in agents), encoding="utf-8")
    (st / "skill_usage.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in skills), encoding="utf-8")


def _agent_def(root, folder, name):
    d = root / ".claude/agents" / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(f"---\nname: {name}\ndescription: 시험\ntools: Read\n---\n# {name}\n", encoding="utf-8")


def test_usage_record_appends_one_line(tmp_path):
    at = datetime(2026, 11, 5, 12, 0, 0)
    _state(tmp_path, agents=[{"ts": at.isoformat(), "subagent_type": "code-reviewer"}] * 2,
           skills=[{"ts": at.isoformat(), "kind": "command", "name": "task-run"}])
    rec = nh.record_usage(tmp_path, days=7, by="tester", at=at)
    nh.record_usage(tmp_path, days=7, by="tester", at=at)
    lines = jsonl(tmp_path / "docs/memo/agent_usage.jsonl")
    assert len(lines) == 2 and lines[0] == rec
    assert rec["days"] == 7 and rec["by"] == "tester" and rec["ts"] == "2026-11-05T12:00:00"
    assert rec["counts"] == {"명령": {"task-run": 1}, "에이전트": {"code-reviewer": 2}}


def test_usage_record_keeps_empty_period(tmp_path):
    """기록이 없는 기간도 한 줄 남긴다 — '안 불렀다'도 판정 재료다."""
    _state(tmp_path)
    rec = nh.record_usage(tmp_path, days=7, by="tester", at=datetime(2026, 11, 5))
    assert rec["counts"] == {} and len(jsonl(tmp_path / "docs/memo/agent_usage.jsonl")) == 1


def test_usage_unused_lists_never_called_agents(tmp_path):
    for folder, name in (("quality", "code-reviewer"), ("research", "project-starter"), ("meta", "agent-creator")):
        _agent_def(tmp_path, folder, name)
    (tmp_path / ".claude/agents/README.md").write_text("# 편제\n", encoding="utf-8")   # 정의가 아니다
    memo = tmp_path / "docs/memo"
    memo.mkdir(parents=True)
    (memo / "agent_usage.jsonl").write_text(
        json.dumps({"ts": "2026-11-05T12:00:00", "counts": {"에이전트": {"code-reviewer": 3}}}, ensure_ascii=False) + "\n"
        + "깨진 줄\n"
        + json.dumps({"ts": "2026-11-06T12:00:00", "counts": {"에이전트": {"agent-creator": 1}}}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    assert nh.unused_agents(tmp_path) == ["project-starter"]


def test_usage_unused_without_ledger_is_everyone(tmp_path):
    _agent_def(tmp_path, "quality", "code-reviewer")
    assert nh.unused_agents(tmp_path) == ["code-reviewer"]


# ---- 컨텍스트 임계(REQ-261105-07-6) ----
def usage_transcript(path, tokens, pad=0):
    lines = [json.dumps({"type": "user", "message": {"content": "가" * 1000}}, ensure_ascii=False)] * pad
    lines.append(json.dumps({"type": "assistant", "message": {"usage": {
        "input_tokens": 10, "cache_read_input_tokens": tokens - 10, "cache_creation_input_tokens": 0}}}))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_context_tokens_reads_tail_of_large_transcript(tmp_path):
    p = usage_transcript(tmp_path / "t.jsonl", 150_000, pad=2000)   # 수 MB — 끝에서만 읽는다
    assert nh.context_tokens(p) == 150_000


def test_context_threshold_advises_once(tmp_path):
    p = usage_transcript(tmp_path / "t.jsonl", 130_000)
    env = {"NOVA_HANDOFF_PERCENT": "60", "NOVA_CONTEXT_WINDOW": "200000"}
    out = run_hook("prompt", {"prompt": "계속", "session_id": "s9", "transcript_path": str(p)}, tmp_path, env)
    assert "/session-end" in out["hookSpecificOutput"]["additionalContext"]
    assert run_hook("prompt", {"prompt": "계속", "session_id": "s9", "transcript_path": str(p)}, tmp_path, env) is None


def test_context_below_threshold_is_silent(tmp_path):
    p = usage_transcript(tmp_path / "t.jsonl", 50_000)
    env = {"NOVA_HANDOFF_PERCENT": "60", "NOVA_CONTEXT_WINDOW": "200000"}
    assert run_hook("prompt", {"prompt": "계속", "session_id": "s8", "transcript_path": str(p)}, tmp_path, env) is None


def test_context_window_guess_grows_past_default():
    assert nh.context_percent(150_000, 200_000) == 75
    assert nh.context_percent(300_000, 200_000) == 30   # 기본 창보다 크면 1M 창으로 본다


# ---- 실제 창 크기 — statusLine 입력을 원천으로(REQ-261105-07 추가 요청 2026-11-06) ----
def status_payload(sid, size, pct):
    return {"session_id": sid, "context_window": {"context_window_size": size, "used_percentage": pct}}


def test_statusline_records_window_per_session(tmp_path):
    nh.record_statusline(status_payload("s1", 1_000_000, 12), tmp_path)
    nh.record_statusline(status_payload("s2", 200_000, 40), tmp_path)
    assert nh.recorded_window(tmp_path, "s1") == 1_000_000
    assert nh.recorded_window(tmp_path, "s2") == 200_000
    assert nh.recorded_window(tmp_path, "없음") is None


def test_statusline_ignores_payload_without_window(tmp_path):
    nh.record_statusline({"session_id": "s3"}, tmp_path)
    assert nh.recorded_window(tmp_path, "s3") is None


def test_prompt_uses_recorded_window_no_false_alarm(tmp_path):
    """1M 세션에서 130k 를 써도(실제 13%) 권고하지 않는다 — 200k 고정 분모의 거짓 경보(65%)를 막는다."""
    nh.record_statusline(status_payload("big", 1_000_000, 13), tmp_path)
    p = usage_transcript(tmp_path / "t.jsonl", 130_000)
    assert run_hook("prompt", {"prompt": "계속", "session_id": "big", "transcript_path": str(p)}, tmp_path, {}) is None


def test_prompt_recorded_window_still_advises_when_full(tmp_path):
    nh.record_statusline(status_payload("small", 200_000, 70), tmp_path)
    p = usage_transcript(tmp_path / "t.jsonl", 140_000)   # 200k 의 70% ≥ 기본 임계 65
    out = run_hook("prompt", {"prompt": "계속", "session_id": "small", "transcript_path": str(p)}, tmp_path, {})
    assert "약 70%(임계 65%)" in out["hookSpecificOutput"]["additionalContext"]


def test_default_threshold_is_65(tmp_path):
    p = usage_transcript(tmp_path / "t.jsonl", 126_000)   # 추정 분모 200k 로 63% — 기본 임계 65 아래
    env = {"NOVA_CONTEXT_WINDOW": "200000"}
    assert run_hook("prompt", {"prompt": "계속", "session_id": "s7", "transcript_path": str(p)}, tmp_path, env) is None


def test_statusline_chain_command_skips_self(tmp_path):
    """원래 statusLine(사용자 전역 설정)을 이어 부르되, 자기 자신이면 고르지 않는다(무한 호출 방지)."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps({"statusLine": {"type": "command", "command": "orca-statusline.cmd"}}), encoding="utf-8")
    assert nh.chain_command(home, {}) == "orca-statusline.cmd"
    assert nh.chain_command(home, {"NOVA_STATUSLINE_CHAIN": "다른것"}) == "다른것"
    (home / ".claude" / "settings.json").write_text(json.dumps({"statusLine": {"command": "python nova_hooks.py statusline"}}), encoding="utf-8")
    assert nh.chain_command(home, {}) is None
    assert nh.chain_command(tmp_path / "없는집", {}) is None


def test_statusline_line_without_chain():
    assert nh.status_text(status_payload("s", 1_000_000, 16.4)) == "컨텍스트 16% · 창 1M"
    assert nh.status_text({}) == ""


# ---- 스냅샷 · 인계 주입(REQ-261105-07-7 · 8) ----
def _project(tmp_path):
    (tmp_path / "docs/session").mkdir(parents=True)
    (tmp_path / "docs/plans/tasks").mkdir(parents=True)
    (tmp_path / "docs/session/LATEST.md").write_text("# 인수인계 2026-11-05\n\n" + "다음 할 일 줄\n" * 500, encoding="utf-8")
    (tmp_path / "docs/plans/tasks/tasks_REQ_01.md").write_text("- [x] 끝남\n", encoding="utf-8")
    (tmp_path / "docs/plans/tasks/tasks_REQ_02.md").write_text("- [x] 끝남\n- [ ] 남음\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("event", ["precompact", "sessionend"])
def test_snapshot_copies_handoff_and_open_tasks(tmp_path, event):
    root = _project(tmp_path)
    assert run_hook(event, {"session_id": "s1"}, root) is None
    snaps = list((root / ".claude/state/backups").iterdir())
    assert len(snaps) == 1
    files = sorted(p.relative_to(snaps[0]).as_posix() for p in snaps[0].rglob("*") if p.is_file())
    assert files == ["docs/plans/tasks/tasks_REQ_02.md", "docs/session/LATEST.md"]


def test_snapshot_prunes_old_backups(tmp_path):
    base = tmp_path / "b"
    for i in range(25):
        (base / f"20261105-0000{i:02d}-precompact").mkdir(parents=True)
    nh.prune_backups(base, keep=20)
    left = sorted(p.name for p in base.iterdir())
    assert len(left) == 20 and left[0] == "20261105-000005-precompact"


def test_sessionstart_injects_handoff_head(tmp_path):
    root = _project(tmp_path)
    out = run_hook("sessionstart", {"session_id": "s1", "source": "startup"}, root)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "인수인계 2026-11-05" in ctx and len(ctx) <= nh.HANDOFF_HEAD_CHARS + 300


def test_sessionstart_without_handoff_is_silent(tmp_path):
    assert run_hook("sessionstart", {"session_id": "s1"}, tmp_path) is None


# ---- 고장이면 통과(fail-open) ----
@pytest.mark.parametrize("event", ["pretool", "posttool", "prompt", "precompact", "sessionend", "sessionstart", "모르는이벤트"])
def test_fail_open_on_broken_input(tmp_path, event):
    assert run_hook(event, "깨진 입력 {", tmp_path) is None


# ---- 배선 · 물려받기 ----
def test_settings_wiring():
    s = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    cmds = lambda ev: [h["command"] for g in s["hooks"].get(ev, []) for h in g["hooks"]]
    pre = cmds("PreToolUse")
    assert len(pre) == 1 and "nova_hooks.py" in pre[0] and pre[0].endswith(" pretool")   # 이벤트마다 파이썬 한 번
    for ev, arg in [("PostToolUse", "posttool"), ("UserPromptSubmit", "prompt"), ("PreCompact", "precompact"),
                    ("SessionEnd", "sessionend"), ("SessionStart", "sessionstart")]:
        assert any("nova_hooks.py" in c and c.endswith(" " + arg) for c in cmds(ev)), ev
    assert any(c.startswith("echo") for c in cmds("UserPromptSubmit")) and any(c.startswith("echo") for c in cmds("SessionStart"))
    deny = set(s["permissions"]["deny"])
    for pat in ["Read(./.env)", "Read(./.env.*)", "Read(./**/.env)", "Read(./**/.env.*)",
                "Read(./**/*.key)", "Read(./**/*.pem)", "Read(./**/credentials.json)"]:
        assert pat in deny, pat


def test_state_dir_is_gitignored():
    assert ".claude/state/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
