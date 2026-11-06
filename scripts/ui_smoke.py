#!/usr/bin/env python3
"""웹 샘플 앱 브라우저 스모크 — 실제 게이트웨이 · 서비스 · 웹을 띄운 상태에서 사용자의 흐름을 따라간다.

  1) python nova.py stack up   — 게이트웨이(메모리 DB) + 데모 로그인 웹 빌드 · 기동(빈 포트를 골라 .stack/state.json 에 적는다)
     (데모 로그인 버튼은 NEXT_PUBLIC_DEV_LOGIN=1 로 빌드할 때만 들어간다 — 운영 빌드에는 데모 계정이 없다. 감사 ① 21)
  2) python nova.py ui-smoke [웹 주소] [--api <API 주소>] [--only <단계>[,<단계>…]]   — 주소를 주지 않으면 stack 주소
  3) python nova.py stack down — 자식 프로세스까지 내리고 포트가 비었는지 확인
흐름: 로그인 → 빈 목록 → 단축키 n → 입력 검증 → 생성 · 토스트 → 보관 · 실행 취소 → 상세(이벤트 소비) → 삭제 확인 → 권한 오류 문구
     → 디자인 갤러리 · ? 단축키 → 갤러리 토큰 부품(솔리드 · AI · 도메인 · 차트 · 딥 사이드바) → 대시보드(/design/dashboard)
     → 헤더 유틸(알림 · 조직 전환) → 스플릿(/design/split) → 설정(/design/settings) → 폼 모달 → 폼 입력 종류(선택 · 날짜 · 스위치 · 체크박스) → AI 확인 카드 → 갤러리 목록 내보내기 → 헤더 검색 Ctrl+K → 목록 내보내기(CSV) → 운영 화면 권한 없음 → 다크 모드 → 쿠키 세션(httpOnly · 새로고침 유지 · 새 탭 · 로그아웃 뒤 /me 401) → 로그인 확장(아이디 저장) → 로그인 이메일 형식.
     캡처는 docs/screenshots/app-*.png (계획서 §4 '지금 화면').
--only: 단계 이름(아래 STEPS)만 돈다. `--only design` 은 design 과 design-* 단계(갤러리 전부)를 고른다 — 갤러리는 로그인이
     필요 없다. 로그인이 필요한 단계(ops · dark)를 따로 고르면 그 앞에 데모 로그인만 한 번 한다. 인자가 없으면 전체 흐름.
     flow 는 빈 목록에서 시작하므로 DEV_MEMORY_DB 서버를 새로 띄운 뒤 한 번만 돈다(두 번째부터는 앞 실행의 항목이 남는다).
UX 휴리스틱(H1 · H3 · H5 · H6 · H7 · H9 · H10)과 접근성(라벨 연결 · 역할)을 사람 대신 확인하는 회귀 검사다.
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

SHOTS = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
DEFAULT_API = "http://localhost:8080/v1"
API = DEFAULT_API  # main 이 --api 로 덮어쓴다(cookie-session 이 /me 를 부를 때 쓴다)


def login(page: Page, base: str) -> None:
    page.goto(base + "/login")
    page.get_by_role("button", name="사용자").click()
    page.get_by_role("button", name="로그인", exact=True).click()
    page.wait_for_url("**/items")


def step_flow(page: Page, base: str) -> None:
    """홈 → 로그인 → 항목 생성 · 보관 · 실행 취소 · 상세 · 삭제 권한 오류(기존 전체 흐름)."""
    page.goto(base + "/")
    expect(page.get_by_role("heading", name="Nova 샘플 앱")).to_be_visible()
    page.screenshot(path=str(SHOTS / "app-home.png"))

    login(page, base)
    expect(page.get_by_role("heading", name="항목", exact=True)).to_be_visible()
    expect(page.get_by_text("아직 항목이 없습니다")).to_be_visible()
    page.screenshot(path=str(SHOTS / "app-items-empty.png"))
    print("✓ 로그인 → 빈 목록")

    # 새 항목 — 빈 이름이면 오류 칸으로
    page.keyboard.press("n")
    page.wait_for_url("**/items/new")
    page.get_by_role("button", name="만들기").click()
    expect(page.get_by_role("alert").filter(has_text="이름을(를) 입력하세요")).to_be_visible()
    page.screenshot(path=str(SHOTS / "app-items-new-error.png"))
    page.get_by_label("이름").fill("브라우저로 만든 항목")
    page.get_by_role("button", name="만들기").click()
    page.wait_for_url("**/items")
    expect(page.get_by_text("항목을 만들었습니다")).to_be_visible()
    expect(page.get_by_role("cell", name="브라우저로 만든 항목", exact=True)).to_be_visible()
    page.screenshot(path=str(SHOTS / "app-items-list.png"))
    print("✓ 단축키 n → 검증 오류 → 생성 → 목록 · 성공 토스트")

    # 진행 중 버튼 — 포커스 유지 · 중복 호출 막기 · 진행 중 알림(T04-9.05 · 감사 A-F1 · UX-H1)
    # 보관 응답을 붙잡아 두고 키보드로만 누른다. native disabled 면 포커스가 body 로 빠진다
    held = []
    page.route("**/sample/items/*/archive", lambda r: held.append(r))
    archive_btn = page.get_by_role("button", name="보관").first
    archive_btn.focus()
    page.keyboard.press("Enter")
    expect(archive_btn).to_have_attribute("aria-busy", "true")
    expect(archive_btn).to_have_attribute("aria-disabled", "true")
    expect(archive_btn).to_be_focused()
    page.keyboard.press("Enter")  # 진행 중 두 번째 누름 — 호출이 늘면 안 된다
    page.keyboard.press("Space")
    page.wait_for_timeout(300)
    assert len(held) == 1, f"진행 중 중복 호출 {len(held)}건"
    assert page.url.endswith("/items"), f"행 안 버튼의 Enter 가 행 이동을 일으켰다: {page.url}"
    page.unroute("**/sample/items/*/archive")
    held[0].fallback()
    expect(page.get_by_text("보관했습니다")).to_be_visible()
    page.get_by_role("button", name="실행 취소").click()
    expect(page.get_by_text("사용 중")).to_be_visible()
    print("✓ 진행 중 버튼 — 포커스 유지 · aria-busy · 중복 호출 없음")

    # 보관 → 실행 취소
    page.get_by_role("button", name="보관").first.click()
    expect(page.get_by_text("보관했습니다")).to_be_visible()
    expect(page.get_by_text("보관됨")).to_be_visible()
    page.screenshot(path=str(SHOTS / "app-items-undo-toast.png"))
    page.get_by_role("button", name="실행 취소").click()
    expect(page.get_by_text("사용 중")).to_be_visible()
    print("✓ 보관 → 실행 취소 토스트 → 되돌림")

    # 상세 — 이벤트 소비로 활동 기록
    page.get_by_role("cell", name="브라우저로 만든 항목", exact=True).click()
    page.wait_for_url("**/items/*")
    expect(page.get_by_text("만듦")).to_be_visible(timeout=10000)
    page.screenshot(path=str(SHOTS / "app-item-detail.png"))
    print("✓ 상세 — 아웃박스 → 소비 활동 기록 표시")

    # 삭제 — user 는 권한 없음(403) → 오류 토스트
    page.go_back()
    page.get_by_role("button", name="브라우저로 만든 항목 삭제").click()
    expect(page.get_by_role("alertdialog")).to_be_visible()
    page.screenshot(path=str(SHOTS / "app-confirm-dialog.png"))
    page.get_by_role("alertdialog").get_by_role("button", name="삭제").click()
    expect(page.get_by_text("이 기능을 쓸 권한이 없습니다")).to_be_visible()
    print("✓ 삭제 확인 대화상자 → user 권한 없음 오류 토스트(사람 말)")


def step_design(page: Page, base: str) -> None:
    """디자인 갤러리 전체 캡처 · ? 단축키 도움말."""
    page.goto(base + "/design")
    expect(page.get_by_role("heading", name="디자인 갤러리")).to_be_visible()
    page.screenshot(path=str(SHOTS / "app-design.png"), full_page=True)
    page.keyboard.press("?")
    expect(page.get_by_role("dialog", name="단축키")).to_be_visible()
    page.keyboard.press("Escape")
    # 계획 5.01 의 절이 모두 있는가 — 절이 빠지면 갤러리가 부품 목록과 어긋난다
    for title in GALLERY_SECTIONS:
        section(page, title)
    page.emulate_media(color_scheme="dark")
    page.reload()
    expect(page.get_by_role("heading", name="디자인 갤러리")).to_be_visible()
    page.screenshot(path=str(SHOTS / "app-design.dark.png"), full_page=True)
    page.emulate_media(color_scheme="light")
    print(f"✓ 디자인 갤러리 · ? 단축키 도움말 · 새 절 {len(GALLERY_SECTIONS)}개(라이트 · 다크)")


# 계획 REQ_05 T05-5.01 — 갤러리에 있어야 하는 새 절
GALLERY_SECTIONS = ("솔리드 상태 배지", "AI 표식", "도메인 식별 태그", "차트 색", "딥 사이드바 미리보기",
                    "헤더 유틸", "폼 모달", "목록 내보내기", "AI 확인 카드")


# 토큰 변수 → 브라우저가 계산한 실제 색. 부품이 그 토큰을 쓰는지는 '계산된 색이 같다'로 본다(클래스 이름이 아니라 결과)
_TOKEN_JS = """(name) => { const el = document.createElement('i'); el.style.color = `var(${name})`;
  document.body.appendChild(el); const c = getComputedStyle(el).color; el.remove(); return c; }"""


def token(page: Page, name: str) -> str:
    v = page.evaluate(_TOKEN_JS, name)
    assert v and v != "rgba(0, 0, 0, 0)", f"토큰 {name} 을 브라우저가 모른다"
    return v


def css(loc, prop: str) -> str:
    return loc.evaluate("(el, p) => getComputedStyle(el)[p]", prop)


def same(page: Page, loc, prop: str, name: str, what: str) -> None:
    got, want = css(loc, prop), token(page, name)
    assert got == want, f"{what}: {prop} {got} ≠ {name} {want}"


def section(page: Page, title: str):
    sec = page.locator("section.section").filter(has=page.get_by_role("heading", name=title, exact=True))
    expect(sec).to_have_count(1)
    return sec


def check_token_parts(page: Page, mode: str) -> None:
    """갤러리 토큰 부품 단언 — 지금 모드(라이트 · 다크)의 토큰 값과 부품의 계산된 색이 같은가."""
    # 솔리드 상태 배지(G2) — *Solid 배경 · onSolid(경고는 onWarningSolid) 글자
    sec = section(page, "솔리드 상태 배지")
    for tone in ("success", "warning", "danger", "info", "neutral"):
        b = sec.locator(f".badge.solid.{tone}").first
        expect(b).to_be_visible()
        same(page, b, "backgroundColor", f"--color-status-{tone}-solid", f"[{mode}] 솔리드 배지 {tone} 배경")
        ink = "--color-status-on-warning-solid" if tone == "warning" else "--color-status-on-solid"
        same(page, b, "color", ink, f"[{mode}] 솔리드 배지 {tone} 글자")
    assert css(sec.locator(".badge.danger:not(.solid)").first, "backgroundColor") == token(page, "--color-status-danger-bg"), \
        "솔리드 없는 배지가 바뀌었다(기본은 옅은 배지)"

    # AI 표식(G5) — 이름 'AI 생성' · 글자 AI · ai.* 토큰만
    sec = section(page, "AI 표식")
    mark = sec.get_by_role("img", name="AI 생성").first
    expect(mark).to_be_visible()
    expect(mark).to_contain_text("AI")
    same(page, mark, "color", "--color-ai-fg", f"[{mode}] AI 표식 글자")
    same(page, mark, "backgroundColor", "--color-ai-bg", f"[{mode}] AI 표식 바탕")
    same(page, mark, "borderTopColor", "--color-ai-border", f"[{mode}] AI 표식 테두리")

    # 도메인 식별 태그(G6) — 슬롯 1~6 · 글자는 domain.N.text, 점은 domain.N.mark
    sec = section(page, "도메인 식별 태그")
    slots = sec.locator(".domain-tag[data-slot]").evaluate_all("els => els.map(e => e.dataset.slot)")
    assert set(slots) == {str(n) for n in range(1, 7)}, f"도메인 태그 슬롯 {sorted(set(slots))} — 1~6 이 모두 있어야 한다"
    for n in range(1, 7):
        t = sec.locator(f'.domain-tag[data-slot="{n}"]').first
        same(page, t, "color", f"--color-domain-{n}-text", f"[{mode}] 도메인 태그 {n} 글자")
        dot = t.evaluate("el => getComputedStyle(el, '::before').backgroundColor")
        assert dot == token(page, f"--color-domain-{n}-mark"), f"[{mode}] 도메인 태그 {n} 점 {dot}"

    # 차트 색(G7) — 범례 6 · 막대 계열 · 추이 선이 chart.1~6
    sec = section(page, "차트 색")
    legend = sec.get_by_role("list", name="차트 범례")
    items = legend.get_by_role("listitem")
    expect(items).to_have_count(6)
    for n in range(1, 7):
        same(page, items.nth(n - 1).locator("i"), "backgroundColor", f"--color-chart-{n}", f"[{mode}] 범례 {n}")
    bars = sec.locator(".bars .b i")
    expect(bars).to_have_count(6)
    for n in range(1, 7):
        same(page, bars.nth(n - 1), "backgroundColor", f"--color-chart-{n}", f"[{mode}] 막대 계열 {n}")
    lines = sec.locator("svg.spark path[fill='none']")
    expect(lines.first).to_be_visible()
    same(page, lines.first, "stroke", "--color-chart-1", f"[{mode}] 추이 선 계열 1")

    # 딥 사이드바 미리보기(G4) — nav 바탕 · 활성(aria-current) 은 navActive · onNavActive
    sec = section(page, "딥 사이드바 미리보기")
    deep = sec.locator("aside.sidebar.deep")
    expect(deep).to_have_count(1)
    same(page, deep, "backgroundColor", "--color-bg-nav", f"[{mode}] 딥 사이드바 바탕")
    cur = deep.locator('a[aria-current="page"]')
    expect(cur).to_have_count(1)
    same(page, cur, "backgroundColor", "--color-bg-nav-active", f"[{mode}] 딥 사이드바 활성 바탕")
    same(page, cur, "color", "--color-text-on-nav-active", f"[{mode}] 딥 사이드바 활성 글자")
    same(page, deep.locator("a:not([aria-current])").first, "color", "--color-text-on-nav-muted", f"[{mode}] 딥 사이드바 글자")
    other = deep.locator("a:not([aria-current])").first
    other.focus()
    same(page, other, "outlineColor", "--color-border-focus-on-nav", f"[{mode}] 딥 사이드바 포커스 링")
    plain = sec.locator("aside.sidebar:not(.deep)")
    expect(plain).to_have_count(1)
    same(page, plain, "backgroundColor", "--color-bg-surface", f"[{mode}] 기본 사이드바 바탕(그대로)")


def step_design_tokens(page: Page, base: str) -> None:
    """갤러리 — 토큰 부품(T05-2.02): 솔리드 배지 · AI 표식 · 도메인 태그 · 차트 범례 6 · 딥 사이드바 미리보기, 라이트 · 다크."""
    page.emulate_media(color_scheme="light")
    page.goto(base + "/design")
    expect(page.get_by_role("heading", name="디자인 갤러리")).to_be_visible()
    check_token_parts(page, "라이트")
    first = section(page, "솔리드 상태 배지")
    first.scroll_into_view_if_needed()
    page.screenshot(path=str(SHOTS / "app-design-tokens.png"), full_page=True)
    page.emulate_media(color_scheme="dark")
    page.reload()
    expect(page.get_by_role("heading", name="디자인 갤러리")).to_be_visible()
    check_token_parts(page, "다크")
    page.screenshot(path=str(SHOTS / "app-design-tokens.dark.png"), full_page=True)
    page.emulate_media(color_scheme="light")
    print("✓ 갤러리 토큰 부품 — 솔리드 · AI 표식 · 도메인 6 · 차트 6 · 딥 사이드바(라이트 · 다크)")


def check_dashboard(page: Page, mode: str) -> None:
    """DashboardPage 단언(T05-3.01) — 지표 줄 · 블록 격자 · 한 블록 오류 격리 · 갱신 시각 · 솔리드 지표."""
    expect(page.get_by_role("heading", name="관제 대시보드", level=1)).to_be_visible()
    expect(page.get_by_text("마지막 갱신", exact=False)).to_be_visible()
    stats = page.get_by_role("region", name="주요 지표")
    expect(stats.locator(".stat")).to_have_count(4)
    solid = stats.locator(".stat-card.solid.danger")
    expect(solid).to_have_count(1)
    same(page, solid, "backgroundColor", "--color-status-danger-solid", f"[{mode}] 솔리드 지표 바탕")
    same(page, solid.locator(".v"), "color", "--color-status-on-solid", f"[{mode}] 솔리드 지표 글자")
    blocks = page.get_by_role("region", name="블록")
    for title in ("경보 추이 — 지난 24시간", "모듈별 처리량", "최근 경보", "AI 제안", "장비 가용률"):
        expect(blocks.get_by_role("region", name=title, exact=True)).to_be_visible()
    # 한 블록이 실패해도 그 블록만 오류 · 다시 시도, 다른 블록은 내용이 그대로(계획 §6 '열림')
    broken = blocks.get_by_role("region", name="장비 가용률", exact=True)
    expect(broken.get_by_role("alert")).to_contain_text("불러오지 못했습니다")
    expect(broken.get_by_role("button", name="다시 시도")).to_be_visible()
    expect(blocks.get_by_role("alert")).to_have_count(1)
    expect(blocks.get_by_role("region", name="경보 추이 — 지난 24시간", exact=True).get_by_role("img").first).to_be_visible()
    expect(blocks.get_by_role("region", name="최근 경보", exact=True).get_by_text("FW-SEOUL-02 외부 접속 폭주")).to_be_visible()
    # wide 블록은 두 칸을 차지한다(1280 화면)
    wide = blocks.get_by_role("region", name="경보 추이 — 지난 24시간", exact=True).bounding_box()
    half = blocks.get_by_role("region", name="모듈별 처리량", exact=True).bounding_box()
    assert wide and half and wide["width"] > half["width"] * 1.6, f"[{mode}] wide 블록 너비 {wide} · 보통 블록 {half}"


def step_design_dashboard(page: Page, base: str) -> None:
    """갤러리 — 대시보드(T05-3.01): /design/dashboard 의 DashboardPage 시연, 라이트 · 다크."""
    page.emulate_media(color_scheme="light")
    page.goto(base + "/design/dashboard")
    check_dashboard(page, "라이트")
    page.screenshot(path=str(SHOTS / "app-design-dashboard.png"), full_page=True)
    page.emulate_media(color_scheme="dark")
    page.reload()
    check_dashboard(page, "다크")
    page.screenshot(path=str(SHOTS / "app-design-dashboard.dark.png"), full_page=True)
    page.emulate_media(color_scheme="light")
    print("✓ 대시보드 — 지표 4 · 솔리드 지표 · 블록 5 · 한 블록 오류 격리 · 갱신 시각(라이트 · 다크)")


_STORAGE_JS = "() => JSON.stringify({l: {...localStorage}, s: {...sessionStorage}, c: document.cookie})"


def step_design_header(page: Page, base: str) -> None:
    """갤러리 — 헤더 유틸(T05-3.02): 알림 개수 · 테넌트 전환(실패 시 현재 유지 · 오류 토스트 · 저장소를 건드리지 않음)."""
    page.goto(base + "/design")
    sec = section(page, "헤더 유틸")
    notif = sec.get_by_role("link", name="알림 5건")
    expect(notif).to_be_visible()
    assert notif.get_attribute("href"), "알림 링크에 href 가 없다"
    switch = sec.get_by_role("button", name="조직 전환")
    expect(switch).to_contain_text("누리 관제센터")
    before = page.evaluate(_STORAGE_JS)

    # 실패 — 현재 조직 그대로 · 오류 토스트(반쯤 바뀐 상태 금지, 계획 §6 '닫힘')
    switch.click()
    menu = page.get_by_role("menu", name="조직 전환")
    expect(menu).to_be_visible()
    expect(menu.get_by_role("menuitemradio", name="누리 관제센터")).to_have_attribute("aria-checked", "true")
    menu.get_by_role("menuitemradio", name="전환 실패 예시").click()
    expect(page.get_by_role("alert").filter(has_text="조직을 바꾸지 못했습니다")).to_be_visible()
    expect(switch).to_contain_text("누리 관제센터")

    # Esc 로 닫고 연 버튼으로 포커스 복귀
    switch.click()
    expect(menu).to_be_visible()
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    expect(switch).to_be_focused()

    # 성공 — 앱이 넘긴 onSwitch 가 끝나면 새 조직 표시 · 토스트
    switch.click()
    page.get_by_role("menu", name="조직 전환").get_by_role("menuitemradio", name="부산 관제센터").click()
    expect(page.get_by_text("부산 관제센터(으)로 전환했습니다")).to_be_visible()
    expect(switch).to_contain_text("부산 관제센터")
    after = page.evaluate(_STORAGE_JS)
    assert before == after, f"테넌트 전환 부품이 저장소 · 쿠키를 바꿨다: {before} → {after}"
    page.screenshot(path=str(SHOTS / "app-design-header.png"))
    # 다크 — 머리띠 위 알림 · 조직 전환 글자가 inverse 토큰으로 보이는가
    page.emulate_media(color_scheme="dark")
    page.reload()
    sec = section(page, "헤더 유틸")
    switch = sec.get_by_role("button", name="조직 전환")
    expect(switch).to_be_visible()
    same(page, switch, "color", "--color-text-inverse", "[다크] 조직 전환 글자")
    expect(sec.get_by_role("link", name="알림 5건")).to_be_visible()
    sec.scroll_into_view_if_needed()
    page.screenshot(path=str(SHOTS / "app-design-header.dark.png"))
    page.emulate_media(color_scheme="light")
    print("✓ 헤더 유틸 — 알림 5건 · 조직 전환 실패 시 유지 · 성공 토스트 · 저장소 그대로(다크 캡처 포함)")


def step_design_export(page: Page, base: str) -> None:
    """갤러리 — 목록 내보내기 절(T05-5.01): 화면 값은 그대로, 파일 미리보기는 **** · ' 접두 · 동작 열 없음, 라이트 · 다크."""
    page.emulate_media(color_scheme="light")
    page.goto(base + "/design")
    sec = section(page, "목록 내보내기")
    expect(sec.get_by_role("cell", name="010-1234-5678 홍길동")).to_be_visible()
    pre = sec.get_by_label("내보낼 CSV 미리보기")
    text = pre.inner_text()
    assert text.splitlines()[0] == "이름,메모", f"미리보기 머리 {text.splitlines()[:1]} — 동작 열은 빠져야 한다"
    for want in ("'=SUM(A1:A3),****", '"쉼표, 포함",', "'-2 빼기,"):
        assert want in text, f"미리보기에 '{want}' 가 없다:\n{text}"
    for secret in ("010-1234-5678", "hong@example.com"):
        assert secret not in text, f"미리보기에 개인정보 원문 '{secret}' 이 남았다"
    expect(sec.get_by_role("link", name="목록에서 내려받아 보기")).to_have_attribute("href", "/items")
    sec.scroll_into_view_if_needed()
    page.screenshot(path=str(SHOTS / "app-design-export.png"))
    page.emulate_media(color_scheme="dark")
    page.reload()
    sec = section(page, "목록 내보내기")
    pre = sec.get_by_label("내보낼 CSV 미리보기")
    same(page, pre, "backgroundColor", "--color-bg-subtle", "[다크] CSV 미리보기 바탕")
    same(page, pre, "color", "--color-text-primary", "[다크] CSV 미리보기 글자")
    sec.scroll_into_view_if_needed()
    page.screenshot(path=str(SHOTS / "app-design-export.dark.png"))
    page.emulate_media(color_scheme="light")
    print("✓ 갤러리 목록 내보내기 — 개인정보 **** · 수식 ' · 동작 열 제외 미리보기(라이트 · 다크)")


