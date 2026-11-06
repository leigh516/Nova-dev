"""심층 감사 분모(scripts/audit_scope.py) — 생성물 제외 · 범위 · 게이트 표 · 축 이름이 명령 문서와 맞는지."""
import re
from pathlib import Path

import audit_scope as au

ROOT = Path(__file__).resolve().parents[1]


def test_generated_files_are_excluded_with_reason():
    d = au.scope([])
    ex = d["excluded"]
    for p in ("web/packages/ui/src/tokens.css", "docker-compose.yml", "docs/registry/screens.md",
              "docs/warehouse/inbound/checklist/checklist.html", "uv.lock"):
        assert p in ex and ex[p], p
    assert d["k3s_known"]
    assert d["audited"] + len(ex) == d["tracked"]
    assert "scripts/checklist_form/template.html" not in ex   # 원천은 감사 대상


def test_scope_narrows_by_path():
    d = au.scope(["services/sample"])
    files = {f for a in d["axes"].values() for f in a["list"]}
    assert files and all(f.startswith("services/sample/") for f in files)


def test_gates_table_matches_lint():
    src = (ROOT / "nova.py").read_text(encoding="utf-8")
    body = src[src.index("def cmd_lint"):src.index("def cmd_gen")]
    steps = set(re.findall(r'script\("([a-z0-9_]+\.py)"', body))
    assert steps == set(au.GATES)   # lint 에 단계를 더하면 감사 게이트 표에도 적는다


def test_axes_match_command_doc():
    doc = (ROOT / ".claude/commands/deep-audit.md").read_text(encoding="utf-8")
    table = doc[doc.index("| 축 | 무엇을 묻나"):doc.index("### 위임 프롬프트")]
    names = set(re.findall(r"^\| \*\*([^*]+)\*\* \|", table, re.M))
    assert names == set(au.AXES)
