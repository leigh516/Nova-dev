#!/usr/bin/env python3
"""에이전트 · 스킬 정의 검사 — 정의가 같은 규격으로 말하게 하고, 에이전트 편제표가 낡지 않게 한다(ADR-009).

  uv run python scripts/claude_check.py --check    (lint 에서 실행, 틀리면 종료코드 1)
  uv run python scripts/claude_check.py --write    (.claude/agents/README.md 편제표를 다시 만든다)
  uv run python scripts/claude_check.py --report   (편제표 · 경고 · 오류 출력)

에이전트(.claude/agents/<폴더>/<이름>.md — 폴더형, ADR-010. Claude Code 는 하위 폴더를 재귀로 읽고 name 으로만 식별한다)
  A1 frontmatter 키(name · description · tools 필수, model 선택)   A2 name == 파일 이름 · [a-z0-9-]+ · 폴더를 가로질러 유일
  A3 description 한글 · 40~400자 · 호출 조건 표지 · 상시 자동 호출 문구 금지
  A4 tools 허용 도구명   A5 읽기 전용 자리(폴더 정책 · 판정자 이름)에 쓰기 도구 없음   A6 읽기 전용 자리는 Bash(실측)
  A7 본문 6절 순서   A8 반환 4절 낱말   A9 단일 기록자 명령은 '하지 않는 것' 절에만
  A10 상대 링크 · /명령 실재   A11 명령 · 스킬이 부르는 에이전트가 정의에 있음 · 폐지된 이름 금지(안 불리는 에이전트는 경고, meta 제외)
  A12 README 편제표 == 생성 결과   A13 색 리터럴 금지   A14 사용자를 "Nova"로 부르지 않음
  A15 model 값   A16 묶음은 폴더에서 파생 — `> 묶음:` 줄을 쓰지 않는다(원천이 둘이 된다)
  A17 도메인 에이전트(<팩>-specialist)는 domain/ 에만 있고 짝 팩(packs/<팩>/pack.json)이 있다 — 명령은 '<팩>-specialist' 로 부르므로 A11 경고에서 뺀다
  A18 정의는 정해진 폴더(research · planning · development · quality · docs · ops · meta · domain) 안에만 — 루트에는 README 만
  A19 README '상황 → 에이전트' 빠른 표의 이름이 정의에 있다
스킬(.claude/skills/<이름>/SKILL.md)
  S1 name == 폴더 · description 한글   S2 canon: design-system 이면 색 · px · 비율 리터럴 금지
  S3 상대 링크 · 백틱 안 저장소 경로 실재   S4 한글 없는 md 금지
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, read, write  # noqa: E402

HANGUL = re.compile(r"[가-힣]")

REQUIRED_KEYS = ("name", "description", "tools")
OPTIONAL_KEYS = ("model",)
MODELS = {"opus", "sonnet", "haiku", "inherit"}
TOOLS = {"Read", "Write", "Edit", "Grep", "Glob", "Bash", "WebSearch", "WebFetch", "NotebookEdit", "Agent", "TodoWrite"}
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}

# 폴더 → 묶음(편제표 순서). 폴더가 정본이다 — 묶음 · 읽기 전용 여부가 여기서 파생된다(ADR-010)
FOLDERS = {"research": "조사", "planning": "설계", "development": "구현", "quality": "검증 · 판정",
           "docs": "기록", "ops": "운영", "meta": "메타", "domain": "도메인"}
READONLY_FOLDERS = {"research", "planning", "quality", "domain"}   # 쓰기 도구 없이 Bash 로 잰다
OPS_WRITERS = {"release-manager", "incident-responder"}           # ops/ 는 기본 읽기 전용, 이 둘만 쓴다
NO_CALL_FOLDERS = {"meta", "domain"}                               # 명령이 이름으로 부르지 않아도 경고하지 않는다
# 판정자 이름 — 두 번째 방어선(쓰기 폴더에 판정자 이름이 있으면 A5)
JUDGE_SUFFIXES = ("-auditor", "-reviewer", "-tester", "-analyst", "-specialist", "-guardian")
DOMAIN_SUFFIX = "-specialist"   # 도메인 팩과 짝인 에이전트 — scripts/packs.py agent 가 packs/_template/agent.md 에서 만든다
# 폐지된 이름 — 명령 · 스킬이 부르면 새 이름을 안내한다(ADR-010)
RETIRED = {"synthesizer": "project-manager · integrator", "planner": "task-planner · masterplanner · orchestrator",
           "implementer": "backend-developer · frontend-developer · devops-engineer · refactorer",
           "ui-auditor": "accessibility-auditor · design-token-guardian"}
QUICK_HEADING = "## 상황 → 에이전트"

SECTIONS = ["언제 나를 부르나", "따르는 규칙", "수행 절차", "반환 형식", "하지 않는 것", "실패·불확실 처리"]
RETURN_WORDS = ("핵심 답", "실측", "근거", "미해결")
DONT = "하지 않는 것"
# 단일 기록자(ADR-008) — 번호 붙는 기록 · 원장 · 커밋 · 푸시는 main 만 한다. 정의에는 '하지 않는 것' 절에만 이름이 나온다.
FORBIDDEN = ("docs_new.py", "git_record.py", "registry.py sync", "masterplan adopt", "release ship", "git push", "git commit")

GROUP_LINE = re.compile(r"^>\s*묶음:\s*(\S+)", re.M)

# 다른 담당이 만들고 있는 명령 — 에이전트 본문이 미리 불러도 된다. 다른 담당이 만들면 비운다.
PENDING_COMMANDS: set[str] = set()   # 다른 담당이 만드는 중인 명령 — 모두 생겼으므로 비웠다
# Claude Code 내장 에이전트 — 정의 파일 없이 부를 수 있다
BUILTIN_AGENTS = {"Explore", "general-purpose", "Plan"}
AGENT_LIKE = re.compile(r"-(auditor|reviewer|analyst|writer|manager|tester|developer|engineer|architect|designer|keeper"
                        r"|guardian|planner|responder|director|researcher|creator|starter|advisor|specialist)$")

ROSTER_START = "<!-- 편제표: scripts/claude_check.py --write 가 만든다 — 손으로 고치지 않는다 -->"
ROSTER_END = "<!-- 편제표 끝 -->"

PROACTIVE = re.compile(r"proactively|must be used|항상 먼저|상시 자동|자동으로 항상", re.I)
TRIGGER = re.compile(r"때|부른다|쓴다")
COLOR = re.compile(r"(?<![\w.&])#[0-9a-fA-F]{3,8}\b")
PX = re.compile(r"\b\d+px\b")
RATIO = re.compile(r"\b\d+(\.\d+)?:1\b")
NOVA_AS_USER = re.compile(
    r"Nova\s*(께서|에게|한테)"
    r"|Nova\s*(가|이)\s*(정|결정|판단|승인|고르|선택|원하)"
    r"|Nova\s*의\s*(판단|결정|승인|지시)")
LINK = re.compile(r"\]\(([^)\s]+)\)")
SLASH_CMD = re.compile(r"(?<![\w/.\-~:<])/([a-z][a-z0-9-]*)(?![\w/.\-])")
BACKTICK = re.compile(r"`([^`\n]+)`")
REPO_PATH = re.compile(r"(?<![\w./-])((?:docs|scripts|web|apps|design|services)/[^\s`'\"(),;|]*)")
PLACEHOLDER = re.compile(r"[<*{…]|\.\.\.|YY|MM|DD|NN|X\.Y|XX")


# ───────────────────────── 읽기
def frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    """`---` 사이 `키: 값` 줄 → (사전, 본문). 형식이 아니면 (None, 전체)."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        k, sep, v = line.partition(":")
        meta[k.strip()] = v.strip() if sep else ""
    return meta, text[end + 5:]


