#!/usr/bin/env python3
"""Nova 도구 호출 훅 묶음 — `python nova_hooks.py <이벤트>` (REQ-261105-07).

이벤트마다 파이썬을 **한 번만** 띄운다(도구 호출마다 붙는 지연을 줄이려고 훅을 파일 여럿으로 나누지 않았다).
  pretool       PreToolUse — 기존 응답 검사(persona_guard --pretool)를 같은 프로세스에서 부르고,
                셸로 저장소 파일 쓰기를 거부 · `sed -i` 경고 · 되돌림(checkout/restore/reset --hard) 경고와 기록
  posttool      PostToolUse — 에이전트(Agent · Task) · 스킬(Skill) 호출 기록, SOUL 5종 편집 기록
  prompt        UserPromptSubmit — 사용자 슬래시 명령 기록, 컨텍스트 사용률이 임계(기본 65% · NOVA_HANDOFF_PERCENT)를 넘으면
                한 번 `/session-end` 권고. 분모는 statusline 이 남긴 그 세션의 실제 창, 없으면 추정(200k · NOVA_CONTEXT_WINDOW)
  statusline    statusLine — 입력의 창 크기 · 사용률을 `.claude/state/context_window.json` 에 남기고, 원래 statusLine
                (NOVA_STATUSLINE_CHAIN, 없으면 ~/.claude/settings.json 의 것)에 같은 입력을 넘겨 그 출력을 그대로 낸다
  precompact    PreCompact — 인계서 · 진행 중 tasks 를 `.claude/state/backups/<시각>/` 로 복사
  sessionend    SessionEnd — 같은 복사
  sessionstart  SessionStart — `docs/session/LATEST.md` 머리를 맥락으로 넣는다
  usage         사람용 요약 — 최근 N일 명령 · 스킬 · 에이전트 호출 수(`python nova.py usage --days 7`)
                `--record` 는 그 집계를 커밋되는 원장 docs/memo/agent_usage.jsonl 에 한 줄(회차 마감 — 본 작업 트리만),
                `--unused` 는 원장 전체에서 한 번도 안 불린 에이전트(ADR-010 재검토 조건의 원천 — REQ-261105-08)

막는 것은 둘뿐이다: 비밀 파일 읽기(settings 의 permissions.deny — 이 파일이 아니다)와 저장소 안 파일에 셸로 쓰기.
나머지는 경고 · 기록만 한다 — 거짓 거부는 이 훅의 가장 비싼 실패라서(한 번이면 사람이 훅을 끈다, psg05 shell-payload-guard 의 교훈).
어떤 예외가 나도 종료 0 · 출력 없음(fail-open) — 검사기 고장으로 일을 막지 않는다.
기록은 `.claude/state/*.jsonl`(git 무시 — 기계마다 로컬).
"""
from __future__ import annotations

# 평소 경로(정상 명령 통과)에서 안 쓰는 모듈(subprocess · shutil · fnmatch · datetime)은 쓰는 함수 안에서 들인다 —
# 이 훅은 도구 호출마다 뜨고, 이 PC 에서 그 넷만으로 0.6초가 붙었다(-X importtime 실측).
import importlib.util
import json
import os
import posixpath
import re
import sys
from pathlib import Path

HANGUL = re.compile(r"[가-힣]")
HANDOFF_HEAD_CHARS = 1500     # 세션 시작 때 넣는 인계서 머리 길이 상한 — 전문은 /session-start 가 읽는다
BACKUP_KEEP = 20              # 스냅샷 폴더 개수 상한(오래된 것부터 지운다)
DEFAULT_WINDOW = 200_000      # 컨텍스트 창 기본값 — 쓴 토큰이 이보다 크면 1M 창으로 본다
SOUL_FILES = {"soul.md", "identity.md", ".claude/soul/user.md", ".claude/soul/style.md", ".claude/soul/memory.md"}
# 저장소 안이지만 셸로 써도 되는 자리(실행 상태 · 임시 · git 내부 — 전부 git 무시 대상)
SAFE_PREFIXES = (".git/", ".venv/", "node_modules/", ".run/", ".collab/", ".claude/state/", ".pytest_tmp")


def _load_persona():
    """기존 응답 검사(persona_guard)를 같은 프로세스로 들인다 — 없거나 깨지면 그 검사만 빠진다."""
    try:
        p = Path(__file__).resolve().with_name("persona_guard.py")
        spec = importlib.util.spec_from_file_location("persona_guard", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # 응답 검사가 없어도 셸 · 되돌림 판정은 계속한다
        return None


PERSONA = _load_persona()


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def now() -> "datetime":
    from datetime import datetime
    return datetime.now()


# ───────────────────────── 셸 구문 쪼개기 ─────────────────────────
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(?:'([^']+)'|\"([^\"]+)\"|\\?([A-Za-z_][\w-]*))")
PY_STDIN = re.compile(r"\bpython(?:3(?:\.\d+)?)?(?:\.exe)?\s+-(?=\s|$|<)")


