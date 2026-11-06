"""디자인 토큰 WCAG 대비 검사(scripts/gen_tokens.py check_contrast) — 통과 사례만이 아니라 실패 사례도 잡는지.

check_contrast 가 늘 [] 을 돌려주게 망가져도 저장소 토큰 검사는 통과하므로, 대비가 낮은 색 쌍을 넣은 복사본으로 확인한다.
"""
import copy
import re

import gen_tokens as gt


def tree():
    return copy.deepcopy(gt.load())


def test_repo_tokens_pass_contrast():
    assert gt.check_contrast(tree()) == []


def test_ratio_formula():
    assert round(gt.ratio("#FFFFFF", "#000000"), 1) == 21.0
    assert round(gt.ratio("#777777", "#FFFFFF"), 2) == 4.48            # 회색 777 은 흰 배경에서 4.5 미달(널리 알려진 경계값)
    assert gt.ratio("#123456", "#123456") == 1.0


def test_low_contrast_text_fails_in_both_modes():
    t = tree()
    sem = t["semantic"]["color"]
    sem["text"]["primary"] = {"$value": "#EEEEEE"}                     # 밝은 배경 위 거의 흰 글자
    sem["bg"]["canvas"] = {"$value": "#FFFFFF"}
    t["contrast"]["$value"] = [["text.primary", "bg.canvas", "text"]]
    errs = gt.check_contrast(t)
    assert len(errs) == 2, errs                                       # light · dark 모드 각각
    assert all("text.primary on bg.canvas" in e and "< 4.5 (text)" in e for e in errs)


def test_mode_specific_failure_and_ui_threshold():
    t = tree()
    sem = t["semantic"]["color"]
    # light 는 통과(검정), dark 만 낮은 대비 — 모드별 값($extensions nova.modes)을 따로 검사하는지
    sem["text"]["primary"] = {"$value": "#000000", "$extensions": {gt.MODE_KEY: {"dark": "#FAFAFA"}}}
    sem["bg"]["canvas"] = {"$value": "#FFFFFF"}
    t["contrast"]["$value"] = [["text.primary", "bg.canvas", "text"]]
    errs = gt.check_contrast(t)
    assert len(errs) == 1 and errs[0].startswith("[dark]"), errs
    # ui(3:1) 기준 — 3.5:1 은 ui 로는 통과, text 로는 실패
    sem["border"]["strong"] = {"$value": "#888888"}                    # 흰 배경 대비 약 3.5:1
    t["contrast"]["$value"] = [["border.strong", "bg.canvas", "ui"]]
    assert gt.check_contrast(t) == []
    t["contrast"]["$value"] = [["border.strong", "bg.canvas", "text"]]
    assert len(gt.check_contrast(t)) == 2


def test_reference_values_are_resolved():
    """참조({primitive.color.…})를 따라가 실제 색으로 비교한다 — 원시 색을 바꾸면 의미 토큰 검사가 실패한다."""
    t = tree()
    pair = t["contrast"]["$value"][0]
    fg = pair[0].split(".")
    node = t["semantic"]["color"]
    for part in fg:
        node = node[part]
    ref = node["$value"]
    assert ref.startswith("{primitive.")
    prim = t
    for part in ref.strip("{}").split("."):
        prim = prim[part]
    prim["$value"] = "#FFFFFF"                                         # 글자 원시 색을 흰색으로
    for m in gt.MODES:                                                 # 모드 덮어쓰기도 같은 원시 색을 보게
        node.setdefault("$extensions", {}).setdefault(gt.MODE_KEY, {})[m] = ref
    t["contrast"]["$value"] = [pair]
    assert gt.check_contrast(t), "원시 색을 흰색으로 바꿨는데 대비 오류가 없다"


# plan_REQ_05 §2 — 운영 콘솔용 새 의미 색 5묶음. 이름이 빠지거나 대비 쌍 없이 들어오면 실패한다
NEW_TOKENS = (
    [f"status.{k}Solid" for k in ("success", "warning", "danger", "info", "neutral")] + ["status.onSolid", "status.onWarningSolid"]
    + ["bg.nav", "bg.navActive", "text.onNav", "text.onNavMuted", "text.onNavActive", "border.focusOnNav"]
    + ["ai.fg", "ai.bg", "ai.border"]
    + [f"domain.{n}.{k}" for n in range(1, 7) for k in ("mark", "text")]
    + [f"chart.{n}" for n in range(1, 7)]
)


