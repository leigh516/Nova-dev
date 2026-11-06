# nicomms → Nova 대응표

원본(psg05 저장소의 DESIGN_SYSTEM.md · design-tokens.css · 카탈로그 `nicomms` 섹션 — 이 저장소에는 없다, 읽기만 한다)의 **개념**을 Nova 의 **의미 토큰 이름 · 부품**에 잇는다. 값은 적지 않는다 — Nova 값의 정본은 `design/tokens/brand.tokens.json`, CSS 이름은 생성물 `tokens.css` 의 `var(--color-…)` · `var(--space-…)` 다(토큰 경로 `semantic.color.text.primary` ↔ CSS `--color-text-primary`).

판정: **대응** = 그대로 쓴다 · **근사** = 쓰되 원본과 뜻이 조금 다르다(차이를 적었다) · **갭** = Nova 에 없다 → 아래 「갭」 절 · [exit.md](exit.md)

## 1. 축

| 원본 개념 | Nova | 판정 |
|---|---|---|
| 명암 `data-theme` light · dark | 같은 이름 + 토큰 `$extensions["nova.modes"].dark` | 대응 |
| 브랜드 `data-tenant` (런타임 전환) | 프로젝트 단위 원시 `primitive.color.brand` · `accent` (디자인 시스템 README §2) | 근사 — 한 앱 안 런타임 브랜드 전환은 없다 |
| 형 `data-style` = base | 현재 Nova 토큰 그 자체 | 대응 |
| 형 `data-style` = neo (작은 반경 · 중성 표면 · 좁고 옅은 그림자) | — | **갭 G1** |
| 형 `data-style` = glendale (큰 반경 · 푸른 기 표면 · 퍼지는 틴트 그림자) | — | **갭 G1** |
| 원본 제품 `--neo-*` 변수 체계 | **들이지 않는다**(원본 psg05 도 유입 0 을 계약으로 삼았다) | 대상 아님 |

## 2. 색 — 의미 토큰

| 원본 개념 | Nova 의미 토큰 | 판정 |
|---|---|---|
| 표면 위계: 앱 바탕 < 표면 < 표면-2 | `color.bg.canvas` < `color.bg.surface` · `color.bg.subtle` | 대응 |
| 표면 위계: 떠 있는 층(elevated) | `color.bg.surface` + `elevation.overlay` | 근사 — 별도 표면 색 없이 그림자로 구분 |
| 텍스트 위계 strong · default · muted | `color.text.primary` · `secondary` · `muted` | 대응 |
| 텍스트 subtle (비텍스트 전용 톤) | `color.border.control` (UI 경계용) | 근사 — 글자에 쓰지 않는다 |
| 상태 성공 · 경고 · 위험 · 정보 · 중립 (+ 옅은 배경) | `color.status.successFg/Bg` · `warningFg/Bg` · `dangerFg/Bg` · `infoFg/Bg` · `neutralFg/Bg` | 대응 |
| 링크 | `color.status.linkFg/Bg` | 대응 |
| 솔리드 상태 배경 + 흰 잉크(히트맵 · 강조 타일 전용) | `color.status.<상태>Solid` · `color.status.onSolid` + `Badge` · `StatusBadge` `solid` · `Stat` `solid` | 대응(G2 해소 — REQ-261104-16) |
| 솔리드 경고 위 잉크(테마 반전) | `color.status.onWarningSolid` | 대응(G2) |
| 브랜드 원색(식별 · 솔리드 버튼) | `color.action.primary` | 대응 |
| 브랜드 솔리드 위 글자 | `color.action.onPrimary` | 대응 |
| 브랜드 판독 톤(작은 글자 · 아이콘) | `color.text.brand` | 대응 |
| 브랜드 포커스 링 | `color.border.focus` | 대응 |
| 브랜드 그라데이션 | — (Nova 는 단색 `action.primary`) | **갭 G3** |
| 딥 스크림(근-흑, 몰입형 딥 사이드바 바탕) | `color.bg.inverse` · `color.text.inverse` · `color.text.inverseMuted` | 근사 — 브랜드 색을 섞은 딥 톤은 아니다 |
| 딥 사이드바(브랜드 톤 바탕 · 흰 글자 · 활성만 솔리드) | AppShell `navTone: "deep"` — `color.bg.nav` · `bg.navActive` · `text.onNav` · `onNavMuted` · `onNavActive` · `border.focusOnNav` | 대응(G4 해소) |
| AI 표식 그라데이션 · ✦ 칩 | `AiMark` + `color.ai.fg` · `bg` · `border` | 근사(G5 해소) — 그라데이션 없이 단색 표식(G3 은 미룸) |
| 도메인 액센트 9종(모듈 식별색) + 판독 톤 | `DomainTag` + `color.domain.<1~6>Mark` · `<1~6>Text`(상태색과 분리 검사 — `gen_tokens` `check_separation` · `scan_usage`) | 근사(G6 해소) — 6종, 주황 · 갈색 계열 제외 |
| 등급 · 멤버십 뱃지 그라데이션(도메인 축 파생) | — (그라데이션은 G3 과 함께 미룸) | 대상 아님 |
| 차트 팔레트 1~6 | `color.chart.1`~`6` · `chartColor()` · `ChartLegend` | 대응(G7 해소) |

