"""원격 CI 워크플로(.github/workflows/check.yml)가 전체 검사를 실제로 부르도록 지키는 시험(REQ-261105-10-2)."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "check.yml"


def load() -> dict:
    assert WF.exists(), "check.yml 이 없다"
    return yaml.safe_load(WF.read_text(encoding="utf-8"))


def triggers(doc: dict) -> dict:
    # YAML 1.1 은 키 on 을 True 로 읽는다
    return doc.get("on", doc.get(True))


def steps(doc: dict) -> list[dict]:
    return [s for j in doc["jobs"].values() for s in j["steps"]]


def test_푸시와_pr에_걸린다():
    t = triggers(load())
    assert "push" in t and "pull_request" in t and "workflow_dispatch" in t


def test_전체_검사를_부른다():
    runs = [s.get("run", "") for s in steps(load())]
    assert any("python nova.py check" in r for r in runs)
    assert any(r.strip() == "uv sync" for r in runs)


def test_uv_버전이_고정이다():
    uv = [s for s in steps(load()) if str(s.get("uses", "")).startswith("astral-sh/setup-uv")]
    assert uv, "setup-uv 단계가 없다"
    version = str(uv[0].get("with", {}).get("version", ""))
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"uv 버전이 고정이 아니다: {version!r}"


def test_같은_브랜치_이전_실행을_취소한다():
    c = load()["concurrency"]
    assert c["cancel-in-progress"] is True
    assert "github.ref" in c["group"]


def test_파이썬_312와_리눅스():
    doc = load()
    assert all(j["runs-on"] == "ubuntu-latest" for j in doc["jobs"].values())
    py = [s for s in steps(doc) if str(s.get("uses", "")).startswith("actions/setup-python")]
    assert py and str(py[0]["with"]["python-version"]) == "3.12"
