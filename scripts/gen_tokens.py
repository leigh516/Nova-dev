#!/usr/bin/env python3
"""디자인 토큰 생성기 — design/tokens/brand.tokens.json(DTCG 2025.10) → 웹 CSS · KMP Kotlin + WCAG 2.2 AA 대비 검사.

검사 셋: 대비(contrast 쌍) · 분리(separation — 상태색과 도메인색이 같은 값 · 원시 참조 금지) ·
사용(scan_usage — 부품 · 갤러리 · 모바일 부품 · nicomms 스킬의 토큰 밖 색과 상태 · 도메인 섞어 쓰기).

  python nova.py tokens                         # = uv run python scripts/gen_tokens.py (생성 + 검사, 미달이면 종료 코드 1)
  uv run python scripts/gen_tokens.py --check   # 생성물이 원천과 같은지 · 대비만 검사(lint)

값은 토큰 파일 하나에서만 바꾼다. 생성물(tokens.css · DesignTokens.kt)은 손으로 고치지 않는다.
Kotlin 패키지는 nova.project.json 의 kt_package + ".uikit".

디자인 킷(REQ-261106-04 · ADR-016): design/tokens/kits/catalog.json 의 킷 = brand.tokens.json 위에 덮는 부분 트리.
nova.project.json design.kit(없으면 nova)이 고른 킷으로 생성하고, --check 는 목록의 **모든 킷**을 대비 · 분리 ·
상태색 겹침으로 검사한다(미달 킷이 고를 수 있는 상태로 남지 않게). 킷을 고르는 명령은 scripts/kits.py(python nova.py kit).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, same, write  # noqa: E402

SRC = ROOT / "design" / "tokens" / "brand.tokens.json"
OUT_CSS = ROOT / "web" / "packages" / "ui" / "src" / "tokens.css"
KITS_REL = Path("design") / "tokens" / "kits"
DEFAULT_KIT = "nova"
MODES = ("light", "dark")
MODE_KEY = "nova.modes"
MIN = {"text": 4.5, "ui": 3.0}
# 서로 같으면 안 되는 상태색 짝(-4) — 브랜드가 초록이면 정보색(brand 계열)이 성공색과 겹쳐 '정보'와 '정상'을 구분하지 못한다
DISTINCT_STATUS = (("infoFg", "successFg"), ("infoBg", "successBg"), ("infoSolid", "successSolid"))


def project(root: Path = ROOT) -> dict:
    """nova.project.json — 임시 폴더(시험 · new_project 대상)에서도 쓰게 root 를 받는다."""
    return json.loads((root / "nova.project.json").read_text(encoding="utf-8"))


def kt_package(root: Path = ROOT) -> str:
    return f"{project(root).get('kt_package', 'kr.nova')}.uikit"


def out_kt(root: Path = ROOT) -> Path:
    return root / "apps" / "kmp" / "uikit" / "src" / "commonMain" / "kotlin" / Path(*kt_package(root).split(".")) / "DesignTokens.kt"


def load(path: Path = SRC) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def merge(base: dict, over: dict) -> dict:
    """킷 덮어쓰기 — 사전은 재귀로 합치고 그 밖(값 · 목록)은 킷 값으로 바꾼다. base 는 바꾸지 않는다."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def catalog(root: Path = ROOT) -> list[dict]:
    """킷 목록(design/tokens/kits/catalog.json kits) — 파일이 없으면 기본 킷 하나만(오래된 복제본)."""
    p = root / KITS_REL / "catalog.json"
    if not p.exists():
        return [{"id": DEFAULT_KIT, "label": "Nova 기본", "tokens": None}]
    return json.loads(p.read_text(encoding="utf-8"))["kits"]


def selected_kit(root: Path = ROOT) -> str:
    return (project(root).get("design") or {}).get("kit") or DEFAULT_KIT


def load_kit(kit_id: str, root: Path = ROOT) -> dict:
    """기본 원천 + 킷 덮어쓰기. 목록에 없는 id · 없는 토큰 파일은 KeyError / FileNotFoundError."""
    entry = next((k for k in catalog(root) if k["id"] == kit_id), None)
    if entry is None:
        raise KeyError(f"모르는 킷: {kit_id} — 목록 {[k['id'] for k in catalog(root)]}")
    base = load(root / SRC.relative_to(ROOT))
    if not entry.get("tokens"):
        return base
    return merge(base, load(root / KITS_REL / entry["tokens"]))


def walk(node: dict, path: tuple = (), inherited_type: str | None = None):
    """(경로, 토큰 노드, $type) 를 순회 — $value 가 있으면 토큰."""
    t = node.get("$type", inherited_type)
    if "$value" in node:
        yield path, node, t
        return
    for k, v in node.items():
        if not k.startswith("$") and isinstance(v, dict):
            yield from walk(v, path + (k,), t)