def _semantic_color_paths(t) -> set[str]:
    return {".".join(p) for p, _n, _t in gt.walk(t["semantic"]["color"])}


def test_new_pairs_registered():
    """ai · domain · chart · *Solid · nav 토큰은 모두 있고, 각자 contrast 쌍에 한 번 이상 나온다(새 색 쌍은 WCAG 검사 대상)."""
    t = tree()
    paths = _semantic_color_paths(t)
    missing = [p for p in NEW_TOKENS if p not in paths]
    assert not missing, f"새 의미 토큰 없음: {missing}"
    in_pairs = {x for fg, bg, _k in t["contrast"]["$value"] for x in (fg, bg)}
    watched = [p for p in paths if p.split(".")[0] in ("ai", "domain", "chart") or p.endswith("Solid")
               or p in ("bg.nav", "bg.navActive", "border.focusOnNav") or p.startswith("text.onNav")]
    unpaired = sorted(p for p in watched if p not in in_pairs)
    assert not unpaired, f"대비 쌍이 없는 새 토큰: {unpaired}"


def _with_domain(t, mark: dict) -> dict:
    """복사본에 분리 규칙과 도메인 슬롯 하나를 넣는다 — 저장소 원천과 무관하게 검사기만 본다."""
    t["separation"] = {"$value": [["status", "domain"]]}
    t["semantic"]["color"]["domain"] = {"1": {"mark": mark, "text": {"$value": "#123456"}}}
    return t


def test_separation_same_value_fails():
    """도메인 식별색이 상태색과 값이 같으면(참조가 달라도) 오류 — '빨강 = 위험'이 도메인 태그에서 흐려진다."""
    t = _with_domain(tree(), {"$value": "#b42f2f", "$extensions": {gt.MODE_KEY: {"dark": "#000001"}}})   # = red.700 = status.dangerFg(라이트)
    errs = gt.check_separation(t)
    assert errs and all(e.startswith("[light]") for e in errs), errs
    assert any("domain.1.mark" in e and "status.dangerFg" in e and "같은 값" in e for e in errs), errs


def test_separation_same_primitive_fails():
    """같은 원시 색을 참조해도 오류 — 원시 값을 바꿔도 함께 바뀌어 다시 섞인다."""
    t = _with_domain(tree(), {"$value": "#000001", "$extensions": {gt.MODE_KEY: {"dark": "{primitive.color.green.300}"}}})
    errs = gt.check_separation(t)
    assert errs and all(e.startswith("[dark]") for e in errs), errs
    assert any("domain.1.mark" in e and "status.successFg" in e and "원시" in e for e in errs), errs


def test_separation_distinct_passes():
    t = _with_domain(tree(), {"$value": "#000001"})
    assert gt.check_separation(t) == []


def test_repo_tokens_pass_separation():
    """저장소 원천에 status · domain 분리 규칙이 걸려 있고 도메인 6슬롯이 그 규칙을 통과한다."""
    t = tree()
    assert ["status", "domain"] in t["separation"]["$value"]
    assert sorted(k for k in t["semantic"]["color"]["domain"] if not k.startswith("$")) == [str(n) for n in range(1, 7)]
    assert gt.check_separation(t) == []


