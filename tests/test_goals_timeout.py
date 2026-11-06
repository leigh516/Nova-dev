"""종료 조건 명령 판정의 시간 제한 — 기본 1200초 · NOVA_EXIT_TIMEOUT 으로 늘린다(느린 PC 에서 전체 test 가 20분을 넘는다 — 2026-11-06 v0.2.0 ship)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import goals  # noqa: E402

ITEM = [{"id": "E1", "check": "python nova.py test", "expect": "통과", "how": "명령", "judged": ""}]


def _capture(monkeypatch):
    seen = {}

    def fake(*a, **k):
        seen["timeout"] = k.get("timeout")
        return subprocess.CompletedProcess(a, 0, "", "")
    monkeypatch.setattr(goals.subprocess, "run", fake)
    return seen


def test_default_timeout_is_1200(monkeypatch):
    monkeypatch.delenv("NOVA_EXIT_TIMEOUT", raising=False)
    seen = _capture(monkeypatch)
    goals.judge(ITEM)
    assert seen["timeout"] == 1200


def test_env_timeout_overrides(monkeypatch):
    monkeypatch.setenv("NOVA_EXIT_TIMEOUT", "3600")
    seen = _capture(monkeypatch)
    goals.judge(ITEM)
    assert seen["timeout"] == 3600


def test_explicit_timeout_wins(monkeypatch):
    monkeypatch.setenv("NOVA_EXIT_TIMEOUT", "3600")
    seen = _capture(monkeypatch)
    goals.judge(ITEM, timeout=5)
    assert seen["timeout"] == 5
