"""저장소 전체 pytest 설정 — 실행마다 따로 쓰는 임시 폴더 (REQ-261104-17).

`--basetemp` 를 주지 않은 실행은 `.pytest_tmp/run-<프로세스번호>` 를 쓴다. pytest 는 시작할 때 basetemp 를 비우므로,
모두가 `.pytest_tmp` 하나를 쓰면 동시에 돌던 다른 담당 · 세션의 임시 폴더가 지워진다. 서비스 폴더(services/<svc>)에서
돌려도 저장소 루트의 pytest.ini 가 rootdir 이라 이 파일이 함께 읽힌다.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
KEEP_SECONDS = 24 * 3600   # 하루 지난 run-* 는 지운다 — 쌓이지 않게, 그러나 막 끝난 실행의 결과는 남긴다


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    if config.option.basetemp:
        return  # 부르는 쪽(nova.py test · quick · 담당)이 정한 폴더를 그대로 쓴다
    base = ROOT / ".pytest_tmp"
    base.mkdir(exist_ok=True)
    cutoff = time.time() - KEEP_SECONDS
    for d in base.glob("run-*"):
        try:
            if d.stat().st_mtime < cutoff:
                shutil.rmtree(d)
        except OSError as e:  # 다른 실행이 쓰는 중이면 못 지운다 — 다음 실행이 다시 시도한다(실패로 만들 일이 아니다)
            print(f"  ! 지난 임시 폴더를 지우지 못함: {d} — {e}", file=sys.stderr)
    config.option.basetemp = str(base / f"run-{os.getpid()}")