def _boxes(a, b) -> tuple[dict, dict]:
    ba, bb = a.bounding_box(), b.bounding_box()
    assert ba and bb, f"영역 위치를 못 읽었다: {ba} · {bb}"
    return ba, bb


def step_design_split(page: Page, base: str) -> None:
    """스플릿(T05-3.07): 목록 왼쪽 · 상세 오른쪽 · ?sel 유지(새로고침) · ↑↓ 이동 · 900px 아래 위아래 쌓기, 라이트 · 다크."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(base + "/design/split")
    expect(page.get_by_role("heading", name="장비 — 스플릿 시연", level=1)).to_be_visible()
    lst = page.get_by_role("region", name="목록")
    detail = page.get_by_role("region", name="상세")
    expect(detail).to_contain_text("왼쪽 목록에서 항목을 고르세요")
    lst.get_by_role("cell", name="FW-SEOUL-02", exact=True).click()
    page.wait_for_url("**/design/split?sel=fw-02")
    expect(detail.get_by_role("heading", name="FW-SEOUL-02")).to_be_visible()
    cur = lst.locator('tbody tr[aria-current="true"]')
    expect(cur).to_have_count(1)
    expect(cur).to_contain_text("FW-SEOUL-02")
    # ↑ ↓ — 행 포커스에서 고른 행 · 주소 · 포커스가 함께 옮겨 간다(UX H7)
    page.keyboard.press("ArrowDown")
    page.wait_for_url("**/design/split?sel=ips-01")
    expect(detail.get_by_role("heading", name="IPS-CORE-01")).to_be_visible()
    expect(cur).to_be_focused()
    page.keyboard.press("ArrowUp")
    page.wait_for_url("**/design/split?sel=fw-02")
    # 새로고침해도 같은 행(UX H6)
    page.reload()
    expect(detail.get_by_role("heading", name="FW-SEOUL-02")).to_be_visible()
    expect(cur).to_contain_text("FW-SEOUL-02")
    lb, db = _boxes(lst, detail)
    assert db["x"] >= lb["x"] + lb["width"] - 1 and abs(db["y"] - lb["y"]) < 4, f"1280 에서 나란히가 아니다: 목록 {lb} · 상세 {db}"
    page.screenshot(path=str(SHOTS / "app-design-split.png"), full_page=True)
    # 900px 아래 — 목록 위 · 상세 아래
    page.set_viewport_size({"width": 800, "height": 800})
    lb, db = _boxes(lst, detail)
    assert db["y"] >= lb["y"] + lb["height"] - 1, f"800 에서 위아래로 쌓이지 않았다: 목록 {lb} · 상세 {db}"
    page.set_viewport_size({"width": 1280, "height": 800})
    # 주소의 sel 이 목록에 없으면 안내(빈 상세가 아니라)
    page.goto(base + "/design/split?sel=nope")
    expect(detail).to_contain_text("고른 항목을 찾을 수 없습니다")
    # 다크 — 고른 행 강조가 토큰 색
    page.emulate_media(color_scheme="dark")
    page.goto(base + "/design/split?sel=fw-02")
    expect(detail.get_by_role("heading", name="FW-SEOUL-02")).to_be_visible()
    same(page, cur.locator("td").first, "backgroundColor", "--color-status-info-bg", "[다크] 고른 행 바탕")
    page.screenshot(path=str(SHOTS / "app-design-split.dark.png"), full_page=True)
    page.emulate_media(color_scheme="light")
    print("✓ 스플릿 — 나란히 · ?sel 유지(새로고침) · ↑↓ 이동 · 900px 아래 쌓기 · 없는 sel 안내(라이트 · 다크)")


def step_design_settings(page: Page, base: str) -> None:
    """설정(T05-3.09): 왼쪽 구역 탭 · 오른쪽 슬롯 · ?tab 유지(새로고침) · 구역마다 저장 · 키보드 이동, 라이트 · 다크."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(base + "/design/settings")
    expect(page.get_by_role("heading", name="설정 — 시연", level=1)).to_be_visible()
    tabs = page.get_by_role("tablist", name="설정 — 시연 구역")
    expect(tabs.get_by_role("tab")).to_have_count(3)
    expect(tabs.get_by_role("tab", name="일반")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("tabpanel", name="일반")).to_be_visible()
    tabs.get_by_role("tab", name="알림").click()
    page.wait_for_url("**/design/settings?tab=notify")
    panel = page.get_by_role("tabpanel", name="알림")
    expect(panel).to_be_visible()
    page.reload()
    expect(panel).to_be_visible()
    expect(tabs.get_by_role("tab", name="알림")).to_have_attribute("aria-selected", "true")
    # 구역마다 저장 — 이 구역의 저장만 · 이 구역 이름으로 토스트
    expect(page.get_by_role("button", name="저장")).to_have_count(1)
    panel.get_by_role("switch", name="위험 경보 문자 받기").click()
    panel.get_by_role("button", name="저장").click()
    expect(page.get_by_text("알림 설정을 저장했습니다")).to_be_visible()
    lb, pb = _boxes(tabs, panel)
    assert pb["x"] > lb["x"] + lb["width"] - 1, f"1280 에서 구역 목록이 왼쪽이 아니다: {lb} · {pb}"
    page.screenshot(path=str(SHOTS / "app-design-settings.png"), full_page=True)
    # 키보드 — ↓ 다음 구역 · Home 첫 구역(포커스도 따라간다)
    tabs.get_by_role("tab", name="알림").focus()
    page.keyboard.press("ArrowDown")
    page.wait_for_url("**/design/settings?tab=security")
    expect(tabs.get_by_role("tab", name="보안")).to_be_focused()
    expect(page.get_by_role("tabpanel", name="보안")).to_be_visible()
    page.keyboard.press("Home")
    expect(tabs.get_by_role("tab", name="일반")).to_be_focused()
    # 모르는 tab 은 첫 구역
    page.goto(base + "/design/settings?tab=nope")
    expect(page.get_by_role("tabpanel", name="일반")).to_be_visible()
    # 900px 아래 — 구역 목록이 위
    page.set_viewport_size({"width": 800, "height": 800})
    lb, pb = _boxes(tabs, page.get_by_role("tabpanel", name="일반"))
    assert pb["y"] >= lb["y"] + lb["height"] - 1, f"800 에서 구역 목록이 위가 아니다: {lb} · {pb}"
    page.set_viewport_size({"width": 1280, "height": 800})
    page.emulate_media(color_scheme="dark")
    page.goto(base + "/design/settings?tab=notify")
    sel = page.get_by_role("tab", name="알림")
    same(page, sel, "backgroundColor", "--color-status-info-bg", "[다크] 고른 구역 바탕")
    page.screenshot(path=str(SHOTS / "app-design-settings.dark.png"), full_page=True)
    page.emulate_media(color_scheme="light")
    print("✓ 설정 — 구역 탭 · ?tab 유지(새로고침) · 구역마다 저장 · ↓ · Home · 모르는 tab 은 첫 구역 · 900px 아래 쌓기(라이트 · 다크)")


