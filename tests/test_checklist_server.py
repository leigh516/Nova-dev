"""체크리스트 저장 서버(scripts/checklist.py serve) — 같은 출처만 저장 · JSON 만 · 크기 상한 · /files/ 폴더 · 확장자 · CSP."""
import http.client
import json
import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import checklist as ck
import warehouse as wh

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def server(tmp_path, monkeypatch):
    """임시 창고에 서버를 띄운다 — 실제 docs/warehouse 에는 쓰지 않는다(test_checklist 의 repo 픽스처와 같은 방식)."""
    shutil.copytree(ROOT / "docs" / "warehouse", tmp_path / "warehouse")
    (tmp_path / "product").mkdir()
    for p in (tmp_path / "warehouse/inbound/checklist").glob("checklist_*"):
        p.unlink()
    monkeypatch.setattr(wh, "WH", tmp_path / "warehouse")
    monkeypatch.setattr(wh, "PRODUCT", tmp_path / "product")
    monkeypatch.setattr(wh, "ROOT", tmp_path)
    for cat in ck.MOCKUP_DIRS:
        (tmp_path / "warehouse/inbound" / cat).mkdir(parents=True, exist_ok=True)
    (tmp_path / "warehouse/inbound/html-mockup/m.html").write_text("<h1>목업</h1>", encoding="utf-8")
    (tmp_path / "warehouse/inbound/html-mockup/secret.txt").write_text("비밀", encoding="utf-8")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ck.Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def req(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    finally:
        c.close()


def doc(answers=None):
    return {"form": "nova-checklist", "tree_version": "1", "status": "draft", "revision": 1, "created": "2030-01-02",
            "updated": "2030-01-02T10:00:00", "file": "", "lv": 1, "answers": answers or {}}


def save(port, payload, ctype="application/json", origin=None):
    h = {"Content-Type": ctype}
    if origin is not None:
        h["Origin"] = origin
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return req(port, "POST", "/api/save", body, h)


def test_save_same_origin_ok(server):
    for origin in (None, f"http://127.0.0.1:{server}", f"http://localhost:{server}"):
        st, _, body = save(server, doc(), origin=origin)
        assert st == 200, body
        assert ck.FILE_RE.match(json.loads(body)["file"])
    assert len(list(ck.ck_dir().glob("checklist_*.json"))) == 3


def test_save_rejects_bad_payload(server):
    for payload in (b"{not json", {"form": "x", "answers": {}}, [1, 2], {"form": "nova-checklist", "answers": {"what.kind": "new"}}):
        st, _, body = save(server, payload)
        assert st == 400, (payload, body)
        assert json.loads(body)["error"]["code"] == "INVALID"
    assert list(ck.ck_dir().glob("checklist_*.json")) == []


def test_save_rejects_other_origin(server):
    for origin in ("http://evil.example", f"http://127.0.0.1:{server + 1}", "null", f"https://127.0.0.1:{server}"):
        st, _, body = save(server, doc(), origin=origin)
        assert st == 403, origin
        assert json.loads(body)["error"]["code"] == "FORBIDDEN_ORIGIN"
    assert list(ck.ck_dir().glob("checklist_*.json")) == []


def test_save_rejects_non_json_content_type(server):
    for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"):
        st, _, body = save(server, doc(), ctype=ctype)
        assert st == 415, ctype
        assert "application/json" in json.loads(body)["error"]["message"]
    assert save(server, doc(), ctype="application/json; charset=utf-8")[0] == 200


def test_save_rejects_too_large(server):
    """상한을 넘으면 본문을 읽지 않고 413 — 머리글만 보내 서버가 본문을 기다리지 않는지 본다."""
    c = http.client.HTTPConnection("127.0.0.1", server, timeout=30)
    try:
        c.putrequest("POST", "/api/save")
        c.putheader("Content-Type", "application/json")
        c.putheader("Content-Length", str(ck.MAX_SAVE + 1))
        c.endheaders()
        r = c.getresponse()
        st, body = r.status, r.read()
    finally:
        c.close()
    assert st == 413 and json.loads(body)["error"]["code"] == "TOO_LARGE"
    assert save(server, b"{}", ctype="application/json")[0] == 400                # 상한 안쪽은 내용 검사로 넘어간다
    assert list(ck.ck_dir().glob("checklist_*.json")) == []


def test_files_stay_inside_mockup_dirs(server):
    st, h, body = req(server, "GET", "/files/html-mockup/m.html")
    assert st == 200 and "목업" in body.decode("utf-8")
    assert h.get("Content-Security-Policy") == "sandbox"
    for path in ("/files/html-mockup/..%2F..%2F..%2Fproduct%2Fintake.json", "/files/html-mockup/../checklist/README.md",
                 "/files/checklist/README.md", "/files/html-mockup/%2e%2e/%2e%2e/README.md"):
        assert req(server, "GET", path)[0] == 404, path


def test_files_only_allowed_extensions(server):
    assert req(server, "GET", "/files/html-mockup/secret.txt")[0] == 404
