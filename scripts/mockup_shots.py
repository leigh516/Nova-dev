#!/usr/bin/env python3
"""계획서 화면 목업 → PNG. 계획을 세울 때 화면을 미리 보고 확인하기 위한 도구(plans/README §4).

  uv run python scripts/mockup_shots.py                                   # docs/plans/mockups/**/*.html 전부
  uv run python scripts/mockup_shots.py docs/plans/mockups/REQ_01/app-items.html
  uv run python scripts/mockup_shots.py --themes light,dark                 # 두 모드(기본이 아닌 모드는 <이름>.<모드>.png)
페이지 오류 · 콘솔 오류 · 빈 화면(요소 · 글자 하한)이 있으면 종료 코드 1.

목업 파일은 '화면 본문'만 쓴다(화면 규약: 템플릿 호출 + 데이터 정의). 첫 줄 주석에 앱 · 메뉴를 적으면
실제 웹 AppShell 과 같은 상단바 · 사이드바로 감싸고, 실제 웹의 tokens.css · styles.css 를 그대로 써서 찍는다
→ 목업과 나중에 구현한 화면의 모양이 같다. 결과 PNG 는 같은 폴더 · 같은 이름(.png).

    <!-- mockup: {"app": "app", "active": "/items", "title": "항목 — 일괄 보관 추가", "width": 1280, "theme": "light"} -->

app: docs/plans/mockups/_shell.json 의 앱 키 | bare(셸 없음) · active: 메뉴 강조 · extra_links: 메뉴 추가(NEW 표시)
새로 생기는 부분에는 class="mock-new"(점선 강조).
"""
from __future__ import annotations

import html as H
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT  # noqa: E402

UI = ROOT / "web" / "packages" / "ui" / "src"
MOCKS = ROOT / "docs" / "plans" / "mockups"
META_RE = re.compile(r"<!--\s*mockup:\s*(\{.*?\})\s*-->", re.S)


def shell_config() -> dict:
    return json.loads((MOCKS / "_shell.json").read_text(encoding="utf-8"))


def wrap(body_html: str, meta: dict, cfg: dict | None = None) -> str:
    cfg = cfg or shell_config()
    css = (UI / "styles.css").read_text(encoding="utf-8").replace('@import "./tokens.css";', (UI / "tokens.css").read_text(encoding="utf-8"))
    css += ("\n.mock-new{outline:2px dashed var(--color-action-accent);outline-offset:3px;border-radius:var(--radius-md)}"
            "\n.mock-tag{display:inline-block;margin-left:6px;font-size:10px;font-weight:700;color:var(--color-status-warning-fg);"
            "background:var(--color-status-warning-bg);border-radius:5px;padding:1px 5px;vertical-align:middle}\n")
    app = meta.get("app", "bare")
    body = body_html
    apps = cfg.get("apps", {})
    if app in apps:
        a = apps[app]
        links = [tuple(x) for x in a["links"]] + [tuple(x) for x in meta.get("extra_links", [])]
        new = {x[0] for x in meta.get("extra_links", [])}

        def link(href: str, label: str, *_icon: str) -> str:
            cur = ' aria-current="page"' if href == meta.get("active") else ""
            tag = '<span class="mock-tag">NEW</span>' if href in new else ""
            return f'<a href="#"{cur}>{H.escape(label)}{tag}</a>'

        brand = cfg.get("brand", "App")
        chip = f'<button class="userchip"><span class="avatar">{H.escape(a.get("user", "?")[0])}</span><span class="hide-sm">{H.escape(a.get("user", ""))} · 로그아웃</span></button>'
        logo = f'<a class="brand"><span class="mark">{H.escape(brand[0])}</span>{H.escape(brand)}<small style="opacity:.7;font-size:12px">{H.escape(a.get("product", ""))}</small></a>'
        icons = '<a class="iconbtn">?</a><button class="iconbtn">◐</button>'
        if a.get("layout") == "side":
            body = (f'<header class="topbar"><div class="topbar-in" style="max-width:none">{logo}<div class="grow"></div>{icons}{chip}</div></header>'
                    f'<div class="sidebar-layout"><aside class="sidebar">{"".join(link(*x) for x in links)}</aside><main>{body_html}</main></div>')
        else:
            body = (f'<header class="topbar"><div class="topbar-in">{logo}<nav class="nav grow">{"".join(link(*x) for x in links)}</nav>{icons}{chip}</div></header>'
                    f'<main>{body_html}</main>')
    theme = meta.get("theme", "light")
    return f'<!doctype html><html lang="ko" data-theme="{theme}"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


