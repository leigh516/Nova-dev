"""nova.py test 묶음 구성 — xdist 는 기본으로 끄고(2026-11-05 실측: 이 PC 에서 이득 없음), NOVA_TEST_WORKERS 로 켤 때만
repo 묶음에 붙으며, 'auto' 의 작업 수는 코어 · 동시 묶음 수로 제한된다."""
import importlib.util
from pathlib import Path

import pytest

NOVA = Path(__file__).resolve().parents[1] / "nova.py"
spec = importlib.util.spec_from_file_location("nova_cli", NOVA)
nova = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nova)


def test_xdist_off_by_default(monkeypatch):
    monkeypatch.delenv("NOVA_TEST_WORKERS", raising=False)
    assert nova.repo_parallel_args(4) == []
    assert all("-n" not in c for _, c, _ in nova.test_groups([]))


def test_xdist_only_on_repo_group_when_on(monkeypatch):
    monkeypatch.setenv("NOVA_TEST_WORKERS", "auto")
    groups = nova.test_groups([])
    assert any(n == "repo" for n, _, _ in groups)
    for name, cmd, _ in groups:
        assert ("-n" in cmd) == (name == "repo"), (name, cmd)
    repo = next(c for n, c, _ in groups if n == "repo")
    assert repo[repo.index("--dist") + 1] == "loadgroup"


@pytest.mark.parametrize("cores,groups,expect", [(8, 4, "4"), (8, 1, "4"), (4, 4, "1"), (2, 6, "1"), (16, 3, "4")])
def test_auto_worker_count(monkeypatch, cores, groups, expect):
    monkeypatch.setenv("NOVA_TEST_WORKERS", "auto")
    monkeypatch.setattr(nova.os, "cpu_count", lambda: cores)
    args = nova.repo_parallel_args(groups)
    assert args[args.index("-n") + 1] == expect


def test_workers_env_number_and_off(monkeypatch):
    monkeypatch.setenv("NOVA_TEST_WORKERS", "0")
    assert nova.repo_parallel_args(4) == []
    monkeypatch.setenv("NOVA_TEST_WORKERS", "6")
    assert nova.repo_parallel_args(4)[1] == "6"