def step_design_form_dialog(page: Page, base: str) -> None:
    """폼 모달(T05-3.08, 검토 초점 4): 첫 칸 포커스 · Tab 가두기 · Esc · 연 버튼 복귀 · 입력이 있으면 닫기 확인 · 저장."""
    page.goto(base + "/design")
    sec = section(page, "폼 모달")
    opener = sec.get_by_role("button", name="연락처 추가")
    opener.click()
    dlg = page.get_by_role("dialog", name="연락처 추가")
    expect(dlg).to_be_visible()
    name = dlg.get_by_label("이름")
    expect(name).to_be_focused()
    for _ in range(5):                     # 칸 3 + 버튼 2 — 다섯 번이면 한 바퀴 돌아 첫 칸
        page.keyboard.press("Tab")
    expect(name).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(dlg.get_by_role("button", name="저장")).to_be_focused()
    # 입력이 없으면 Esc 로 바로 닫히고 연 버튼으로
    page.keyboard.press("Escape")
    expect(dlg).to_be_hidden()
    expect(page.get_by_role("alertdialog")).to_have_count(0)
    expect(opener).to_be_focused()
    # 입력이 있으면 Esc → 닫기 확인(기본 포커스 '계속 입력') → Esc 는 확인만 닫는다 · 입력 그대로
    opener.click()
    name.fill("홍길동")
    page.keyboard.press("Escape")
    ask = page.get_by_role("alertdialog", name="입력한 내용을 버리고 닫을까요?")
    expect(ask).to_be_visible()
    expect(ask.get_by_role("button", name="계속 입력")).to_be_focused()
    page.screenshot(path=str(SHOTS / "app-design-form-dialog.png"))
    page.keyboard.press("Escape")
    expect(ask).to_be_hidden()
    expect(dlg).to_be_visible()
    expect(name).to_have_value("홍길동")
    expect(name).to_be_focused()
    # 바깥 누름 → 확인 → 버리고 닫기 → 닫히고 연 버튼으로
    page.mouse.click(5, 5)
    expect(ask).to_be_visible()
    ask.get_by_role("button", name="버리고 닫기").click()
    expect(dlg).to_be_hidden()
    expect(opener).to_be_focused()
    # 다시 열면 빈 칸 · 빈 제출은 칸 오류 · 저장하면 토스트 · 닫힘 · 복귀
    opener.click()
    expect(name).to_have_value("")
    dlg.get_by_role("button", name="저장").click()
    expect(dlg.get_by_role("alert").filter(has_text="이름을(를) 입력하세요")).to_be_visible()
    expect(name).to_be_focused()
    name.fill("홍길동")
    dlg.get_by_label("이메일").fill("hong@example.com")
    dlg.get_by_role("button", name="저장").click()
    expect(page.get_by_text("연락처를 추가했습니다")).to_be_visible()
    expect(dlg).to_be_hidden()
    expect(opener).to_be_focused()
    page.emulate_media(color_scheme="dark")
    page.reload()
    section(page, "폼 모달").get_by_role("button", name="연락처 추가").click()
    expect(dlg).to_be_visible()
    same(page, dlg, "backgroundColor", "--color-bg-surface", "[다크] 폼 모달 바탕")
    page.screenshot(path=str(SHOTS / "app-design-form-dialog.dark.png"))
    page.keyboard.press("Escape")
    page.emulate_media(color_scheme="light")
    print("✓ 폼 모달 — 첫 칸 · Tab 가두기 · Esc · 연 버튼 복귀 · 입력 중 닫기 확인(Esc · 바깥) · 칸 오류 · 저장 토스트(라이트 · 다크)")


