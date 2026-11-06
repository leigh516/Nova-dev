"""쓰기 경로 감시 — 서비스 라우터의 POST/PUT/PATCH/DELETE 처리기는 require_human 을 부른다(STD-AX-001 L1 · ADR-012 P4).

템플릿(`services/_template`)은 자리표시(__PKG__ · __SERVICE__) 때문에 import 할 수 없어 소스(AST)로 읽는다.
게이트웨이는 업무 라우터가 아니라(로그인 · 운영 API) 빼고, `/internal` 계약 API 는 서비스 간 호출(행위자 system)이라 뺀다.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRITE_METHODS = {"post", "put", "patch", "delete"}
SKIP_SERVICES = {"gateway"}


def _str_arg(call: ast.Call, pos: int, kw: str) -> str | None:
    if len(call.args) > pos and isinstance(call.args[pos], ast.Constant) and isinstance(call.args[pos].value, str):
        return call.args[pos].value
    for k in call.keywords:
        if k.arg == kw and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
            return k.value.value
    return None


def _router_prefixes(tree: ast.Module) -> dict[str, str]:
    """`router = APIRouter(prefix="/x")` → {"router": "/x"}"""
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
            if name == "APIRouter":
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        out[t.id] = _str_arg(node.value, 99, "prefix") or ""
    return out


def _calls_require_human(fn: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "require_human"
               for n in ast.walk(fn))


def write_handlers(source: str) -> list[tuple[str, str, str, bool]]:
    """소스의 쓰기 처리기 — (함수 이름, 메서드, 전체 경로, require_human 호출 여부)."""
    tree = ast.parse(source)
    prefixes = _router_prefixes(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in WRITE_METHODS):
                continue
            owner = dec.func.value.id if isinstance(dec.func.value, ast.Name) else ""
            path = prefixes.get(owner, "") + (_str_arg(dec, 0, "path") or "")
            if path.startswith("/internal") or "/internal/" in path:
                continue
            found.append((node.name, dec.func.attr.upper(), path, _calls_require_human(node)))
    return found


def missing_guard(source: str) -> list[str]:
    return [f"{m} {p} ({name})" for name, m, p, ok in write_handlers(source) if not ok]


def _service_sources() -> dict[str, str]:
    out = {}
    for svc_dir in sorted((ROOT / "services").iterdir()):
        if not svc_dir.is_dir() or svc_dir.name in SKIP_SERVICES:
            continue
        for py in sorted(svc_dir.rglob("*.py")):
            rel = py.relative_to(svc_dir).parts
            if rel[0] in {"tests", "migrations"} or "__pycache__" in rel:
                continue
            out[py.relative_to(ROOT).as_posix()] = py.read_text(encoding="utf-8")
    return out


def test_every_write_handler_requires_human():
    sources = _service_sources()
    bad = {path: miss for path, src in sources.items() if (miss := missing_guard(src))}
    assert not bad, f"AI 쓰기를 막지 않은 처리기(require_human 필요 — STD-AX-001 L1): {bad}"


def test_guard_sees_known_write_handlers():
    """감시가 공허하지 않게 — 샘플 5개 · 템플릿 1개 쓰기 처리기를 실제로 찾아야 한다."""
    sources = _service_sources()
    sample = {(m, p) for _, m, p, _ in write_handlers(sources["services/sample/sample/items.py"])}
    assert sample == {("POST", "/sample/items"), ("PATCH", "/sample/items/{item_id}"),
                      ("POST", "/sample/items/{item_id}/archive"), ("POST", "/sample/items/{item_id}/restore"),
                      ("DELETE", "/sample/items/{item_id}")}
    tmpl = {(m, p) for _, m, p, _ in write_handlers(sources["services/_template/__PKG__/records.py"])}
    assert tmpl == {("POST", "/__SERVICE__/records")}


def test_guard_fails_when_one_is_missing():
    """하나를 빼면 잡는다 — 샘플 소스에서 require_human 한 곳을 require 로 바꾼 사본."""
    src = (ROOT / "services/sample/sample/items.py").read_text(encoding="utf-8")
    broken = src.replace('require_human("항목 보관 해제")', "require()", 1)
    assert broken != src
    assert missing_guard(broken) == ["POST /sample/items/{item_id}/restore (restore_item)"]
    internal = 'router = APIRouter(prefix="/internal/x")\n@router.post("/sync")\ndef sync(): ...\n'
    assert missing_guard(internal) == []  # 서비스 간 계약 API 는 대상 밖
    plain = 'router = APIRouter(prefix="/x")\n@router.put("/a")\nasync def put_a(request):\n    principal(request).require()\n'
    assert missing_guard(plain) == ["PUT /x/a (put_a)"]
