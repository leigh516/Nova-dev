"""pytest 임시 폴더 — 한 실행이 다른 실행의 작업 폴더를 지우지 않는다 (REQ-261104-17 · 2026-11-04 실측).

pytest.ini 가 --basetemp=.pytest_tmp 하나로 고정돼 있으면, --basetemp 없이 pytest 를 돌릴 때마다 pytest 가 그 폴더를
통째로 비워 동시에 돌던 담당 · 세션의 `.pytest_tmp/<이름>` 이 사라진다(PNG · DB 파일 소실, 재현 안 되는 실패)."""
import os
import subprocess
import sys
import uuid

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.slow  # 하위 프로세스로 pytest 를 한 번 더 띄운다 — 이 PC 에서 수십 초~2분
def test_run_without_basetemp_keeps_other_runs_folders(tmp_path):
    other = ROOT / ".pytest_tmp" / f"다른실행-{uuid.uuid4().hex[:8]}"
    other.mkdir(parents=True)
    (other / "표지.txt").write_text("남아야 한다", encoding="utf-8")
    probe = tmp_path / "test_probe.py"
    probe.write_text("def test_uses_tmp(tmp_path):\n    (tmp_path / 'x').write_text('1')\n", encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(ROOT),
                            "-c", str(ROOT / "pytest.ini"), str(probe)],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        assert r.returncode == 0, r.stdout + r.stderr
        assert (other / "표지.txt").exists(), "basetemp 없이 돈 pytest 가 다른 실행의 임시 폴더를 지웠다"
    finally:
        import shutil
        shutil.rmtree(other, ignore_errors=True)  # 표지 폴더 정리 — 실패해도 다음 실행에 해가 없다