def resolve(tree: dict, ref, mode: str, depth: int = 0):
    if isinstance(ref, str) and ref.startswith("{") and ref.endswith("}"):
        if depth > 8:
            raise ValueError(f"참조 순환: {ref}")
        node = tree
        for part in ref[1:-1].split("."):
            node = node[part]
        return value_of(tree, node, mode, depth + 1)
    return ref


def value_of(tree: dict, node: dict, mode: str, depth: int = 0):
    v = node.get("$extensions", {}).get(MODE_KEY, {}).get(mode, node["$value"]) if mode != "light" else node["$value"]
    return resolve(tree, v, mode, depth)


def css_value(v) -> str:
    if isinstance(v, dict) and "unit" in v:
        return f"{v['value']}{v['unit']}"
    if isinstance(v, list):
        return ", ".join(f'"{x}"' if " " in x else x for x in v)
    return str(v)


def kebab(path: tuple) -> str:
    return "-".join(re.sub(r"([a-z])([A-Z])", r"\1-\2", p).lower() for p in path)


def camel(path: tuple) -> str:
    s = "".join(p[:1].upper() + p[1:] for p in path)
    return s[:1].lower() + s[1:]


def lum(h: str) -> float:
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a: str, b: str) -> float:
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def check_contrast(tree: dict) -> list[str]:
    errs = []
    sem = tree["semantic"]["color"]
    for fg, bg, kind in tree["contrast"]["$value"]:
        for mode in MODES:
            def get(p):
                node = sem
                for part in p.split("."):
                    node = node[part]
                return value_of(tree, node, mode)
            r = ratio(get(fg), get(bg))
            if r < MIN[kind]:
                errs.append(f"[{mode}] {fg} on {bg}: {r:.2f} < {MIN[kind]} ({kind})")
    return errs


def _raw_ref(node: dict, mode: str):
    """모드의 원래 참조 문자열(따라가기 전) — 같은 원시 색을 가리키는지 비교할 때 쓴다."""
    return node.get("$extensions", {}).get(MODE_KEY, {}).get(mode, node["$value"]) if mode != "light" else node["$value"]


def check_separation(tree: dict) -> list[str]:
    """분리 규칙(원천 최상위 separation) — 짝지은 두 묶음(예: status · domain)의 토큰이 같은 값이나 같은 원시 참조를 쓰면 오류.

    상태색과 도메인 식별색이 같으면 '이 색 = 위험' 같은 상태 의미가 흐려져 경보를 놓친다(plan_REQ_05 §6).
    """
    errs = []
    sem = tree["semantic"]["color"]
    for a, b in tree.get("separation", {}).get("$value", []):
        if a not in sem or b not in sem:
            continue
        left = [(".".join((a,) + p), n) for p, n, _t in walk(sem[a])]
        right = [(".".join((b,) + p), n) for p, n, _t in walk(sem[b])]
        for mode in MODES:
            for pa, na in left:
                ra, va = _raw_ref(na, mode), str(value_of(tree, na, mode)).upper()
                for pb, nb in right:
                    rb = _raw_ref(nb, mode)
                    if isinstance(ra, str) and ra.startswith("{") and ra == rb:
                        errs.append(f"[{mode}] {pb} 와 {pa}: 같은 원시 참조 {ra} — 상태색과 분리")
                    elif str(value_of(tree, nb, mode)).upper() == va:
                        errs.append(f"[{mode}] {pb} 와 {pa}: 같은 값 {va} — 상태색과 분리")
    return errs


def check_status_distinct(tree: dict) -> list[str]:
    """정보 · 성공 상태색 겹침(REQ-261106-04-4) — 두 모드에서 같은 값이나 같은 원시 참조면 오류."""
    errs = []
    st = tree["semantic"]["color"].get("status", {})
    for a, b in DISTINCT_STATUS:
        if a not in st or b not in st:
            continue
        for mode in MODES:
            ra, rb = _raw_ref(st[a], mode), _raw_ref(st[b], mode)
            va, vb = str(value_of(tree, st[a], mode)).upper(), str(value_of(tree, st[b], mode)).upper()
            if isinstance(ra, str) and ra.startswith("{") and ra == rb:
                errs.append(f"[{mode}] status.{a} 와 status.{b}: 같은 원시 참조 {ra} — 정보색과 성공색을 나눈다")
            elif va == vb:
                errs.append(f"[{mode}] status.{a} 와 status.{b}: 같은 값 {va} — 정보색과 성공색을 나눈다")
    return errs


def kit_errors(tree: dict) -> list[str]:
    """킷 한 벌의 값 검사 — 대비 · 분리 · 상태색 겹침(사용 검사 scan_usage 는 킷과 무관해 따로)."""
    return check_contrast(tree) + check_separation(tree) + check_status_distinct(tree)


