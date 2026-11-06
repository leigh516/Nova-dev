"""new_project — 생성한 프로젝트가 자기 기준으로 생성물 · 문서 · 원장 검사를 통과하고, 플랫폼 기록은 가져가지 않는다."""
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import new_project

# 느린 테스트(실측 10초 이상 — 하위 프로세스 · 저장소 복제) — quick 에서 빠지고 전체 test 에서만 돈다(REQ-261104-17)
# 무거운 module 범위 픽스처(made — 새 프로젝트 생성, 단독 2분 넘음)를 xdist 가 작업자마다 다시 만들지 않게
# 한 작업자에 묶는다(--dist loadgroup 일 때 적용 — 분석 보고 test-speed-analysis 안 2)
pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("new_project")]

TODAY = dt.date(2030, 5, 6)
ROOT = Path(__file__).resolve().parents[1]


def lint_steps() -> list[list[str]]:
    """nova.py cmd_lint 의 검사 단계 — 원천에서 읽는다(test_audit_scope 와 같은 방식). 단계를 더하면 새 프로젝트 검증도 따라온다."""
    src = (ROOT / "nova.py").read_text(encoding="utf-8")
    body = src[src.index("def cmd_lint"):src.index("def cmd_gen")]
    steps = [[f"scripts/{m.group(1)}", *re.findall(r'"([^"]*)"', m.group(2))]
             for m in re.finditer(r'script\("([a-z0-9_]+\.py)"((?:\s*,\s*"[^"]*")*)', body)]
    assert len(steps) >= 10, steps
    return steps


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    dest = tmp_path_factory.mktemp("proj") / "shop"
    # Nova 가 여러 판본을 낸 뒤를 흉내 낸다 — 새 프로젝트는 Nova 판본을 물려받지 않고 0.1.0 에서 시작해야 한다
    # 원본이 다른 디자인 킷을 골랐어도 새 프로젝트는 기본 킷 nova 로 시작해야 한다(REQ-261106-04)
    upstream = {**new_project.project(), "version": "7.3.1", "design": {"kit": "newtype", "source": "manual"}}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(new_project, "project", lambda: upstream)
        # 작업 트리(HEAD)를 검증한다 — 기본(최신 정식 태그)은 그 판본의 생성기로 만들어 지금 코드를 시험하지 않는다
        new_project.create(dest, "쇼핑몰", "shop", owner="tester", remote="https://github.com/acme/shop", git=False, today=TODAY, ref="HEAD")
    return dest


def run(dest, *args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": os.pathsep.join([str(dest / "packages" / "common-py"), str(dest / "scripts")])}
    return subprocess.run([sys.executable, *args], cwd=dest, env=env, capture_output=True, text=True, encoding="utf-8")


def test_meta_and_identity(made):
    meta = json.loads((made / "nova.project.json").read_text(encoding="utf-8"))
    assert meta["name"] == "쇼핑몰" and meta["slug"] == "shop"
    assert meta["image_registry"] == "ghcr.io/acme/shop" and meta["domain"] == "shop.local"
    assert meta["version"] == "0.1.0"  # 판본은 새 프로젝트의 것 — 운영 이미지 태그 · Helm 판본도 여기서 시작한다
    assert 'newTag: "0.1.0"' in (made / "infra/k3s/overlays/prod/kustomization.yaml").read_text(encoding="utf-8")
    # 규모 프로파일 — Nova 의 platform 을 물려받지 않고 product 로 시작한다(REQ-261104-17-5)
    import project_profile
    assert meta["profile"]["value"] == "product" and project_profile.check(meta) == []
    # 디자인 킷 — 원본(newtype)을 물려받지 않고 nova, 생성물도 nova 값
    assert meta["design"]["kit"] == "nova" and meta["design"]["source"] == "default"
    assert "--color-action-primary: #4F5BD5;" in (made / "web/packages/ui/src/tokens.css").read_text(encoding="utf-8")
    assert '"쇼핑몰"' in (made / "web/apps/app/lib/app.ts").read_text(encoding="utf-8")
    assert '"setApplicationId"("kr.shop.app")' in (made / "apps/kmp/composeApp/build.gradle.kts").read_text(encoding="utf-8")
    assert (made / "CLAUDE.md").read_text(encoding="utf-8").startswith("# 쇼핑몰 — 저장소 작업 규칙")


def test_platform_records_are_not_copied(made):
    assert not list((made / "docs/history").glob("history_[0-9]*.md"))
    assert not list((made / "docs/git").glob("git_[0-9]*.md"))
    assert not list((made / "docs/plans").glob("plan_REQ_*.md"))
    assert not (made / "docs/screenshots").exists()
    assert not (made / ".venv").exists() and not (made / "web/node_modules").exists()
    reqs = sorted(p.name for p in (made / "docs/requirement").glob("requirement_*_*.md"))
    assert reqs == ["requirement_300506_01.md"]
    adr = (made / "docs/adr/ADR-003-uuid-v7-ids.md").read_text(encoding="utf-8")  # 플랫폼 결정은 물려받는다
    assert "https://github.com/nicomms6925/Nova-dev/blob/main/docs/requirement/requirement_261103_06.md" in adr  # 근거는 원본 저장소로


@pytest.mark.parametrize("args", lint_steps(), ids=lambda a: a[0].split("/")[-1])
def test_lint_step_passes_in_new_project(made, args):
    """새 프로젝트에서 lint 전 단계가 통과한다(예전엔 10단계 중 6개만 돌렸다)."""
    assert (made / args[0]).exists(), f"새 프로젝트에 검사 스크립트가 없다: {args[0]}"
    r = run(made, *args)
    assert r.returncode == 0, f"{args}: {r.stdout}{r.stderr}"


def test_generated_checks_pass_in_new_project(made):
    assert "part-of: shop" in (made / "infra/k3s/base/kustomization.yaml").read_text(encoding="utf-8")


def test_new_project_repo_tests_pass(made):
    r = run(made, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--basetemp={made / '.pt'}",
            "tests/test_docs.py", "tests/test_registry.py", "tests/test_topic_catalog.py", "tests/test_infra.py")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("slug,msg", [("Shop", "slug"), ("x", "slug")])
def test_rejects_bad_slug(tmp_path, slug, msg):
    with pytest.raises(SystemExit) as e:
        new_project.create(tmp_path / "p", "x", slug, git=False)
    assert msg in str(e.value)


def test_rejects_non_empty_dest(tmp_path):
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "a.txt").write_text("x")
    with pytest.raises(SystemExit, match="비어 있지 않습니다"):
        new_project.create(tmp_path / "p", "x", "abc", git=False)