def step_design_form_kinds(page: Page, base: str) -> None:
    """폼 입력 종류(T07-3.01): select · date · switch · checkbox — 라벨 연결 · 키보드 · 칸 오류(aria) · 범위 밖 날짜 · 값 타입."""
    page.goto(base + "/design")
    sec = section(page, "폼 입력 종류")
    opener = sec.get_by_role("button", name="점검 일정 추가")
    opener.click()
    dlg = page.get_by_role("dialog", name="점검 일정 추가")
    expect(dlg).to_be_visible()
    kind = dlg.get_by_role("combobox", name="점검 종류")
    date = dlg.get_by_label("점검일")
    notify = dlg.get_by_role("switch", name="끝나면 알림 받기")
    agree = dlg.get_by_role("checkbox", name="점검 중 서비스가 멈출 수 있음을 확인했습니다")
    expect(kind).to_be_focused()            # 첫 칸이 선택 칸이어도 열면 첫 칸
    expect(date).to_have_attribute("type", "date")
    expect(date).to_have_attribute("min", "2026-01-01")
    expect(notify).to_have_attribute("aria-checked", "false")
    # 빈 제출 → 필수 칸마다 오류 · 첫 오류 칸(선택)으로 · 오류 문구가 칸에 aria 로 이어진다
    dlg.get_by_role("button", name="저장").click()
    expect(dlg.get_by_role("alert").filter(has_text="점검 종류을(를) 고르세요")).to_be_visible()
    expect(dlg.get_by_role("alert").filter(has_text="점검일을(를) 고르세요")).to_be_visible()
    expect(dlg.get_by_role("alert").filter(has_text="이 항목을 선택해야 진행할 수 있습니다")).to_be_visible()
    expect(kind).to_be_focused()
    expect(agree).to_have_attribute("aria-invalid", "true")
    err_id = agree.get_attribute("aria-describedby")
    assert err_id and page.locator(f"#{err_id}").inner_text() == "이 항목을 선택해야 진행할 수 있습니다", f"체크박스 오류가 aria-describedby 로 이어지지 않음: {err_id}"
    # 필수 선택 칸은 '고르지 않음'으로 되돌아갈 수 없다(UX H5)
    expect(kind.locator("option[value='']")).to_be_disabled()
    kind.select_option("urgent")
    expect(dlg.get_by_role("alert").filter(has_text="점검 종류")).to_have_count(0)
    # 범위 밖 날짜는 칸 오류(키보드 입력으로 min · max 를 넘겨도 막는다)
    date.fill("2025-12-31")
    expect(dlg.get_by_role("alert").filter(has_text="2026-01-01 ~ 2026-12-31 사이 날짜를 고르세요")).to_be_visible()
    date.fill("2026-11-20")
    expect(dlg.get_by_role("alert").filter(has_text="사이 날짜")).to_have_count(0)
    # 스위치 · 체크박스는 키보드(Space)로 · 라벨 누름으로도 바뀐다
    notify.focus()
    page.keyboard.press("Space")
    expect(notify).to_have_attribute("aria-checked", "true")
    dlg.locator("label", has_text="끝나면 알림 받기").click()
    notify.focus()
    expect(notify).to_have_attribute("aria-checked", "false")
    page.keyboard.press("Tab")
    expect(agree).to_be_focused()           # 스위치 다음 Tab 은 체크박스
    page.keyboard.press("Space")
    expect(agree).to_be_checked()
    expect(dlg.get_by_role("alert")).to_have_count(0)
    notify.click()
    page.screenshot(path=str(SHOTS / "app-design-form-kinds.png"))
    # 입력이 있으면 닫기 전에 묻는다(스위치 · 체크박스만 바꿔도 '입력함')
    dlg.get_by_role("button", name="저장").click()
    expect(page.get_by_text("점검 일정을 추가했습니다")).to_be_visible()
    expect(dlg).to_be_hidden()
    expect(opener).to_be_focused()
    expect(sec.get_by_label("저장한 값")).to_have_text('{"kind":"urgent","date":"2026-11-20","notify":true,"agree":true}')
    # 스위치만 켜고 닫아도 버릴지 묻는다
    opener.click()
    expect(notify).to_have_attribute("aria-checked", "false")   # 다시 열면 처음 값
    notify.click()
    page.keyboard.press("Escape")
    ask = page.get_by_role("alertdialog", name="입력한 내용을 버리고 닫을까요?")
    expect(ask).to_be_visible()
    ask.get_by_role("button", name="버리고 닫기").click()
    expect(dlg).to_be_hidden()
    # 다크 — 칸 바탕 · 스위치 켜짐 색이 토큰과 같은가
    page.emulate_media(color_scheme="dark")
    page.reload()
    section(page, "폼 입력 종류").get_by_role("button", name="점검 일정 추가").click()
    expect(dlg).to_be_visible()
    same(page, kind, "backgroundColor", "--color-bg-surface", "[다크] 선택 칸 바탕")
    same(page, date, "backgroundColor", "--color-bg-surface", "[다크] 날짜 칸 바탕")
    notify.click()
    same(page, notify, "backgroundColor", "--color-status-success-fg", "[다크] 스위치 켜짐")
    page.screenshot(path=str(SHOTS / "app-design-form-kinds.dark.png"))
    page.keyboard.press("Escape")
    page.get_by_role("alertdialog").get_by_role("button", name="버리고 닫기").click()
    page.emulate_media(color_scheme="light")
    print("✓ 폼 입력 종류 — 선택 · 날짜(범위) · 스위치 · 체크박스: 라벨 · 키보드 · 칸 오류 aria · 첫 오류 칸 · 값 타입 · 닫기 확인(라이트 · 다크)")


