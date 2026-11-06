#!/usr/bin/env python3
"""응답 검사 훅(Stop) — 응답이 끝날 때 STYLE.md 의 기계로 잴 수 있는 규칙을 검사하고, 어기면 다시 쓰게 한다.

검사(이번 사용자 메시지 뒤에 Claude 가 쓴 글 전부 — 진행 알림 한 줄 포함):
  ① 한국어 규칙(CLAUDE.md 규칙 0): 한글이 하나도 없는 영어 문장 줄
  ② 쓰지 않는 첫머리: "물론입니다" · "당연히 도와드리겠습니다" · "네, 알겠습니다" · "좋은 질문입니다"
코드 블록 · `인라인 코드` · 주소 · 경로 · 표의 구분 줄은 검사하지 않는다(식별자 · 명령은 영어 그대로 허용).

`--pretool`(PreToolUse — REQ-261105-01): 도구를 부르기 **직전**에 같은 판정(english_lines)으로 다음을 본다.
  · 마지막 도구 결과 뒤에 쓴 글 조각(지금 호출 바로 앞의 진행 알림) · 도구 설명(tool_input.description)
  걸리면 그 호출을 거부(deny)하고 이유를 돌려준다. 거부도 도구 결과로 남으므로 다음 호출은 새 조각만 본다(되풀이 차단 없음).
  응답이 끝날 때까지 기다리면 그 사이 줄이 이미 화면에 쌓인다 — 가장 자주 미끄러지는 자리가 도구 사이 한 줄이다.

끝없는 되풀이를 막는다: 이미 이 훅 때문에 다시 쓰는 중(stop_hook_active)이면 막지 않는다.
어떤 오류가 나도 세션을 막지 않는다(조용히 통과) — 막으면 사람이 훅을 꺼 버린다.
입력: Claude Code Stop 훅 JSON(stdin) — transcript_path · stop_hook_active
출력: 막을 때만 {"decision": "block", "reason": "..."}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FORBIDDEN_OPENINGS = ("물론입니다", "당연히 도와드리겠습니다", "네, 알겠습니다", "좋은 질문입니다")
PRETOOL_MARK = "[도구 호출 전 검사"   # pretool_verdict 가 내는 거부 이유의 머리 — 같은 문구를 아래에서 쓴다
HANGUL = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
WORD = re.compile(r"[A-Za-z][A-Za-z']+")
# 영어 문장을 가르는 기능어 — 식별자만 늘어놓은 줄(예: "Next.js + React")은 걸리지 않게 한다
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "to", "of", "and", "or", "for", "with", "this", "that",
    "it", "its", "i", "i'll", "i'm", "we", "we'll", "let", "let's", "now", "next", "then", "all", "not", "no", "will",
    "need", "needed", "here", "there", "so", "but", "if", "on", "in", "at", "as", "by", "from", "into", "done",
    "passed", "pass", "fails", "failed", "found", "fix", "fixed", "check", "checks", "looks", "good", "you", "your",
}
CODE_FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")
QUOTED = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|“[^”\n]*”|‘[^’\n]*’")
URL = re.compile(r"https?://\S+")
PATHLIKE = re.compile(r"(?:[\w.-]+[/\\])+[\w.*-]+|\b[\w-]+\.(?:py|md|json|tsx?|kt|html|ya?ml|css|sh|txt)\b")


def english_lines(text: str) -> list[str]:
    """한글이 없고 영어 문장으로 보이는 줄.

    한글은 따옴표 · 인라인 코드 **밖에서** 찾는다 — "… must be '미해결'. Fixing that." 처럼 인용 낱말 하나 때문에
    영어 문장이 빠져나가지 않게(T06-9.02). 한국어 문장 속 영어 인용은 바깥에 한글이 있으므로 그대로 통과한다."""
    text = CODE_FENCE.sub("\n", text)
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or re.fullmatch(r"[|:\-\s]+", line):
            continue
        if HANGUL.search(QUOTED.sub(" ", INLINE.sub(" ", line))):
            continue
        clean = PATHLIKE.sub(" ", URL.sub(" ", INLINE.sub(" ", line)))
        words = [w.lower() for w in WORD.findall(clean)]
        stop = sum(w in STOPWORDS for w in words)
        if (len(words) >= 4 and stop >= 1) or (len(words) >= 3 and stop >= 2):   # 이름 나열("Next.js + React")은 통과
            out.append(line[:120])
    return out


def assistant_texts(transcript: Path) -> list[str]:
    """마지막 사용자 메시지(도구 결과가 아닌 것) 뒤에 Claude 가 쓴 글 조각들.

    도구 호출 전 검사(--pretool)가 이미 거부한 호출 바로 앞의 조각은 뺀다 — 그 자리에서 사과 · 재작성을 마쳤으므로
    응답 끝에 같은 줄을 다시 잡으면 같은 사과를 두 번 하게 된다(T06-9.01)."""
    texts: list[str] = []
    pending: list[str] = []   # 마지막 도구 결과 뒤의 조각 — 다음 도구 결과가 거부인지 보고 넘긴다
    for raw in transcript.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        msg = e.get("message") or {}
        content = msg.get("content")
        if e.get("type") == "user":
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
            if any(isinstance(b, dict) and b.get("type") == "text" for b in blocks) and not e.get("isMeta"):
                texts, pending = [], []   # 새 사용자 요청 — 여기서부터 센다
            elif any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
                if not any(PRETOOL_MARK in str(b.get("content", "")) for b in blocks if isinstance(b, dict)):
                    texts += pending
                pending = []
        elif e.get("type") == "assistant" and isinstance(content, list):
            pending += [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return texts + pending


def _tail_entries(transcript: Path, chunk: int = 256 * 1024):
    """기록 파일을 끝에서부터 거꾸로 낸다(새 것 먼저). 세션 기록은 수십 MB 라 처음부터 읽으면 도구마다 2초가 붙는다."""
    size = transcript.stat().st_size
    with transcript.open("rb") as f:
        end, rest = size, b""
        while end > 0:
            start = max(0, end - chunk)
            f.seek(start)
            buf = f.read(end - start) + rest
            lines = buf.split(b"\n")
            rest = lines.pop(0) if start > 0 else b""   # 잘린 앞줄은 다음 덩어리와 이어 붙인다
            for raw in reversed(lines):
                try:
                    yield json.loads(raw.decode("utf-8", errors="ignore"))
                except ValueError:
                    continue
            end = start


def latest_segment(transcript: Path) -> list[str]:
    """마지막 도구 결과(또는 사용자 요청) 뒤에 Claude 가 쓴 글 조각 — 지금 부르는 도구 바로 앞의 글."""
    texts: list[str] = []
    for e in _tail_entries(transcript):
        content = (e.get("message") or {}).get("content")
        if e.get("type") == "user" and not e.get("isMeta"):
            break   # 도구 결과든 새 요청이든 여기서 조각이 끊긴다
        if e.get("type") == "assistant" and isinstance(content, list):
            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"] + texts
    return texts


def pretool_verdict(texts: list[str], tool_input: dict) -> str:
    problems = []
    eng = [ln for t in texts for ln in english_lines(t)]
    if eng:
        problems.append(f"도구 직전 진행 알림이 한국어가 아닙니다 {len(eng)}줄: " + " / ".join(f"\"{x}\"" for x in eng[:3]))
    desc = tool_input.get("description") if isinstance(tool_input, dict) else None
    if isinstance(desc, str) and english_lines(desc):
        problems.append(f"도구 설명(description)이 한국어가 아닙니다: \"{desc[:120]}\"")
    if not problems:
        return ""
    return (PRETOOL_MARK + " — CLAUDE.md 규칙 0 · REQ-261105-01] " + " · ".join(problems)
            + " → 이 호출은 실행하지 않았습니다. 사용자에게 짧게 사과하고 같은 내용을 한국어로 다시 쓴 뒤, 한국어 설명으로 같은 도구를 다시 부르세요.")


def pretool_main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        tp = Path(data.get("transcript_path") or "")
        texts = latest_segment(tp) if tp.is_file() else []
        reason = pretool_verdict(texts, data.get("tool_input") or {})
        if reason:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                     "permissionDecisionReason": reason}}, ensure_ascii=False))
    except Exception:  # 검사기 고장으로 도구를 막지 않는다
        return 0
    return 0


def verdict(texts: list[str]) -> str:
    problems = []
    first = next((t.strip() for t in texts if t.strip()), "")
    for f in FORBIDDEN_OPENINGS:
        if first.startswith(f):
            problems.append(f"쓰지 않는 첫머리 '{f}'로 시작했습니다(STYLE.md)")
    eng = [ln for t in texts for ln in english_lines(t)]
    if eng:
        sample = " / ".join(f"\"{x}\"" for x in eng[:3])
        problems.append(f"한국어가 아닌 문장 {len(eng)}줄: {sample}")
    if not problems:
        return ""
    return ("[응답 검사 — CLAUDE.md 규칙 0 · .claude/soul/STYLE.md] " + " · ".join(problems)
            + " → 사용자에게 짧게 사과하고, 방금 영어로 쓴 내용을 한국어로 다시 전하세요. 이후 모든 문장(진행 알림 포함)을 한국어로 쓰세요.")


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        if data.get("stop_hook_active"):
            return 0
        tp = Path(data.get("transcript_path") or "")
        if not tp.is_file():
            return 0
        reason = verdict(assistant_texts(tp))
        if reason:
            print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    except Exception:  # 검사기 고장으로 세션을 막지 않는다
        return 0
    return 0


if __name__ == "__main__":
    for s in (sys.stdout,):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    raise SystemExit(pretool_main() if "--pretool" in sys.argv[1:] else main())
