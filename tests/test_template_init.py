"""템플릿에서 시작하기 — 안전장치(원천 · 이미 초기화 · 더러운 트리) · 작업 트리 바꾸기 · 상류 기준선 찾기."""
import pytest
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import template_init as ti  # noqa: E402


def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def repo(p: Path, files: dict[str, str]) -> Path:
    p.mkdir(parents=True)
    sh(p, "init", "-q", "-b", "main")
    sh(p, "config", "user.email", "t@t")
    sh(p, "config", "user.name", "t")
    for k, v in files.items():
        (p / k).parent.mkdir(parents=True, exist_ok=True)
        (p / k).write_text(v, encoding="utf-8")
    sh(p, "add", "-A")
    sh(p, "commit", "-q", "-m", "첫 커밋")
    return p


def test_norm_url_ignores_protocol_and_suffix():
    assert ti.norm_url("https://github.com/A/Nova-dev.git") == ti.norm_url("git@github.com:a/nova-dev")


def test_guard_refuses_source_initialized_and_dirty(tmp_path):
    r = repo(tmp_path / "r", {"a.txt": "1"})
    src = "https://github.com/me/Nova-dev"
    sh(r, "remote", "add", "origin", src + ".git")
    why = ti.guard(r, {"slug": "nova", "platform": {"source": src}})
    assert any("원천" in w for w in why)
    sh(r, "remote", "set-url", "origin", "https://github.com/me/shop")
    assert ti.guard(r, {"slug": "nova", "platform": {"source": src}}) == []
    assert any("이미 초기화" in w for w in ti.guard(r, {"slug": "shop", "platform": {"source": src}}))
    (r / "a.txt").write_text("2", encoding="utf-8")
    assert any("커밋 안 된" in w for w in ti.guard(r, {"slug": "nova", "platform": {"source": src}}))


def test_replace_tree_keeps_git_and_installs(tmp_path):
    root = repo(tmp_path / "root", {"old.md": "옛것", "docs/h.md": "옛 기록"})   # 추적 목록을 읽으므로 진짜 저장소
    (root / "node_modules").mkdir()
    new = tmp_path / "new"
    (new / "docs").mkdir(parents=True)
    (new / "docs" / "n.md").write_text("새 기록", encoding="utf-8")
    (new / "README.md").write_text("새것", encoding="utf-8")
    ti.replace_tree(root, new)
    assert (root / ".git" / "HEAD").exists() and (root / "node_modules").exists()
    assert not (root / "old.md").exists() and not (root / "docs" / "h.md").exists()
    assert (root / "docs" / "n.md").read_text(encoding="utf-8") == "새 기록"


def test_replace_tree_keeps_git_ignored_files(tmp_path):
    """S2 — 무시 파일(.env · data/ · .venv)은 지우지 않는다. 바꾸는 것은 git 이 추적하는 파일뿐이다."""
    root = repo(tmp_path / "root", {".gitignore": ".env\ndata/\n.venv/\n", "old.md": "옛것", "docs/h.md": "옛 기록",
                                    "data/.keep": ""})
    sh(root, "add", "-f", "data/.keep")
    sh(root, "commit", "-q", "-m", "data 자리")
    (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (root / "data" / "app.db").write_text("운영 데이터", encoding="utf-8")
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / ".venv" / "lib" / "x.py").write_text("", encoding="utf-8")
    new = tmp_path / "new"
    (new / "docs").mkdir(parents=True)
    (new / "docs" / "n.md").write_text("새 기록", encoding="utf-8")
    (new / "data").mkdir()
    (new / "data" / ".keep").write_text("", encoding="utf-8")
    (new / ".gitignore").write_text(".env\ndata/\n.venv/\n", encoding="utf-8")
    ti.replace_tree(root, new)
    assert (root / ".env").read_text(encoding="utf-8") == "SECRET=1\n"
    assert (root / "data" / "app.db").read_text(encoding="utf-8") == "운영 데이터"
    assert (root / ".venv" / "lib" / "x.py").exists()
    assert not (root / "old.md").exists() and not (root / "docs" / "h.md").exists()
    assert (root / "docs" / "n.md").read_text(encoding="utf-8") == "새 기록" and (root / "data" / ".keep").exists()


def test_replace_tree_refuses_without_git_list(tmp_path):
    """추적 목록을 읽지 못하면(git 저장소가 아님) 아무것도 지우지 않고 멈춘다 — 무엇이 무시 파일인지 모르면 지울 수 없다."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.md").write_text("그대로", encoding="utf-8")
    new = tmp_path / "new"
    new.mkdir()
    with pytest.raises(SystemExit, match="추적"):
        ti.replace_tree(root, new)
    assert (root / "a.md").exists()


@pytest.mark.slow  # 실측 10초 이상 — quick 에서 빠지고 전체 test 에서만(REQ-261104-17)
def test_find_base_matches_template_tree(tmp_path):
    # 원천: 커밋 둘. 템플릿 복사본: 원천 첫 커밋과 같은 내용의 새 단일 커밋(GitHub 템플릿과 같은 모양)
    src = repo(tmp_path / "src", {"a.txt": "1", "d/b.txt": "2"})
    first = sh(src, "rev-parse", "HEAD")
    (src / "a.txt").write_text("1-개선", encoding="utf-8")
    sh(src, "commit", "-qam", "개선")
    copy = repo(tmp_path / "copy", {"a.txt": "1", "d/b.txt": "2"})
    assert ti.find_base(copy, src.as_posix()) == first
    # 같은 내용이 없으면 빈 값(추측하지 않는다)
    other = repo(tmp_path / "other", {"a.txt": "다름"})
    assert ti.find_base(other, src.as_posix()) == ""


# ───────────────────────── 최신 정식 릴리스에서 시작(REQ-261105-06-4 · 8)
def test_pick_source_ref_latest_formal_tag(tmp_path, capsys):
    src = repo(tmp_path / "src", {"a.txt": "1"})
    sh(src, "tag", "-a", "v0.1.0", "-m", "x")
    c1 = sh(src, "rev-parse", "HEAD")
    (src / "a.txt").write_text("2", encoding="utf-8")
    sh(src, "commit", "-qam", "다음")
    sh(src, "tag", "-a", "v0.2.0-rc.1", "-m", "rc")
    copy = repo(tmp_path / "copy", {"a.txt": "1"})
    tag, commit = ti.pick_source_ref(copy, src.as_posix(), None)
    assert (tag, commit) == ("v0.1.0", c1)
    assert sh(copy, "cat-file", "-t", commit) == "commit"               # 태그 내용을 받아 두었다
    assert "v0.1.0" not in sh(copy, "tag", "--list")                    # 복제본에 Nova 태그를 남기지 않는다
    assert ti.pick_source_ref(copy, src.as_posix(), "HEAD") == ("HEAD", "")
    with pytest.raises(SystemExit, match="v9.9.9"):
        ti.pick_source_ref(copy, src.as_posix(), "v9.9.9")
    assert ti.pick_source_ref(copy, (tmp_path / "없음").as_posix(), None) == ("HEAD", "")
    assert "닿지 못" in capsys.readouterr().out


def test_add_upstream_remote_once(tmp_path):
    copy = repo(tmp_path / "copy", {"a.txt": "1"})
    ti.add_upstream_remote(copy, "https://github.com/a/nova")
    ti.add_upstream_remote(copy, "https://github.com/a/nova")           # 두 번 불러도 실패하지 않는다
    assert sh(copy, "remote", "get-url", "upstream") == "https://github.com/a/nova"
