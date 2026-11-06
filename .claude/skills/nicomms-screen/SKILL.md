---
name: nicomms-screen
description: nicomms 템플릿(운영 콘솔 형태)으로 화면 한 벌을 조립한다 — "nicomms 템플릿(스타일)로 화면 만들어줘", "관리 콘솔 · 운영 화면을 nicomms 형태로", "스플릿 뷰 · 설정형 슬롯 화면을 nicomms 처럼" 같은 요청 때 쓴다. 사이드 셸 + 골격 A 목록 · B 스플릿 · C 설정형 + 로그인 · 확인 창 · 칩 규칙을 Nova 의 AppShell · ListPage · DetailPage · FormPage · LoginPage · useConfirm · useAction · StatusBadge 로 옮겨 조립하고, 원본 고유 형(data-style · MDI 탭)은 대응표와 갭(토큰 · 부품 제안)으로 처리한다(딥 사이드바 · 헤더 유틸 · 스플릿 · 설정형 · 폼 모달 · AI 확인 카드는 이제 Nova 부품이 있다). nicomms 를 말하지 않는 일반 화면 조립은 nova-screen 스킬 몫이고, 부품 하나 신설이나 색 · 간격 변경은 디자인 시스템 README 로 간다.
canon: design-system
---

# nicomms-screen — 운영 콘솔 형태를 Nova 부품으로 조립한다

nicomms 는 psg05(project-start-guide-05)에서 실 운영 제품(NiComms)의 관리 콘솔 인상을 **형만 읽어** 재조립한 템플릿이다. 이 스킬은 그 **조립 순서와 UX 판단**만 Nova 로 옮긴다. 원본의 값 · 토큰 체계 · 축(data-tenant · data-style)은 들이지 않는다.

🔴 **이 스킬은 값을 갖지 않는다.** 색 · 간격 · 반경 · 대비 기준은 아래 정본에만 있다. 정본과 이 스킬이 다르면 정본이 옳다(`scripts/claude_check.py` S2 가 이 본문에 값이 새는 것을 막는다).
- 화면 규약 `docs/conventions/ui.md` (§1 3층 · §2 규칙 · §3 부품 · §5 템플릿)
- UX `docs/conventions/ux-heuristics.md` (H1~H10 · 심각도 0~4)
- 토큰 `design/tokens/brand.tokens.json` → `python nova.py tokens` · 디자인 시스템 [README](../../../docs/design-system/README.md)
- 계획 `docs/plans/README.md` §4 (목업 · 4.1 UX 점검)
- AI 기능 `docs/std/STD-AX-001.md` (등급 L0~L3 · `require_human`)

일반 화면 절차(조회 → 골격 → 조립 → 목업 → 기록 → 확인)는 [nova-screen](../nova-screen/SKILL.md) 이 정본이다. 이 스킬은 **nicomms 형태에서 달라지는 자리만** 덧붙인다 — 같은 내용을 두 벌로 적지 않는다.

## 0. 조회 먼저 — 만들 것을 줄인다
원본에서 판단 포인트 넷(MDI 탭바 · 모달 크기 · 로그인 패턴 · 계층 코드 화면)이 **조회 한 번에 무효**가 됐다 — 넷 다 이미 있었다. 그러니 먼저 찾는다.
1. 화면 대장 `docs/registry/screens.md` — 같은 일을 하는 화면이 이미 있나. 있으면 그 조립을 그대로 쓴다
2. 권한 대장 `docs/registry/permissions.md` — 이 화면의 행위 `<모듈>.<행위>` 가 있나. 없으면 `services/gateway/gateway/rbac.json` 에 먼저
3. 새 이름(화면 · 라우트 · 권한 · 용어)이 필요하면 `python nova.py naming lookup <개념>` — 이미 있거나 별칭이면 만들지 않는다
4. 부품 · 템플릿 목록 `docs/conventions/ui.md` §3 · §5, 내보내는 이름 `web/packages/ui/src/index.ts`
5. 원본 요소가 Nova 에 있는지는 [references/style-map.md](references/style-map.md) — **대응**이면 그 부품을, **갭**이면 §7 출구로
6. 결과는 계획서 §0 영향분석 · §8 재사용 칸에(`/plan-new`). 화면이 여럿이면 화면 목록 · 골격 배정은 `screen-architect` 에이전트에 맡긴다

## 1. 축 — Nova 에는 하나뿐이다
원본은 루트 속성 셋(`data-theme` 명암 · `data-tenant` 브랜드 · `data-style` 형)으로 화면을 갈아 끼웠다. Nova 는 다르다.

