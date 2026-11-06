"""`python nova.py migrate <svc> new "<설명>" | up | status` — 마이그레이션 명령(ADR-011 · T03-2.08).

명령은 `python -m nova_common.migrate` 로 돈다(서비스는 services/<svc> 에서 `<pkg>.main:svc` 로 연다)."""
import pytest
import os
import shutil
import subprocess
import sys
from pathlib import Path

from nova_common import migrate

# 느린 테스트(실측 10초 이상 — 하위 프로세스 · 저장소 복제) — quick 에서 빠지고 전체 test 에서만 돈다(REQ-261104-17)
pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]


def _run(args, cwd=ROOT, **env):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("NOVA_", "DATABASE_URL"))}
    e.update(PYTHONIOENCODING="utf-8", **env)
    return subprocess.run([sys.executable, "-m", "nova_common.migrate", *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", env=e)


def test_help_lists_migrate():
    r = subprocess.run([sys.executable, str(ROOT / "nova.py"), "help"], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 0 and "migrate" in r.stdout and "new" in r.stdout


def test_up_then_status(tmp_path):
    url = f"sqlite:///{(tmp_path / 'sample.db').as_posix()}"
    before = _run(["sample", "status"], DATABASE_URL_SAMPLE=url)
    assert before.returncode == 0, before.stdout + before.stderr
    assert "올릴 리비전" in before.stdout
    up = _run(["sample", "up"], DATABASE_URL_SAMPLE=url)
    assert up.returncode == 0, up.stdout + up.stderr
    after = _run(["sample", "status"], DATABASE_URL_SAMPLE=url)
    assert after.returncode == 0 and "최신" in after.stdout and migrate.platform_head() in after.stdout and _sample_head() in after.stdout


def _sample_head() -> str:
    """샘플 서비스의 지금 최신 리비전(s000N) — 리비전이 늘어도 테스트가 숫자를 다시 박지 않게 파일 수에서 계산한다."""
    n = len(list((ROOT / "services/sample/migrations/versions").glob("[0-9][0-9][0-9][0-9]_*.py")))
    return f"s{n:04d}"
    assert "차이 없음" in after.stdout


def test_new_autogenerates_next_revision(tmp_path):
    """모델에 칸을 더하면 new 가 다음 리비전(지금 최신 + 1)을 만든다 — 복사한 서비스 폴더(--root)에서, 실제 DB 는 건드리지 않는다."""
    shutil.copytree(ROOT / "services/sample", tmp_path / "services/sample", ignore=shutil.ignore_patterns("__pycache__", "tests"))
    models = tmp_path / "services/sample/sample/models.py"
    src = models.read_text(encoding="utf-8")
    anchor = '    memo: Mapped[str | None] = mapped_column(Text, nullable=True, comment="메모")\n'
    assert anchor in src
    models.write_text(src.replace(anchor, anchor + '    color: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="색")\n'), encoding="utf-8")
    r = _run(["sample", "new", "item color 칸 추가", "--root", str(tmp_path)], DATABASE_URL_SAMPLE="sqlite://")
    assert r.returncode == 0, r.stdout + r.stderr
    nxt = int(_sample_head()[1:]) + 1   # 다음 리비전 번호(지금 최신 + 1)
    made = sorted((tmp_path / "services/sample/migrations/versions").glob(f"{nxt:04d}_*.py"))
    assert len(made) == 1
    body = made[0].read_text(encoding="utf-8")
    assert f'revision = "s{nxt:04d}"' in body or f"revision = 's{nxt:04d}'" in body
    assert "add_column" in body and "color" in body and "drop_column" in body
    # 다시 돌리면 차이가 없으니 빈 리비전을 만들지 않는다
    again = _run(["sample", "new", "또", "--root", str(tmp_path)], DATABASE_URL_SAMPLE="sqlite://")
    assert again.returncode == 1 and "차이가 없" in again.stdout


def test_unknown_service_and_bad_action():
    r = _run(["no-such-svc", "status"])
    assert r.returncode == 2 and "서비스" in (r.stdout + r.stderr)
    r = _run(["sample", "jump"])
    assert r.returncode == 2
