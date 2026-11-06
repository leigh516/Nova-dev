#!/usr/bin/env python3
"""체크리스트 폼 브라우저 스모크 — 임시 창고에서 서버를 띄우고 실제로 클릭한다(저장소 자료는 건드리지 않음).

  uv run python scripts/checklist_smoke.py [--shots <폴더>]
확인: 자동 채움 · 하위 질문 펼침 · 질문/섹션 건너뛰기 스위치 · 3단 범위 · 기술 선택 · 표 입력 · 표준 디자인 킷(고름 → 미리보기 → md 킷 결정 → import 설정 · 갭) · 용어 풀이 · 임시저장 → 이어가기 → 제출 · 불러오기 · 모바일 · intake 가져오기
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checklist as ck  # noqa: E402
import warehouse as wh  # noqa: E402
from novalib import ROOT  # noqa: E402

INTAKE = {"version": 1, "gaps": [], "files": [{
    "path": "prd/기획서.md", "category": "prd", "sha256": "-", "size": 1, "status": "분석됨", "analyzed": "2030-01-01",
    "summary": "매장 예약 기획", "findings": [
        {"id": "E-001", "area": "목적 · 배경", "kind": "사실", "text": "지금은 엑셀로 예약을 받는다", "quote": "엑셀로 관리 중"},
        {"id": "E-002", "area": "화면", "kind": "요구", "text": "직원은 태블릿으로 본다", "quote": "매장 태블릿"}]}]}
PREFILL = {"answers": {
    "what.kind": {"value": "replace", "evidence": ["E-001"]},
    "what.replace.current": {"value": ["paper"], "evidence": ["E-001"]},
    "screen.devices": {"value": ["tablet"], "evidence": ["E-002"]}}}


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def rgb(h: str) -> str:
    return f"rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})"


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="nova-ck-", dir=ROOT / ".pytest_tmp" if (ROOT / ".pytest_tmp").exists() else None))
    try:
        shutil.copytree(ROOT / "docs" / "warehouse", tmp / "warehouse")
        (tmp / "product").mkdir()
        wh.WH, wh.PRODUCT = tmp / "warehouse", tmp / "product"
        for p in (tmp / "warehouse" / "inbound" / "checklist").glob("checklist_*"):
            p.unlink()
        (tmp / "product" / "intake.json").write_text(json.dumps(INTAKE, ensure_ascii=False), encoding="utf-8")
        (tmp / "product" / "checklist_prefill.json").write_text(json.dumps(PREFILL, ensure_ascii=False), encoding="utf-8")
        (tmp / "warehouse" / "inbound" / "html-mockup" / "mockup_예약.html").write_text("<!doctype html><title>예약 목업</title><h1>예약 목업</h1>", encoding="utf-8")
        assert ck.check_answers(PREFILL["answers"], ck.tree(), "prefill", prefill=True) == []
        kit = next((k for k in ck.kits() if k["id"] != "nova"), None)   # 기본 말고 첫 킷 — 킷 이름을 스모크에 박지 않는다
        assert kit, f"킷 목록에 기본(nova) 말고 고를 킷이 없다 — {ck.KITS_CATALOG}"
        orig = (ck.PROJECT_JSON, ck.run_kit_use)
        port = free_port()
        srv = ThreadingHTTPServer(("127.0.0.1", port), ck.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        shots = Path(a.shots) if a.shots else None
        if shots:
            shots.mkdir(parents=True, exist_ok=True)
        steps = []
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("dialog", lambda d: d.accept())
            page.goto(f"http://127.0.0.1:{port}/")
            sec, nav = page.locator("main"), page.locator("nav")
            ckdir = tmp / "warehouse/inbound/checklist"
            # 1 자동 채움 — 배지 · 근거 · 하위 질문이 이미 펼쳐져 있다 · 보기 설명 · 쉬운 설명
            nav.get_by_role("button", name="무엇을 만드나").click()
            expect(sec.get_by_text("자료에서 채움 · 확인 필요").first).to_be_visible()
            expect(sec.get_by_text("지금은 엑셀로 예약을 받는다").first).to_be_visible()
            expect(sec.get_by_text("지금은 무엇으로 하고 있나요?")).to_be_visible()
            expect(sec.get_by_text("빈 땅에 새 건물 짓기", exact=False).first).to_be_hidden()   # 쉬운 설명은 접혀 있다
            sec.locator("details.help summary").first.click()
            expect(sec.get_by_text("빈 땅에 새 건물 짓기", exact=False).first).to_be_visible()
            if shots:
                page.screenshot(path=str(shots / "checklist-prefill.png"), full_page=True)
            sec.get_by_role("button", name="맞아요").first.click()
            expect(sec.get_by_text("확인함").first).to_be_visible()
            steps.append("자동 채움 · 근거 · 맞아요 · 쉬운 설명(접힘/펼침)")
            # 2 보기 클릭 → 하위 질문 펼침
            nav.get_by_role("button", name="누가 쓰나").click()
            expect(sec.get_by_text("고객 회원가입이 필요한가요?")).to_have_count(0)
            sec.locator("label.chip", has_text="외부 고객").click()
            expect(sec.get_by_text("고객 회원가입이 필요한가요?")).to_be_visible()
            both = sec.locator('input[name="users.customer.signup"][value="both"]')   # 고르면 이름 앞에 ✓ 가 붙으므로 값으로 찾는다
            both.focus()
            page.keyboard.press("Space")                                         # 키보드로 답한다 → 다시 그려도 포커스가 같은 보기에 남는다
            expect(both).to_be_checked()
            assert page.evaluate("[document.activeElement.name, document.activeElement.value]") == ["users.customer.signup", "both"],                 page.evaluate("document.activeElement.outerHTML.slice(0, 200)")
            sec.locator("label.chip", has_text="여러 조직이 각자 쓴다").click()
            expect(sec.get_by_text("조직끼리 데이터를 어떻게 보나요?")).to_be_visible()
            sec.locator("label.chip", has_text="본사는 전체를 본다").click()
            steps.append("보기 클릭 → 하위 질문 펼침(2단계) · 키보드로 답해도 포커스 유지")
            # 3 질문 스위치로 건너뛰기
            q_count = sec.get_by_role("group", name="사용자는 대략 몇 명인가요?")
            q_count.get_by_role("switch", name="건너뛰기").click()
            expect(q_count.get_by_text("건너뜀")).to_be_visible()
            expect(q_count.locator("label.chip", has_text="100명 이하")).to_be_hidden()
            if shots:
                page.screenshot(path=str(shots / "checklist-tree.png"), full_page=True)
            steps.append("질문 스위치 — 건너뛰기")
            # 4 섹션 스위치로 건너뛰기
            nav.get_by_role("button", name="AI 기능").click()
            sec.get_by_role("switch", name="이 섹션 답하기").click()
            expect(sec.get_by_text("이 섹션은 건너뛰었습니다")).to_be_visible()
            expect(nav.locator("li.off")).to_contain_text("AI 기능")
            steps.append("섹션 스위치 — 섹션 건너뛰기")
            # 5 글 입력
            nav.get_by_role("button", name="기본 정보").click()
            sec.get_by_role("textbox", name="프로젝트(제품) 이름은 무엇인가요?").fill("매장 예약")
            sec.get_by_role("textbox", name="프로젝트(제품) 이름은 무엇인가요?").blur()
            expect(page.locator("#title")).to_contain_text("매장 예약")
            steps.append("글 입력 · 제목 반영")
            # 6 단계(자세히) — 기술 선택 · 공통 기능 · 표 입력
            page.locator("#levels").get_by_role("button", name="자세히").click()
            nav.get_by_role("button", name="기술 선택").click()
            front = sec.get_by_role("group", name="화면(웹)은 무엇으로 만들까요?")
            expect(front.get_by_text("기술 결정")).to_be_visible()
            expect(front.locator("label.chip", has_text="Vue 3")).to_contain_text("Nova 공통 화면 부품을 쓸 수 없다")
            front.locator("label.chip", has_text="Next.js + React").click()
            expect(front.locator("label.chip", has_text="Next.js + React").locator(".badge.rec")).to_have_text("Nova 기본")
            sec.get_by_role("group", name="서버 구조는?").locator("label.chip", has_text="모듈러 모놀리스").click()
            nav.get_by_role("button", name="공통 기능").click()
            sec.get_by_role("group", name="인증").locator("label.chip", has_text="Nova 내장 기능 쓰기").click()
            nav.get_by_role("button", name="어떤 기능이 필요한가").click()
            sec.get_by_role("textbox", name="화면 / 기능 1").fill("오늘 예약 목록")
            sec.get_by_role("textbox", name="화면 / 기능 1").blur()
            sec.get_by_role("combobox", name="구분 1").select_option("must")
            expect(sec.get_by_role("textbox", name="화면 / 기능 2")).to_be_visible()   # 빈 줄이 하나 더 생긴다
            if shots:
                page.screenshot(path=str(shots / "checklist-tech.png"), full_page=True)
            steps.append("자세히 — 기술 선택(Nova 기본 · 주의) · 공통 기능 · 표 입력")
            # 6-1 디자인 — 색 견본 · 직접 지정 · 세밀 조정 · 대비 · 보기 미리보기 · 실시간 미리보기
            nav.get_by_role("button", name="디자인").click()
            expect(sec.locator(".dpv .frame")).to_be_visible()
            # 6-0 표준 디자인 킷(REQ-261106-04-2) — 보기는 catalog.json 에서 · 고르면 미리보기가 그 킷 값으로
            assert page.locator(".dpv").get_attribute("data-kit") == ""
            kit_chip = sec.locator("label.chip").filter(has=page.locator(f'input[name="{ck.KIT_QID}"][value="{kit["id"]}"]'))
            expect(kit_chip).to_contain_text(kit["label"])
            kit_chip.click()
            dpv = sec.locator(".dpv")
            expect(dpv).to_have_attribute("data-kit", kit["id"])
            expect(dpv).to_have_attribute("data-main", kit["preview"]["hex"])
            expect(dpv).to_contain_text("킷: " + kit["label"])
            expect(sec.locator(".dpv .frame span", has_text="예약 등록").first).to_have_css("background-color", rgb(kit["preview"]["hex"]))
            if shots:
                page.screenshot(path=str(shots / "checklist-kit.png"), full_page=False)
            steps.append(f"표준 디자인 킷 — catalog 의 {kit['id']} 고름 → 미리보기 색 {kit['preview']['hex']} · 킷 배지")
            sec.get_by_role("radio", name="블루 #2563EB").click()
            expect(sec.get_by_role("radio", name="블루 #2563EB")).to_have_attribute("aria-checked", "true")
            expect(sec.locator(".dpv .frame span", has_text="예약 등록").first).to_have_css("background-color", "rgb(37, 99, 235)")
            hexbox = sec.get_by_role("textbox", name="메인 컬러(브랜드 색)를 골라 주세요 — HEX 색 코드")
            hexbox.fill("#FFD400")
            hexbox.press("Enter")
            expect(sec.locator(".cpv").first.get_by_text("미달").first).to_be_visible()                       # 노랑은 흰 글자 대비 미달
            expect(sec.locator(".cpv").first.get_by_text("글자에는", exact=False)).to_be_visible()      # 글자용 진한 색 제안
            sec.locator("details.help summary", has_text="세밀하게 조정").first.click()
            fine = sec.locator("details.help", has=page.locator("summary", has_text="세밀하게 조정")).first
            light = sec.get_by_role("slider", name="메인 컬러(브랜드 색)를 골라 주세요 — 밝기")
            light.fill("35")
            expect(fine).to_have_attribute("open", "")                          # 답이 바뀌어 다시 그려도 세밀 조정 칸은 열린 채
            light.focus()
            page.keyboard.press("ArrowLeft")                                     # 키보드로 막대를 움직인다
            expect(fine).to_have_attribute("open", "")
            assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "메인 컬러(브랜드 색)를 골라 주세요 — 밝기"
            expect(light).to_have_value("34")
            def pick(name):   # '살짝 둥글게' 와 '둥글게' 를 구분 — 보기 이름을 앞에서부터 맞춘다
                sec.locator("label.chip").filter(has=page.get_by_role("radio", name=re.compile("^" + name))).click()
            pick("둥글게")
            pick("위쪽 가로 메뉴")
            pick("카드")
            expect(sec.locator(".dpv .card").first).to_be_visible()
            if shots:
                page.screenshot(path=str(shots / "checklist-design.png"), full_page=True)
            steps.append("디자인 — 색 견본 · HEX 직접 지정 · 세밀 조정(다시 그려도 열림 · 포커스 유지) · 대비 미달 · 글자용 색 제안 · 보기 미리보기 · 실시간 미리보기")
            # 7-1 디자인을 어디서 — AI 디자인 도구 · 외부 디자인 시스템
            pick("AI 디자인 도구로 시안을 제안받기")
            expect(sec.get_by_text("어떤 도움을 받을까요? (여러 개)")).to_be_visible()
            sec.locator("label.chip", has_text="화면 시안 · 다듬기(impeccable)").click()
            steps.append("디자인 가져오기 — AI 디자인 도구(스킬) 선택")
            # 7-2 목업 채택 — 저장 서버가 입고 목업을 바로 보여 주고, 열어 보기 · 채택 수준 · 메모
            nav.get_by_role("button", name="목업 · 기존 화면 채택").click()
            pick("있다")
            item = sec.locator(".mk .item", has_text="html-mockup/mockup_예약.html")
            expect(item).to_be_visible()
            href = item.get_by_role("link", name="열어 보기 ↗").get_attribute("href")
            r = page.request.get(f"http://127.0.0.1:{port}/{href}")
            assert r.ok and "예약 목업" in r.text(), r.status
            assert page.request.get(f"http://127.0.0.1:{port}/files/html-mockup/..%2F..%2F..%2Fproduct%2Fintake.json").status == 404   # 두 폴더 밖은 막는다
            item.locator("label.chip", has_text="그대로 채택").click()
            sec.locator(".mk .item", has_text="mockup_예약.html").get_by_role("textbox").fill("예약 화면 전부")
            sec.locator(".mk .item", has_text="mockup_예약.html").get_by_role("textbox").blur()
            pick("목업 스타일에 맞춰 새로 만든다")
            steps.append("목업 채택 — 입고 목업 목록 · 열어 보기 · 그대로 채택 · 메모 · 폴더 밖 차단")
            # 7-3 Nova 보기 — 부품 · 기술의 [보기 ↗] → 실제 예시 · 실제 화면
            nav.get_by_role("button", name="화면 부품").click()
            sec.locator("label.chip", has_text="목록 화면").get_by_role("button", name="목록 화면 — Nova 에서 실제 모습 보기").click()
            expect(sec.locator("#g-list")).to_be_visible()
            expect(sec.locator("#g-list img")).to_have_attribute("alt", "목록 화면(ListPage + 표) — 실제 화면")
            if shots:
                page.screenshot(path=str(shots / "checklist-nova.png"), full_page=True)
            page.get_by_role("button", name="질문으로 돌아가기").click()
            sec.locator("label.chip", has_text="칸반 보드").click()
            expect(sec.locator("label.chip", has_text="칸반 보드")).to_contain_text("Nova 에 아직 없다")
            steps.append("Nova 보기 — [보기 ↗] → 갤러리(실제 예시 · 실제 화면) · 없는 부품 요청")
            # 7 전문가 단계 · 용어 풀이
            page.locator("#levels").get_by_role("button", name="전문가").click()
            expect(nav.get_by_role("button", name="이름 · 용어")).to_be_visible()
            page.get_by_role("button", name="용어 풀이").click()
            sec.get_by_role("textbox", name="용어 찾기").fill("배포")
            expect(sec.locator("dl.terms dt", has_text="배포").first).to_be_visible()
            if shots:
                page.screenshot(path=str(shots / "checklist-terms.png"), full_page=True)
            page.get_by_role("button", name="질문으로 돌아가기").click()
            page.locator("#levels").get_by_role("button", name="기본").click()
            steps.append("전문가 단계 · 용어 풀이 찾기")
            # 8 임시저장 → (창을 닫고) 이어가기 → 제출
            page.get_by_role("button", name="임시저장").click()
            expect(page.locator("#toast")).to_contain_text("임시저장했습니다")
            files = sorted(p.name for p in ckdir.glob("checklist_*"))
            assert len(files) == 2, files
            doc = json.loads((ckdir / files[0]).read_text(encoding="utf-8"))
            assert doc["status"] == "draft" and doc["skipped_sections"] == ["ai"] and doc["answers"]["users.count"]["state"] == "unknown"
            assert doc["answers"]["tech.frontend"]["value"] == "next" and doc["answers"]["scope.items"]["value"] == [{"name": "오늘 예약 목록", "priority": "must"}]
            main = doc["answers"]["design.color.main"]["value"]
            assert main["preset"] == "" and main["hex"] != "#FFD400" and main["text_hex"], main   # 세밀 조정으로 밝기를 바꾼 직접 지정 색
            assert doc["answers"]["design.radius"]["value"] == "round" and doc["answers"]["design.layout"]["value"] == "top"
            assert doc["answers"]["mockup.list"]["value"] == {"html-mockup/mockup_예약.html": {"level": "all", "note": "예약 화면 전부"}}, doc["answers"].get("mockup.list")
            assert "kanban" in doc["answers"]["parts.need"]["value"] and doc["answers"]["design.source"]["value"] == "skill"
            assert doc["answers"][ck.KIT_QID]["value"] == kit["id"]
            page.close()
            p2 = ctx.new_page()   # 같은 브라우저 — 자동 저장으로 이어진다
            p2.on("dialog", lambda d: d.accept())
            p2.goto(f"http://127.0.0.1:{port}/")
            expect(p2.locator("#title")).to_contain_text("매장 예약")
            expect(p2.locator("#toast")).to_contain_text("이어서")
            p2.locator("nav").get_by_role("button", name="누가 쓰나").click()
            g = p2.locator("main").get_by_role("group", name="사용자는 대략 몇 명인가요?")
            g.get_by_role("switch", name="건너뛰기").click()
            g.locator("label.chip", has_text="100명 이하").click()
            p2.get_by_role("button", name="완료하고 제출").click()
            expect(p2.locator("#toast")).to_contain_text("제출했습니다")
            assert len(list(ckdir.glob("checklist_*.json"))) == 1   # 같은 파일에 이어서 저장
            doc = json.loads((ckdir / files[0]).read_text(encoding="utf-8"))
            assert doc["status"] == "complete" and doc["revision"] == 2 and doc["answers"]["users.count"]["value"] == "100"
            md = (ckdir / files[1]).read_text(encoding="utf-8")
            assert "status: complete" in md and "  - 고객 회원가입이 필요한가요? → **둘 다**" in md and "## 건너뛴 섹션" in md
            assert "`foundation.stack.frontend` — 화면(웹)은 무엇으로 만들까요? → Next.js + React" in md, md
            assert "## 디자인 결정" in md and "메인 컬러(브랜드 색)를 골라 주세요 → 직접 지정 #" in md and "대비" in md
            assert f"**킷 결정**: {kit['label']} (`{kit['id']}`)" in md and "체크리스트로 설정됨" in md, md
            steps.append("임시저장 → 다시 열어 이어가기 → 완료하고 제출(같은 파일 · 판 2)")
            # 9 다른 브라우저에서 불러오기
            p3 = b.new_page()
            p3.on("dialog", lambda d: d.accept())
            p3.goto(f"http://127.0.0.1:{port}/")
            p3.get_by_role("button", name="불러오기").click()
            expect(p3.locator("#title")).to_contain_text("매장 예약")
            steps.append("다른 브라우저에서 불러오기(서버 최신본)")
            # 10 모바일 폭
            p4 = b.new_page(viewport={"width": 390, "height": 844})
            p4.goto(f"http://127.0.0.1:{port}/")
            assert p4.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "모바일 가로 스크롤"
            if shots:
                p4.screenshot(path=str(shots / "checklist-mobile.png"))
            steps.append("모바일 폭 가로 스크롤 없음")
            b.close()
            assert not errors, errors
        # 11 intake 가져오기 — 건너뛴 섹션도 부족 항목으로 · 고른 킷을 설정(임시 메타 · 설정 동작은 대역 — 저장소 토큰은 건드리지 않음)
        meta = tmp / "nova.project.json"
        meta.write_text(json.dumps({"name": "스모크", "design": {"kit": "nova", "source": "default"}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        used = []

        def fake_use(kid):
            used.append(kid)
            m = json.loads(meta.read_text(encoding="utf-8"))
            m["design"] = {"kit": kid, "date": "2030-01-02", "by": "스모크", "source": "checklist"}
            meta.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return True, f"킷 {kid} 설정"
        ck.PROJECT_JSON, ck.run_kit_use = meta, fake_use
        rel, nf, ng = ck.import_to_intake()
        intake = wh.load("intake")
        assert rel and nf >= 8
        whys = {g["why"] for g in intake["gaps"]}
        assert any("섹션을 건너뜀" in w for w in whys), whys
        steps.append(f"intake 가져오기 — 발견 {nf} · 부족 {ng}(건너뛴 섹션 포함)")
        d = json.loads(meta.read_text(encoding="utf-8"))["design"]
        assert used == [kit["id"]] and d["kit"] == kit["id"] and d["origin"].endswith(f"#{ck.KIT_QID}"), d
        kit_gaps = [g for g in intake["gaps"] if f"#{ck.KIT_QID}:" in g["origin"]]
        assert len(kit_gaps) == len(kit.get("gaps", [])), kit_gaps
        steps.append(f"킷 설정 — design.kit={kit['id']} · 출처 {d['origin']} · 킷 부품 갭 {len(kit_gaps)}개 → 부족 항목")
        srv.shutdown()
        for i, s in enumerate(steps, 1):
            print(f"✓ {i}. {s}")
        print(f"✓ 체크리스트 스모크 {len(steps)}단계 통과")
        return 0
    finally:
        if "orig" in locals():
            ck.PROJECT_JSON, ck.run_kit_use = orig
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
