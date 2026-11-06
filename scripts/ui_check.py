#!/usr/bin/env python3
"""토큰 밖 값 검사기 — 웹 화면 · 부품이 디자인 토큰 밖의 색 · 간격을 쓰는지(plan_REQ_04 T04-5.01 · R14).

  uv run python scripts/ui_check.py          # 위반 목록 출력, 있으면 종료 코드 1 (python nova.py lint 의 한 단계)

잡는 것
  - ts · tsx 의 색 리터럴: hex(#RGB · #RRGGBB · #RRGGBBAA) · rgb() · rgba() · hsl() · hsla()
  - tsx 의 style={{ … }} 안 px: 숫자 값(marginTop: 12 → React 가 px 로 붙인다) · "16px" 같은 문자열
    (0 · 단위 없는 속성(opacity · zIndex · flex …) · 변수 · var(--…) 는 통과)
  - css 의 색 리터럴(생성물 tokens.css 는 뺀다 — 값이 있는 것이 정상)

예외는 선언 web/ui-check.json 에만, **이유와 함께** 둔다(반목표: 화면마다 예외 코드를 늘리는 것). 예외에 `token` 을 적으면
그 값이 토큰 원천(design/tokens/brand.tokens.json)의 값과 같은지도 본다 — 토큰이 바뀌었는데 사본이 남는 것을 잡는다.
쓰이지 않는 예외도 오류다(고친 뒤 예외가 남아 다음 위반을 숨기지 않게).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT  # noqa: E402

CONFIG = ROOT / "web" / "ui-check.json"
SUFFIXES = {".ts", ".tsx", ".css"}
SKIP_PARTS = {"node_modules", ".next", "dist", "build", "out"}
SKIP_NAMES = {"tokens.css", "next-env.d.ts"}          # 생성물

RAW_COLOR = re.compile(r"(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])|\b(?:rgba?|hsla?)\(")
PX_STRING = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)px\b")
PX_NUMBER = re.compile(r"(?<![\w$.\]])([A-Za-z]+)\s*:\s*(-?\d+(?:\.\d+)?)(?![\w.])")
# React 가 px 를 붙이지 않는 속성 — 숫자를 그대로 써도 토큰 밖 간격이 아니다
UNITLESS = {"opacity", "zIndex", "flex", "flexGrow", "flexShrink", "order", "lineHeight", "fontWeight", "zoom",
            "gridRow", "gridColumn", "gridRowStart", "gridRowEnd", "gridColumnStart", "gridColumnEnd",
            "columnCount", "fillOpacity", "strokeOpacity", "stopOpacity", "strokeWidth", "tabSize", "orphans", "widows"}


def load_config(path: Path = CONFIG) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.setdefault("roots", ["web"])
    cfg.setdefault("exceptions", [])
    return cfg


def _strip_comments(text: str) -> str:
    """주석을 같은 길이의 공백으로 바꾼다 — 줄 번호 · 위치는 그대로(주석의 'React #418' 같은 것은 색이 아니다)."""
    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    return re.sub(r"(^|[\s;{}(,])//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), text)


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _style_spans(text: str):
    """style={{ … }} 의 안쪽(중괄호 짝을 맞춰) 시작 · 끝 위치."""
    for m in re.finditer(r"\bstyle=\{\{", text):
        depth, i = 2, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        yield m.end(), i - 2


def scan_text(rel: str, text: str) -> list[tuple[str, int, str]]:
    """(경로, 줄, 종류) 목록. 종류: '색' · '인라인 px'."""
    code = _strip_comments(text)
    out: list[tuple[str, int, str]] = []
    for m in RAW_COLOR.finditer(code):
        out.append((rel, _line(code, m.start()), "색"))
    if rel.endswith(".tsx"):
        for a, b in _style_spans(code):
            seg = code[a:b]
            hits = [m.start() for m in PX_STRING.finditer(seg) if float(m.group(1)) != 0]
            hits += [m.start() for m in PX_NUMBER.finditer(seg) if m.group(1) not in UNITLESS and float(m.group(2)) != 0]
            for h in sorted(set(_line(code, a + x) for x in hits)):
                out.append((rel, h, "인라인 px"))
    return sorted(set(out), key=lambda v: (v[0], v[1], v[2]))


MESSAGE = {"색": "토큰 밖 색 — 의미 토큰 var(--color-…) 로 바꾼다(새 값이면 brand.tokens.json → python nova.py tokens)",
           "인라인 px": "인라인 px — 클래스 · 간격 토큰 var(--space-…) 로 바꾼다(styles.css)"}


def _files(root: Path, cfg: dict):
    for r in cfg["roots"]:
        base = root / r
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            parts = set(p.relative_to(root).parts)
            if p.is_file() and p.suffix in SUFFIXES and p.name not in SKIP_NAMES and not (SKIP_PARTS & parts):
                yield p


def _token_value(tree: dict, name: str, mode: str):
    import gen_tokens as gt
    node = tree["semantic"]
    for part in name.split("."):
        node = node[part]
    return gt.value_of(tree, node, mode)


def run(root: Path = ROOT, cfg: dict | None = None, tree: dict | None = None) -> list[str]:
    """오류 메시지 목록(비면 통과) — 남은 위반 + 선언 오류(이유 없음 · 쓰이지 않음 · 토큰 값 어긋남)."""
    cfg = cfg if cfg is not None else load_config()
    errs: list[str] = []
    excs = cfg.get("exceptions", [])
    for i, e in enumerate(excs):
        if not str(e.get("reason", "")).strip():
            errs.append(f"web/ui-check.json: exceptions[{i}] ({e.get('path')} · {e.get('match')}) 이유가 없다 — 예외는 이유와 함께만")
        if not e.get("path") or not e.get("match"):
            errs.append(f"web/ui-check.json: exceptions[{i}] path · match 가 필요하다")
    used = [False] * len(excs)
    for p in _files(root, cfg):
        rel = p.relative_to(root).as_posix()
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        for _rel, n, kind in scan_text(rel, text):
            line = lines[n - 1] if n - 1 < len(lines) else ""
            hit = next((k for k, e in enumerate(excs) if e.get("path") == rel and e.get("match") and e["match"] in line), None)
            if hit is not None:
                used[hit] = True   # 이유 없는 예외는 위에서 선언 오류로 따로 알린다 — 같은 줄을 두 번 세지 않는다
                continue
            errs.append(f"{rel}:{n}: {MESSAGE[kind]}")
    for k, e in enumerate(excs):
        if not used[k] and e.get("path") and e.get("match"):
            errs.append(f"web/ui-check.json: 쓰이지 않는 예외 — {e['path']} · {e['match']} (고쳤으면 예외를 지운다)")
        if e.get("token") and e.get("match"):
            if tree is None:
                import gen_tokens as gt
                tree = gt.load()
            try:
                want = str(_token_value(tree, e["token"], e.get("mode", "light")))
            except KeyError:
                errs.append(f"web/ui-check.json: 없는 토큰 {e['token']} — {e['path']}")
                continue
            if want.upper() != str(e["match"]).upper():
                errs.append(f"web/ui-check.json: {e['path']} 의 {e['match']} 가 토큰 {e['token']}({e.get('mode', 'light')}) 값 {want} 와 다르다"
                            " — 원천 값으로 맞춘다")
    return errs


def main() -> int:
    errs = run()
    if errs:
        print("\n".join("✗ " + e for e in errs))
        print(f"✗ 토큰 밖 값 {len(errs)}건 — docs/conventions/ui.md 규칙 · 예외는 web/ui-check.json(이유 필수)")
        return 1
    print("✓ 토큰 밖 값 없음(웹 화면 · 부품 — 색 · 인라인 px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