def step_design_ai_card(page: Page, base: str) -> None:
    """AI 확인 카드(T05-3.10, 검토 초점 3): 렌더만으로 실행 없음 · 기본 포커스 취소 · Enter · 새로고침에 실행 없음 ·
    대상 · 범위 · 파라미터 · 되돌림 · 되돌릴 수 없으면 위험 버튼 · 승인 중 잠금 · 승인 토스트."""
    page.goto(base + "/design")
    sec = section(page, "AI 확인 카드")
    card = sec.get_by_role("region", name="방화벽 3대 외부 접속 차단")
    expect(card).to_be_visible()
    expect(sec.get_by_text("승인 실행 0회")).to_be_visible()   # 렌더만으로 onApprove 가 불리지 않았다
    expect(card.get_by_role("img", name="AI 제안")).to_be_visible()
    for label in ("대상", "범위", "출발지", "동작", "되돌림"):
        expect(card.locator("dt", has_text=label)).to_have_count(1)
    cancel = card.get_by_role("button", name="취소")
    expect(cancel).to_be_focused()
    # Enter 를 그냥 쳐도 실행되지 않는다(취소가 눌린다)
    page.keyboard.press("Enter")
    expect(card).to_be_hidden()
    expect(sec.get_by_text("승인 실행 0회")).to_be_visible()
    expect(page.get_by_text("승인했습니다", exact=False)).to_have_count(0)
    # 새로고침 — 다시 제안 상태로 그려질 뿐 실행 없음
    page.reload()
    sec = section(page, "AI 확인 카드")
    card = sec.get_by_role("region", name="방화벽 3대 외부 접속 차단")
    expect(card).to_be_visible()
    expect(card.get_by_role("button", name="취소")).to_be_focused()
    expect(sec.get_by_text("승인 실행 0회")).to_be_visible()
    # 되돌릴 수 없는 실행 — "되돌릴 수 없습니다" · 위험 버튼 · 포커스는 여전히 취소
    sec.get_by_role("button", name="되돌림 없음").click()
    expect(card.get_by_text("되돌릴 수 없습니다")).to_be_visible()
    approve = card.get_by_role("button", name="승인하고 실행")
    assert "danger" in (approve.get_attribute("class") or ""), "되돌릴 수 없는데 위험 버튼이 아니다"
    expect(card.get_by_role("button", name="취소")).to_be_focused()
    page.screenshot(path=str(SHOTS / "app-design-ai-card.png"))
    # 승인 — 진행 중 둘 다 잠김 → 토스트 · 1회
    approve.click()
    expect(card.get_by_role("button", name="취소")).to_be_disabled()
    expect(page.get_by_text("승인했습니다 — 실행을 요청했습니다")).to_be_visible()
    expect(sec.get_by_text("승인 실행 1회")).to_be_visible()
    page.emulate_media(color_scheme="dark")
    page.reload()
    card = section(page, "AI 확인 카드").get_by_role("region", name="방화벽 3대 외부 접속 차단")
    same(page, card, "borderTopColor", "--color-ai-border", "[다크] AI 확인 카드 테두리")
    card.scroll_into_view_if_needed()
    page.screenshot(path=str(SHOTS / "app-design-ai-card.dark.png"))
    page.emulate_media(color_scheme="light")
    print("✓ AI 확인 카드 — 렌더만으로 실행 없음 · 취소 포커스 · Enter · 새로고침에 실행 없음 · 되돌림 없음 위험 버튼 · 승인 토스트(라이트 · 다크)")


