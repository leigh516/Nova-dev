"""실행 스택(scripts/stack.py) — 포트 고르기 · 상태 파일 · 주소 읽기 · 프로세스 트리 정리 · 실제 기동/정리(REQ-261105-10-4 · E5)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stack  # noqa: E402


def _listen() -> tuple[socket.socket, int]:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    return s, s.getsockname()[1]


def test_port_busy_and_pick_skips_busy_port():
    s, port = _listen()
    try:
        assert stack.port_busy(port)
        picked = stack.pick_port(port)
        assert picked != port and picked > port
        assert not stack.port_busy(picked)
    finally:
        s.close()


def test_pick_port_avoids_given_ports():
    # 임시 포트 대역은 Windows 가 예약해 묶을 수 없는 칸이 많다(Hyper-V 제외 대역) — 개발 서버가 쓰는 낮은 대역에서 잰다
    port = stack.pick_port(18500)
    assert stack.pick_port(port, avoid={port}) != port


def test_endpoints_default_without_state(tmp_path):
    ep = stack.endpoints(tmp_path)
    assert ep == {"api": stack.DEFAULT_API, "web": stack.DEFAULT_WEB, "from": "기본값"}


def test_endpoints_from_running_state(tmp_path):
    stack.save_state(tmp_path, {"gateway": {"pid": os.getpid(), "port": 8123},
                                "web": {"pid": os.getpid(), "port": 3123}})
    ep = stack.endpoints(tmp_path)
    assert ep["api"] == "http://localhost:8123/v1"
    assert ep["web"] == "http://localhost:3123"
    assert ep["from"] == "stack"


def test_endpoints_ignores_stale_state(tmp_path):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    stack.save_state(tmp_path, {"gateway": {"pid": dead.pid, "port": 8123}})
    assert stack.endpoints(tmp_path)["from"] == "기본값"


def test_env_overrides_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_API", "http://localhost:9999/v1")
    assert stack.endpoints(tmp_path)["api"] == "http://localhost:9999/v1"


def test_state_file_is_json_under_dot_stack(tmp_path):
    stack.save_state(tmp_path, {"gateway": {"pid": 1, "port": 2}})
    p = tmp_path / ".stack" / "state.json"
    assert json.loads(p.read_text(encoding="utf-8"))["gateway"]["port"] == 2
    stack.clear_state(tmp_path)
    assert stack.load_state(tmp_path) is None


@pytest.mark.slow
def test_kill_tree_kills_grandchild(tmp_path):
    """자식이 띄운 손자까지 내려간다 — npx → node 처럼 한 단계 아래 프로세스가 포트를 잡는 경우."""
    marker = tmp_path / "grandchild.pid"
    code = ("import subprocess,sys,time;"
            f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']);"
            f"open(r'{marker}','w').write(str(p.pid));time.sleep(60)")
    child = stack.spawn([sys.executable, "-c", code], cwd=tmp_path, log=tmp_path / "c.log", env={})
    for _ in range(100):
        if marker.exists() and marker.read_text():
            break
        time.sleep(0.1)
    grand = int(marker.read_text())
    assert stack.alive(child.pid) and stack.alive(grand)
    stack.kill_tree(child.pid)
    for _ in range(50):
        if not stack.alive(child.pid) and not stack.alive(grand):
            break
        time.sleep(0.1)
    assert not stack.alive(child.pid)
    assert not stack.alive(grand)


@pytest.mark.slow
def test_up_gateway_then_down_frees_port(tmp_path):
    """E5 의 게이트웨이 절반 — up(웹 없이) → healthz 응답 → status 실행 중 → down → 포트 비고 남은 프로세스 0."""
    st = stack.up(ROOT, web=False, state_root=tmp_path, gw_port=stack.pick_port(18080))
    port, pid = st["gateway"]["port"], st["gateway"]["pid"]
    try:
        assert stack.http_ok(f"http://127.0.0.1:{port}/healthz")
        assert stack.status(tmp_path)["gateway"]["running"] is True
    finally:
        left = stack.down(tmp_path)
    assert left == []
    assert not stack.port_busy(port)
    assert not stack.alive(pid)
    assert stack.load_state(tmp_path) is None