def test_superpowers_inherited(made):
    """새 프로젝트도 Superpowers 설정 · 명령을 물려받고, 플랫폼 인터뷰 기록은 비운다."""
    settings = json.loads((made / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"]["superpowers@claude-plugins-official"] is True
    assert (made / ".claude/commands/req-interview.md").exists()
    # 훅 묶음(REQ-261105-07)은 물려받고, 이 기계의 훅 기록(.claude/state/ — git 무시)은 옮기지 않는다
    assert (made / ".claude/hooks/nova_hooks.py").exists() and (made / ".claude/hooks/persona_guard.py").exists()
    pre = [h["command"] for g in settings["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert any("nova_hooks.py" in c and c.endswith(" pretool") for c in pre)
    assert "Read(./**/.env)" in settings["permissions"]["deny"]
    assert not (made / ".claude/state").exists()
    iv = made / "docs/requirement/interviews"
    assert (iv / "_template.md").exists() and not list(iv.glob("interview_[0-9]*.md"))


def test_warehouse_starts_empty(made):
    """자료 창고 · 제품 정본은 구조(README · 빈 틀)만 물려받고 내용은 비어 있다(REQ-261104-02)."""
    for side in ("inbound", "outbound"):
        files = [p.relative_to(made).as_posix() for p in (made / "docs/warehouse" / side).rglob("*") if p.is_file()]
        assert files and all(f.endswith(("README.md", "checklist/checklist.html")) for f in files), files
        form = made / "docs/warehouse" / side / "checklist/checklist.html"
        assert '"prefill": {"answers": {}}' in form.read_text(encoding="utf-8")  # 빈 폼(플랫폼 자료로 채우지 않음)
    assert (made / "docs/product/_template_prd.json").exists() and not (made / "docs/product/prd.json").exists()
    assert (made / ".claude/commands/foundation.md").exists()


def test_lint_fails_on_missing_script(tmp_path, monkeypatch, capsys):
    """회귀 — lint 단계의 스크립트가 없으면 '건너뜀'만 찍고 통과하던 결함. 검사 단계는 실패, 선택 단계는 건너뛴다."""
    spec = importlib.util.spec_from_file_location("nova_cli", ROOT / "nova.py")
    nova = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nova)
    (tmp_path / "scripts").mkdir()
    monkeypatch.setattr(nova, "ROOT", tmp_path)
    monkeypatch.setattr(nova, "sh", lambda *a, **k: pytest.fail("없는 스크립트를 실행하려 했다"))
    nova.script("없는.py")                                                          # 선택 단계 — 건너뜀
    assert "건너뜀" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:
        nova.script("없는.py", "--check", required=True)
    assert e.value.code == 1 and "없다" in capsys.readouterr().out
    monkeypatch.setattr(nova, "ensure_env", lambda: None)
    with pytest.raises(SystemExit):
        nova.cmd_lint([])                                                           # lint 는 첫 단계부터 실패해야 한다