def split_heredocs(text: str) -> tuple[str, list[tuple[str, str]]]:
    """heredoc 본문을 떼어 낸다 → (본문을 뺀 명령, [(머리 줄, 본문)]).

    본문은 셸 명령이 아니라 데이터다 — `git commit -F - <<'EOF'` 본문에 '> docs/a.md' 라는 글자가 있다고 쓰기로 읽으면
    고친 사실을 기록하는 일 자체가 막힌다(psg05 승격 당일 과차단). 파이썬에 넘기는 본문만 따로 본다."""
    lines = text.split("\n")
    out: list[str] = []
    bodies: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in HEREDOC.finditer(line):
            delim = m.group(1) or m.group(2) or m.group(3)
            body = []
            while i < len(lines) and lines[i].strip() != delim:
                body.append(lines[i])
                i += 1
            i += 1   # 닫는 줄
            bodies.append((line, "\n".join(body)))
    return "\n".join(out), bodies


def segments(text: str, escape: str = "\\") -> list[tuple[list[str], list[str]]]:
    """명령 단위로 쪼갠다 → [(낱말들, 리다이렉트 대상들)]. 따옴표 안의 `>` · `;` · `|` 는 글자로 둔다.

    셸 문법을 다 풀지는 않는다 — 틀리면 대상을 **덜** 뽑는 쪽(통과)으로 틀리게 짰다."""
    segs: list[tuple[list[str], list[str]]] = []
    words: list[str] = []
    redirs: list[str] = []
    buf: list[str] = []
    st = {"inword": False, "pending": None}   # pending: "out"(쓰기 대상) · "in"(입력 — 버린다)
    q = None

    def end_word():
        if st["inword"]:
            w = "".join(buf)
            if st["pending"] == "out":
                redirs.append(w)
            elif st["pending"] is None:
                words.append(w)
            st["pending"] = None
        buf.clear()
        st["inword"] = False

    def end_seg():
        nonlocal words, redirs
        end_word()
        if words or redirs:
            segs.append((words, redirs))
        words, redirs = [], []
        st["pending"] = None

    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if q:
            if c == q:
                q = None
            elif q == '"' and c == escape and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            else:
                buf.append(c)
            i += 1
            continue
        if c in "'\"":
            q = c
            st["inword"] = True
        elif c == escape and i + 1 < n:
            buf.append(text[i + 1])
            st["inword"] = True
            i += 2
            continue
        elif c in " \t\r":
            end_word()
        elif c == "&" and i + 1 < n and text[i + 1] == ">":
            end_word()            # &> 대상 — 아래 > 갈래가 받는다
        elif c in "\n;|&":
            end_seg()
        elif c in "()" and not (c == "(" and buf and buf[-1] == "$"):
            end_seg()
        elif c == ">":
            if st["inword"] and "".join(buf).isdigit():
                buf.clear()       # 2> 의 2 — 낱말이 아니다
                st["inword"] = False
            else:
                end_word()
            j = i + 1
            if j < n and text[j] == ">":
                j += 1
            if j < n and text[j] == "&":   # 2>&1 · >&2 — 파일이 아니다
                j += 1
                while j < n and (text[j].isdigit() or text[j] == "-"):
                    j += 1
                i = j
                continue
            if j < n and text[j] == "|":
                j += 1
            st["pending"] = "out"
            i = j
            continue
        elif c == "<":
            end_word()
            while i + 1 < n and text[i + 1] == "<":
                i += 1
            st["pending"] = "in"
        else:
            buf.append(c)
            st["inword"] = True
        i += 1
    end_seg()
    return segs


def _cmd_words(words: list[str]) -> list[str]:
    """앞에 붙은 환경 변수(VAR=값)를 떼어 낸 낱말들."""
    k = 0
    while k < len(words) and re.fullmatch(r"[A-Za-z_]\w*=.*", words[k]):
        k += 1
    return words[k:]


def _name(word: str) -> str:
    return re.split(r"[\\/]", word)[-1].lower()


# ───────────────────────── 경로 판정 ─────────────────────────
def norm(p: str) -> str:
    p = p.replace("\\", "/")
    m = re.match(r"^/([a-zA-Z])(/|$)", p)          # Git Bash 의 /f/… → f:/…
    if m:
        p = f"{m.group(1)}:/{p[3:]}"
    p = posixpath.normpath(p)
    return p.lower() if re.match(r"^[A-Za-z]:", p) else p   # 윈도 경로는 대소문자를 가리지 않는다


def _is_abs(p: str) -> bool:
    return bool(re.match(r"^([A-Za-z]:[\\/]|[\\/])", p))