def step_header_search(page: Page, base: str) -> None:
    """헤더 검색 · Ctrl+K(T05-3.03, 검토 초점 5): 입력 칸 안에서는 / · n 이 먹지 않고, 각 키가 자기 대상만 연다."""
    page.goto(base + "/items")
    expect(page.get_by_role("heading", name="항목", exact=True)).to_be_visible()
    hs = page.get_by_role("searchbox", name="전체 검색")
    list_q = page.get_by_role("textbox", name="검색", exact=True)
    expect(hs).to_be_visible()
    page.locator("body").click(position={"x": 5, "y": 300})
    page.keyboard.press("Control+k")
    expect(hs).to_be_focused()
    page.keyboard.type("n/")
    expect(hs).to_have_value("n/")
    page.wait_for_timeout(300)
    assert page.url.endswith("/items"), f"헤더 검색 칸 안의 n 이 새로 만들기로 갔다: {page.url}"
    expect(list_q).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(hs).not_to_be_focused()
    page.keyboard.press("/")
    expect(list_q).to_be_focused()
    page.keyboard.type("n")
    page.wait_for_timeout(300)
    assert page.url.endswith("/items"), f"목록 검색 칸 안의 n 이 새로 만들기로 갔다: {page.url}"
    page.keyboard.press("Control+k")
    expect(hs).to_be_focused()
    hs.fill("브라우저")
    page.keyboard.press("Enter")
    page.wait_for_url("**/items?q=*")
    expect(list_q).to_have_value("브라우저")
    page.locator("body").click(position={"x": 5, "y": 300})
    page.keyboard.press("?")
    expect(page.get_by_role("dialog", name="단축키")).to_contain_text("Ctrl+K")
    page.keyboard.press("Escape")
    print("✓ 헤더 검색 — Ctrl+K · 입력 칸 안 / · n 무시 · / 는 목록 검색 · Enter 로 onSearch · 단축키 도움말")


def step_login_ext(page: Page, base: str) -> None:
    """로그인 확장(T05-3.04): 아이디 저장(이메일만) → 재방문 채움 · 끄면 지움 · 찾기 링크 · 저장소 예외에도 로그인."""
    page.goto(base + "/login")
    page.evaluate("() => localStorage.clear()")
    page.reload()
    remember = page.get_by_role("checkbox", name="아이디 저장")
    email = page.get_by_label("이메일")
    expect(remember).to_be_visible()
    expect(remember).not_to_be_checked()
    expect(page.get_by_role("link", name="아이디 · 비밀번호 찾기")).to_have_attribute("href", "/help")
    page.get_by_role("button", name="책임자").click()
    remember.check()
    page.get_by_role("button", name="로그인", exact=True).click()
    page.wait_for_url("**/items")
    stored = page.evaluate("() => Object.values(localStorage).concat(Object.values(sessionStorage)).join('\\n')")
    assert "nova1234" not in stored, "비밀번호가 브라우저 저장소에 남았다"
    # 로그아웃 → 다시 찾아오면 저장한 이메일이 채워져 있다(UX H6)
    page.get_by_role("button", name="로그아웃").click()
    page.wait_for_url("**/login")
    page.goto(base + "/login")
    expect(email).to_have_value("manager@nova.dev")
    expect(remember).to_be_checked()
    page.screenshot(path=str(SHOTS / "app-login.png"))
    page.emulate_media(color_scheme="dark")
    page.reload()
    expect(email).to_have_value("manager@nova.dev")
    page.screenshot(path=str(SHOTS / "app-login.dark.png"))
    page.emulate_media(color_scheme="light")
    page.reload()
    # 끄고 로그인하면 지운다 → 다음 방문은 기본값
    page.get_by_role("button", name="사용자").click()
    remember.uncheck()
    page.get_by_role("button", name="로그인", exact=True).click()
    page.wait_for_url("**/items")
    page.get_by_role("button", name="로그아웃").click()
    page.wait_for_url("**/login")
    page.goto(base + "/login")
    expect(email).to_have_value("user@nova.dev")
    expect(remember).not_to_be_checked()

    # 사생활 모드처럼 아이디 저장소가 예외를 내도 로그인은 된다(계획 §6 '열림') — 저장 열쇠 '<접두사>_login_id' 만 막는다
    ctx = page.context.browser.new_context(viewport={"width": 1280, "height": 800}, locale="ko-KR")
    p2 = ctx.new_page()
    errs: list[str] = []
    p2.on("pageerror", lambda e: errs.append(str(e)))
    p2.add_init_script("""(() => { const blocked = (k) => String(k).endsWith('_login_id');
      for (const m of ['getItem', 'setItem', 'removeItem']) { const o = Storage.prototype[m];
        Storage.prototype[m] = function (k, ...r) { if (blocked(k)) throw new DOMException('막힘', 'SecurityError'); return o.call(this, k, ...r); }; } })()""")
    p2.goto(base + "/login")
    p2.get_by_role("checkbox", name="아이디 저장").check()
    p2.get_by_role("button", name="로그인", exact=True).click()
    p2.wait_for_url("**/items")
    ctx.close()
    assert not errs, f"저장소 예외가 화면 오류로 번졌다: {errs}"

    # 다음 단계를 위해 다시 '사용자'로
    login(page, base)
    print("✓ 로그인 확장 — 아이디 저장 → 재방문 채움 · 끄면 지움 · 비밀번호 저장 없음 · 찾기 링크 · 저장소 예외에도 로그인")