| 원본 축 | Nova 에서 |
|---|---|
| 명암(`data-theme`) | 같다 — 라이트 · 다크 둘 다에서 동작해야 한다. 값은 토큰의 `nova.modes` 가 바꾸고 화면은 모른다 |
| 브랜드(`data-tenant`) | 런타임 축이 아니라 **프로젝트 단위** — 디자인 시스템 README §2(원시 `brand` · `accent` 팔레트만 바꾼다) |
| 형(`data-style` neo · glendale) | **없다 — 갭.** 화면에서 흉내 내지 않는다. 필요하면 [style-map.md](references/style-map.md) 「갭」 절의 토큰 제안으로 |

- 축으로 분기하는 조건부 마크업 · 화면 안 스타일 덮어쓰기를 쓰지 않는다
- 원본 인상(딥 사이드바 · 다크 기본)을 내고 싶다는 요청은 **토큰 · AppShell 설정 제안**이지 화면 작업이 아니다 → `design-rule-architect` 에이전트가 변경안을 쓰고 사람이 정한다

## 2. 셸 — AppShell 하나로
원본 셸(ConsoleShell + 브랜드 사이드바 + 헤더 유틸 + MDI 탭바 + 안내 배너 + 상태 푸터)은 Nova 에서 이렇게 선다.

```
AppShell (config.layout = "side")    좌 사이드 내비 — 메뉴는 서버 메뉴 원천(menuChannel)
 ├ 상단바                              브랜드 · 테마 전환 · 로그아웃 (AppShell 이 그린다)
 ├ PageHeader (crumbs · description)  브레드크럼 + 페이지 목적 한 줄(원본 안내 배너 자리)
 ├ (본문 — §3 골격)
 └ config.footer                      서버 상태(StatusBadge) · 버전 · 가동시간(mono)
```
- 앱 차이는 **AppShell 설정으로만**(ui.md §2-10) — 콘솔용 셸을 새로 만들지 않는다
- 메뉴는 `services/gateway/gateway/menu.json` 에 — 화면 코드에 박지 않는다
- 헤더 유틸은 AppShell `config.header`(`HeaderSearch` · `NotificationLink` · `TenantSwitcher`), 딥 톤 사이드바는 `navTone: "deep"` 으로 간다. MDI 탭바만 Nova 에 없다 → 갭(§7). **없는 채로 먼저 낸다** — 탭바 없이도 브라우저 탭 · 브레드크럼이 같은 일을 한다

## 3. 골격 — 셋 중 하나를 고른다
원본 화면 8종이 이 셋으로 덮였다. **먼저 골격을 정하고**, 골격은 화면 안에 그리지 않는다(ui.md §2-1 템플릿 먼저).

| 골격 | 쓰는 곳 | Nova | 상태 |
|---|---|---|---|
| A 목록형 | 한 종류를 검색해 나열(테넌트 · 사용자 관리) | `ListPage` — 검색 · `filters` 슬롯 · `DataTable` · `Pagination` · 주 행동 `primary` | ✅ |
| B 스플릿 뷰 | 좌측 유형을 고르면 우측이 그 유형이 됨(메뉴 · 거래처 관리) | 템플릿 없음 — `AppShell` 안에 유형 선택 + `ListPage` 를 화면에서 짜지 않는다 | 🗺 템플릿 먼저 |
| C 설정형 | 개수 상한이 있는 항목 편집(사이드바 링크 관리) | 템플릿 없음 — 탭(`Segmented`) + 슬롯 카드(`Card`) 배열 | 🗺 템플릿 먼저 |
| 상세 · 입력 | 단건 보기 · 등록 · 수정 | `DetailPage` · `FormPage` | ✅ |

- B · C 가 필요하면 `web/packages/ui/src/templates/` 에 템플릿을 먼저 만들고 ui.md §5 에 행을 더한다(계획에 🆕 task). 부품 · 템플릿 신설 판단은 `design-asset-keeper` 에이전트
- 계층 코드 관리(대 · 중 · 소를 가로로 펼치는 밀러 칼럼) · 트리는 Nova 에 없다 → 갭(§7). 계층은 우선 **표 들여쓰기**로 간다
- 골격별 UX 판단(모드 전환 패널 · 들여쓰기 · 빈 슬롯)은 [references/patterns.md](references/patterns.md)