def resolve(target: str, cwd: str | None, root: str) -> str | None:
    """쓰기 대상을 절대 경로로 — 실행 때에야 값이 정해지는 것($변수 · 글롭 · ~)은 None(판정 불가 → 통과)."""
    if not target or re.search(r"[$`*?{}()\[\]]", target) or target.startswith("~"):
        return None
    low = target.lower()
    if low in ("nul", "con", "/dev/null") or low.startswith("/dev/"):
        return None
    if _is_abs(target):
        return norm(target)
    if cwd is None:
        return None
    return norm(cwd.replace("\\", "/").rstrip("/") + "/" + target)


def repo_rel(path: str | None, root: str) -> str | None:
    """저장소 안이면 상대 경로, 밖이거나 안전한 자리면 None."""
    if not path:
        return None
    r = norm(root)
    if not path.startswith(r.rstrip("/") + "/"):
        return None
    rel = path[len(r.rstrip("/")) + 1:]
    return None if rel.lower().startswith(SAFE_PREFIXES) else rel


# ───────────────────────── 파이썬 코드 속 쓰기 ─────────────────────────
PY_OPEN = re.compile(r"""\bopen\(\s*[rRbBuU]*(['"])([^'"]+)\1\s*,\s*(?:mode\s*=\s*)?[rRbB]*(['"])([^'"]*)\3""")
PY_PATH_WRITE = re.compile(r"""\bPath\(\s*[rR]?(['"])([^'"]+)\1\s*\)\s*\.\s*write_(?:text|bytes)\(""")
PY_BIND = re.compile(r"""\b([A-Za-z_]\w*)\s*=\s*(?:Path\(\s*)?[rR]?(['"])([^'"]+)\2""")
PS_WRITE_ALL = re.compile(r"""WriteAll(?:Text|Lines|Bytes)\(\s*(['"])(.+?)\1""")


def python_write_targets(code: str) -> list[str]:
    """파이썬 코드가 쓰는 파일 — open(…,'w'|'a'|'x'|'+') · Path(…).write_text · 한 번만 묶인 이름."""
    out = [m.group(2) for m in PY_OPEN.finditer(code) if re.search(r"[wax+]", m.group(4))]
    out += [m.group(2) for m in PY_PATH_WRITE.finditer(code)]
    binds: dict[str, str] = {}
    for m in PY_BIND.finditer(code):
        name = m.group(1)
        if len(re.findall(rf"\b{re.escape(name)}\s*=(?!=)", code)) == 1:   # 값이 하나로 정해진 이름만
            binds[name] = m.group(3)
    for name, val in binds.items():
        n = re.escape(name)
        for m in re.finditer(rf"\bopen\(\s*{n}\s*,\s*(?:mode\s*=\s*)?[rRbB]*(['\"])([^'\"]*)\1", code):
            if re.search(r"[wax+]", m.group(2)):
                out.append(val)
        if re.search(rf"\b{n}\s*\.\s*write_(?:text|bytes)\(", code):
            out.append(val)
    return out