def step_login_email(page: Page, base: str) -> None:
    """이메일 형식(T04-4.06): 서버와 같은 EMAIL_PATTERN 으로 칸 오류 — 틀린 형식은 서버로 보내지 않는다 · 고치면 오류가 사라진다."""
    ctx = page.context.browser.new_context(viewport={"width": 1280, "height": 800}, locale="ko-KR")
    p2 = ctx.new_page()
    sent: list[str] = []
    p2.on("request", lambda r: sent.append(r.url) if r.url.endswith("/auth/login") else None)
    p2.goto(base + "/login")
    email = p2.get_by_label("이메일")
    email.fill("user@")
    p2.get_by_label("비밀번호").fill("nova1234")
    p2.get_by_role("button", name="로그인", exact=True).click()
    msg = "이메일 형식이 아닙니다. 예: name@example.com"
    expect(p2.get_by_role("alert").filter(has_text=msg)).to_be_visible()
    expect(email).to_have_attribute("aria-invalid", "true")
    assert not sent, f"형식이 틀린 이메일을 서버로 보냈다: {sent}"
    assert p2.url.rstrip("/").endswith("/login"), p2.url
    p2.screenshot(path=str(SHOTS / "app-login-email-error.png"))
    # 고치기 시작하면 칸 오류가 사라지고(UX H9), 맞는 형식이면 로그인된다
    email.fill("user@nova.dev")
    expect(p2.get_by_text(msg)).to_have_count(0)
    p2.get_by_role("button", name="로그인", exact=True).click()
    p2.wait_for_url("**/items")
    ctx.close()
    print("✓ 로그인 이메일 형식 — 칸 오류 · aria-invalid · 서버 미호출 · 고치면 사라짐 · 맞는 형식 로그인")


_EXPORT_ROWS = [
    {"name": "=SUM(A1:A3)", "memo": "010-1234-5678 홍길동"},
    {"name": "쉼표, 포함", "memo": None},
    {"name": '줄\n바꿈 "따옴표"', "memo": "hong@example.com"},
    {"name": "+1 더하기", "memo": "서울시 어딘가"},
    {"name": "@명령", "memo": None},
    {"name": "-2 빼기", "memo": None},
] + [{"name": f"행 {n}", "memo": None} for n in range(7, 104)]


def _export_route(state: dict):
    import json
    from urllib.parse import parse_qs, urlparse

    def handle(route):
        qs = parse_qs(urlparse(route.request.url).query)
        page_no, size = int(qs.get("page", ["1"])[0]), int(qs.get("size", ["20"])[0])
        if size == 100:
            state["pages"].append(page_no)
            if state.get("deny") and page_no == 2:
                route.fulfill(status=403, content_type="application/json",
                              body=json.dumps({"error": {"code": "forbidden", "message": "이 기능을 쓸 권한이 없습니다"}}))
                return
        rows = [{"id": f"r{i}", "status": "active", "created_at": "2026-11-01T00:00:00Z", "updated_at": "2026-11-01T00:00:00Z", **r}
                for i, r in enumerate(_EXPORT_ROWS)]
        chunk = rows[(page_no - 1) * size: page_no * size]
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"items": chunk, "total": len(rows), "page": page_no, "size": size}, ensure_ascii=False))
    return handle


def step_export(page: Page, base: str) -> None:
    """목록 내보내기(T05-3.05 테스트 · 3.06 구현): 다운로드 내용 — BOM · 개인정보 가림 **** · 수식 무력화 ' · 쉼표 · 줄바꿈 따옴표,
    size=100 쪽 순회, 중간 403 이면 파일 없음."""
    import csv
    import io

    state: dict = {"pages": []}
    page.route("**/sample/items?*", _export_route(state))
    try:
        page.goto(base + "/items")
        expect(page.get_by_role("cell", name="행 7", exact=True)).to_be_visible()
        btn = page.get_by_role("button", name="내보내기(CSV)")
        expect(btn).to_be_visible()
        expect(page.get_by_text("개인정보", exact=False).first).to_be_visible()
        with page.expect_download() as dl:
            btn.click()
        d = dl.value
        assert d.suggested_filename.endswith(".csv"), f"파일 이름 {d.suggested_filename}"
        raw = Path(d.path()).read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf"), "BOM 이 없다 — 엑셀에서 한글이 깨진다"
        text = raw[3:].decode("utf-8")
        assert state["pages"] == [1, 2], f"size=100 쪽 순회가 아니다: {state['pages']}"
        rows = list(csv.reader(io.StringIO(text, newline="")))
        head, body = rows[0], rows[1:]
        assert len(body) == len(_EXPORT_ROWS), f"행 수 {len(body)} ≠ {len(_EXPORT_ROWS)}"
        assert "이름" in head and "메모" in head and "동작" not in head, f"머리 {head}"
        name, memo = head.index("이름"), head.index("메모")
        got = [r[name] for r in body[:6]]
        assert got == ["'=SUM(A1:A3)", "쉼표, 포함", '줄\n바꿈 "따옴표"', "'+1 더하기", "'@명령", "'-2 빼기"], f"이름 열 {got}"
        assert '"쉼표, 포함"' in text and '"줄\n바꿈 ""따옴표"""' in text, "쉼표 · 줄바꿈 · 따옴표 값을 따옴표로 감싸지 않았다"
        assert [r[memo] for r in body[:4]] == ["****", "", "****", "****"], f"개인정보 열 {[r[memo] for r in body[:4]]}"
        for secret in ("010-1234-5678", "hong@example.com", "서울시"):
            assert secret not in text, f"개인정보 원문 '{secret}' 이 파일에 남았다"
        expect(page.get_by_text("내보냈습니다", exact=False)).to_be_visible()

        # 중간 쪽이 403 이면 파일을 만들지 않는다(일부만 담긴 파일 금지, 계획 §6)
        state.update(pages=[], deny=True)
        downloads: list = []
        page.on("download", lambda d: downloads.append(d))  # 내장 메서드는 Playwright 가 처리기로 감싸지 못한다
        btn.click()
        expect(page.get_by_role("alert").filter(has_text="권한")).to_be_visible()
        page.wait_for_timeout(800)
        assert not downloads, "403 인데 파일이 내려왔다"
    finally:
        page.unroute("**/sample/items?*")
    print("✓ 내보내기 — BOM · 개인정보 **** · 수식 ' · 쉼표 · 줄바꿈 따옴표 · size=100 순회 · 403 이면 파일 없음")