def _put(root, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_scan_mixing_status_domain_fails(tmp_path):
    """한 CSS 규칙 블록 · TSX 한 줄 · Kotlin 한 줄에 상태색과 도메인색을 함께 쓰면 오류 — 따로 쓰면 통과."""
    _put(tmp_path, "web/packages/ui/src/a.css",
         ".tag { color: var(--color-status-danger-fg);\n  border-color: var(--color-domain-1-mark); }\n"
         ".ok1 { color: var(--color-status-danger-fg); }\n.ok2 { color: var(--color-domain-2-text); }\n")
    _put(tmp_path, "web/apps/app/app/design/page.tsx",
         'const a = { color: "var(--color-status-success-fg)", background: "var(--color-domain-3-mark)" };\n'
         'const b = "var(--color-status-success-fg)";\nconst c = "var(--color-domain-3-mark)";\n')
    _put(tmp_path, "apps/kmp/uikit/src/commonMain/kotlin/X.kt", "val c = if (x) t.statusDangerFg else t.domain1Mark\nval d = t.statusInfoFg\n")
    errs = gt.scan_usage(tmp_path)
    assert len(errs) == 3, errs
    assert any(e.startswith("web/packages/ui/src/a.css:1") for e in errs), errs
    assert any(e.startswith("web/apps/app/app/design/page.tsx:1") for e in errs), errs
    assert any(e.startswith("apps/kmp/uikit/src/commonMain/kotlin/X.kt:1") for e in errs), errs
    assert all("상태색" in e and "도메인" in e for e in errs), errs


def test_scan_raw_color_fails(tmp_path):
    """부품 · 갤러리 · 모바일 부품 · nicomms 스킬에 색 값(hex · rgb() · Color(0x…))을 쓰면 오류 — 주석 · 생성물 · 범위 밖은 제외."""
    _put(tmp_path, "web/packages/ui/src/components/x.tsx",
         'const s = { color: "#FF0000" };\n// React #418 오류 주석은 색이 아니다\n * 주석 줄 #4F5BD5\nconst u = "http://a.b/c";\n')
    _put(tmp_path, "web/packages/ui/src/styles.css", ".x { background: rgb(1, 2, 3); }\n")
    _put(tmp_path, "web/packages/ui/src/tokens.css", ":root { --c: #FFFFFF; }\n")                    # 생성물 — 제외
    _put(tmp_path, "apps/kmp/uikit/src/commonMain/kotlin/Y.kt", "val c = Color(0xFF112233)\n")
    _put(tmp_path, "apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/DesignTokens.kt", "val c = Color(0xFF112233)\n")  # 생성물
    _put(tmp_path, "apps/kmp/uikit/build/gen/Z.kt", "val c = Color(0xFF112233)\n")                     # 빌드 산출 — 제외
    _put(tmp_path, ".claude/skills/nicomms-screen/references/style-map.md", "| 남색 | #1E2366 |\n# 제목\n")
    _put(tmp_path, "web/apps/app/app/items/page.tsx", 'const s = "#FF0000";\n')                         # 범위 밖
    errs = gt.scan_usage(tmp_path)
    got = sorted(e.split(":")[0] + ":" + e.split(":")[1] for e in errs)
    assert got == sorted([
        "web/packages/ui/src/components/x.tsx:1", "web/packages/ui/src/styles.css:1",
        "apps/kmp/uikit/src/commonMain/kotlin/Y.kt:1", ".claude/skills/nicomms-screen/references/style-map.md:1",
    ]), errs
    assert all("토큰 밖 색" in e for e in errs), errs


def test_scan_allowlist(tmp_path):
    """허용 목록은 비었다 — 대화상자 백드롭도 color.overlay.scrim 토큰으로 옮겼다(plan_REQ_04 T04-5.02). 옛 rgba 줄은 다시 오류."""
    assert gt.ALLOW_RAW == set()
    path = "web/packages/ui/src/styles.css"
    _put(tmp_path, path, ".dialog-backdrop { background: var(--color-overlay-scrim); }\n.old { background: rgba(13, 16, 22, .45); }\n")
    errs = gt.scan_usage(tmp_path)
    assert len(errs) == 1 and errs[0].startswith(path + ":2"), errs


def test_scrim_is_translucent_token():
    """반투명 막은 #RRGGBBAA 토큰 — CSS 는 그대로, Kotlin 은 0xAARRGGBB 로 바꿔 쓴다."""
    t = tree()
    v = gt.value_of(t, t["semantic"]["color"]["overlay"]["scrim"], "light")
    assert re.fullmatch(r"#[0-9A-Fa-f]{8}", v), v
    assert "--color-overlay-scrim: " + v in gt.gen_css(t)
    assert gt.kt_color("#0D101673") == "Color(0x730D1016)" and gt.kt_color("#0D1016") == "Color(0xFF0D1016)"


def test_repo_scan_usage_clean():
    assert gt.scan_usage(gt.ROOT) == []