def sections(body: str) -> list[tuple[str, str]]:
    """H2 절 목록 — (제목, 내용)."""
    parts = re.split(r"^## +(.+?)\s*$", body, flags=re.M)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]


@dataclass
class Agent:
    path: Path
    text: str
    meta: dict[str, str] | None
    body: str
    tools: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return (self.meta or {}).get("name", self.path.stem)

    root: Path | None = None

    @property
    def folder(self) -> str:
        """정의가 놓인 폴더(.claude/agents 바로 아래면 '')."""
        base = (self.root or ROOT) / ".claude" / "agents"
        parts = self.path.relative_to(base).parts
        return parts[0] if len(parts) > 1 else ""

    @property
    def group(self) -> str:
        return FOLDERS.get(self.folder, "")

    @property
    def readonly(self) -> bool:
        if self.folder in READONLY_FOLDERS:
            return True
        if self.folder == "ops":
            return self.name not in OPS_WRITERS
        return False

    @property
    def writes(self) -> bool:
        return bool(WRITE_TOOLS & set(self.tools))


def load_agents(root: Path) -> list[Agent]:
    out = []
    base = root / ".claude" / "agents"
    for p in sorted(base.rglob("*.md")):
        if p.name == "README.md" and p.parent == base:
            continue
        text = read(p).replace("\r\n", "\n")
        meta, body = frontmatter(text)
        tools = [t.strip() for t in (meta or {}).get("tools", "").split(",") if t.strip()]
        out.append(Agent(p, text, meta, body, tools, root=root))
    return out


