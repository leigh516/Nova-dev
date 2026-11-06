"""응답 검사 훅(.claude/hooks/persona_guard.py) — 영어 문장 · 금지 첫머리를 잡고, 식별자 · 코드는 통과시키고, 되풀이를 막는다."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "persona_guard.py"
spec = importlib.util.spec_from_file_location("persona_guard", HOOK)
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)


def transcript(tmp_path, *assistant_texts, user="체크리스트를 고쳐 주세요"):
    lines = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "이전 요청의 답 — All checks pass."}]}},
             {"type": "user", "message": {"content": user}}]
    for t in assistant_texts:
        lines.append({"type": "assistant", "message": {"content": [{"type": "text", "text": t}, {"type": "tool_use", "name": "Bash"}]}})
        lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}})   # 도구 결과는 새 요청이 아니다
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines), encoding="utf-8")
    return p


def run(payload):
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    return json.loads(r.stdout) if r.stdout.strip() else None


def test_english_progress_note_is_blocked(tmp_path):
    p = transcript(tmp_path, "먼저 파일을 읽겠습니다.", "Two fixes are needed.", "All 9 steps passed.")
    out = run({"transcript_path": str(p)})
    assert out["decision"] == "block" and "Two fixes are needed." in out["reason"] and "한국어" in out["reason"]


def test_korean_with_identifiers_and_code_passes(tmp_path):
    p = transcript(tmp_path, "`python nova.py test` 를 돌렸습니다.\n```bash\nuv run pytest tests -q\nAll tests passed\n```",
                   "| 층 | 기술 |\n|---|---|\n| 화면 | Next.js + React + TypeScript |", "scripts/checklist.py build 결과입니다",
                   "Next.js + React")
    assert run({"transcript_path": str(p)}) is None


def test_previous_turn_is_not_counted(tmp_path):
    p = transcript(tmp_path, "모두 한국어로 답했습니다.")   # 이전 요청의 "All checks pass." 는 세지 않는다
    assert run({"transcript_path": str(p)}) is None


def test_forbidden_opening(tmp_path):
    p = transcript(tmp_path, "네, 알겠습니다. 바로 하겠습니다.")
    assert "첫머리" in run({"transcript_path": str(p)})["reason"]


def test_no_infinite_loop_and_never_crashes(tmp_path):
    p = transcript(tmp_path, "Two fixes are needed.")
    assert run({"transcript_path": str(p), "stop_hook_active": True}) is None   # 다시 쓰는 중이면 막지 않는다
    assert run({"transcript_path": str(tmp_path / "없음.jsonl")}) is None
    r = subprocess.run([sys.executable, str(HOOK)], input="깨진 입력", capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and not r.stdout.strip()


def test_hook_is_registered():
    s = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]]
    assert any("persona_guard.py" in c for c in cmds)


# ---- 도구 호출 전 검사(PreToolUse — REQ-261105-01) ----
def pretool_transcript(tmp_path, *segments):
    """요청 → (글 조각 → 도구 호출 → 도구 결과)… → 마지막 글 조각 → 지금 부르는 도구 호출(아직 결과 없음)."""
    lines = [{"type": "user", "message": {"content": "작업을 계속해주세요"}}]
    for i, t in enumerate(segments):
        lines.append({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}})
        lines.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}})
        if i < len(segments) - 1:
            lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}})
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines), encoding="utf-8")
    return p


def run_pre(payload):
    r = subprocess.run([sys.executable, str(HOOK), "--pretool"], input=json.dumps(payload, ensure_ascii=False),
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    return json.loads(r.stdout) if r.stdout.strip() else None


def _denied(out):
    return bool(out) and out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pretool_blocks_english_note_right_before_tool(tmp_path):
    p = pretool_transcript(tmp_path, "먼저 파일을 읽겠습니다.", "Now running the tests and then commit.")
    out = run_pre({"transcript_path": str(p), "tool_name": "Bash", "tool_input": {"command": "ls", "description": "목록을 봅니다"}})
    assert _denied(out) and out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Now running the tests" in reason and "한국어" in reason


def test_pretool_checks_only_latest_segment(tmp_path):
    # 앞 조각의 영어는 이미 도구 결과가 돌아온 뒤라 지금 호출을 막지 않는다(그 줄은 Stop 훅 몫) — 되풀이 차단 방지
    p = pretool_transcript(tmp_path, "Two fixes are needed now.", "이제 한국어로 다시 쓰고 진행하겠습니다.")
    assert run_pre({"transcript_path": str(p), "tool_name": "Bash", "tool_input": {"command": "ls"}}) is None


def test_pretool_blocks_english_description(tmp_path):
    p = pretool_transcript(tmp_path, "테스트를 돌리겠습니다.")
    out = run_pre({"transcript_path": str(p), "tool_name": "Bash",
                   "tool_input": {"command": "uv run pytest", "description": "Run the full test suite for the repo"}})
    assert _denied(out) and "description" in out["hookSpecificOutput"]["permissionDecisionReason"]
    ok = run_pre({"transcript_path": str(p), "tool_name": "Bash",
                  "tool_input": {"command": "uv run pytest", "description": "전체 테스트를 돌립니다"}})
    assert ok is None


def test_pretool_never_crashes(tmp_path):
    assert run_pre({"transcript_path": str(tmp_path / "없음.jsonl"), "tool_name": "Bash", "tool_input": {}}) is None
    r = subprocess.run([sys.executable, str(HOOK), "--pretool"], input="깨진 입력", capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and not r.stdout.strip()


def test_pretool_hook_is_registered():
    s = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for g in s["hooks"].get("PreToolUse", []) for h in g["hooks"]]
    # REQ-261105-07: PreToolUse 는 nova_hooks.py pretool 한 줄 — 그 안에서 persona_guard 판정을 같은 프로세스로 부른다
    assert any("nova_hooks.py" in c and c.endswith(" pretool") for c in cmds)
    src = (ROOT / ".claude/hooks/nova_hooks.py").read_text(encoding="utf-8")
    assert "persona_guard.py" in src and "pretool_verdict" in src


def test_pretool_reads_tail_of_large_transcript(tmp_path):
    # 큰 기록(덩어리 경계를 여러 번 넘는다)에서도 마지막 조각만 정확히 고른다
    p = pretool_transcript(tmp_path, *["앞선 작업을 했습니다. " + "가" * 3000] * 300, "Now running the tests and then commit.")
    texts = pg.latest_segment(p)
    assert texts == ["Now running the tests and then commit."]


def test_stop_skips_segment_already_denied_by_pretool(tmp_path):
    # 도구 호출 전 검사가 이미 막은 줄은 응답 끝 검사가 다시 잡지 않는다(같은 사과를 두 번 하지 않게 — T06-9.01)
    lines = [{"type": "user", "message": {"content": "작업을 계속해주세요"}},
             {"type": "assistant", "message": {"content": [{"type": "text", "text": "Now updating the style-map rows."}]}},
             {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
             {"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True,
                                                       "content": "PreToolUse:Bash hook error: [도구 호출 전 검사 — CLAUDE.md 규칙 0] …"}]}},
             {"type": "assistant", "message": {"content": [{"type": "text", "text": "죄송합니다. 대응표를 고치겠습니다."}]}}]
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines), encoding="utf-8")
    assert run({"transcript_path": str(p)}) is None
    # 막히지 않은 영어 줄은 그대로 잡는다
    lines[3]["message"]["content"][0]["content"] = "ok"
    lines[3]["message"]["content"][0]["is_error"] = False
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines), encoding="utf-8")
    assert run({"transcript_path": str(p)})["decision"] == "block"


def test_english_line_with_quoted_korean_word_is_caught():
    # 한글이 따옴표 안에만 있으면 영어 문장이다(T06-9.02) — 한국어 문장 속 영어 인용은 계속 통과
    assert pg.english_lines("The intent table row name must be '미해결'. Fixing that.")
    assert not pg.english_lines('앞 줄 "Now updating the style-map rows." 를 영어로 썼습니다.')
    assert not pg.english_lines("`python nova.py test` 를 돌렸습니다.")