# 사용 검사(scan_usage) — 토큰을 소비하는 쪽(부품 · 갤러리 · 모바일 부품 · nicomms 스킬)이 지키는지
SCAN_DIRS = ("web/packages/ui/src", "web/apps/app/app/design", "apps/kmp/uikit", ".claude/skills/nicomms-screen")
SCAN_SUFFIXES = {".css", ".ts", ".tsx", ".kt", ".md"}
SCAN_SKIP_PARTS = {"build", "node_modules", ".gradle"}
SCAN_SKIP_NAMES = {"tokens.css", "DesignTokens.kt"}          # 생성물 — 값이 있는 것이 정상
# (경로, 줄 내용) — 토큰으로 옮기지 못한 색. 늘리지 말고 토큰으로 옮긴다. 대화상자 백드롭은 color.overlay.scrim 으로
# 옮겨 비었다(plan_REQ_04 T04-5.02). 웹 화면 · 부품 전체의 토큰 밖 값은 scripts/ui_check.py 가 따로 본다
ALLOW_RAW: set[tuple[str, str]] = set()
RAW_COLOR = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|\b(?:rgba?|hsla?)\(|\bColor\(0x[0-9a-fA-F]+")
USE_STATUS = re.compile(r"--color-status-|\.status[A-Z]\w*")
USE_DOMAIN = re.compile(r"--color-domain-|\.domain\d\w*")


def _strip_comment(line: str, suffix: str) -> str:
    """주석은 색 값이 아니다(예: 'React #418', 대비 설명의 hex) — 코드 부분만 남긴다. md 는 전부 본문."""
    if suffix == ".md":
        return line
    s = line.strip()
    if s.startswith(("//", "*", "/*")):
        return ""
    line = re.sub(r"/\*.*?\*/", "", line)
    return re.sub(r"(^|\s)//.*$", "", line)


def _mixed(text: str) -> bool:
    return bool(USE_STATUS.search(text) and USE_DOMAIN.search(text))


def scan_usage(root: Path) -> list[str]:
    """상태색 · 도메인색을 한 CSS 규칙 블록 / TSX · Kotlin 한 줄에 섞어 쓰면 오류, 토큰 밖 색(hex · rgb() · Color(0x…))도 오류."""
    errs = []
    for d in SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            rel_parts = path.relative_to(root).parts
            if (not path.is_file() or path.suffix not in SCAN_SUFFIXES or path.name in SCAN_SKIP_NAMES
                    or SCAN_SKIP_PARTS & set(rel_parts)):
                continue
            rel = "/".join(rel_parts)
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                code = _strip_comment(line, path.suffix)
                if RAW_COLOR.search(code) and (rel, line.strip()) not in ALLOW_RAW:
                    errs.append(f"{rel}:{i}: 토큰 밖 색 — 의미 토큰 var(--color-…) 로 바꾼다")
                if path.suffix in (".tsx", ".ts", ".kt") and _mixed(code):
                    errs.append(f"{rel}:{i}: 상태색과 도메인 식별색을 한 줄에 섞었다 — 따로 쓴다")
            if path.suffix == ".css":
                for m in re.finditer(r"\{[^{}]*\}", text):     # 가장 안쪽 규칙 블록(@media 안 규칙도)
                    if _mixed(m.group(0)):
                        line_no = text.count("\n", 0, m.start()) + 1
                        errs.append(f"{rel}:{line_no}: 상태색과 도메인 식별색을 한 규칙 블록에 섞었다 — 따로 쓴다")
    return errs


def _source_note(kit: str) -> str:
    """머리 주석의 원천 — 기본 킷은 지금까지와 같은 글자(바이트 동일), 다른 킷은 덮은 파일까지 적는다."""
    return "design/tokens/brand.tokens.json" if kit == DEFAULT_KIT else f"design/tokens/brand.tokens.json + 킷 {kit}"


def gen_css(tree: dict, kit: str = DEFAULT_KIT) -> str:
    lines = [f"/* 생성 파일 — scripts/gen_tokens.py (원천: {_source_note(kit)}). 직접 고치지 않는다. */", ":root {"]
    for p, n, _t in walk(tree["primitive"]):
        lines.append(f"  --{kebab(p)}: {css_value(n['$value'])};")
    for p, n, _t in walk(tree["semantic"]):
        lines.append(f"  --{kebab(p)}: {css_value(value_of(tree, n, 'light'))};")
    lines += ["  color-scheme: light;", "}"]
    dark = [f"  --{kebab(p)}: {css_value(value_of(tree, n, 'dark'))};" for p, n, _t in walk(tree["semantic"])
            if value_of(tree, n, "dark") != value_of(tree, n, "light")]
    body = "\n".join(dark) + "\n  color-scheme: dark;"
    lines += ['@media (prefers-color-scheme: dark) {', '  :root:not([data-theme="light"]) {', "  " + body.replace("\n", "\n  "), "  }", "}",
              ':root[data-theme="dark"] {', body, "}", ""]
    return "\n".join(lines)


def kt_color(h: str) -> str:
    """#RRGGBB → 0xFFRRGGBB, 반투명 #RRGGBBAA(CSS 순서) → 0xAARRGGBB(Compose 순서)."""
    h = h.lstrip("#").upper()
    if len(h) == 8:
        return f"Color(0x{h[6:]}{h[:6]})"
    return f"Color(0xFF{h})"


def gen_kt(tree: dict, kit: str = DEFAULT_KIT, package: str | None = None) -> str:
    package = package or kt_package()
    sem = list(walk(tree["semantic"]["color"]))
    props = "\n".join(f"    val {camel(p)}: Color," for p, _n, _t in sem)

    def inst(mode):
        return "\n".join(f"    {camel(p)} = {kt_color(value_of(tree, n, mode))}," for p, n, _t in sem)
    dims = []
    for group in ("space", "radius"):
        for p, n, _t in walk(tree["primitive"][group]):
            dims.append(f"    val {camel((group,) + p)} = {n['$value']['value']}.dp")
    for p, n, _t in walk(tree["semantic"]["size"]):
        dims.append(f"    val {camel(('size',) + p)} = {n['$value']['value']}.dp")
    fonts = [f"    val {camel(('font',) + p)} = {n['$value']['value']}.sp" for p, n, _t in walk(tree["primitive"]["font"]["size"])]
    weights = [f"    val {camel(('weight',) + p)} = FontWeight({n['$value']})" for p, n, _t in walk(tree["primitive"]["font"]["weight"])]
    durs = [f"    const val {camel(('duration',) + p)}Ms = {n['$value']['value']}" for p, n, _t in walk(tree["primitive"]["duration"])]
    return f'''// 생성 파일 — scripts/gen_tokens.py (원천: {_source_note(kit)}). 직접 고치지 않는다.
package {package}

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** 의미 색 토큰(라이트 · 다크) — 웹 tokens.css 의 --color-* 와 같은 이름 · 값. */
@Immutable
data class ColorTokens(
{props}
)

val LightColors = ColorTokens(
{inst("light")}
)

val DarkColors = ColorTokens(
{inst("dark")}
)

/** 간격 · 반경 · 크기 · 글꼴 크기 · 굵기 · 시간 토큰 — 4pt 격자. */
object Dimens {{
{chr(10).join(dims)}
{chr(10).join(fonts)}
{chr(10).join(weights)}
{chr(10).join(durs)}
}}
'''


def outputs(root: Path = ROOT, kit: str | None = None) -> dict[Path, str]:
    """선택된 킷(또는 kit)으로 만든 생성물 — {경로: 내용}."""
    kit = kit or selected_kit(root)
    tree = load_kit(kit, root)
    return {root / OUT_CSS.relative_to(ROOT): gen_css(tree, kit), out_kt(root): gen_kt(tree, kit, kt_package(root))}


def catalog_errors(root: Path = ROOT) -> list[str]:
    """목록의 모든 킷을 값 검사 — 고르지 않은 킷도(미달 킷이 '채택 가능'으로 남지 않게)."""
    errs = []
    for entry in catalog(root):
        try:
            tree = load_kit(entry["id"], root)
        except (KeyError, FileNotFoundError, json.JSONDecodeError) as e:   # 깨진 킷 파일은 그 킷의 실패로 보고한다
            errs.append(f"킷 {entry['id']}: 토큰을 읽지 못함 — {e}")
            continue
        errs += [f"킷 {entry['id']}: {e}" for e in kit_errors(tree)]
    return errs


def main(check: bool, root: Path = ROOT) -> int:
    kit = selected_kit(root)
    if kit not in {k["id"] for k in catalog(root)}:
        print(f"✗ nova.project.json design.kit = {kit} 가 킷 목록(design/tokens/kits/catalog.json)에 없다 — python nova.py kit list")
        return 1
    tree = load_kit(kit, root)
    errs = catalog_errors(root) + scan_usage(root)
    outs = outputs(root, kit)
    if check:
        for path, text in outs.items():
            if not same(path, text):
                errs.append(f"생성물이 최신이 아님: {path.relative_to(root).as_posix()} — python nova.py tokens 실행")
    else:
        for path, text in outs.items():
            if not same(path, text):
                write(path, text)
                print("생성", path.relative_to(root).as_posix())
    pairs = len(tree["contrast"]["$value"]) * len(MODES)
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return 1
    print(f"✓ 디자인 토큰 최신 · WCAG 2.2 AA 대비 {pairs}쌍 통과 · 킷 {kit}(목록 {len(catalog(root))}개 모두 검사 통과)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