def is_judge(name: str) -> bool:
    return name.endswith(JUDGE_SUFFIXES)


def command_names(root: Path) -> set[str]:
    return {p.stem for p in (root / ".claude" / "commands").glob("*.md")}


def call_sources(root: Path) -> list[tuple[str, Path]]:
    """에이전트를 부르는 문서 — 명령(/이름)과 스킬(스킬 이름)."""
    out = [(p.stem, p) for p in sorted((root / ".claude" / "commands").glob("*.md"))]
    out += [(f"스킬 {p.parent.name}", p) for p in sorted((root / ".claude" / "skills").glob("*/SKILL.md"))]
    return out


def agent_calls(root: Path, defined: set[str]) -> tuple[dict[str, set[str]], list[str]]:
    """명령 · 스킬 md 가 부르는 에이전트 → ({에이전트: {부르는 곳}}, 정의 없는 · 폐지된 호출 오류).

    부름으로 세는 것: 백틱 안 이름이 정의된 에이전트 이름과 같으면(축 표처럼 '에이전트' 낱말이 없는 줄도).
    정의 없음으로 잡는 것(오탐을 줄이려 좁게): `이름` 바로 뒤 '에이전트', `subagent_type: 이름`,
    에이전트처럼 생긴 백틱 이름(-auditor · -reviewer · -analyst · -writer · -manager · -tester).
    """
    calls: dict[str, set[str]] = {}
    errors: list[str] = []
    for cmd, p in call_sources(root):
        rel = _rel(root, p)
        for n, line in enumerate(read(p).splitlines(), 1):
            ticks = BACKTICK.findall(line)
            for tok in ticks:
                if tok in defined:
                    calls.setdefault(tok, set()).add(cmd)
                if tok in RETIRED:
                    errors.append(f"A11 폐지된 에이전트 이름: {rel}:{n} → `{tok}` — 새 이름: {RETIRED[tok]}(ADR-010)")
            strict = set(re.findall(r"`([a-z][a-z0-9-]*)`\s*에이전트", line))
            strict |= set(re.findall(r"subagent_type:\s*`?([A-Za-z][\w-]*)", line))
            strict |= {t for t in ticks if re.fullmatch(r"[a-z][a-z0-9-]*", t) and AGENT_LIKE.search(t)}
            for tok in sorted(strict - defined - BUILTIN_AGENTS - set(RETIRED)):
                errors.append(f"A11 정의 없는 에이전트: {rel}:{n} → `{tok}` — .claude/agents/<폴더>/{tok}.md 를 만들거나 이름을 고친다")
    return calls, errors


# ───────────────────────── 편제표
def roster(root: Path) -> str:
    agents = load_agents(root)
    calls, _ = agent_calls(root, {a.name for a in agents})
    order = {f: i for i, f in enumerate(FOLDERS)}
    rows = sorted(agents, key=lambda a: (order.get(a.folder, len(FOLDERS)), a.name))
    out = ["| 폴더 | 이름 | 묶음 | 쓰기 | 부르는 곳 |", "|---|---|---|---|---|"]
    for a in rows:
        where = " · ".join(c if c.startswith("스킬 ") else f"/{c}" for c in sorted(calls.get(a.name, ())))
        if not where and a.name.endswith(DOMAIN_SUFFIX):
            where = "<팩>-specialist 자리"
        out.append(f"| {a.folder or '(루트)'} | `{a.name}` | {a.group or '—'} | {'쓰기' if a.writes else '읽기 전용'} | {where or '—'} |")
    return "\n".join(out)


