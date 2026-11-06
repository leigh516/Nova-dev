#!/usr/bin/env python3
"""푸시한 커밋을 docs/git/git_YYMMDD_NN.md 로 기록하고 git_index.md 에 한 줄 추가한다.

  uv run python scripts/git_record.py "<요약>" [커밋범위]
기본 범위: git 인덱스(docs/git/git_index.md) 마지막 행이 가리키는 기록의 마지막 커밋..HEAD — 기록 사이의 커밋이
빠지지 않게(여러 커밋을 한 번에 푸시해도). 그 기록을 못 찾으면 예전대로 HEAD~1..HEAD.
범위 안 커밋이 .env · *.key · *.pem · id_rsa 를 건드리면 경고한다(비밀이 원격에 올라갔을 수 있다).
원격 URL 은 remote.origin.url 에서 계산한다(하드코딩 없음).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, read, require_main, write  # noqa: E402

GIT_DIR = ROOT / "docs" / "git"


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 실패: {r.stderr.strip()}")
    return r.stdout.rstrip("\n")


def web_url(remote: str) -> str:
    """git@github.com:o/r.git · https://github.com/o/r(.git) → https://github.com/o/r"""
    remote = remote.strip()
    m = re.match(r"git@([^:]+):(.+?)(\.git)?$", remote)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    return re.sub(r"\.git$", "", re.sub(r"https://[^@/]+@", "https://", remote))


FALLBACK = "HEAD~1..HEAD"
SECRET = re.compile(r"(^|/)(\.env|id_rsa|[^/]+\.key|[^/]+\.pem)$")


def default_range(gdir: Path | None = None) -> str:
    """git 인덱스 마지막 행 → 그 기록 문서 '## 커밋' 의 마지막 해시 → '<해시>..HEAD'. 못 찾거나 git 이 모르는 해시면 FALLBACK."""
    gdir = gdir or GIT_DIR
    idx = gdir / "git_index.md"
    if not idx.exists():
        return FALLBACK
    links = re.findall(r"^\|\s*\[[^\]]+\]\(([^)]+\.md)\)", read(idx), re.M)
    if not links or not (gdir / links[-1]).exists():
        return FALLBACK
    body = read(gdir / links[-1])
    sec = re.search(r"^## 커밋\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    shas = re.findall(r"^- `([0-9a-f]{7,40})`", sec.group(1) if sec else "", re.M)
    if not shas:
        return FALLBACK
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{shas[-1]}^{{commit}}"], cwd=ROOT, capture_output=True, text=True)
    return f"{shas[-1]}..HEAD" if r.returncode == 0 else FALLBACK


def changed_files(rng: str) -> list[str]:
    files = git("diff", "--name-only", rng) if ".." in rng else git("show", "--name-only", "--format=", rng)
    return [f.strip() for f in files.splitlines() if f.strip()]


def secret_files(rng: str) -> list[str]:
    return [f for f in changed_files(rng) if SECRET.search(f)]


HISTORY_DOC = re.compile(r"(?:^|/)docs/history/(history_\d{6}_\d{2})\.md$")


def history_links(rng: str, gdir: Path | None = None) -> str:
    """추적 칸 '연결' — 범위 안 커밋이 건드린 이력 문서 링크(지금도 있는 것만). 없으면 '없음 — …'(자리표시가 아니다)."""
    hist = (gdir or GIT_DIR).parent / "history"
    names = sorted({m.group(1) for f in changed_files(rng) if (m := HISTORY_DOC.search(f))})
    links = [f"[{n}](../history/{n}.md)" for n in names if (hist / f"{n}.md").exists()]
    return " · ".join(links) if links else "없음 — 이 범위의 커밋이 이력 문서를 건드리지 않았다"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    if argv[0] not in ("-h", "--help"):
        # 번호가 붙는 기록 — worktree 에서 쓰면 두 브랜치가 같은 번호를 만든다(단일 기록자 · ADR-008)
        require_main("git 기록(번호가 붙는 기록)")
    # -h/--help 는 사용법만 출력하고 끝낸다 — 예전에는 '--help' 를 요약으로 받아 기록 파일을 만들었다
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("summary", help="기록 요약(한국어)")
    ap.add_argument("range", nargs="?", default="", help="커밋 범위(기본: 마지막 git 기록의 마지막 커밋..HEAD, 없으면 HEAD~1..HEAD)")
    a = ap.parse_args(argv)
    summary, rng = a.summary, a.range or default_range()
    if not a.range and rng != FALLBACK and git("rev-list", "--count", rng) == "0":
        rng = FALLBACK  # 지난 기록 뒤 새 커밋이 없다 — 예전 기본으로(빈 기록을 만들지 않게)
    if ".." in rng and git("rev-list", "--count", "HEAD") == "1":
        rng = "HEAD"  # 첫 커밋
    print(f"범위: {rng}")
    for f in secret_files(rng):
        print(f"⚠ 경고: 비밀일 수 있는 파일이 범위 안 커밋에 있다 — {f} (원격에 올라갔다면 키를 바꾸고 이력에서 지운다)")
    now = dt.datetime.now()
    day = now.strftime("%y%m%d")
    n = 1
    while (GIT_DIR / f"git_{day}_{n:02d}.md").exists():
        n += 1
    gid = f"git_{day}_{n:02d}"
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    try:
        url = f"{web_url(git('config', '--get', 'remote.origin.url'))}/tree/{branch}"
    except SystemExit:
        url = "(원격 없음)"
    log_args = ["log", "--reverse", "--format=- `%h` %s"]
    commits = git(*log_args, rng) if ".." in rng else git(*log_args, "-1", rng)
    stat = git("diff", "--stat", rng) if ".." in rng else git("show", "--stat", "--format=", rng)
    stat = "\n".join(stat.splitlines()[-25:])
    # 추적 칸 다섯(REQ-261105-04) — git 기록은 사람 칸까지 생성기가 채운다(원천 = 커밋 범위, 연결 = 범위 안 이력)
    trace = (
        f"| 문서 ID | {gid} |\n| 생성 | {now.date().isoformat()} · `git_record.py` |\n"
        f"| 위치 | `docs/git/{gid}.md` |\n| 원천 | 커밋 범위 `{rng}` |\n| 연결 | {history_links(rng)} |\n"
    )
    text = (
        f"# {gid} · {summary}\n\n| 항목 | 값 |\n|---|---|\n"
        f"| 일시 | {now.strftime('%Y-%m-%d %H:%M')} |\n| 브랜치 | `{branch}` → origin |\n| 원격 | {url} |\n{trace}\n"
        f"## 커밋\n{commits}\n\n## 변경 파일 통계\n```\n{stat}\n```\n"
    )
    write(GIT_DIR / f"{gid}.md", text)
    first = commits.splitlines()[0].split("`")[1] if commits else "-"
    idx = GIT_DIR / "git_index.md"
    body = read(idx)
    if not body.endswith("\n"):
        body += "\n"
    write(idx, body + f"| [{gid}]({gid}.md) | {now.date().isoformat()} | `{first}` | {summary} |\n")
    print(f"docs/git/{gid}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
