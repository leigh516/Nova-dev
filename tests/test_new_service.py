"""new_service — 템플릿에서 만든 서비스가 카탈로그 · 토픽 · 권한에 등록되고, 그 자체 테스트가 통과한다."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import new_service

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    for rel in ("packages/common-py/nova_common/services.json", "infra/k3s/base/kafka-topics.txt", "services/gateway/gateway/rbac.json"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    shutil.copytree(ROOT / "services/_template", tmp_path / "services/_template",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def test_create_registers_everything(repo):
    dest = new_service.create(repo, "order-hub", "business", "ORDER", "주문")
    assert (dest / "order_hub" / "main.py").exists() and (dest / "tests" / "test_records.py").exists()
    # 새 서비스는 migrations 폴더를 갖고 시작한다(ADR-011) — 자리표시자가 남지 않는다
    for rel in ("migrations/env.py", "migrations/versions/0001_initial.py", "tests/test_migrations.py"):
        assert (dest / rel).exists(), rel
        assert "__SERVICE__" not in (dest / rel).read_text(encoding="utf-8") and "__PKG__" not in (dest / rel).read_text(encoding="utf-8")
    text = (dest / "order_hub" / "records.py").read_text(encoding="utf-8")
    assert "__" not in text.replace("__future__", "").replace("__init__", "")
    cat = json.loads((repo / "packages/common-py/nova_common/services.json").read_text(encoding="utf-8"))
    names = [s["name"] for s in cat["services"]]
    assert names[-1] == "gateway" and "order-hub" in names
    spec = next(s for s in cat["services"] if s["name"] == "order-hub")
    assert spec["routes"] == ["/order-hub"] and spec["scope"] == "ORDER"
    assert "order_hub.record.created 3 7" in (repo / "infra/k3s/base/kafka-topics.txt").read_text(encoding="utf-8")
    rbac = json.loads((repo / "services/gateway/gateway/rbac.json").read_text(encoding="utf-8"))
    assert "order-hub.*" in rbac["roles"]["manager"]["perms"]


@pytest.mark.slow  # 실측 10초 이상 — quick 에서 빠지고 전체 test 에서만(REQ-261104-17)
def test_generated_service_tests_pass(repo):
    dest = new_service.create(repo, "order-hub", "business", "ORDER", "주문")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("NOVA_", "DATABASE_URL"))}  # 다른 테스트가 남긴 설정 제외
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--basetemp={repo / '.pt'}", "tests"],
                       cwd=dest, capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("args,msg", [
    (("Order", "business", "ORDER"), "소문자"),
    (("order", "business", "or"), "대문자"),
    (("sample", "business", "NEW"), "이미 있는 서비스"),
    (("order", "business", "SAMPLE"), "이미 쓰는 범위"),
    (("order", "gateway", "ORDER"), "그룹은"),
    (("json", "business", "JSONX"), "표준 모듈"),
])
def test_rejects_bad_input(repo, args, msg):
    with pytest.raises(SystemExit) as e:
        new_service.create(repo, *args)
    assert msg in str(e.value)