## 4. 조립 — 데이터 정의만
- 목록: `columns` · `rowActions` · 빈 상태 문구 · 주 행동. 상태 칩은 `StatusBadge` 에 **서버가 준 매핑**을 넘긴다(화면에 상태 → 색 표 금지)
- 서버를 부르는 버튼은 반드시 `useAction`(웹) / `rememberAction`(모바일)
- 되돌리기 어려운 행위는 `useConfirm`(원본 Alert/Confirm 모달 자리), 되돌릴 수 있는 행위는 확인 대신 실행 취소(H3)
- 원본 폼 모달은 짧은 입력이면 **`FormDialog`**(`size` sm · md · lg, FormPage 와 같은 필드 정의), 칸이 많거나 주소로 공유해야 하면 **`FormPage`** 로 간다. 딥 헤더는 없다(표면 바탕)
- ID · 사업자번호 · 금액 · 일시 · URL 은 mono(`code` 또는 토큰 `font.family.mono`) · `fmtAt` · `fmtNumber` · `fmtMoney`
- 칩 색 규칙(상태 vs 분류 뉴트럴) · AI ✦ 규칙은 [references/patterns.md](references/patterns.md)
- 버튼 · 빈 상태 · 오류 문구는 컴포넌트 기본값, 바꿀 때만 `ux-writer` 에이전트에 맡긴다(H9 · 용어집)

## 5. 로그인
`LoginPage` 를 쓴다(새로 만들지 않는다). 원본이 얹은 셋 — **아이디 저장 · 아이디/비밀번호 찾기 · 상대편 로그인으로 가는 전환 링크**(플랫폼 ↔ 테넌트처럼 주소가 다른 두 로그인) — 은 `LoginPage` `rememberId`(아이디만 저장) · `links`(찾기 · 전환)로 받는다. 두 로그인이 실제로 있는 프로젝트라면 전환 링크는 필수다. 분할 레이아웃만 갭이다 — 모양 때문에 로그인 화면을 따로 짜지 않는다.

## 6. 목업 → 검증 (nova-screen §3 · §5 와 같다)
1. 목업 `docs/plans/mockups/<REQ>/<앱>-<화면>.html` — 첫 줄 메타 주석에 `"app"` · `"active"`(셸이 사이드면 실제 AppShell 로 감싼다). 갭 요소를 목업에 그렸다면 `class="mock-new"` 로 표시해 **없는 것임을 보이게** 한다
2. `python nova.py mockups --themes light,dark` → PNG 를 **직접 열어** 라이트 · 다크 둘 다 본다
3. 계획서 §4 그림 + 4.1 UX 점검표(H1~H10 · 심각도). 평가자 둘 — 사람 + `accessibility-auditor` 에이전트(대비 · 포커스 · 누름 영역)
4. 구현 뒤 기록: 머리 주석 `/** @screen 이름 · @status … */` → `uv run python scripts/registry.py sync --by <이름> --note <사유>` → `uv run python scripts/ledgers.py`
5. 확인(`nova-ui-verify` 스킬): `python nova.py web-build` → `python nova.py ui-smoke` · 모바일이면 `python nova.py kmp-test` · 흐름 시나리오는 `e2e-tester` 에이전트 · 토큰 밖 색 · 하드코딩은 `design-token-guardian` 에이전트 → 마지막에 `python nova.py check`
- 스크린샷이 이상하면 **대상을 고치기 전에 관측을 의심한다** — 같은 조작을 기존 화면(항목 목록)으로 한 번 돌려 본다. 폭 · 넘침은 그림이 아니라 숫자로 판정한다

## 7. 출구 — 없는 것이 필요할 때
금지는 "만들지 마라"가 아니라 **"제자리에서 즉흥으로 만들지 말고 등재하고 쓰라"**다. 갈래별 행선지는 [references/exit.md](references/exit.md).

## 하지 않는 것
- 원본 `--neo-*` 같은 외부 토큰 체계 · 사설 CSS 변수 · data-tenant / data-style 속성 들이기 — **형은 받고 체계는 받지 않는다**
- 화면 안에 색 값 · 픽셀 · 상태 → 색 표 · 조건부 스타일 분기 쓰기
- 골격 B · C · 폼 모달 · 탭바를 화면 파일 안에 직접 짜기(템플릿 · 부품 먼저)
- 일반 확인 창(`useConfirm`)으로 AI 쓰기 승인을 대신하기(patterns.md 「AI ✦」)
- 생성물(`tokens.css` · 대장 · 원장) 손 편집