def step_ops(page: Page, base: str) -> None:
    page.goto(base + "/ops")
    expect(page.get_by_text("이 화면을 볼 권한이 없습니다")).to_be_visible()
    print("✓ 운영 화면 — user 는 권한 없음 상태")


def step_dark(page: Page, base: str) -> None:
    page.emulate_media(color_scheme="dark")
    page.goto(base + "/items")
    page.screenshot(path=str(SHOTS / "app-items-dark.png"))
    page.emulate_media(color_scheme="light")


def step_cookie_session(page: Page, base: str) -> None:
    """쿠키 세션(T04-8.09): 토큰은 httpOnly 쿠키에만 — 스크립트로 못 읽고, 새로고침에 유지, 로그아웃이 지운다."""
    page.goto(base + "/items")
    # 1) 스크립트가 읽는 쿠키에는 토큰이 없어야 한다(HttpOnly)
    assert "nova_token" not in page.evaluate("() => document.cookie"), "nova_token 이 document.cookie 로 읽힌다"
    # 2) localStorage 에 토큰을 두지 않는다(표시용 사용자 캐시만)
    keys = page.evaluate("() => Object.keys(localStorage)")
    assert not [k for k in keys if k.endswith("_token")], f"localStorage 에 토큰 키가 있다: {keys}"
    # 3) 그래도 로그인은 살아 있다 — 쿠키 속성 확인 + 새로고침 뒤 유지
    cookie = next((c for c in page.context.cookies() if c["name"] == "nova_token"), None)
    assert cookie is not None, "nova_token 쿠키가 없다"
    assert cookie["httpOnly"] is True, "nova_token 이 HttpOnly 가 아니다"
    assert cookie["sameSite"] == "Lax", f"nova_token SameSite 가 Lax 가 아니다: {cookie['sameSite']}"
    # 새로고침 뒤 /me 응답을 기다려 200 을 단언한다 — 표시용 캐시만으로 화면이 그려져 통과하는 것을 막는다
    with page.expect_response(lambda r: r.url.endswith("/me")) as me_reload:
        page.reload()
    assert me_reload.value.status == 200, f"새로고침 뒤 /me 가 {me_reload.value.status} (200 이어야 한다)"
    expect(page.get_by_role("heading", name="항목", exact=True)).to_be_visible()
    assert "/login" not in page.url, "새로고침 뒤 로그인 화면으로 갔다"
    # 새 탭 — 같은 문맥(쿠키 공유)의 새 페이지가 다시 로그인하지 않고 항목 화면을 연다
    tab = page.context.new_page()
    try:
        with tab.expect_response(lambda r: r.url.endswith("/me")) as me_tab:
            tab.goto(base + "/items")
        assert me_tab.value.status == 200, f"새 탭 /me 가 {me_tab.value.status} (200 이어야 한다)"
        expect(tab.get_by_role("heading", name="항목", exact=True)).to_be_visible()
        assert "/login" not in tab.url, "새 탭에서 로그인 화면으로 갔다"
    finally:
        tab.close()
    # 양성 대조 — 로그아웃 전에는 같은 방식의 /me 가 200 이어야 로그아웃 뒤 401 이 의미를 가진다
    before = page.request.get(API + "/me")
    assert before.status == 200, f"로그아웃 전 /me 가 {before.status} (200 이어야 한다)"
    # 4) 로그아웃 — 서버의 쿠키 지우기 응답을 기다린 뒤 같은 문맥에서 /me 가 401 이어야 한다
    with page.expect_response(lambda r: r.url.endswith("/auth/logout")):
        page.get_by_role("button", name="로그아웃").click()
    page.wait_for_url("**/login")
    me = page.request.get(API + "/me")
    assert me.status == 401, f"로그아웃 뒤 /me 가 {me.status} (401 이어야 한다)"
    assert not [c for c in page.context.cookies() if c["name"] == "nova_token"], "로그아웃 뒤에도 nova_token 쿠키가 남았다"
    print("✓ 쿠키 세션 — 스크립트로 못 읽음 · localStorage 토큰 없음 · 새로고침 유지 · 새 탭 · 로그아웃 뒤 /me 401")


# (이름, 함수, 로그인 필요) — 순서가 전체 흐름의 순서다
STEPS = [
    ("flow", step_flow, False),
    ("design", step_design, False),
    ("design-tokens", step_design_tokens, False),
    ("design-dashboard", step_design_dashboard, False),
    ("design-header", step_design_header, False),
    ("design-split", step_design_split, False),
    ("design-settings", step_design_settings, False),
    ("design-form-dialog", step_design_form_dialog, False),
    ("design-form-kinds", step_design_form_kinds, False),
    ("design-ai-card", step_design_ai_card, False),
    ("design-export", step_design_export, False),
    ("header-search", step_header_search, True),
    ("export", step_export, True),
    ("ops", step_ops, True),
    ("dark", step_dark, True),
    ("cookie-session", step_cookie_session, True),
    ("login-ext", step_login_ext, False),
    ("login-email", step_login_email, False),
]


def pick(only: str | None) -> list:
    if not only:
        return STEPS
    want = [w.strip() for w in only.split(",") if w.strip()]
    chosen = [s for s in STEPS if any(s[0] == w or s[0].startswith(w + "-") for w in want)]
    unknown = [w for w in want if not any(s[0] == w or s[0].startswith(w + "-") for s in STEPS)]
    if unknown or not chosen:
        sys.exit(f"모르는 단계: {', '.join(unknown) or only} — 고를 수 있는 단계: {', '.join(s[0] for s in STEPS)}")
    return chosen


def main() -> int:
    global API
    ap = argparse.ArgumentParser(description="웹 샘플 앱 브라우저 스모크")
    ap.add_argument("base", nargs="?", help="웹 주소(없으면 python nova.py stack 이 띄운 주소, 그것도 없으면 http://localhost:3100)")
    ap.add_argument("--only", help="이 단계만(쉼표로 여럿, 'design' 은 design-* 포함)")
    ap.add_argument("--api", help=f"게이트웨이 API 주소(없으면 stack 주소, 그것도 없으면 {DEFAULT_API}) — cookie-session 이 /me 를 부른다")
    a = ap.parse_args()
    import stack  # 같은 scripts/ 폴더 — 표준 라이브러리만 쓴다

    ep = stack.endpoints()
    API = (a.api or ep["api"]).rstrip("/")
    base = (a.base or ep["web"]).rstrip("/")
    print(f"■ 웹 {base} · API {API}" + ("" if a.base and a.api else f" (주소 출처: {ep['from']})"))
    steps = pick(a.only)
    SHOTS.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        # 새 탭 단계(page.context.new_page)가 필요해 브라우저 기본 문맥 대신 명시 문맥을 만든다
        ctx = b.new_context(viewport={"width": 1280, "height": 800}, locale="ko-KR")
        page = ctx.new_page()
        # 오류 수집은 문맥에 건다 — 새 탭을 포함한 모든 페이지에 적용된다
        ctx.on("weberror", lambda w: errors.append(f"페이지 오류: {w.error}"))
        ctx.on("console", lambda m: errors.append(f"콘솔 {m.type}: {m.text}") if m.type == "error" else None)
        logged_in = False
        for name, fn, needs_login in steps:
            if needs_login and not logged_in:
                login(page, base)
                logged_in = True
            fn(page, base)
            logged_in = logged_in or name in ("flow", "login-ext")
            if name == "cookie-session":
                logged_in = False  # 이 단계가 로그아웃으로 끝난다 — 뒤의 로그인 필요 단계는 다시 로그인
        b.close()

    real = [e for e in errors if "403" not in e and "Failed to load resource" not in e]
    for e in real:
        print("✗", e)
    print(f"브라우저 시나리오 통과 — 단계 {len(steps)}개({', '.join(s[0] for s in steps)})" if not real else "콘솔 오류 있음")
    return 1 if real else 0


if __name__ == "__main__":
    sys.exit(main())
