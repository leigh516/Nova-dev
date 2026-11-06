#!/usr/bin/env python3
"""템플릿에서 시작하기 — GitHub 'Use this template' 으로 만든 저장소를 그 자리에서 새 프로젝트로 바꾼다.

  python nova.py init --name "<프로젝트 이름>" --slug <영문-소문자> [--owner 이름] [--domain 도메인] [--app-id 패키지] [--ref 태그|HEAD] [--dry]

템플릿 복사본에는 Nova 의 기록(요구 · 계획 · 이력 · git 기록 · 세션)과 이름이 그대로 들어 있다.
이 명령은 new_project.py 의 create() 를 임시 폴더에 돌려 '새 프로젝트'를 만든 뒤, 이 저장소의 작업 트리를 그것으로 바꾼다
(.git 은 그대로 — 원격 · 이력 유지). 결과는 `python nova.py new-project` 로 만든 것과 같다.

지키는 것
  - Nova 원천 저장소에서는 돌지 않는다(원격이 Nova 자신이면 거부) — 원천의 기록을 지우지 않게
  - 이미 초기화된 저장소(slug 가 nova 가 아님)에서는 돌지 않는다
  - 커밋 안 된 변경이 있으면 거부한다(되돌릴 수 있게 — git checkout 한 번으로 원래대로)
  - 상류 기준선: 이 저장소 첫 커밋의 tree 가 Nova 의 어느 커밋 tree 와 같은지 찾아 upstream.base 로 남긴다
    (템플릿 복사는 내용을 그대로 옮기므로 tree 해시가 같다). Nova 에 접근할 수 없으면 비워 두고 안내한다
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import versions  # noqa: E402
from novalib import ROOT, project, write  # noqa: E402

KEEP = {".git", ".venv", "node_modules"}   # 바꾸지 않는 것 — 저장소 이력 · 설치물


def git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    except OSError:   # git 이 없는 PC — 판정에 쓰는 값만 비운다(호출부가 비면 안내한다)
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def norm_url(u: str) -> str:
    """https · ssh · .git 차이를 없앤 비교용 주소."""
    u = u.strip().lower().removesuffix(".git").rstrip("/")
    for p in ("https://", "http://", "ssh://", "git@"):
        u = u.removeprefix(p)
    return u.replace("github.com:", "github.com/")


def guard(root: Path, meta: dict) -> list[str]:
    """돌면 안 되는 이유 목록(비면 진행)."""
    why = []
    if meta.get("slug") != "nova":
        why.append(f"이미 초기화된 저장소다(slug={meta.get('slug')}) — 새 프로젝트는 템플릿에서 새 저장소를 만든다")
    source = (meta.get("platform") or {}).get("source") or meta.get("git_remote", "")
    origin = git(root, "config", "--get", "remote.origin.url")
    if origin and source and norm_url(origin) == norm_url(source):
        why.append("이 저장소는 Nova 원천이다(원격이 플랫폼 원본) — 원천의 기록을 지우지 않는다. 템플릿으로 새 저장소를 만든 뒤 거기서 실행")
    if git(root, "status", "--porcelain"):
        why.append("커밋 안 된 변경이 있다 — 먼저 커밋해 두면 이 명령을 git 으로 되돌릴 수 있다")
    return why


def find_base(root: Path, source: str) -> str:
    """이 저장소 첫 커밋의 tree 와 같은 tree 를 가진 Nova 커밋(없으면 "")."""
    first = git(root, "rev-list", "--max-parents=0", "HEAD").splitlines()
    if not first or not source:
        return ""
    want = git(root, "rev-parse", f"{first[-1]}^{{tree}}")
    if not want:
        return ""
    git(root, "fetch", "-q", "--depth", "200", source, "main")   # 접근 못 하면 FETCH_HEAD 가 없어 아래가 빈 값
    log = git(root, "log", "--format=%H %T", "-n", "200", "FETCH_HEAD")
    for line in log.splitlines():
        c, t = line.split()
        if t == want:
            return c
    return ""


def pick_source_ref(root: Path, source: str, ref: str | None) -> tuple[str, str]:
    """어느 판본으로 초기화할까 → (태그, 커밋). 기본은 원천의 최신 정식 태그(rc 제외 — 규약 versioning.md §6).
    "HEAD" 를 고르거나, 원천에 닿지 못하거나, 정식 태그가 없으면 ("HEAD", "") — 지금처럼 이 저장소 작업 트리에서 만든다.
    태그 내용은 FETCH_HEAD 로만 받는다 — 복제본에 Nova 태그를 남기면 복제본 자기 판본(release suggest)이 Nova 번호에 섞인다."""
    if ref == "HEAD":
        return "HEAD", ""
    if not source:
        print("⚠ 원천 주소(platform.source · git_remote)가 없다 — 이 저장소 작업 트리에서 만든다")
        return "HEAD", ""
    try:
        tags = versions.remote_tags(source, root)
    except RuntimeError as e:
        print(f"⚠ 원천에 닿지 못했다 — 이 저장소 작업 트리에서 만든다: {e}")
        return "HEAD", ""
    tag = ref or versions.latest_formal(tags)
    if not tag:
        print("⚠ 원천에 정식 태그가 없다 — 이 저장소 작업 트리에서 만든다")
        return "HEAD", ""
    if tag not in tags:
        raise SystemExit(f"✗ 원천에 태그 {tag} 이 없다 — 후보: {', '.join(versions.formal_sorted(tags)) or '(없음)'}")
    fetched = subprocess.run(["git", "fetch", "-q", "--no-tags", source, f"refs/tags/{tag}"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if fetched.returncode != 0:
        raise SystemExit(f"✗ 원천 태그 {tag} 를 받지 못했다: {fetched.stderr.strip()}")
    return tag, git(root, "rev-parse", "FETCH_HEAD^{commit}")


def add_upstream_remote(root: Path, url: str) -> None:
    """상류 git 원격 'upstream' 을 단다(이미 있으면 그대로) — upstream tags · plan 이 이 주소로 판본을 본다."""
    if url and not git(root, "remote", "get-url", "upstream"):
        subprocess.run(["git", "remote", "add", "upstream", url], cwd=root, check=True, capture_output=True)


def tracked(root: Path) -> list[str]:
    """root 저장소가 추적하는 파일(상대 경로). 못 읽으면 멈춘다 — 무엇이 무시 파일인지 모르면 아무것도 지울 수 없다."""
    def run(*args: str) -> subprocess.CompletedProcess | None:
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True)
        except OSError:
            return None
    top = run("rev-parse", "--show-toplevel")
    # 상위 폴더의 다른 저장소가 답하면(root 가 저장소 루트가 아님) 그 목록은 root 의 것이 아니다
    if not top or top.returncode != 0 or Path(top.stdout.decode("utf-8").strip()).resolve() != root.resolve():
        raise SystemExit(f"✗ {root} 의 git 추적 목록을 읽지 못했다(저장소 루트가 아님) — 무시 파일(.env · data/ …)을 지우지 않으려고 멈춘다")
    ls = run("ls-files", "-z")
    if not ls or ls.returncode != 0:
        raise SystemExit("✗ git ls-files 실패 — 무시 파일(.env · data/ …)을 지우지 않으려고 멈춘다")
    return [x for x in ls.stdout.decode("utf-8").split("\0") if x]


def replace_tree(root: Path, new: Path) -> None:
    """root 의 추적 파일(KEEP 제외)을 new 의 내용으로 바꾼다.
    git 무시 파일(.env · data/ · 로컬 설정)은 그대로 둔다 — 커밋에 없으니 git checkout 으로도 되살릴 수 없다."""
    emptied: set[Path] = set()
    for rel in tracked(root):
        if rel.split("/", 1)[0] in KEEP:
            continue
        p = root / rel
        if p.is_file() or p.is_symlink():
            p.unlink()
            emptied.add(p.parent)
    for d in sorted(emptied, key=lambda x: len(x.parts), reverse=True):   # 추적 파일만 있던 폴더는 비면 치운다(깊은 곳부터)
        while d != root and d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    for p in new.iterdir():
        if p.name in KEEP:
            continue
        dst = root / p.name
        shutil.copytree(p, dst, dirs_exist_ok=True) if p.is_dir() else shutil.copy2(p, dst)   # 남은 무시 파일 옆에 겹쳐 놓는다


def init(name: str, slug: str, *, owner: str | None = None, domain: str | None = None, app_id: str | None = None,
         root: Path = ROOT, dry: bool = False, ref: str | None = None) -> dict:
    meta = project()
    why = guard(root, meta)
    if why:
        for w in why:
            print("✗", w)
        raise SystemExit(1)
    source = (meta.get("platform") or {}).get("source") or meta.get("git_remote", "")
    origin = git(root, "config", "--get", "remote.origin.url")
    tag, commit = pick_source_ref(root, source, ref)
    if tag == "HEAD":
        if ref == "HEAD":
            print("⚠ --ref HEAD — 정식 판본이 아니라 이 저장소 작업 트리에서 만든다")
        base = find_base(root, source)
    else:
        base = commit
    if dry:
        print(f"■ (--dry) {name} · {slug} · 원격 {origin or '(없음)'} · 판본 {tag if tag != 'HEAD' else '(작업 트리)'}"
              f" · 상류 기준선 {base[:10] or '(찾지 못함)'}")
        return {"base": base, "origin": origin, "tag": "" if tag == "HEAD" else tag}
    import new_project as np
    with tempfile.TemporaryDirectory(prefix="nova-init-") as tmp:
        if tag == "HEAD":
            out = np.create(Path(tmp) / "p", name, slug, owner=owner, remote=origin or None, domain=domain, app_id=app_id,
                            git=False, ref="HEAD")
        else:   # 원천 판본의 내용 · 생성기로 만든다(new-project 의 기본과 같다)
            out = np.create_from_ref(Path(tmp) / "p", commit, root=root, name=name, slug=slug, owner=owner, remote=origin or None,
                                     domain=domain, app_id=app_id, git=False, tag=tag, url=source)
        m = json.loads((out / "nova.project.json").read_text(encoding="utf-8"))
        # create() 는 '나'를 상류로 적는다 — 템플릿에서는 Nova 원천이 상류
        m["upstream"] = {"url": source, "base": base, **({"tag": tag} if tag != "HEAD" else {})}
        m.setdefault("platform", {})["via"] = "github-template"
        write(out / "nova.project.json", json.dumps(m, ensure_ascii=False, indent=2) + "\n")
        replace_tree(root, out)
    add_upstream_remote(root, source)
    print(f"✓ {name} 프로젝트로 초기화했습니다 — 판본 {tag if tag != 'HEAD' else '(작업 트리)'} · 상류 기준선 "
          f"{base[:10] or '(비어 있음 — 첫 upstream plan 전에 nova.project.json upstream.base 를 Nova 태그로)'} · git 원격 upstream")
    return {"base": base, "origin": origin, "tag": "" if tag == "HEAD" else tag}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--owner")
    ap.add_argument("--domain")
    ap.add_argument("--app-id")
    ap.add_argument("--dry", action="store_true", help="검사 · 기준선 찾기만 하고 바꾸지 않는다")
    ap.add_argument("--ref", help="초기화할 판본(원천 태그 · HEAD) — 없으면 원천의 최신 정식 태그, HEAD 는 이 작업 트리(경고)")
    a = ap.parse_args(argv)
    init(a.name, a.slug, owner=a.owner, domain=a.domain, app_id=a.app_id, dry=a.dry, ref=a.ref)
    if not a.dry:
        print("다음:")
        print("  python nova.py install && python nova.py check")
        print('  git add -A && git commit -m "chore(init): Nova 템플릿에서 프로젝트 초기화" && git push')
        print("  /session-start → docs/requirement 첫 요구 원문 채우기 → /checklist 또는 /req-interview")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(main())
