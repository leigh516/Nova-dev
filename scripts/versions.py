#!/usr/bin/env python3
"""판본 번호 규칙 — SemVer X.Y.Z 와 사전 판본 X.Y.Z-rc.N, 정식 태그 고르기 · 최소 올림(규약 docs/conventions/versioning.md).

release · new_project · template_init · upstream 이 같은 잣대를 쓰게 하는 한 곳이다.
'정식 태그' = vX.Y.Z(사전 판본 -rc.N 제외). 정렬은 숫자로 한다(문자 순서면 v0.10.0 이 v0.9.0 보다 앞선다).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$")
LEVELS = ("patch", "minor", "major")


def parse(v: str) -> tuple[int, int, int, int | None] | None:
    m = PATTERN.match(v.removeprefix("v"))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), (int(m.group(4)) if m.group(4) is not None else None)


def valid(v: str) -> bool:
    return parse(v) is not None


def key(v: str) -> tuple[int, ...]:
    """정렬 열쇠 — 같은 X.Y.Z 에서는 rc 가 정식보다 앞선다."""
    p = parse(v)
    if p is None:
        return (-1,)
    return (p[0], p[1], p[2], 0, p[3]) if p[3] is not None else (p[0], p[1], p[2], 1, 0)


def core(v: str) -> tuple[int, int, int]:
    p = parse(v)
    if p is None:
        raise ValueError(f"판본 형식이 아니다: {v}")
    return p[0], p[1], p[2]


def is_rc(v: str) -> bool:
    p = parse(v)
    return p is not None and p[3] is not None


def is_formal(tag: str) -> bool:
    """정식 태그인가 — 'v' 로 시작하고 rc 가 아닌 X.Y.Z."""
    return tag.startswith("v") and valid(tag) and not is_rc(tag)


def formal_sorted(tags) -> list[str]:
    """정식 태그만 오래된 것부터."""
    return sorted((t for t in tags if is_formal(t)), key=key)


def latest_formal(tags) -> str:
    f = formal_sorted(tags)
    return f[-1] if f else ""


def bump(last: str, level: str) -> str:
    """last 에서 level 만큼 올린 최소 판본. 0.x 동안은 깨짐(major)도 0.y 올림으로 낸다(규약 §0.x)."""
    x, y, z = core(last)
    if level == "major":
        return f"0.{y + 1}.0" if x == 0 else f"{x + 1}.0.0"
    if level == "minor":
        return f"{x}.{y + 1}.0"
    return f"{x}.{y}.{z + 1}"


def is_toplevel(root: Path) -> bool:
    """root 가 git 저장소의 맨 위인가 — 아니면 상위 저장소(예: 테스트 임시 폴더를 품은 Nova)의 태그 · 변경을 잘못 빌린다."""
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    except OSError:          # git 이 없는 PC
        return False
    return r.returncode == 0 and Path(r.stdout.strip()).resolve() == Path(root).resolve()


def local_tags(root: Path) -> list[str]:
    """root 저장소의 v* 태그. git 이 없거나 root 가 저장소 맨 위가 아니면 빈 목록(호출부가 '태그 없음'으로 경고한다)."""
    if not is_toplevel(root):
        return []
    r = subprocess.run(["git", "tag", "--list", "v*"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.split() if r.returncode == 0 else []


def remote_tags(url: str, cwd: Path) -> dict[str, str]:
    """원격(또는 경로)의 태그 → 커밋. 주석 태그는 벗긴 커밋(^{})을 쓴다. 닿지 못하면 RuntimeError."""
    r = subprocess.run(["git", "ls-remote", "--tags", url], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"git ls-remote {url} 실패: {r.stderr.strip()}")
    out: dict[str, str] = {}
    for ln in r.stdout.splitlines():
        sha, _, ref = ln.partition("\t")
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            out[name[:-3]] = sha          # 벗긴 커밋이 이긴다
        else:
            out.setdefault(name, sha)
    return out