MIN_NODES, MIN_TEXT = 20, 10   # 이보다 적으면 빈 화면으로 본다(종료 코드 0 인데 PNG 가 하얀 경우를 잡는다)


def judge(nodes: int, text_len: int, errors: list[str]) -> list[str]:
    """한 장의 판정 — 문제 목록(비면 정상). 브라우저 없이 시험할 수 있게 순수 함수로 둔다."""
    out = [f"오류: {e}" for e in errors]
    if nodes < MIN_NODES or text_len < MIN_TEXT:
        out.append(f"빈 화면으로 보인다(요소 {nodes}개 · 글자 {text_len}자 — 하한 {MIN_NODES} · {MIN_TEXT})")
    return out


def out_path(f: Path, theme: str, default: str) -> Path:
    """기본 테마는 <이름>.png, 그 밖의 테마는 <이름>.<테마>.png."""
    return f.with_suffix(".png") if theme == default else f.with_name(f"{f.stem}.{theme}.png")


def shoot(files: list[Path], themes: list[str] | None = None) -> int:
    """찍은 장수를 돌려준다. 오류 · 빈 화면이 하나라도 있으면 SystemExit(1)."""
    from playwright.sync_api import sync_playwright

    cfg = shell_config()
    n, bad = 0, []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for f in files:
            src = f.read_text(encoding="utf-8")
            m = META_RE.search(src)
            meta = json.loads(m.group(1)) if m else {}
            default = meta.get("theme", "light")
            for theme in (themes or [default]):
                errors: list[str] = []
                page = b.new_page(viewport={"width": meta.get("width", 1280), "height": meta.get("height", 720)}, device_scale_factor=1)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("console", lambda c: errors.append(c.text) if c.type == "error" else None)
                page.set_content(wrap(META_RE.sub("", src), {**meta, "theme": theme}, cfg), wait_until="load")
                nodes = page.evaluate("document.body.querySelectorAll('*').length")
                text_len = page.evaluate("(document.body.innerText || '').trim().length")
                out = out_path(f, theme, default)
                page.screenshot(path=str(out), full_page=True)
                page.close()
                problems = judge(nodes, text_len, errors)
                rel = out.relative_to(ROOT).as_posix()
                if problems:
                    bad.append(rel)
                    print(f"✗ {rel}")
                    for x in problems:
                        print(f"    {x}")
                else:
                    print(f"✓ {rel}")
                n += 1
        b.close()
    if bad:
        print(f"✗ {len(bad)}장에 문제가 있다 — PNG 를 열어 보고 목업을 고친다")
        raise SystemExit(1)
    return n


def main(argv: list[str]) -> int:
    themes = None
    if "--themes" in argv:   # 예: --themes light,dark — 두 모드를 모두 찍어 다크 대비를 눈으로 본다
        i = argv.index("--themes")
        themes = [x.strip() for x in argv[i + 1].split(",") if x.strip()]
        argv = argv[:i] + argv[i + 2:]
    files = [Path(a).resolve() for a in argv] if argv else sorted(p for p in MOCKS.rglob("*.html") if not p.name.startswith("_"))
    if not files:
        print("목업 없음 — docs/plans/mockups/<REQ>/<화면>.html 을 만드세요")
        return 0
    shoot(files, themes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