## 3. 크기 · 글꼴 · 움직임

| 원본 개념 | Nova 토큰 | 판정 |
|---|---|---|
| 간격 척도 | `space.*` (원시, CSS `--space-*`) | 대응 |
| 반경 | `radius.sm` ~ `pill` (원시, CSS `--radius-*`) | 근사 — 의미 반경이 없어 형 축(G1)을 얹을 자리가 없다 |
| 그림자 | `elevation.card` · `elevation.overlay` | 대응 |
| 컨트롤 높이 · 누름 영역 | `size.control.sm/md/lg` · `size.target.web/touch` | 대응 |
| 본문 글꼴 | `font.family.base` | 대응 |
| 데이터 글꼴(ID · 금액 · 일시 mono) | `font.family.mono` | 대응 |
| 제목 전용 글꼴(display) | — | **갭 G8** |
| 모션 시간 | `duration.fast/base/slow` | 대응 |
| 그라데이션 각도 고정 | — (그라데이션 자체가 G3) | 대상 아님 |

## 4. 부품 · 골격

| 원본 | Nova | 판정 |
|---|---|---|
| ConsoleShell | `AppShell` (`layout: "side"`) | 대응 |
| AppHeader + 브레드크럼 | AppShell 상단바 + `PageHeader` `crumbs` | 대응 |
| 헤더 유틸(알림 · 테넌트 전환 · 헤더 검색 · 프로필) | AppShell `config.header` — `HeaderSearch`(Ctrl+K) · `NotificationLink` · `TenantSwitcher` · `HeaderUtils` | 대응(C1 해소) — 프로필 메뉴는 없음 |
| MDI 탭바(닫을 수 있는 탭) | — | **부품 갭 C2** |
| 안내 배너(페이지 목적 한 줄) | `PageHeader` `description` | 근사 — 별도 배너 부품은 없다 |
| 푸터 오른쪽(서버 상태 · 버전 · 가동시간) | `AppShell` `config.footer` + `StatusBadge` + mono | 대응 |
| 라벨-좌측 검색 패널 | `ListPage` `filters` 슬롯 | 근사 — `FilterBar` 는 ui.md §3 🗺 |
| 표 + 쪽 나눔 | `DataTable` + `Pagination` | 대응 |
| 결과 헤더(총 건수 · 내보내기 · 등록) | `ListPage` `primary` + `export`(CSV — `toCsv` · 개인정보 열 가림) | 대응(C3 해소) |
| KPI 카드 · 밀집 평면형 | `Stat` · `DashboardPage`(지표 줄 + 블록 격자) | 근사 — 평면 · 밀집 변형 없음 |
| 상태 점(최소 상태 표식) | `StatusBadge` (글자 포함) | 근사 |
| 골격 B 스플릿 뷰 | `SplitPage`(`?sel` · ↑↓) | 대응(C4 해소) |
| 골격 C 설정형 슬롯 | `SettingsPage`(`?tab` · 구역마다 저장) | 대응(C5 해소) |
| 계층 코드 관리(밀러 칼럼) · 트리 | — | **부품 갭 C6** |
| 폼 모달(딥 헤더) · 모달 크기 단계 | `FormDialog`(`size: sm · md · lg` · FormPage 필드 공유) | 근사(C7 해소) — 딥 헤더 없이 표면 바탕 |
| Alert/Confirm 모달 | `ConfirmDialog` · `useConfirm` | 대응 |
| 로그인 분할 레이아웃 · 아이디 저장 · 찾기 · 전환 링크 | `LoginPage` `rememberId` · `links` | 근사(C8 해소) — 분할 레이아웃은 없음 |
| AI 실행 확인 카드 | `AiConfirmCard`(L2 — 대상 · 범위 · 파라미터 · 되돌림 필수, 승인 API 는 서버 `require_human`) | 대응(C9 해소) |
| 아이콘 세트(lucide) | AppShell `NavLink.icon` 문자열 | 근사 — 승인 세트 결정 없음 |

