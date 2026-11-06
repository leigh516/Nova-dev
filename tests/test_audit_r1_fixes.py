"""심층 감사(review_261104_02) 1회차 즉시 고침의 회귀 테스트."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import goals  # noqa: E402


def test_workflow_run_blocks_do_not_interpolate_inputs():
    """S1 — Actions 입력을 run 셸 본문에 직접 넣으면 명령 주입이 된다. 환경 변수로만 받는다."""
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        for job in doc.get("jobs", {}).values():
            for step in job.get("steps", []):
                run = step.get("run", "")
                assert "${{ inputs." not in run and "${{ github.event" not in run, f"{wf.name}: {step.get('name')}"


def test_git_record_refuses_in_worktree(monkeypatch):
    """D2 — git 기록은 번호가 붙는 기록이다. worktree 안에서는 쓰지 않고 거부한다(단일 기록자)."""
    import pytest
    import git_record
    import novalib
    monkeypatch.setattr(novalib, "in_linked_worktree", lambda cwd=None: True)
    monkeypatch.delenv("NOVA_ALLOW_WORKTREE_WRITE", raising=False)
    with pytest.raises(SystemExit, match="단일 기록자"):
        git_record.main(["요약"])


def test_human_judgement_requires_dated_fulfilled():
    """F8 — '충족 안 됨' · '충족 못함' 은 충족이 아니다. '충족 YYYY-MM-DD' 형식만."""
    def judge(text):
        return goals.judge([{"id": "E1", "check": "본다", "expect": "-", "how": "사람", "judged": text}], run=False)[0][1]
    assert judge("충족 2026-11-04 — 사용자 확인")
    assert not judge("충족 안 됨")
    assert not judge("충족 못함 2026-11-04")
    assert not judge("")