def readme_block(text: str) -> str | None:
    s, e = text.find(ROSTER_START), text.find(ROSTER_END)
    if s < 0 or e < s:
        return None
    return text[s + len(ROSTER_START):e].strip("\n")


def write_readme(root: Path) -> bool:
    """README 편제표를 다시 쓴다. 바뀌었으면 True."""
    p = root / ".claude" / "agents" / "README.md"
    text = read(p).replace("\r\n", "\n")
    if readme_block(text) is None:
        raise SystemExit(f"✗ {p} 에 편제표 표식이 없다 — 다음 두 줄을 넣는다:\n{ROSTER_START}\n{ROSTER_END}")
    s, e = text.find(ROSTER_START) + len(ROSTER_START), text.find(ROSTER_END)
    new = text[:s] + "\n" + roster(root) + "\n" + text[e:]
    if new == text:
        return False
    write(p, new)
    return True


# ───────────────────────── 에이전트 검사
def _rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def check_agent(root: Path, a: Agent, commands: set[str]) -> list[str]:
    f = _rel(root, a.path)
    e: list[str] = []
    meta = a.meta
    if meta is None:
        return [f"A1 frontmatter 없음: {f} — 첫 줄 '---' 부터 name · description · tools"]
    for k in REQUIRED_KEYS:
        if not meta.get(k):
            e.append(f"A1 필수 키 없음: {f} '{k}'")
    for k in meta:
        if k not in REQUIRED_KEYS + OPTIONAL_KEYS:
            e.append(f"A1 허용되지 않은 키: {f} '{k}' — name · description · tools · (model) 만")
    name = meta.get("name", "")
    if name != a.path.stem or not re.fullmatch(r"[a-z0-9-]+", name):
        e.append(f"A2 이름: {f} name '{name}' — 파일 이름 '{a.path.stem}' 과 같고 [a-z0-9-]+ 여야 한다")
    d = meta.get("description", "")
    if not HANGUL.search(d):
        e.append(f"A3 description 한글 아님: {f}")
    if not 40 <= len(d) <= 400:
        e.append(f"A3 description 길이 {len(d)}자: {f} — 40~400자")
    if not TRIGGER.search(d):
        e.append(f"A3 description 에 호출 조건이 없다: {f} — '…할 때' · '부른다' · '쓴다'")
    if PROACTIVE.search(d):
        e.append(f"A3 상시 자동 호출 문구: {f} — 명령이 정한 자리에서만 부른다(ADR-009)")
    if not a.tools:
        e.append(f"A4 tools 비어 있음: {f}")
    for t in a.tools:
        if t not in TOOLS:
            e.append(f"A4 모르는 도구: {f} '{t}' — 오타는 권한을 조용히 지운다")
    if a.folder not in FOLDERS:
        e.append(f"A18 정의 위치: {f} — {' · '.join(FOLDERS)} 폴더 안에 둔다(루트는 README 만)")
    if a.readonly or is_judge(name):
        bad = sorted(WRITE_TOOLS & set(a.tools))
        if bad:
            why = f"{a.folder}/ 는 읽기 전용 폴더" if a.readonly else "판정자 이름"
            e.append(f"A5 읽기 전용 자리에 쓰기 도구: {f} {', '.join(bad)} — {why}(쓰기는 development · docs · meta · ops 의 {', '.join(sorted(OPS_WRITERS))})")
        if "Bash" not in a.tools:
            e.append(f"A6 읽기 전용 자리에 Bash 없음: {f} — 실측 대신 문서를 인용하게 된다")
    secs = sections(a.body)
    titles = [t for t, _ in secs]
    got = [t for t in titles if t in SECTIONS]
    if got != SECTIONS:
        e.append(f"A7 본문 6절 순서: {f} — {' → '.join(SECTIONS)} (지금 {' → '.join(titles) or '없음'})")
    ret = dict(secs).get("반환 형식", "")
    missing = [w for w in RETURN_WORDS if w not in ret]
    if missing:
        e.append(f"A8 반환 형식에 빠진 절: {f} {', '.join(missing)}")
    outside = a.text
    for t, c in secs:
        if t == DONT:
            outside = outside.replace(c, "\n", 1)
    for w in FORBIDDEN:
        if w in outside:
            e.append(f"A9 단일 기록자 명령이 '하지 않는 것' 절 밖에: {f} '{w}' — main 만 한다(ADR-008)")
    for l in LINK.findall(a.body):
        if l.startswith(("http:", "https:", "mailto:", "#")):
            continue
        target = l.split("#", 1)[0]
        if target and not (a.path.parent / target).resolve().exists():
            e.append(f"A10 깨진 링크: {f} → {l}")
    for c in sorted(set(SLASH_CMD.findall(a.body))):
        if c not in commands and c not in PENDING_COMMANDS:
            e.append(f"A10 없는 명령: {f} '/{c}' — .claude/commands/{c}.md 가 없다")
    for m in COLOR.findall(a.text):
        e.append(f"A13 색 리터럴: {f} '{m}' — 색은 토큰 이름으로 말한다")
    for m in NOVA_AS_USER.finditer(a.text):
        e.append(f"A14 사용자 호칭: {f} '{m.group(0)}' — 사용자는 '사용자'다(Nova 는 플랫폼 이름)")
    model = meta.get("model")
    if model is not None and model not in MODELS:
        e.append(f"A15 model 값: {f} '{model}' — opus · sonnet · haiku · inherit")
    if GROUP_LINE.search(a.body):
        e.append(f"A16 묶음 줄: {f} '> 묶음: …' — 묶음은 폴더에서 파생한다(줄을 지운다)")
    if name.endswith(DOMAIN_SUFFIX) and a.folder != "domain":
        e.append(f"A17 도메인 에이전트 위치: {f} — .claude/agents/domain/ 에 둔다")
    if a.folder == "domain" and not name.endswith(DOMAIN_SUFFIX):
        e.append(f"A17 domain/ 에는 <팩>-specialist 만: {f}")
    return e