# ───────────────────────── 셸 쓰기 판정 ─────────────────────────
def shell_write_verdict(command: str, cwd: str | None, root: str, tool: str = "Bash") -> dict | None:
    """셸(Bash · PowerShell)로 저장소 안 파일을 쓰는가 → None(무관) · warn · deny.

    잡는 것: 리다이렉트(> · >>) · tee · PowerShell Set-Content/Add-Content/Out-File/WriteAllText ·
    python -c / python - 의 open(…,'w') · Path.write_text. `sed -i` 는 경고만(작은 체크박스 치환에 자주 쓰여 왔다).
    통과: /dev/null · 2>&1 · 저장소 밖(스크래치 · $TEMP) · git 무시 실행 폴더 · 따옴표 · heredoc 본문 속 글자."""
    if not isinstance(command, str) or not command.strip():
        return None
    shell_text, bodies = split_heredocs(command)
    escape = "`" if tool == "PowerShell" else "\\"
    hatch = bool(re.search(r"(?:^|[\s;&])NOVA_SHELL_WRITE=1(?:\s|$)", shell_text))
    deny: list[str] = []
    sed: list[str] = []
    kinds: list[str] = []
    cur = cwd or root

    def hit(t: str, kind: str, into: list[str]):
        rel = repo_rel(resolve(t, cur, root), root)
        if rel and t not in into:
            into.append(t)
            if into is deny and kind not in kinds:
                kinds.append(kind)

    for words, redirs in segments(shell_text, escape):
        w = _cmd_words(words)
        name = _name(w[0]) if w else ""
        if name == "cd":
            cur = resolve(w[1], cur, root) if len(w) > 1 else None   # 모르는 자리로 가면 상대 경로는 판정하지 않는다
            continue
        for t in redirs:
            hit(t, "리다이렉트 >", deny)
        if name == "tee":
            for x in w[1:]:
                if not x.startswith("-"):
                    hit(x, "tee", deny)
        if tool == "PowerShell" and name in ("set-content", "add-content", "out-file", "sc", "ac"):
            lw = [x.lower() for x in w]
            idx = next((k for k, x in enumerate(lw) if x in ("-path", "-filepath", "-literalpath")), None)
            t = w[idx + 1] if idx is not None and idx + 1 < len(w) else next((x for x in w[1:] if not x.startswith("-")), "")
            hit(t, name, deny)
        # python 은 명령 자리(앞에 uv run · timeout 정도만)에서만 본다 — 인자 속 글자 'python -c' 는 명령이 아니다
        k = next((k for k, x in enumerate(w[:4]) if re.fullmatch(r"python(?:3(?:\.\d+)?)?(?:\.exe)?", _name(x))), None)
        if k is not None and all(re.fullmatch(r"uv|run|timeout|\d+[smh]?|--", x) for x in w[:k]):
            if k + 2 < len(w) and w[k + 1] == "-c":
                for t in python_write_targets(w[k + 2]):
                    hit(t, "python -c", deny)
        if name == "sed" and any(x == "--in-place" or re.fullmatch(r"-[a-zA-Z]*i\S*", x) for x in w[1:]):
            args = [x for x in w[1:] if not x.startswith("-")]
            has_e = any(x == "-e" or x.startswith("--expression") for x in w[1:])
            for t in (args if has_e else args[1:]):
                hit(t, "sed -i", sed)
    for m in PS_WRITE_ALL.finditer(shell_text):
        hit(m.group(2), "WriteAllText", deny)
    for header, body in bodies:
        if PY_STDIN.search(header):
            for t in python_write_targets(body):
                hit(t, "python - <<", deny)

    if deny:
        what = " · ".join(kinds)
        if hatch:
            return {"action": "warn", "targets": deny, "message":
                    f"[셸 쓰기 — NOVA_SHELL_WRITE=1 로 허용됨] {what} 로 저장소 파일 {', '.join(deny)} 을 씁니다. "
                    "실행 뒤 git diff 로 들어간 내용을 확인하세요."}
        return {"action": "deny", "targets": deny, "message":
                f"[셸 쓰기 거부 — REQ-261105-07] 셸({what})로 저장소 안 파일 {', '.join(deny)} 을 쓰려 해서 이 호출을 실행하지 않았습니다. "
                "셸을 지나면 줄바꿈 · 역슬래시 · NUL 이 바뀌어 쓴 것과 다른 내용이 들어갈 수 있습니다(교훈 2026-11-05). "
                "대신 Edit · Write 도구로 고치거나, 스크래치 폴더에 스크립트를 Write 로 쓰고 `python <경로>` 로 실행하세요. "
                "사용자가 셸 쓰기를 허락한 경우에만 명령 앞에 NOVA_SHELL_WRITE=1 을 붙입니다."}
    if sed:
        return {"action": "warn", "targets": sed, "message":
                f"[셸 제자리 편집 경고] sed -i 로 저장소 파일 {', '.join(sed)} 을 고칩니다. 막지는 않았지만 Edit 도구를 권장합니다 — "
                "셸 치환은 역슬래시 · 대괄호 이스케이프가 조용히 빗나가 0건 치환으로 끝날 수 있습니다. 실행 뒤 grep -c 로 바뀐 것을 확인하세요."}
    return None


# ───────────────────────── 되돌림 판정 ─────────────────────────
def parse_porcelain_z(out: str) -> list[str]:
    """`git status --porcelain=v1 -z` → 추적 중이면서 바뀐 파일(새 파일 ?? · 무시 !! 는 되돌림이 지우지 않는다)."""
    parts = out.split("\0")
    files: list[str] = []
    i = 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        code, path = e[:2], e[3:]
        if code[0] in "RC":
            i += 1    # 이름 바꾸기는 다음 칸이 옛 이름
        if code in ("??", "!!"):
            continue
        if path not in files:
            files.append(path)
    return files


def _spec_match(f: str, spec: str, cwd_rel: str) -> bool:
    if spec.startswith(":/"):
        full = posixpath.normpath(spec[2:] or ".")
    else:
        full = posixpath.normpath(posixpath.join(cwd_rel, spec) if cwd_rel else spec)
    if full in (".", ""):
        return True
    if re.search(r"[*?\[]", full):   # 셸이 펼친 글롭처럼 — * 는 / 를 넘지 않는다
        import fnmatch
        return fnmatch.fnmatchcase(f, full) and f.count("/") == full.count("/")
    return f == full or f.startswith(full.rstrip("/") + "/")


