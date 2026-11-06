"""토큰 밖 값 검사기(scripts/ui_check.py — plan_REQ_04 T04-5.01 · R14).

잡는 것: ts · tsx 의 hex · rgb() · hsl() 색, tsx 의 style={{ … }} 안 px(숫자 · "16px" 문자열), css 의 색 리터럴.
예외는 web/ui-check.json 에 이유와 함께만 — 이유 없는 예외 · 쓰이지 않는 예외 · 토큰 값과 어긋난 예외는 오류.
"""
from pathlib import Path

import gen_tokens as gt
import ui_check as uc

CFG = {"roots": ["web"], "exceptions": []}


def _put(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _where(errs: list[str]) -> list[str]:
    return sorted(":".join(e.split(":")[:2]) for e in errs)


def test_catches_colors_in_tsx_and_css(tmp_path):
    _put(tmp_path, "web/apps/a/app/page.tsx",
         'const a = "#1A2B3C";\n'
         "const b = { color: 'rgb(1, 2, 3)' };\n"
         "const c = 'hsl(10 20% 30%)';\n"
         "// 주석의 #FFFFFF 와 React #418 은 색이 아니다\n"
         '<a href="#add-item">추가</a>\n')
    _put(tmp_path, "web/packages/ui/src/x.css", ".a { background: rgba(0, 0, 0, .4); }\n.b { color: var(--color-text-primary); }\n")
    errs = uc.run(tmp_path, CFG)
    assert _where(errs) == ["web/apps/a/app/page.tsx:1", "web/apps/a/app/page.tsx:2", "web/apps/a/app/page.tsx:3",
                            "web/packages/ui/src/x.css:1"], errs
    assert all("토큰 밖 색" in e for e in errs), errs


def test_catches_inline_px_in_style(tmp_path):
    _put(tmp_path, "web/apps/a/app/page.tsx",
         '<p style={{ marginTop: 12 }}>가</p>\n'
         '<div style={{ ["--gap" as string]: "16px" }} />\n'
         '<form style={{ width: "min(420px, 100%)" }} />\n'
         "<div style={{\n  margin: 0,\n  paddingLeft: 18,\n}} />\n"
         "<i style={{ height, width }} />\n"
         "<i style={{ opacity: 0.7, zIndex: 3, flex: 1, paddingTop: 0 }} />\n"
         "<i style={{ height: `${Math.max(2, v)}px`, opacity: v ? 1 : 0.25 }} />\n"
         '<i style={{ padding: "var(--space-3)" }} />\n'
         "<Skeleton height={20} />\n")
    errs = uc.run(tmp_path, CFG)
    assert _where(errs) == ["web/apps/a/app/page.tsx:1", "web/apps/a/app/page.tsx:2", "web/apps/a/app/page.tsx:3",
                            "web/apps/a/app/page.tsx:6"], errs
    assert all("인라인 px" in e for e in errs), errs


def test_skips_generated_and_build_dirs(tmp_path):
    _put(tmp_path, "web/packages/ui/src/tokens.css", ":root { --c: #FFFFFF; }\n")
    _put(tmp_path, "web/node_modules/x/a.tsx", 'const a = "#FFFFFF";\n')
    _put(tmp_path, "web/apps/a/.next/b.ts", 'const a = "#FFFFFF";\n')
    assert uc.run(tmp_path, CFG) == []


def test_exception_needs_reason(tmp_path):
    _put(tmp_path, "web/apps/a/app/layout.tsx", 'export const v = { themeColor: "#141821" };\n')
    cfg = {"roots": ["web"], "exceptions": [{"path": "web/apps/a/app/layout.tsx", "match": "#141821", "reason": " "}]}
    errs = uc.run(tmp_path, cfg)
    assert any("이유" in e for e in errs), errs
    # 이유가 있으면 그 줄은 통과
    cfg["exceptions"][0]["reason"] = "Next 메타는 CSS 변수를 못 받는다"
    assert uc.run(tmp_path, cfg) == []


def test_unused_exception_is_error(tmp_path):
    _put(tmp_path, "web/apps/a/app/page.tsx", "const a = 1;\n")
    cfg = {"roots": ["web"], "exceptions": [{"path": "web/apps/a/app/page.tsx", "match": "#000000", "reason": "옛 예외"}]}
    errs = uc.run(tmp_path, cfg)
    assert len(errs) == 1 and "쓰이지 않는 예외" in errs[0], errs


def test_exception_value_must_match_token(tmp_path):
    """themeColor 처럼 토큰을 못 쓰는 자리 — 값이 지정한 토큰과 같아야 한다(토큰이 바뀌면 lint 가 잡는다)."""
    tree = gt.load()
    inverse = str(gt.value_of(tree, tree["semantic"]["color"]["bg"]["inverse"], "dark"))
    _put(tmp_path, "web/apps/a/app/layout.tsx", f'export const v = {{ themeColor: "{inverse}" }};\n')
    exc = {"path": "web/apps/a/app/layout.tsx", "match": inverse, "reason": "메타 값", "token": "color.bg.inverse", "mode": "dark"}
    assert uc.run(tmp_path, {"roots": ["web"], "exceptions": [exc]}) == []
    _put(tmp_path, "web/apps/a/app/layout.tsx", 'export const v = { themeColor: "#123456" };\n')
    errs = uc.run(tmp_path, {"roots": ["web"], "exceptions": [{**exc, "match": "#123456"}]})
    assert len(errs) == 1 and "토큰" in errs[0] and "color.bg.inverse" in errs[0], errs


def test_repo_config_is_valid_and_clean():
    """저장소 선언(web/ui-check.json)은 예외마다 이유가 있고, 저장소 화면 · 부품에 위반이 없다(lint 와 같은 판정)."""
    cfg = uc.load_config()
    assert all(str(e.get("reason", "")).strip() for e in cfg["exceptions"])
    assert uc.run(uc.ROOT, cfg) == []