def quick_table_errors(root: Path, defined: set[str]) -> list[str]:
    """A19 — README '상황 → 에이전트' 표의 이름이 실재하는가."""
    p = root / ".claude" / "agents" / "README.md"
    if not p.exists():
        return []
    text = read(p).replace("\r\n", "\n")
    m = re.search(rf"^{re.escape(QUICK_HEADING)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return [f"A19 빠른 표 없음: .claude/agents/README.md '{QUICK_HEADING}' 절 — 상황마다 부를 에이전트"]
    errs = []
    for tok in sorted(set(BACKTICK.findall(m.group(1)))):
        if re.fullmatch(r"[a-z][a-z0-9-]*", tok) and tok not in defined and AGENT_LIKE.search(tok) or tok in RETIRED:
            errs.append(f"A19 빠른 표의 없는 이름: `{tok}`")
    return errs


def check(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(오류, 경고). 오류는 에이전트 · 스킬 모두, 경고는 어느 명령도 부르지 않는 에이전트."""
    agents = load_agents(root)
    errors: list[str] = []
    warnings: list[str] = []
    if not agents:
        errors.append("A0 에이전트 정의 없음: .claude/agents/<폴더>/*.md — 비어 있으면 아무것도 검증하지 않은 것이다")
    commands = command_names(root)
    seen: dict[str, Path] = {}
    for a in agents:
        errors += check_agent(root, a, commands)
        if a.name in seen:
            errors.append(f"A2 이름 중복: {a.name} — {_rel(root, seen[a.name])} · {_rel(root, a.path)}")
        seen[a.name] = a.path
    calls, call_errors = agent_calls(root, set(seen))
    errors += call_errors
    errors += quick_table_errors(root, set(seen))
    for a in agents:
        if a.name.endswith(DOMAIN_SUFFIX):
            stem = a.name[: -len(DOMAIN_SUFFIX)]
            # 팩 이름의 밑줄은 에이전트 이름에서 하이픈이 된다(scripts/packs.py agent_name) — 거꾸로 맞춰 본다
            packs = [d for d in (root / "packs").glob("*/pack.json") if d.parent.name.replace("_", "-") == stem] if (root / "packs").exists() else []
            if not packs:
                errors.append(f"A17 짝 없는 도메인 에이전트: {a.name} — packs/{stem}/pack.json 이 없다(팩을 지웠으면 에이전트도 지운다)")
            continue   # 명령은 '<팩>-specialist' 로 부른다 — 이름으로 세지 않는다
        if a.name not in calls and a.folder not in NO_CALL_FOLDERS:
            warnings.append(f"A11 어느 명령 · 스킬도 부르지 않는 에이전트: {a.name}")
    readme = root / ".claude" / "agents" / "README.md"
    if agents:
        block = readme_block(read(readme).replace("\r\n", "\n")) if readme.exists() else None
        if block is None:
            errors.append("A12 편제표 없음: .claude/agents/README.md — 표식 두 줄을 넣고 --write")
        elif block != roster(root):
            errors.append("A12 편제표가 낡았다: .claude/agents/README.md — uv run python scripts/claude_check.py --write")
    errors += skill_errors(root)
    return errors, warnings


# ───────────────────────── 스킬 검사
def _path_exists(root: Path, p: str) -> bool:
    p = p.rstrip(".:")
    target = root / p
    if target.exists():
        return True
    # 명령이 만드는 산출물 — 같은 폴더에 `_template_<이름>` 이 있으면 생길 파일로 본다(예: docs/product/prd.json)
    return (target.parent / f"_template_{target.name}").exists()


def skill_errors(root: Path) -> list[str]:
    errors: list[str] = []
    base = root / ".claude" / "skills"
    if not base.exists():
        return errors
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        skill = d / "SKILL.md"
        rel = _rel(root, skill)
        if not skill.exists():
            errors.append(f"S1 SKILL.md 없음: {_rel(root, d)}")
            continue
        meta, _body = frontmatter(read(skill).replace("\r\n", "\n"))
        if meta is None:
            errors.append(f"S1 frontmatter 없음: {rel}")
            meta = {}
        if meta.get("name") != d.name:
            errors.append(f"S1 이름: {rel} name '{meta.get('name', '')}' — 폴더 이름 '{d.name}' 과 같아야 한다")
        if not HANGUL.search(meta.get("description", "")):
            errors.append(f"S1 description 한글 아님: {rel}")
        canon = meta.get("canon") == "design-system"
        for md in sorted(d.rglob("*.md")):
            mrel = _rel(root, md)
            text = read(md).replace("\r\n", "\n")
            if not HANGUL.search(text):
                errors.append(f"S4 한국어 아님: {mrel} — 스킬 본문 · 참고는 한국어로 쓴다")
            body = frontmatter(text)[1] if md == skill else text
            for n, line in enumerate(body.splitlines(), 1):
                if canon and not re.search(r"allowlist-canon:\s*\S", line):
                    for rx, what in ((COLOR, "색"), (PX, "px"), (RATIO, "비율")):
                        m = rx.search(line)
                        if m:
                            errors.append(f"S2 정본 값 리터럴({what}): {mrel} '{m.group(0)}' — 값은 정본(토큰 · ui.md)을 가리킨다. 인용이면 같은 줄 'allowlist-canon: <사유>'")
                for l in LINK.findall(line):
                    if l.startswith(("http:", "https:", "mailto:", "#")):
                        continue
                    target = l.split("#", 1)[0]
                    if target and not (md.parent / target).resolve().exists():
                        errors.append(f"S3 깨진 링크: {mrel} → {l}")
                for tok in BACKTICK.findall(line):
                    if re.search(r"(^|\s)cd\s", tok):
                        continue   # 명령이 폴더를 옮기면 경로 기준이 바뀐다
                    for p in REPO_PATH.findall(tok):
                        if PLACEHOLDER.search(p):
                            continue
                        if not _path_exists(root, p):
                            errors.append(f"S3 없는 경로: {mrel} `{p}`")
    return errors


# ───────────────────────── 실행
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="오류가 있으면 종료코드 1")
    ap.add_argument("--write", action="store_true", help="README 편제표를 다시 만든다")
    ap.add_argument("--report", action="store_true", help="편제표 · 경고 · 오류 출력")
    a = ap.parse_args(argv)
    if a.write:
        print("✓ 편제표 갱신: .claude/agents/README.md" if write_readme(ROOT) else "✓ 편제표 그대로")
    errors, warnings = check(ROOT)
    if a.report:
        print(roster(ROOT), "\n")
    for w in warnings:
        print("⚠", w)
    for e in errors:
        print("✗", e)
    if not errors:
        print(f"✓ 에이전트 {len(load_agents(ROOT))}개 · 스킬 정의 정상")
    return 1 if (errors and a.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