def revert_hits(command: str, dirty: list[str], cwd_rel: str) -> list[str]:
    """되돌림 명령(checkout -- · checkout . · restore · reset --hard)이 덮을 미커밋 파일."""
    if not dirty or not isinstance(command, str):
        return []
    hits: set[str] = set()
    for words, _ in segments(split_heredocs(command)[0]):
        w = _cmd_words(words)
        if len(w) < 2 or _name(w[0]) not in ("git", "git.exe"):
            continue
        k = 1
        while k < len(w) and w[k].startswith("-"):
            k += 2 if w[k] in ("-C", "-c") else 1
        if k >= len(w):
            continue
        sub, rest = w[k], w[k + 1:]
        whole, specs = False, []
        if sub == "reset":
            whole = "--hard" in rest
        elif sub == "checkout":
            if "--" in rest:
                specs = rest[rest.index("--") + 1:]
            elif rest == ["."]:
                specs = ["."]
        elif sub == "restore":
            staged = "--staged" in rest or "-S" in rest
            worktree = "--worktree" in rest or "-W" in rest
            if staged and not worktree:
                continue   # 색인만 내린다 — 작업 파일은 그대로
            skip = False
            for x in rest:
                if skip:
                    skip = False
                elif x in ("-s", "--source"):
                    skip = True
                elif x != "--" and not x.startswith("-"):
                    specs.append(x)
        for f in dirty:
            if whole or any(_spec_match(f, s, cwd_rel) for s in specs):
                hits.add(f)
    return [f for f in dirty if f in hits]


REVERT_HINT = re.compile(r"\bgit\b[^\n]*\b(?:checkout|restore|reset)\b")


def _dirty_files(root: Path) -> list[str]:
    import subprocess
    r = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1", "-z"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=5)
    return parse_porcelain_z(r.stdout) if r.returncode == 0 else []


# ───────────────────────── 기록 ─────────────────────────
def append_jsonl(root: Path, name: str, rec: dict) -> None:
    d = root / ".claude" / "state"
    d.mkdir(parents=True, exist_ok=True)
    with (d / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now().isoformat(timespec="seconds"), **rec}, ensure_ascii=False) + "\n")


def _rel_to_root(path: str, root: Path) -> str | None:
    """저장소 기준 상대 경로 — 비교는 norm(윈도는 소문자)으로, 돌려주는 값은 원래 글자대로."""
    p, r = norm(path), norm(str(root)).rstrip("/")
    if not p.startswith(r + "/"):
        return None
    raw = posixpath.normpath(path.replace("\\", "/"))
    return raw[-(len(p) - len(r) - 1):]


# ───────────────────────── 이벤트 ─────────────────────────
def on_pretool(data: dict, root: Path) -> dict | None:
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    denies: list[str] = []
    notes: list[str] = []
    if PERSONA is not None:
        tp = Path(data.get("transcript_path") or "")
        texts = PERSONA.latest_segment(tp) if str(tp) not in ("", ".") and tp.is_file() else []
        r = PERSONA.pretool_verdict(texts, ti)
        if r:
            denies.append(r)
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if tool in ("Bash", "PowerShell") and isinstance(cmd, str):
        cwd = data.get("cwd") or str(root)
        v = shell_write_verdict(cmd, cwd, str(root), tool)
        if v:
            (denies if v["action"] == "deny" else notes).append(v["message"])
            append_jsonl(root, "shell_writes.jsonl", {"session": data.get("session_id"), "action": v["action"],
                                                     "targets": v["targets"], "command": cmd[:300]})
        if REVERT_HINT.search(cmd):
            cwd_rel = _rel_to_root(cwd, root) or ""
            hit = revert_hits(cmd, _dirty_files(root), cwd_rel)
            if hit:
                append_jsonl(root, "revert_events.jsonl", {"session": data.get("session_id"), "command": cmd[:300], "hit": hit})
                shown = ", ".join(hit[:10]) + (f" 외 {len(hit) - 10}개" if len(hit) > 10 else "")
                notes.append(f"[되돌림 경고 — REQ-261105-07] 이 명령은 커밋되지 않은 수정 {len(hit)}개를 덮습니다: {shown}. "
                             "다른 담당(worktree · 에이전트)의 작업일 수 있습니다(교훈 2026-11-05). 막지는 않았습니다 — "
                             "지우면 안 되는 것이었다면 바로 사용자에게 알리고, 다음부터는 경로를 좁히거나 git stash 로 먼저 보관하세요.")
    if denies:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": " / ".join(denies + notes)}}
    if notes:
        msg = " / ".join(notes)
        return {"systemMessage": msg, "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}}
    return None


def on_posttool(data: dict, root: Path) -> None:
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    sid = data.get("session_id")
    if tool in ("Agent", "Task"):
        append_jsonl(root, "agent_runs.jsonl", {"session": sid, "subagent_type": ti.get("subagent_type") or "general-purpose",
                                                "description": str(ti.get("description") or "")[:200]})
    elif tool == "Skill":
        append_jsonl(root, "skill_usage.jsonl", {"session": sid, "kind": "skill",
                                                 "name": ti.get("skill") or ti.get("command") or ti.get("name") or "?"})
    elif tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        fp = ti.get("file_path") or ti.get("notebook_path") or ""
        rel = _rel_to_root(fp, root) if fp else None
        if rel and rel.lower() in SOUL_FILES:
            append_jsonl(root, "soul_edits.jsonl", {"session": sid, "tool": tool, "file": rel})
    return None


SLASH = re.compile(r"^\s*/([A-Za-z][\w:.-]*)(?=\s|$)")
CMD_TAG = re.compile(r"<command-name>/?([\w:.-]+)</command-name>")


def context_tokens(transcript: Path, max_entries: int = 400) -> int | None:
    """마지막 응답이 쓴 컨텍스트 크기(입력 + 캐시 토큰) — 기록을 끝에서부터 읽는다(전체를 읽지 않는다)."""
    if PERSONA is None or not transcript.is_file():
        return None
    for i, e in enumerate(PERSONA._tail_entries(transcript)):
        if i >= max_entries:
            return None
        u = (e.get("message") or {}).get("usage") if isinstance(e, dict) else None
        if isinstance(u, dict) and isinstance(u.get("input_tokens"), int):
            total = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            if total > 0:
                return total
    return None


def context_percent(tokens: int, window: int) -> int:
    if tokens > window:
        window = 1_000_000   # 기본 창을 넘었다 = 큰 창 세션이다
    return round(tokens * 100 / window)


# ---- 실제 창 크기 — 훅 입력에는 창 크기가 없고 statusLine 입력에만 있다(2026-11-06 — 200k 고정 분모로 1M 세션에서 거짓 권고)
WINDOW_STATE = "context_window.json"


def record_statusline(data: dict, root: Path) -> None:
    """statusLine 입력의 세션별 창 크기 · 사용률을 `.claude/state/` 에 남긴다 — 프롬프트 훅이 분모로 읽는다."""
    cw = data.get("context_window") if isinstance(data, dict) else None
    size = cw.get("context_window_size") if isinstance(cw, dict) else None
    if not isinstance(size, int) or size <= 0:
        return
    p = root / ".claude" / "state" / WINDOW_STATE
    seen = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    sid = str(data.get("session_id") or "nosession")
    seen.pop(sid, None)   # 최근 것을 뒤로 — 50개만 남길 때 오래된 세션부터 버린다
    seen[sid] = {"window": size, "percent": cw.get("used_percentage"), "at": now().isoformat(timespec="seconds")}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(list(seen.items())[-50:]), ensure_ascii=False), encoding="utf-8")