## 갭 — 토큰 제안 후보 (G, 8건 — G2 · G4 · G5 · G6 · G7 은 REQ-261104-16 으로 해소, 남은 3건 G1 · G3 · G8)
토큰 갭은 화면에서 메우지 않는다. 필요한 프로젝트가 생기면 `brand.tokens.json` 에 **의미 토큰**을 더하는 변경안을 쓰고(`design-rule-architect` 에이전트) → `python nova.py tokens`(대비 자동 검사) → 사람 승인. 이름은 역할 이름으로(값 이름 금지 — 디자인 시스템 README §1-3).

| ID | 무엇 | 제안 모양(이름은 후보) | 먼저 확인할 것 |
|---|---|---|---|
| G1 | 형 축(neo · glendale) | **킷 축으로 받는다**([ADR-016](../../../../docs/adr/ADR-016-nicomms-g1.md) · REQ-261106-04) — 킷 = 토큰 한 벌(`design/tokens/kits/`) + 부품 갭 목록. 프로젝트마다 `python nova.py kit use <id>` 로 하나를 고른다(체크리스트 `design.kit` 에서 고르면 import 때 설정). 한 앱 안 런타임 형 전환은 하지 않는다. glendale 은 대비 미달로 킷 목록에 넣지 않았다 | 원하는 형이 킷 목록(`kit list`)에 있나 — 없으면 새 킷 토큰 파일을 더하는 변경안(대비 검사 통과가 조건) |
| ~~G2~~ 해소 | 솔리드 상태 배경 + 위 잉크 | `color.status.<상태>Solid` · `color.status.onSolid` (+ 경고 반전 잉크) | 데이터 시각화(히트맵) 소비처가 실제로 있나 |
| G3 | 브랜드 그라데이션 | `color.brand.gradient` 류 — 다만 대비 검사 쌍을 정의하기 어렵다 | 단색으로 안 되는 이유 |
| ~~G4~~ 해소 | 딥 사이드바 톤 | `color.bg.nav` · `color.text.onNav` · `color.text.onNavMuted` + AppShell 설정 `navTone` | `bg.inverse` 로 충분한가(근사 행) |
| ~~G5~~ 해소 | AI 표식 | `color.ai.*`(표식 색 · 그라데이션) + ✦ 표식 부품 — C9 와 한 묶음 | STD-AX 등급 판정이 L1 이상인 기능이 있나 |
| ~~G6~~ 해소 | 도메인 식별색(+ 판독 톤 · 등급 뱃지) | `color.domain.<모듈>` + `color.domain.<모듈>Text` — **상태색과 섞지 않는 규칙**을 함께 | 도메인 팩(STD-DOMAIN-PACK) 이 모듈 구분을 화면에 요구하나 |
| ~~G7~~ 해소 | 차트 팔레트 | `color.chart.1`~`6` | `DashboardPage` 🗺 와 한 묶음으로 |
| G8 | 제목 전용 글꼴 | `font.family.display` | 한국어 글꼴 범위 · 라이선스 |

## 부품 · 템플릿 갭 (C, 9건 — C1 · C3 · C4 · C5 · C7 · C8 · C9 는 REQ-261104-16 으로 해소, 남은 2건 C2 · C6)
행선지는 [exit.md](exit.md) 1행(ui.md §3 · §5 🗺 행 + 계획 🆕 task, 먼저 만든 프로젝트는 Nova 로 역제안).

| ID | 무엇 | 묶을 곳 |
|---|---|---|
| ~~C1~~ 해소 | 헤더 유틸(알림 · 테넌트 전환 · 헤더 검색) | ui.md §3 레이아웃 행 · 테넌트 전환은 STD-TENANCY 와 함께 |
| C2 | MDI 탭바 | ui.md §3 레이아웃 행(AppShell 설정 슬롯) |
| ~~C3~~ 해소 | 목록 내보내기 | ui.md §3 목록 행 |
| ~~C4~~ 해소 | 스플릿 뷰 템플릿 | ui.md §5 템플릿 |
| ~~C5~~ 해소 | 설정형 슬롯 템플릿 | ui.md §5 템플릿 |
| C6 | 밀러 칼럼 · 트리 | ui.md §3 목록 행 |
| ~~C7~~ 해소 | 폼 모달 · 모달 크기 단계 | ui.md §3 피드백 행 |
| ~~C8~~ 해소 | 로그인 확장(분할 · 아이디 저장 · 찾기 · 전환 링크) | ui.md §3 인증 행(🗺 이미 있음) |
| ~~C9~~ 해소 | AI 실행 확인 카드 | ui.md §3 피드백 행 + STD-AX ③ — G5 와 한 묶음 |
