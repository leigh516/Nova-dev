#!/usr/bin/env python3
"""도메인 팩 검사 · 생성 (STD-DOMAIN-PACK-001).

  uv run python scripts/packs.py check                                   # lint — 의존 방향 · pack.json · 켜진 팩
  uv run python scripts/packs.py new <팩> --title "<이름>" --extends <서비스>[,<서비스>]
  uv run python scripts/packs.py agent <팩>                              # 팩과 짝인 도메인 에이전트 다시 만들기
  python nova.py new-pack <팩> --title "<이름>" --extends <서비스>

검사(실패):
  · 코어(services/** · packages/**)가 팩을 import — 코어 오염 금지 1조(분기가 필요하면 포트를 늘린다)
  · 팩이 다른 팩을 import — 금지 2조(공통이 필요하면 코어 승격)
  · pack.json 이름 ≠ 폴더, extends 에 없는 서비스
  · nova.project.json "packs" 에 없는 팩
  · 팩과 짝인 도메인 에이전트(.claude/agents/<팩>-specialist.md)가 없음 — 팩마다 업무를 아는 판정자를 하나 둔다
    (틀은 packs/_template/agent.md, 지식은 베끼지 않고 팩을 읽는다 — ADR-009)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, project, write  # noqa: E402

from nova_common import catalog  # noqa: E402

import naming  # noqa: E402

PACKS = ROOT / "packs"
AGENT_TEMPLATE = "agent.md"   # packs/_template/agent.md — 팩 폴더에는 남기지 않고 .claude/agents/ 로 만든다
IMPORT = re.compile(r"^\s*(?:from|import)\s+packs(?:\.(\w+))?", re.M)
NAME = naming.pattern("pack")  # 명명 규약 선언 정본(registry/naming.json)에서


def pack_dirs() -> list[Path]:
    return sorted(p for p in PACKS.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")) and p.name != "__pycache__") if PACKS.exists() else []


def check() -> list[str]:
    errs = []
    for base in (ROOT / "services", ROOT / "packages"):
        for py in base.rglob("*.py"):
            if "_template" in py.parts or ".venv" in py.parts:
                continue
            if IMPORT.search(py.read_text(encoding="utf-8")):
                errs.append(f"코어가 팩을 import: {py.relative_to(ROOT).as_posix()} — 분기가 필요하면 포트(@packs.port)를 늘린다")
    names = {s.name for s in catalog.services()}
    for d in pack_dirs():
        meta_f = d / "pack.json"
        if not meta_f.exists():
            errs.append(f"팩 {d.name}: pack.json 없음")
            continue
        meta = json.loads(meta_f.read_text(encoding="utf-8"))
        if meta.get("name") != d.name:
            errs.append(f"팩 {d.name}: pack.json name '{meta.get('name')}' ≠ 폴더 이름")
        for svc in meta.get("extends", []):
            if svc not in names:
                errs.append(f"팩 {d.name}: extends 에 없는 서비스 {svc}")
        if not agent_path(d.name).exists():
            errs.append(f"팩 {d.name}: 도메인 에이전트 없음 {agent_path(d.name).relative_to(ROOT).as_posix()} — uv run python scripts/packs.py agent {d.name}")
        for py in d.rglob("*.py"):
            for m in IMPORT.finditer(py.read_text(encoding="utf-8")):
                if m.group(1) and m.group(1) != d.name:
                    errs.append(f"팩 {d.name} 이(가) 다른 팩 {m.group(1)} 을(를) import: {py.relative_to(ROOT).as_posix()} — 공통이면 코어로 승격")
    for p in project().get("packs", []):
        if not (PACKS / p / "pack.json").exists():
            errs.append(f"nova.project.json packs: 없는 팩 {p}")
    return errs


def agent_name(pack: str) -> str:
    """팩 이름(밑줄 허용) → 에이전트 이름(소문자 · 숫자 · 하이픈 — claude_check A2). 예: demo_x → demo-x-specialist."""
    return pack.replace("_", "-") + "-specialist"


def agent_path(name: str, root: Path = ROOT) -> Path:
    return root / ".claude" / "agents" / "domain" / f"{agent_name(name)}.md"   # 폴더형 편제(ADR-010)


def agent(name: str, title: str | None = None, root: Path = ROOT) -> Path:
    """팩과 짝인 도메인 에이전트를 틀에서 만든다(있으면 덮어쓴다 — 틀이 바뀌었을 때 다시 맞추는 용도)."""
    d = root / "packs" / name
    if not (d / "pack.json").exists():
        raise SystemExit(f"없는 팩: {name}")
    title = title or json.loads((d / "pack.json").read_text(encoding="utf-8")).get("title", name)
    tpl = (root / "packs" / "_template" / AGENT_TEMPLATE).read_text(encoding="utf-8")
    out = agent_path(name, root)
    write(out, tpl.replace("__AGENT__", agent_name(name)).replace("__PACK__", name).replace("__TITLE__", title))
    import claude_check   # 편제표(.claude/agents/README.md)도 함께 — 만들자마자 lint 가 낡았다고 하지 않게
    claude_check.write_readme(root)
    return out


def new(name: str, title: str, extends: list[str]) -> Path:
    if not NAME.match(name):
        raise SystemExit(f"팩 이름은 영문 소문자 · 숫자 · 밑줄(예: pharma): {name}")
    dest = PACKS / name
    if dest.exists():
        raise SystemExit(f"이미 있는 팩: {name}")
    names = {s.name: s for s in catalog.services()}
    for svc in extends:
        if svc not in names:
            raise SystemExit(f"없는 서비스: {svc}")
    shutil.copytree(PACKS / "_template", dest, ignore=shutil.ignore_patterns("__pycache__", AGENT_TEMPLATE))
    for f in dest.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".md", ".py"):
            write(f, f.read_text(encoding="utf-8").replace("__PACK__", name).replace("__TITLE__", title))
    meta = json.loads((dest / "pack.json").read_text(encoding="utf-8"))
    meta["extends"] = extends
    meta.setdefault("entities", [])  # 이 팩의 개념(개념 원장 layer=pack) — naming entity add … --layer pack --pack <팩> 와 함께 적는다
    write(dest / "pack.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    for svc in extends:
        pkg = names[svc].package
        write(dest / "policies" / f"{pkg}.py", f'''"""{title} 팩 — {svc} 서비스 포트 구현. 코어 포트 목록은 서비스 코드의 @packs.port(...) 를 찾는다."""
from nova_common.packs import implement  # noqa: F401

# 예:
# @implement("{pkg}.<포트 이름>")
# def rule(...):
#     ...
''')
    agent(name, title)
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    n = sub.add_parser("new")
    n.add_argument("name")
    n.add_argument("--title", required=True)
    n.add_argument("--extends", default="")
    g = sub.add_parser("agent")
    g.add_argument("name")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        errs = check()
        for e in errs:
            print("✗", e)
        if errs:
            return 1
        print(f"✓ 도메인 팩 정상: {len(pack_dirs())}개 · 켜짐 {project().get('packs', [])}")
        return 0
    if a.cmd == "agent":
        print(f"✓ {agent(a.name).relative_to(ROOT).as_posix()} — 편제표도 갱신했다")
        return 0
    dest = new(a.name, a.title, [x for x in a.extends.split(",") if x])
    print(f"✓ {dest.relative_to(ROOT).as_posix()} — glossary.md 부터 채우고, policies/ 에 포트 구현, nova.project.json packs 에 추가하면 켜진다. 도메인 에이전트 {agent_path(a.name).relative_to(ROOT).as_posix()} 와 편제표도 만들었다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