def recorded_window(root: Path, sid: str) -> int | None:
    p = root / ".claude" / "state" / WINDOW_STATE
    try:
        w = json.loads(p.read_text(encoding="utf-8")).get(sid, {}).get("window")
    except (OSError, ValueError, AttributeError):   # 기록이 없거나 깨졌으면 추정으로 돌아간다
        return None
    return w if isinstance(w, int) and w > 0 else None


def chain_command(home: Path, env: dict) -> str | None:
    """이어 부를 원래 statusLine — NOVA_STATUSLINE_CHAIN, 없으면 사용자 전역 설정. 자기 자신은 고르지 않는다."""
    if env.get("NOVA_STATUSLINE_CHAIN"):
        return env["NOVA_STATUSLINE_CHAIN"]
    try:
        cmd = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8")).get("statusLine", {}).get("command")
    except (OSError, ValueError, AttributeError):   # 전역 설정이 없으면 이을 것이 없다
        return None
    return cmd if isinstance(cmd, str) and cmd.strip() and "nova_hooks.py" not in cmd else None


def status_text(data: dict) -> str:
    cw = data.get("context_window") if isinstance(data, dict) else None
    if not isinstance(cw, dict) or not isinstance(cw.get("context_window_size"), int):
        return ""
    size = cw["context_window_size"]
    label = f"{size // 1_000_000}M" if size % 1_000_000 == 0 else f"{size // 1000}k"
    pct = cw.get("used_percentage")
    return f"컨텍스트 {round(pct)}% · 창 {label}" if isinstance(pct, (int, float)) else f"컨텍스트 창 {label}"


def statusline_cli(raw: str) -> int:
    """statusLine 명령 — 기록 → 원래 statusLine(예: Orca) 에 같은 입력을 넘겨 그 출력을 그대로, 없으면 우리 한 줄."""
    import subprocess
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        data = {}
    if isinstance(data, dict):
        try:
            record_statusline(data, project_root())
        except OSError:   # 기록 실패로 상태 줄을 비우지 않는다 — 다음 갱신 때 다시 쓴다
            pass
    out = ""
    cmd = chain_command(Path.home(), dict(os.environ))
    if cmd:
        try:
            r = subprocess.run(cmd, shell=True, input=raw, capture_output=True, text=True, encoding="utf-8", timeout=3)
            out = r.stdout
        except (OSError, subprocess.SubprocessError):   # 원래 상태 줄이 고장 나도 우리 한 줄은 낸다
            out = ""
    print(out.rstrip("\n") if out.strip() else status_text(data if isinstance(data, dict) else {}))
    return 0


