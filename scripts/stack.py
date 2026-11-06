#!/usr/bin/env python3
"""실행 스택 — 게이트웨이(메모리 DB) + 데모 로그인 웹을 명령 하나로 띄우고 내린다(REQ-261105-10-4 · E5).

  python nova.py stack up [--no-web] [--no-build] [--gw-port N] [--web-port N]
  python nova.py stack status [--json]
  python nova.py stack down

- 포트: 게이트웨이는 8080, 웹은 3100 부터 찾아 비어 있는 첫 포트를 쓴다(다른 프로그램이 잡고 있으면 다음 포트).
- 웹 빌드: NEXT_PUBLIC_DEV_LOGIN=1 · NEXT_PUBLIC_API_BASE=<게이트웨이 주소>로 빌드한다. 주소가 빌드에 박히므로
  --no-build 는 지난 빌드의 주소와 같을 때만 건너뛴다.
- 상태: `.stack/state.json`(git 무시) — pid · 포트 · 로그 경로. ui-smoke · kmp-smoke · kmp-snapshots 가 여기서 주소를 읽는다.
- 정리: 자식의 자식까지(npx → node) 내린 뒤 포트가 비었는지 확인하고, 남은 것을 보고한다.
- 출력 인코딩은 UTF-8 로 고정한다(PYTHONIOENCODING · PYTHONUTF8) — Windows 콘솔 코드 페이지에 따라 로그가 깨지던 문제.

표준 라이브러리만 쓴다 — nova.py 와 ui_smoke 가 가볍게 불러 쓴다.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GW_START, WEB_START = 8080, 3100
DEFAULT_API = f"http://localhost:{GW_START}/v1"
DEFAULT_WEB = f"http://localhost:{WEB_START}"
SCAN = 50   # 시작 포트에서 몇 칸까지 찾나

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001 — 재구성을 못 하는 스트림(파이프 대체 등)이면 그대로 쓴다
        pass


# ── 포트 ─────────────────────────────────────────────────────────────
def port_busy(port: int, host: str = "127.0.0.1") -> bool:
    """누가 듣고 있거나(연결됨) 묶을 수 없으면 사용 중. Windows 는 0.0.0.0 에 묶인 포트를 127.0.0.1 로 또 묶을 수 있어 연결도 본다."""
    with socket.socket() as c:
        c.settimeout(0.3)
        if c.connect_ex((host, port)) == 0:
            return True
    with socket.socket() as s:
        try:
            s.bind((host, port))
        except OSError:
            return True
    return False


def pick_port(start: int, *, avoid: set[int] | frozenset[int] = frozenset()) -> int:
    for p in range(start, start + SCAN):
        if p not in avoid and not port_busy(p):
            return p
    raise SystemExit(f"✗ {start}~{start + SCAN - 1} 에 빈 포트가 없다")


# ── 상태 파일 ───────────────────────────────────────────────────────
def _state_path(root: Path) -> Path:
    return Path(root) / ".stack" / "state.json"


def load_state(root: Path = ROOT) -> dict | None:
    p = _state_path(root)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except ValueError:
        print(f"⚠ 상태 파일이 깨졌다 — 무시한다: {p}")
        return None


def save_state(root: Path, state: dict) -> None:
    p = _state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_state(root: Path = ROOT) -> None:
    _state_path(root).unlink(missing_ok=True)


# ── 프로세스 ─────────────────────────────────────────────────────────
def alive(pid: int) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return f'"{pid}"' in r.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # 좀비(끝났지만 부모가 거두지 않음)는 죽은 것으로 본다
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat.rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def spawn(cmd: list[str], *, cwd: Path, log: Path, env: dict) -> subprocess.Popen:
    """부모(nova.py)가 끝나도 살아 있게 띄운다. 새 프로세스 그룹/세션이라 kill_tree 로 자식까지 한 번에 내린다."""
    log.parent.mkdir(parents=True, exist_ok=True)
    full_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **env}
    out = open(log, "ab")  # noqa: SIM115 — 자식이 계속 쓴다. 부모 쪽 핸들은 Popen 뒤 닫는다
    kw: dict = {"cwd": cwd, "env": full_env, "stdin": subprocess.DEVNULL, "stdout": out, "stderr": subprocess.STDOUT}
    try:
        if os.name == "nt":
            base = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            try:
                # 도구(터미널 · CI)가 작업 개체로 묶어 두면 그 명령이 끝날 때 함께 죽는다 — 벗어날 수 있으면 벗어난다
                return subprocess.Popen(cmd, creationflags=base | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw)
            except OSError:
                return subprocess.Popen(cmd, creationflags=base, **kw)
        return subprocess.Popen(cmd, start_new_session=True, **kw)
    finally:
        out.close()


def kill_tree(pid: int) -> None:
    if not alive(pid):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(30):
        if not alive(pid):
            return
        time.sleep(0.1)
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except ProcessLookupError:
        pass


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 — 로컬 주소만
            return 200 <= r.status < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _wait(url: str, pid: int, seconds: float, what: str, log: Path) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if http_ok(url):
            return
        if not alive(pid):
            raise RuntimeError(f"{what} 프로세스가 준비 전에 끝났다 — 로그: {log}\n{_tail(log)}")
        time.sleep(0.5)
    raise RuntimeError(f"{what} 이 {int(seconds)}초 안에 응답하지 않았다({url}) — 로그: {log}\n{_tail(log)}")


def _tail(log: Path, n: int = 15) -> str:
    try:
        return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return "(로그 없음)"


def _npm(name: str) -> str:
    return shutil.which(name) or shutil.which(name + ".cmd") or name


def _py(root: Path) -> str:
    v = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(v) if v.exists() else sys.executable


# ── 명령 ─────────────────────────────────────────────────────────────
def endpoints(root: Path = ROOT) -> dict:
    """ui-smoke · kmp 가 쓸 주소 — 환경 변수(NOVA_API · NOVA_WEB) > 실행 중인 stack > 기본값."""
    st = load_state(root) or {}
    gw, web = st.get("gateway") or {}, st.get("web") or {}
    running = bool(gw) and alive(gw.get("pid", 0))
    ep = {"api": DEFAULT_API, "web": DEFAULT_WEB, "from": "기본값"}
    if running:
        ep.update(api=f"http://localhost:{gw['port']}/v1", **{"from": "stack"})
        if web and alive(web.get("pid", 0)):
            ep["web"] = f"http://localhost:{web['port']}"
    if os.environ.get("NOVA_API"):
        ep.update(api=os.environ["NOVA_API"], **{"from": "환경 변수"})
    if os.environ.get("NOVA_WEB"):
        ep.update(web=os.environ["NOVA_WEB"], **{"from": "환경 변수"})
    return ep


def up(root: Path = ROOT, *, web: bool = True, build: bool = True, gw_port: int | None = None,
       web_port: int | None = None, state_root: Path | None = None) -> dict:
    state_root = Path(state_root or root)
    old = load_state(state_root)
    if old and any(alive((old.get(k) or {}).get("pid", 0)) for k in ("gateway", "web")):
        raise SystemExit("✗ 이미 떠 있다 — python nova.py stack status 로 보고, 다시 띄우려면 stack down 먼저")
    logs = state_root / ".stack"
    gw_port = gw_port or pick_port(GW_START)
    web_port = web_port or (pick_port(WEB_START, avoid={gw_port}) if web else None)
    web_url = f"http://localhost:{web_port}" if web else None
    api = f"http://localhost:{gw_port}/v1"
    state: dict = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "root": str(root)}
    try:
        log = logs / "gateway.log"
        env = {"DEV_MEMORY_DB": "1", "PORT": str(gw_port)}
        if web_url:
            env["GW_CORS_ORIGINS"] = web_url
        p = spawn([_py(root), str(root / "scripts" / "dev_server.py")], cwd=root, log=log, env=env)
        state["gateway"] = {"pid": p.pid, "port": gw_port, "log": str(log)}
        save_state(state_root, state)   # 준비 확인 전에 적는다 — 실패해도 down 이 정리할 수 있게
        print(f"… 게이트웨이 기동 중 :{gw_port} (메모리 DB)", flush=True)
        _wait(f"http://127.0.0.1:{gw_port}/healthz", p.pid, 120, "게이트웨이", log)
        print(f"✓ 게이트웨이 {api}", flush=True)
        if web:
            _web(root, state_root, state, api, web_port, build)
    except (RuntimeError, subprocess.CalledProcessError) as e:
        down(state_root)
        raise SystemExit(f"✗ stack up 실패 — 띄운 것을 내렸다\n{e}") from None
    return state


def _web(root: Path, state_root: Path, state: dict, api: str, port: int, build: bool) -> None:
    webdir = root / "web"
    stamp = state_root / ".stack" / "web_build.json"
    last = {}
    try:
        last = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    env = {"NEXT_PUBLIC_DEV_LOGIN": "1", "NEXT_PUBLIC_API_BASE": api}
    if not build and last.get("api") == api and (webdir / "apps" / "app" / ".next").exists():
        print(f"- 웹 빌드 건너뜀(--no-build · 지난 빌드 주소 {api} 와 같음)", flush=True)
    else:
        if not build:
            print(f"⚠ --no-build 지만 지난 빌드 주소({last.get('api', '없음')})가 지금({api})과 달라 다시 빌드한다", flush=True)
        if not (webdir / "node_modules").exists():
            print("… npm install", flush=True)
            subprocess.run([_npm("npm"), "install"], cwd=webdir, check=True,
                           env={**os.environ, **env})
        print("… 웹 빌드(데모 로그인) — 1~3분", flush=True)
        r = subprocess.run([_npm("npm"), "run", "build", "-w", "apps/app"], cwd=webdir,
                           env={**os.environ, **env}, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError("웹 빌드 실패:\n" + "\n".join((r.stdout + r.stderr).splitlines()[-25:]))
        stamp.write_text(json.dumps({"api": api, "built": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False), encoding="utf-8")
    log = state_root / ".stack" / "web.log"
    p = spawn([_npm("npx"), "--workspace", "apps/app", "next", "start", "-p", str(port)], cwd=webdir, log=log, env=env)
    state["web"] = {"pid": p.pid, "port": port, "log": str(log)}
    save_state(state_root, state)
    _wait(f"http://127.0.0.1:{port}/login", p.pid, 90, "웹", log)
    print(f"✓ 웹 http://localhost:{port} (데모 로그인)", flush=True)


def down(state_root: Path = ROOT) -> list[str]:
    """내리고 남은 것(살아 있는 pid · 아직 잡힌 포트)을 돌려준다 — 빈 목록이면 깨끗하다."""
    st = load_state(state_root)
    if not st:
        return []
    for k in ("web", "gateway"):
        if st.get(k):
            kill_tree(st[k].get("pid", 0))
    left: list[str] = []
    for k in ("web", "gateway"):
        e = st.get(k)
        if not e:
            continue
        for _ in range(50):
            if not alive(e.get("pid", 0)) and not port_busy(e["port"]):
                break
            time.sleep(0.1)
        if alive(e.get("pid", 0)):
            left.append(f"{k} pid {e['pid']} 이 아직 살아 있다")
        if port_busy(e["port"]):
            left.append(f"{k} 포트 {e['port']} 가 아직 잡혀 있다(다른 프로세스일 수 있다)")
    if not left:
        clear_state(state_root)
    return left


def status(state_root: Path = ROOT) -> dict:
    st = load_state(state_root) or {}
    out: dict = {"started": st.get("started")}
    for k, path in (("gateway", "/healthz"), ("web", "/login")):
        e = st.get(k)
        if not e:
            continue
        out[k] = {"port": e["port"], "pid": e["pid"], "running": alive(e["pid"]),
                  "responding": http_ok(f"http://127.0.0.1:{e['port']}{path}"), "log": e.get("log")}
    out["endpoints"] = endpoints(state_root)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("up")
    u.add_argument("--no-web", action="store_true", help="게이트웨이만")
    u.add_argument("--no-build", action="store_true", help="지난 웹 빌드를 다시 쓴다(주소가 같을 때만)")
    u.add_argument("--gw-port", type=int)
    u.add_argument("--web-port", type=int)
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    sub.add_parser("down")
    a = ap.parse_args(argv)
    if a.cmd == "up":
        st = up(ROOT, web=not a.no_web, build=not a.no_build, gw_port=a.gw_port, web_port=a.web_port)
        ep = endpoints(ROOT)
        print(f"■ 스택 실행 중 — api {ep['api']}" + (f" · web {ep['web']}" if st.get("web") else "")
              + "\n  다음: python nova.py ui-smoke (주소는 자동) · 끝나면 python nova.py stack down")
        return 0
    if a.cmd == "status":
        st = status(ROOT)
        if a.json:
            print(json.dumps(st, ensure_ascii=False, indent=2))
            return 0
        if not (st.get("gateway") or st.get("web")):
            print("■ 스택 없음 — python nova.py stack up")
            return 0
        for k in ("gateway", "web"):
            e = st.get(k)
            if e:
                mark = "✓" if e["running"] and e["responding"] else "✗"
                print(f"{mark} {k:8} :{e['port']} pid {e['pid']} · 프로세스 {'살아 있음' if e['running'] else '없음'}"
                      f" · 응답 {'있음' if e['responding'] else '없음'} · 로그 {e['log']}")
        print(f"  주소 — api {st['endpoints']['api']} · web {st['endpoints']['web']} ({st['endpoints']['from']})")
        return 0
    left = down(ROOT)
    if left:
        print("✗ 정리하지 못한 것:\n  " + "\n  ".join(left))
        return 1
    print("✓ 스택 내림 — 포트 비었고 남은 프로세스 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
