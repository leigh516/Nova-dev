#!/usr/bin/env python3
"""SOUL 진화 검토 — 사용자가 **같은 교정을 몇 번이나 다시 말했는가**를 세어 규칙 후보를 낸다(/soul-review).

  uv run python scripts/soul_review.py                       이 저장소의 Claude Code 대화 기록 전부
  uv run python scripts/soul_review.py --transcript <파일>    한 대화만
  uv run python scripts/soul_review.py --min-repeats 2 --json

🔴 SOUL · IDENTITY · USER · STYLE · MEMORY 를 **쓰지 않는다** — 감지는 자동, 반영은 사람 승인(ADR-007).
규칙(무엇을 교정으로 볼지)의 정본: .claude/soul/review-rules.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT  # noqa: E402

RULES = ROOT / ".claude" / "soul" / "review-rules.json"
WRAPPERS = ("<command-message>", "<command-name>", "<task-notification>", "<system-reminder>", "<local-command")


def transcripts_dir(root: Path = ROOT) -> Path:
    """Claude Code 가 이 저장소의 대화를 두는 곳 — 경로의 구분자를 '-' 로 바꾼 이름."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[:\\/]", "-", str(root))


def user_texts(path: Path) -> list[str]:
    """사람이 직접 쓴 말만(도구 결과 · 명령 감싸개 · 시스템 알림 제외)."""
    out = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if e.get("type") != "user" or e.get("isMeta"):
            continue
        c = (e.get("message") or {}).get("content")
        parts = [c] if isinstance(c, str) else [b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text"]
        for t in parts:
            t = (t or "").strip()
            if t and not t.startswith(WRAPPERS):
                out.append(t)
    return out


def review(paths: list[Path], rules: dict, min_repeats: int | None = None) -> list[dict]:
    need = min_repeats or rules.get("min_repeats", 3)
    texts = [(p.name, t) for p in paths for t in user_texts(p)]
    found = []
    for r in rules["rules"]:
        pats = [re.compile(x) for x in r["patterns"]]
        hits = [(f, t) for f, t in texts if any(p.search(t) for p in pats)]
        if len(hits) >= need:
            found.append({"id": r["id"], "label": r["label"], "target": r["target"], "count": len(hits),
                          "sessions": len({f for f, _ in hits}),
                          "quotes": [t[:90] for _, t in hits[:5]]})
    return sorted(found, key=lambda x: -x["count"])


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcript")
    ap.add_argument("--min-repeats", type=int)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    paths = [Path(a.transcript)] if a.transcript else sorted(transcripts_dir().glob("*.jsonl"))
    if not paths:
        print(f"대화 기록이 없다: {transcripts_dir()}")
        return 0
    found = review(paths, rules, a.min_repeats)
    if a.json:
        print(json.dumps(found, ensure_ascii=False, indent=2))
        return 0
    print(f"■ 대화 기록 {len(paths)}개 · 기준 {a.min_repeats or rules.get('min_repeats', 3)}회 이상")
    if not found:
        print("   반복 교정 후보 없음")
    for f in found:
        print(f"\n● {f['label']} — {f['count']}회(대화 {f['sessions']}개) → 반영 후보: {f['target']}")
        for q in f["quotes"]:
            print(f"   - \"{q}\"")
    print("\n※ 이 도구는 SOUL 파일을 고치지 않는다. 반영은 사용자 승인 후(/soul-review 절차).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