def on_prompt(data: dict, root: Path) -> dict | None:
    prompt = str(data.get("prompt") or "")
    m = SLASH.match(prompt) or CMD_TAG.search(prompt)
    if m:
        append_jsonl(root, "skill_usage.jsonl", {"session": data.get("session_id"), "kind": "command", "name": m.group(1)})
    tp = Path(data.get("transcript_path") or "")
    if str(tp) in ("", "."):
        return None
    tokens = context_tokens(tp)
    if not tokens:
        return None
    # 기본 65% — 실제 창 기준이면 남은 35% 로 인계서를 쓰고도 여유가 있다(사용자 결정 2026-11-06)
    limit = int(os.environ.get("NOVA_HANDOFF_PERCENT") or 65)
    window = recorded_window(root, str(data.get("session_id") or "nosession"))
    if window:
        pct = round(tokens * 100 / window)   # 실제 창 — 추정하지 않는다
    else:
        pct = context_percent(tokens, int(os.environ.get("NOVA_CONTEXT_WINDOW") or DEFAULT_WINDOW))
    if pct < limit:
        return None
    marker = root / ".claude" / "state" / "handoff_notified.json"
    seen = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {}
    sid = str(data.get("session_id") or "nosession")
    if seen.get(sid):
        return None   # 세션마다 한 번만 — 매번 뜨면 소음이 되어 무시된다
    seen[sid] = now().isoformat(timespec="seconds")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(dict(list(seen.items())[-50:]), ensure_ascii=False), encoding="utf-8")
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext":
            f"[세션 인계 권고 — REQ-261105-07] 컨텍스트 사용량이 약 {pct}%(임계 {limit}%)입니다. "
            "지금 하던 일을 한 단락 마무리한 뒤 `/session-end` 로 인수인계를 남기고 새 세션에서 `/session-start` 로 이어 가기를 사용자에게 권하세요."}}


def prune_backups(base: Path, keep: int = BACKUP_KEEP) -> None:
    import shutil
    dirs = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    for p in dirs[: max(0, len(dirs) - keep)]:
        shutil.rmtree(p, ignore_errors=True)


def snapshot(root: Path, event: str) -> Path | None:
    """인계서 · 미체크 task 가 남은 tasks 파일을 백업 폴더로 복사한다 — 압축 · 종료로 기억이 잘려도 원본을 되짚게."""
    files = []
    latest = root / "docs" / "session" / "LATEST.md"
    if latest.is_file():
        files.append(latest)
    tdir = root / "docs" / "plans" / "tasks"
    if tdir.is_dir():
        files += [p for p in sorted(tdir.glob("*.md")) if "- [ ]" in p.read_text(encoding="utf-8", errors="ignore")]
    if not files:
        return None
    import shutil
    base = root / ".claude" / "state" / "backups"
    dst = base / f"{now():%Y%m%d-%H%M%S}-{event}"
    k = 1
    while dst.exists():
        k += 1
        dst = base / f"{now():%Y%m%d-%H%M%S}-{event}-{k}"
    for f in files:
        out = dst / f.relative_to(root)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
    prune_backups(base)
    return dst


def on_precompact(data: dict, root: Path) -> None:
    snapshot(root, "precompact")


def on_sessionend(data: dict, root: Path) -> None:
    snapshot(root, "sessionend")


def handoff_head(text: str, limit: int = HANDOFF_HEAD_CHARS) -> str:
    out, size = [], 0
    for line in text.splitlines():
        if size + len(line) + 1 > limit:
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join(out).rstrip()


def on_sessionstart(data: dict, root: Path) -> dict | None:
    latest = root / "docs" / "session" / "LATEST.md"
    if not latest.is_file():
        return None
    head = handoff_head(latest.read_text(encoding="utf-8", errors="ignore"))
    if not head:
        return None
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
            "[지난 세션 인수인계 머리 — docs/session/LATEST.md · 전문은 /session-start 로 읽는다]\n" + head}}


HANDLERS = {"pretool": on_pretool, "posttool": on_posttool, "prompt": on_prompt,
            "precompact": on_precompact, "sessionend": on_sessionend, "sessionstart": on_sessionstart}


# ───────────────────────── 사용 요약(사람용) ─────────────────────────
def summarize_usage(recs: dict[str, list[dict]], days: int, now: "datetime") -> dict[str, dict[str, int]]:
    from collections import Counter
    from datetime import datetime, timedelta
    since = now - timedelta(days=days)

    def recent(r):
        try:
            return datetime.fromisoformat(r["ts"]) >= since
        except (KeyError, ValueError, TypeError):
            return False

    out: dict[str, Counter] = {"명령": Counter(), "스킬": Counter(), "에이전트": Counter()}
    for r in filter(recent, recs.get("skill", [])):
        out["명령" if r.get("kind") == "command" else "스킬"][r.get("name", "?")] += 1
    for r in filter(recent, recs.get("agent", [])):
        out["에이전트"][r.get("subagent_type", "?")] += 1
    return {k: dict(v.most_common()) for k, v in out.items() if v}


