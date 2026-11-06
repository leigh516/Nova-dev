#!/usr/bin/env python3
"""문서 새로 만들기 — 다음 번호 계산 · 템플릿 채우기 · 인덱스 한 줄 추가.

사용:
  uv run python scripts/docs_new.py req      "<제목>"
  uv run python scripts/docs_new.py interview "<주제>"                       (고객 인터뷰 기록 INT-YYMMDD-NN)
  uv run python scripts/docs_new.py plan     "<제목>" --req REQ-261103-01   (plan_REQ_NN + tasks_REQ_NN)
  uv run python scripts/docs_new.py history  "<제목>" [--plan plan_REQ_01]
  uv run python scripts/docs_new.py session  "<요약>"                         (LATEST.md 도 갱신)
  uv run python scripts/docs_new.py review   "<제목>"
  uv run python scripts/docs_new.py verify   "<제목>"
  uv run python scripts/docs_new.py adr      "<제목>" [--slug english-name]
만든 파일 경로를 출력한다. 내용은 템플릿 칸을 채워서 완성한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, project, read, require_main, write  # noqa: E402

DOCS = ROOT / "docs"

# kind: (폴더, 파일 접두어, 인덱스 파일)
DAILY = {
    "req": ("requirement", "requirement", "requirement_index.md"),
    "interview": ("requirement/interviews", "interview", "interview_index.md"),
    "history": ("history", "history", "history_index.md"),
    "session": ("session", "session", "session_index.md"),
    "review": ("reviews", "review", "review_index.md"),
    "verify": ("verification", "verify", "verification_index.md"),
}


def today(now: dt.datetime | None = None) -> dt.date:
    return (now or dt.datetime.now()).date()


def next_daily(folder: Path, prefix: str, day: str) -> int:
    n = 1
    while (folder / f"{prefix}_{day}_{n:02d}.md").exists():
        n += 1
    return n


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8").stdout.strip()
    except Exception:
        return ""


def doc_path(path: Path) -> str:
    """머리 표 '위치' 칸 — 저장소 기준 경로(docs/…). DOCS 를 바꿔 끼운 테스트에서도 같은 모양이 되게 DOCS 기준으로 센다."""
    return "docs/" + path.relative_to(DOCS).as_posix()


def fill(tpl: str, **kw: str) -> str:
    for k, v in kw.items():
        tpl = tpl.replace("{{" + k + "}}", v)
    return tpl


def append_row(index: Path, row: str) -> None:
    text = read(index)
    if not text.endswith("\n"):
        text += "\n"
    write(index, text + row + "\n")


def master_version() -> str:
    m = re.search(r"\|\s*버전\s*\|\s*\*\*v([\d.]+)\*\*", read(DOCS / "plans" / "master_plan.md"))
    return m.group(1) if m else "1.0"


def new_daily(kind: str, title: str, *, plan: str = "", now: dt.datetime | None = None) -> Path:
    folder, prefix, index = DAILY[kind]
    d = today(now)
    day = d.strftime("%y%m%d")
    base = DOCS / folder
    n = next_daily(base, prefix, day)
    date = d.isoformat()
    if kind == "req":
        doc_id = f"REQ-{day}-{n:02d}"
    elif kind == "interview":
        doc_id = f"INT-{day}-{n:02d}"
    else:
        doc_id = f"{prefix}_{day}_{n:02d}"
    path = base / f"{prefix}_{day}_{n:02d}.md"
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    head = git("log", "-1", "--format=%h %s") or "-"
    text = fill(read(base / "_template.md"), ID=doc_id, TITLE=title, DATE=date,
                OWNER=project().get("owner", ""), DATETIME=utc,
                BRANCH=git("rev-parse", "--abbrev-ref", "HEAD") or "-", HEAD=head,
                CMD=f"docs_new.py {kind}", PATH=doc_path(path))
    if kind == "session":
        text = text.replace("## 1. 이번 세션 요약 (3~5줄)", f"## 1. 이번 세션 요약 (3~5줄)\n{title}", 1)
    write(path, text)
    link = f"[{doc_id}]({path.name})"
    rows = {
        "req": f"| {link} | {date} | {title} | 진행 중 | - |",
        "interview": f"| {link} | {date} | {title} | - | - |",
        "history": f"| {link} | {date} | {title} | {plan or '-'} |",
        "session": f"| {link} | {utc} | {title} | (§4 참조) |",
        "review": f"| {link} | {date} | {title} | - |",
        "verify": f"| {link} | {date} | {title} | - |",
    }
    append_row(base / index, rows[kind])
    if kind == "session":
        write(base / "LATEST.md", text)
    return path


def next_plan_no() -> int:
    nums = [int(m.group(1)) for p in (DOCS / "plans").glob("plan_REQ_*.md")
            if (m := re.match(r"plan_REQ_(\d+)\.md$", p.name))]
    return max(nums, default=0) + 1


def new_plan(title: str, req: str, *, now: dt.datetime | None = None) -> Path:
    plans = DOCS / "plans"
    n = next_plan_no()
    nn = f"{n:02d}"
    date = today(now).isoformat()
    req_link = tasks_req_link = "-"
    if req:
        m = re.fullmatch(r"REQ-(\d{6})-(\d{2})", req)
        if not m:
            raise SystemExit(f"요구 ID 형식이 틀립니다: {req} (예: REQ-261103-01)")
        req_link = f"[{req}](../requirement/requirement_{m.group(1)}_{m.group(2)}.md)"
        # tasks 파일은 plans/tasks/ 한 단계 아래 — 같은 요구를 가리키려면 두 단계 올라간다
        tasks_req_link = f"[{req}](../../requirement/requirement_{m.group(1)}_{m.group(2)}.md)"
    plan = plans / f"plan_REQ_{nn}.md"
    tasks = plans / "tasks" / f"tasks_REQ_{nn}.md"
    kw = dict(NN=nn, TITLE=title, DATE=date, REQ_LINK=req_link, MASTER_VERSION=master_version(),
              CMD="docs_new.py plan", PATH=doc_path(plan), TASKS_PATH=doc_path(tasks), TASKS_REQ_LINK=tasks_req_link)
    write(plan, fill(read(plans / "_template_plan.md"), **kw))
    write(tasks, fill(read(plans / "_template_tasks.md"), **kw))
    append_row(plans / "plan_index.md", f"| [plan_REQ_{nn}]({plan.name}) | {title} | {req or '-'} | v1.0 | 진행 중 |")
    return plan


def slugify(title: str) -> str:
    """파일 이름용 — 영문 · 숫자만(URL · 셸 친화). 남는 게 없으면 decision."""
    s = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    return s[:40] or "decision"


def new_adr(title: str, *, slug: str = "", now: dt.datetime | None = None) -> Path:
    adr = DOCS / "adr"
    nums = [int(m.group(1)) for p in adr.glob("ADR-*.md") if (m := re.match(r"ADR-(\d{3})", p.name))]
    n = max(nums, default=0) + 1
    doc_id = f"ADR-{n:03d}"
    date = today(now).isoformat()
    path = adr / f"{doc_id}-{slugify(slug or title)}.md"
    write(path, fill(read(adr / "_template.md"), ID=doc_id, TITLE=title, DATE=date,
                     CMD="docs_new.py adr", PATH=doc_path(path)))
    append_row(adr / "README.md", f"| [{doc_id}]({path.name}) | {date} | {title} | 제안 |")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=[*DAILY, "plan", "adr"])
    ap.add_argument("title")
    ap.add_argument("--req", default="", help="plan: 연결할 요구 ID")
    ap.add_argument("--plan", default="", help="history: 관련 계획")
    ap.add_argument("--slug", default="", help="adr: 파일 이름용 영문 슬러그(기본: 제목에서 영문만)")
    a = ap.parse_args(argv)
    require_main(f"번호가 붙는 기록({a.kind})")   # 단일 기록자 — 두 브랜치가 같은 번호를 만들지 않게(ADR-008)
    if a.kind == "plan":
        path = new_plan(a.title, a.req)
    elif a.kind == "adr":
        path = new_adr(a.title, slug=a.slug)
    else:
        path = new_daily(a.kind, a.title, plan=a.plan)
    print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
