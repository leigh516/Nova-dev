"""SOUL 레이어(ADR-007) — 자동 로딩 · /soul-review 가 반복 교정을 세고 SOUL 파일을 쓰지 않음 · 새 프로젝트 PROJECT.md."""
import hashlib
import json
from pathlib import Path

import soul_review as sr

ROOT = Path(__file__).resolve().parents[1]
SOUL_FILES = [ROOT / "SOUL.md", ROOT / "IDENTITY.md"] + [ROOT / ".claude/soul" / f for f in ("USER.md", "STYLE.md", "MEMORY.md")]


def test_claude_md_imports_soul_layer():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for imp in ("@SOUL.md", "@IDENTITY.md", "@.claude/soul/USER.md", "@.claude/soul/STYLE.md"):
        assert f"\n{imp}\n" in text, imp
    for f in SOUL_FILES:
        assert f.exists() and "한국어" in f.read_text(encoding="utf-8") or f.name in ("IDENTITY.md", "MEMORY.md"), f


def test_soul_review_counts_repeats_and_never_writes(tmp_path):
    before = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in SOUL_FILES}
    lines = []
    for t in ("모든 대화를 한국어로 해주세요", "대화를 한국어로 해주세요", "한국어로 해주세요 규칙입니다", "체크리스트를 고쳐 주세요"):
        lines.append({"type": "user", "message": {"content": t}})
        lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "content": "한국어로 결과"}]}})   # 도구 결과는 세지 않는다
    lines.append({"type": "user", "message": {"content": "<command-message>한국어로</command-message>"}})               # 명령 감싸개도 세지 않는다
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines), encoding="utf-8")
    rules = json.loads(sr.RULES.read_text(encoding="utf-8"))
    found = sr.review([p], rules)
    ko = next(f for f in found if f["id"] == "korean")
    assert ko["count"] == 3 and ko["sessions"] == 1
    assert sr.main(["--transcript", str(p)]) == 0
    assert {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in SOUL_FILES} == before   # SOUL 파일을 쓰지 않는다


def test_transcripts_dir_naming():
    assert sr.transcripts_dir(Path("F:/project-nuri/Nova-dev")).name == "F--project-nuri-Nova-dev"