def _read_jsonl(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue   # 깨진 줄 하나로 요약 전체를 버리지 않는다
    return out


# 호출 기록 원장(REQ-261105-08-3) — .claude/state 는 기계 로컬 · git 무시라 판본을 넘는 판정(ADR-010 재검토 조건:
# 두 판본 동안 안 부른 얇은 정의는 합친다)의 원천이 될 수 없다. 회차 마감(/round-close — 본 작업 트리만, 단일 기록자)에서
# 집계 한 줄을 커밋되는 JSONL 로 옮긴다. 이력은 JSONL(ADR-004).
USAGE_LEDGER = Path("docs") / "memo" / "agent_usage.jsonl"


def record_usage(root: Path, days: int, by: str, at: "datetime") -> dict:
    """최근 days 일 집계를 원장에 한 줄 덧붙이고 그 줄을 돌려준다. 기록이 없는 기간도 남긴다('안 불렀다'도 판정 재료)."""
    st = root / ".claude" / "state"
    recs = {"skill": _read_jsonl(st / "skill_usage.jsonl"), "agent": _read_jsonl(st / "agent_runs.jsonl")}
    rec = {"ts": at.isoformat(timespec="seconds"), "days": days, "by": by, "counts": summarize_usage(recs, days, at)}
    p = root / USAGE_LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _agent_names(root: Path) -> list[str]:
    """정의 파일(.claude/agents/<폴더>/<이름>.md)의 name — frontmatter 가 없으면 파일 이름. README 는 정의가 아니다."""
    names = []
    for f in sorted((root / ".claude" / "agents").rglob("*.md")):
        if f.name == "README.md":
            continue
        m = re.search(r"^name:\s*(\S+)", f.read_text(encoding="utf-8", errors="ignore"), re.M)
        names.append(m.group(1) if m else f.stem)
    return names


def unused_agents(root: Path) -> list[str]:
    """정의된 에이전트 중 원장 전체에서 한 번도 불리지 않은 이름(원장이 없으면 전부)."""
    called: set[str] = set()
    for r in _read_jsonl(root / USAGE_LEDGER):
        called |= set(((r.get("counts") or {}).get("에이전트") or {}).keys())
    return sorted(n for n in _agent_names(root) if n not in called)


def usage_cli(args: list[str]) -> int:
    from datetime import timedelta
    days = 7
    if "--days" in args:
        days = int(args[args.index("--days") + 1])
    root = project_root()
    if "--record" in args:
        by = os.environ.get("USER") or os.environ.get("USERNAME") or "dev"
        rec = record_usage(root, days, by, now())
        n = sum(sum(c.values()) for c in rec["counts"].values())
        print(f"✓ 호출 기록 원장에 한 줄 — {USAGE_LEDGER.as_posix()} · 최근 {days}일 · 호출 {n}건")
        return 0
    if "--unused" in args:
        names = unused_agents(root)
        rows = len(_read_jsonl(root / USAGE_LEDGER))
        print(f"원장 {USAGE_LEDGER.as_posix()} {rows}줄 기준 — 한 번도 안 불린 에이전트 {len(names)}개")
        for n in names:
            print(f"  · {n}")
        return 0
    st = root / ".claude" / "state"
    recs = {"skill": _read_jsonl(st / "skill_usage.jsonl"), "agent": _read_jsonl(st / "agent_runs.jsonl")}
    summary = summarize_usage(recs, days, now())
    print(f"최근 {days}일 호출 수 (.claude/state — 이 기계의 기록)")
    if not summary:
        print("  기록 없음")
    for kind, counts in summary.items():
        print(f"\n[{kind}] 합계 {sum(counts.values())}")
        for name, c in counts.items():
            print(f"  {c:5d}  {name}")
    souls = [r for r in _read_jsonl(st / "soul_edits.jsonl")
             if r.get("ts", "") >= (now() - timedelta(days=days)).isoformat(timespec="seconds")]
    reverts = [r for r in _read_jsonl(st / "revert_events.jsonl")
               if r.get("ts", "") >= (now() - timedelta(days=days)).isoformat(timespec="seconds")]
    print(f"\nSOUL 편집 {len(souls)}건 · 미커밋 파일을 덮은 되돌림 {len(reverts)}건")
    return 0


def main(argv: list[str]) -> int:
    event = argv[1] if len(argv) > 1 else ""
    if event == "usage":
        return usage_cli(argv[2:])
    if event == "statusline":
        try:
            return statusline_cli(sys.stdin.read())
        except Exception:  # 상태 줄 고장으로 화면을 깨지 않는다(fail-open) — 빈 줄로 통과
            return 0
    try:
        data = json.loads(sys.stdin.read() or "{}")
        handler = HANDLERS.get(event)
        if not isinstance(data, dict) or handler is None:
            return 0
        out = handler(data, project_root())
        if out:
            print(json.dumps(out, ensure_ascii=False))
    except Exception:  # 훅 고장으로 도구 · 세션을 막지 않는다(fail-open) — 출력 없이 통과
        return 0
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:  # 재설정이 안 되는 스트림이면 기본 인코딩으로 간다
        pass
    raise SystemExit(main(sys.argv))
