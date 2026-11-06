"""스크립트 공용 도우미 — 저장소 루트 · 프로젝트 설정(nova.project.json) · 파일 쓰기."""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Windows 콘솔(cp949)에서 한글 · 기호 출력이 깨지지 않게
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass


@lru_cache(maxsize=1)
def project() -> dict:
    """nova.project.json — 프로젝트 메타 단일 원천."""
    return json.loads((ROOT / "nova.project.json").read_text(encoding="utf-8"))


def read(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: Path | str, text: str) -> None:
    """UTF-8 · LF 로 쓴다(생성물 비교가 OS 와 무관하게)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def same(path: Path | str, text: str) -> bool:
    """--check 용: 줄 끝 차이는 무시하고 비교."""
    p = Path(path)
    return p.exists() and p.read_text(encoding="utf-8").replace("\r\n", "\n") == text


def env_name(service: str) -> str:
    return service.upper().replace("-", "_")


def py() -> str:
    return os.environ.get("PY", sys.executable)


# ───────────────────────── git 작업 트리 (병렬 개발 · ADR-008)
def git(*args: str, cwd: Path | None = None) -> str:
    import subprocess
    r = subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패: {r.stderr.strip()}")
    return r.stdout.strip()


def main_root(cwd: Path | None = None) -> Path:
    """본 작업 트리 루트 — worktree 안에서도 같은 곳(메시지 버스 · 기록은 여기 하나)."""
    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd))
    return common.parent


def in_linked_worktree(cwd: Path | None = None) -> bool:
    """`git worktree add` 로 만든 작업 트리 안인가 — git-dir 과 git-common-dir 이 다르면 그렇다."""
    try:
        d = Path(git("rev-parse", "--path-format=absolute", "--git-dir", cwd=cwd))
        c = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd))
    except RuntimeError:
        return False
    return d.resolve() != c.resolve()


def current_branch(cwd: Path | None = None) -> str:
    try:
        return git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    except RuntimeError:
        return "main"


def require_main(what: str, cwd: Path | None = None) -> None:
    """단일 기록자 — 번호가 붙는 기록 · 인덱스는 본 작업 트리(main)만 쓴다. 두 브랜치가 같은 번호를 만들면 병합 때 반드시 충돌한다."""
    if os.environ.get("NOVA_ALLOW_WORKTREE_WRITE") == "1" or not in_linked_worktree(cwd):
        return
    raise SystemExit(f"✗ 단일 기록자 규칙: '{what}' 은 본 작업 트리(main)에서만 쓴다. "
                     f"worktree 에서는 코드 · 테스트만 고치고, 기록은 병합(/converge) 뒤 main 에서 남긴다. "
                     f"알릴 것은 메시지 버스로: python nova.py send --to main …")
