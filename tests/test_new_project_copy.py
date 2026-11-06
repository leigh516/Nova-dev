"""새 프로젝트 복사 범위(T04-9.06) — git 무시 파일(.env · .collab/ · settings.local.json …)은 새 프로젝트로 옮기지 않는다.

비밀값 · 로컬 상태가 복제본에 실려 첫 커밋으로 새는 것을 막는다. 하위 프로세스 없이 도는 빠른 테스트(전체 복제는 test_new_project 의 slow 몫)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import new_project  # noqa: E402


def test_git_ignored_paths_skip_in_copy(monkeypatch):
    monkeypatch.setattr(new_project, "_ignored_cache", {".env", ".collab", ".claude/settings.local.json"})
    assert {".env", ".collab"} <= new_project.ignore(str(ROOT), [".env", ".collab", "README.md"])
    assert "README.md" not in new_project.ignore(str(ROOT), [".env", "README.md"])
    out = new_project.ignore(str(ROOT / ".claude"), ["settings.local.json", "settings.json"])
    assert "settings.local.json" in out and "settings.json" not in out


def test_git_ignored_reads_repo_rules(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    (tmp_path / ".gitignore").write_text(".env\nlocal/\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    (tmp_path / "local").mkdir()
    (tmp_path / "local" / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")   # 추적 전 새 파일은 옮긴다(작업 중인 공통부)
    got = new_project.git_ignored(tmp_path)
    assert ".env" in got and "local" in got and "keep.txt" not in got


def test_git_ignored_without_git_is_empty(tmp_path):
    assert new_project.git_ignored(tmp_path) == set()   # git 저장소가 아니면 SKIP_DIRS 만으로 복사한다


# ───────────────────────── 최신 정식 릴리스에서 시작(REQ-261105-06-4 · 8 · T07-4.09)
import json  # noqa: E402

STUB = '''import json, pathlib, sys
dest = pathlib.Path(sys.argv[1])
dest.mkdir(parents=True)
src = pathlib.Path(__file__).resolve().parent.parent
(dest / "marker.txt").write_text((src / "marker.txt").read_text(encoding="utf-8"), encoding="utf-8")
(dest / "args.json").write_text(json.dumps(sys.argv[2:]), encoding="utf-8")
(dest / "nova.project.json").write_text(json.dumps({"name": "x", "upstream": {"url": "엉뚱한 곳", "base": ""}}), encoding="utf-8")
'''


def sh(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def fake_nova(p: Path) -> Path:
    """태그 v0.1.0(marker v1) 뒤에 커밋이 하나 더 있는(marker v2) 작은 Nova."""
    p.mkdir(parents=True)
    sh(p, "init", "-q", "-b", "main")
    sh(p, "config", "user.email", "t@t")
    sh(p, "config", "user.name", "t")
    (p / "scripts").mkdir()
    (p / "scripts/new_project.py").write_text(STUB, encoding="utf-8")
    (p / "marker.txt").write_text("v1", encoding="utf-8")
    sh(p, "add", "-A")
    sh(p, "commit", "-q", "-m", "판본 하나")
    sh(p, "tag", "-a", "v0.1.0", "-m", "v0.1.0")
    sh(p, "tag", "-a", "v0.2.0-rc.1", "-m", "rc")
    (p / "marker.txt").write_text("v2", encoding="utf-8")
    sh(p, "commit", "-qam", "작업 중")
    return p


def test_pick_ref_latest_formal_or_head_with_warning(tmp_path, capsys):
    src = fake_nova(tmp_path / "nova")
    assert new_project.pick_ref(None, src) == "v0.1.0"                 # rc 제외 · 최신 정식
    assert new_project.pick_ref("v0.2.0-rc.1", src) == "v0.2.0-rc.1"   # 사람이 고르면 그대로
    bare = tmp_path / "bare"
    bare.mkdir()
    sh(bare, "init", "-q")
    assert new_project.pick_ref(None, bare) == "HEAD"
    assert "정식 태그가 없다" in capsys.readouterr().out


def test_create_from_tag_uses_tag_content_and_records_upstream(tmp_path):
    src = fake_nova(tmp_path / "nova")
    dest = tmp_path / "out" / "shop"
    new_project.create_from_ref(dest, "v0.1.0", root=src, name="쇼핑몰", slug="shop", owner="나", git=True)
    assert (dest / "marker.txt").read_text(encoding="utf-8") == "v1"   # 작업 트리(v2)가 아니라 태그 내용
    args = json.loads((dest / "args.json").read_text(encoding="utf-8"))
    assert args[:4] == ["--name", "쇼핑몰", "--slug", "shop"] and "--no-git" in args and "--owner" in args
    up = json.loads((dest / "nova.project.json").read_text(encoding="utf-8"))["upstream"]
    assert up == {"url": src.as_posix(), "base": sh(src, "rev-parse", "v0.1.0^{commit}"), "tag": "v0.1.0"}
    assert sh(dest, "remote", "get-url", "upstream") == src.as_posix()    # 상류 원격이 등록된다


def test_dirty_common_lists_only_common_paths(tmp_path):
    src = fake_nova(tmp_path / "nova")
    (src / "scripts/new_project.py").write_text(STUB + "# 고침\n", encoding="utf-8")
    (src / "scripts/new.py").write_text("x = 1\n", encoding="utf-8")
    (src / "marker.txt").write_text("v3", encoding="utf-8")
    assert new_project.dirty_common(src) == ["scripts/new.py", "scripts/new_project.py"]
    sub = tmp_path / "nova" / "scripts"
    assert new_project.dirty_common(sub) == []                           # 저장소 맨 위가 아니면 남의 변경을 읽지 않는다
