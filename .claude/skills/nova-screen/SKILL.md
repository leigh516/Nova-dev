---
name: nova-screen
description: Nova 화면 한 벌을 조립한다 — "목록 화면 만들어줘", "상세 · 입력 · 로그인 화면 추가", "관리 화면 구성", "모바일 화면 추가"처럼 화면 단위 요청 때 쓴다. 웹은 @nova/ui 템플릿(AppShell · ListPage · DetailPage · FormPage · LoginPage), 모바일은 kr.nova.uikit 로 조립하고, 대장 조회 → 목업 · 계획 §4.1 UX 점검 → 화면 머리 주석 → registry sync · ledgers → web-build · ui-smoke · kmp 확인까지 끝낸다. 부품 하나 신설이나 색 · 간격 변경은 여기가 아니다(디자인 시스템 README).
canon: design-system
---

# nova-screen — 화면은 템플릿 호출 + 데이터 정의

이 스킬은 **값을 갖지 않는다.** 색 · 간격 · 부품 목록 · 템플릿이 받는 것의 정본은 아래 문서이고, 스킬은 순서와 판단만 준다. 정본과 이 스킬이 다르면 정본이 옳다.
- 화면 규약 `docs/conventions/ui.md` (§1 3층 · §2 규칙 · §3 부품 · §5 템플릿)
- UX `docs/conventions/ux-heuristics.md` (H1~H10 · 심각도)
- 토큰 `design/tokens/brand.tokens.json` → `python nova.py tokens`
- 계획 `docs/plans/README.md` §4 (목업 · 4.1 UX 점검)

## 0. 조회 먼저 — 새로 만들기 전에 있는 것을 쓴다
1. 대장 `docs/registry/screens.md` — 같은 일을 하는 화면이 이미 있나, 이 표를 쓰는 화면은?
2. `docs/registry/permissions.md` — 이 화면의 행위에 맞는 권한 `<모듈>.<행위>` 이 있나(없으면 `rbac.json` 에 먼저)
3. 부품 · 템플릿 목록 `docs/conventions/ui.md` §3 · §5, 내보내는 이름 `web/packages/ui/src/index.ts`
4. 계획서 §0 영향분석 · §8 재사용 칸에 결과를 적는다(`/plan-new`)

## 1. 골격 고르기(화면이 여럿이면 `screen-architect` 에이전트에 설계를 맡길 수 있다)
| 화면 | 웹 템플릿 | 모바일 |
|---|---|---|
| 목록 | `ListPage` | `ScreenHeader` + 목록 부품 |
| 상세 | `DetailPage` | `ScreenHeader` + `Card` |
| 입력 · 수정 | `FormPage` | `NovaTextField` + `NovaButton` |
| 로그인 | `LoginPage` | 앱 로그인 화면 |
- 맞는 템플릿이 없으면 **템플릿을 먼저** 만든다(ui.md §2) — 화면에 레이아웃을 직접 짜지 않는다
- 모드는 라이트 · 다크 둘 — 둘 다에서 동작해야 한다(토큰이 바꾼다, 화면은 모른다)
- 웹 ↔ 모바일 대응 · 모바일 판단은 [references/mobile.md](references/mobile.md)

## 2. 조립 — 데이터 정의만 쓴다
- 목록: `columns` · `rowActions` · 빈 상태 문구 · 주 행동. 상태 표시는 `StatusBadge` 에 서버가 준 매핑을 넘긴다(화면에서 상태 → 색 표를 만들지 않는다)
- 서버를 부르는 버튼은 **반드시** `useAction`(웹) / `rememberAction`(모바일) — 진행 표시 · 성공 토스트 · 실패 알림 · 실행 취소가 거기서 온다
- 되돌리기 어려운 행위는 `useConfirm` 확인 창, 되돌릴 수 있는 행위는 확인 대신 **실행 취소**(H3)
- 날짜 · 숫자 · 금액은 `fmtAt` · `fmtNumber` · `fmtMoney` — 직접 포맷하지 않는다
- 스타일은 의미 토큰 `var(--color-…)` 만. 새 값이 필요하면 토큰 원천을 고친다
- 판단 기준(모드 전환 패널 · 빈 슬롯 · 칩 색 · 고정폭 숫자)은 [references/patterns.md](references/patterns.md)

## 3. 목업 → 4.1 UX 점검 (계획 단계 — 구현 전)
1. `docs/plans/mockups/<REQ>/<앱>-<화면>.html` — 첫 줄 메타 주석(`mockup_shots.py` 머리말의 형식), 새로 생기는 부분은 `class="mock-new"`
2. `python nova.py mockups` → 같은 이름 PNG. **PNG 를 직접 열어 본다**(Read)
3. 계획서 §4 에 그림 · 4.1 UX 점검표(H1~H10, 심각도 0~4)

## 4. 구현 · 기록
1. 화면 파일 머리 주석 `/** @screen 이름 · @status 기획|설계|개발|완료 */`
2. `uv run python scripts/registry.py sync --by <이름> --note <사유>` → `uv run python scripts/ledgers.py`
3. 메뉴에 올리면 서버 메뉴 원천(`services/gateway/gateway/menu.json`)에 — 화면 코드에 메뉴를 박지 않는다

## 5. 확인 — `nova-ui-verify` 스킬
- 웹: `python nova.py web-build` → `python nova.py ui-smoke`(화면을 바꾸면 반드시)
- 모바일: `python nova.py kmp-test` · `kmp-build` · (게이트웨이 켜고) `kmp-snapshots`
- 마지막에 `python nova.py check`(test + lint)

## 6. 출구 — 없는 것이 필요할 때(판정 재료는 `design-asset-keeper` 에이전트 · 문구는 `ux-writer`)
| 필요한 것 | 가는 곳 |
|---|---|
| 새 부품 | ui.md §3 표에 🗺 행 + 계획에 🆕 task(먼저 만든 프로젝트는 Nova 로 역제안) |
| 새 색 · 간격 · 글꼴 | `design/tokens/brand.tokens.json` → `python nova.py tokens`(WCAG 자동 검사) |
| 새 템플릿 | `web/packages/ui/src/templates/` + ui.md §5 행 |
| 새 권한 · 역할 | `rbac.json` 먼저 → `ledgers.py` |

## 하지 않는 것
- 'nicomms 템플릿 · 스타일로'처럼 nicomms 를 말한 요청 — `nicomms-screen` 스킬 몫
- 화면 안에 색 값 · 픽셀 · 상태 색 표를 직접 쓰기
- 외부 디자인 스킬의 독자 팔레트 · 독자 토큰 이름 들이기(디자인 시스템 README)
- 생성물(`tokens.css` · 대장 · 원장) 손 편집
