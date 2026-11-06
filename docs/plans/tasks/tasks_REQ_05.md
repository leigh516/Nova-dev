# tasks_REQ_05 · nicomms 갭 — 토큰 5 · 부품 7 · DashboardPage — 할 일 체크리스트

계획: [plan_REQ_05 v1.0](../plan_REQ_05.md) · 화면 미리보기는 계획 §4 · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일 · `~~취소~~ — 이유` 하지 않기로 함
선행: 계획 §11.0 판단 A~F 를 사용자가 정한 뒤 1단계를 시작한다(지금은 권고).

## 0단계 · 목업
- [x] T05-0.01 목업 HTML 6장 쓰기 (`docs/plans/mockups/REQ_05/` app-design · app-design-dashboard · app-design-split · app-design-settings · app-design-deepnav · app-login, 새 부분 `mock-new`)
  - 파일: 만들기 `docs/plans/mockups/REQ_05/*.html`
- [x] T05-0.02 목업 PNG 두 모드로 만들기 (`uv run python scripts/mockup_shots.py --themes light,dark` 판정 통과 · .png · .dark.png)
- [x] T05-0.03 목업을 계획 §4 에 잇고 사용자에게 보이기 (§4 표의 '(0단계에서 생성)' 을 이미지로 바꿈 · 이미지 열림) — 2026-11-06 확인: §4 표에 목업 PNG 12장 연결 · '(0단계에서 생성)' 0건(체크 누락 정리)

## 1단계 · 토큰 원천 · 검사
- [x] T05-1.01 원시 팔레트 추가하기 — violet 700/300/100/dark100 · brand.900 · 차트/도메인 6색 × 라이트/다크 단계 (`gen_tokens.py` 생성 성공 · 의미 토큰이 아직 안 쓰므로 대비 변화 없음)
  - 파일: 고치기 `design/tokens/brand.tokens.json`
- [x] T05-1.02 새 쌍 등록을 강제하는 실패 테스트 쓰기 (`test_new_pairs_registered` — semantic.color 의 ai · domain · chart · *Solid · nav 토큰마다 contrast 쌍이 하나 이상, 지금은 실패)
  - 파일: 테스트 `tests/test_gen_tokens.py`
  - [x] `uv run pytest tests/test_gen_tokens.py::test_new_pairs_registered` 실패 확인
- [x] T05-1.03 G2 솔리드 상태 토큰과 쌍 넣기 (`status.{success,warning,danger,info,neutral}Solid` · `onSolid` · `onWarningSolid`, 쌍: 잉크 on 솔리드 text — 판단 B2 면 모드별 잉크 · `python nova.py tokens` 통과)
- [x] T05-1.04 G4 딥 사이드바 토큰과 쌍 넣기 (`bg.nav` · `bg.navActive` · `text.onNav` · `text.onNavMuted` · `text.onNavActive` · `border.focusOnNav`, 쌍: onNav · onNavMuted on nav text / onNavActive on navActive text / navActive · focusOnNav on nav ui · 통과)
- [x] T05-1.05 G5 AI 토큰과 쌍 넣기 (`ai.fg` · `ai.bg` · `ai.border`, 쌍: fg on ai.bg text · fg on bg.surface text · border on bg.surface ui · 통과)
- [x] T05-1.06 분리 검사 실패 테스트 쓰기 (`test_separation_same_value_fails` — domain 값 = status 값이면 오류 / `test_separation_same_primitive_fails` — 같은 원시 참조면 오류 · 실패 확인)
  - 인터페이스: 내주는 것 `check_separation(tree) -> list[str]` · 원천 최상위 `"separation": {"$value": [["status", "domain"]]}`
- [x] T05-1.07 G6 도메인 토큰 · 쌍 · `check_separation` 구현하기 (`domain.{1..6}.mark` ui · `.text` text on bg.surface · bg.canvas, `main()` 오류 목록에 합침 · 1.06 통과)
- [x] T05-1.08 사용 검사 `scan_usage` 실패 테스트 쓰고 구현하기 (한 CSS 규칙 블록 · TSX 한 줄 · Kotlin 한 줄에 `--color-status-`/`status*` 와 `--color-domain-`/`domain*` 가 함께 있으면 오류, `web/packages/ui/src`(tokens.css 제외) · `web/apps/app/app/design` · `apps/kmp/uikit`(DesignTokens.kt 제외) · `.claude/skills/nicomms-screen` 의 hex · rgb() 오류, 허용 목록 styles.css 백드롭 1곳 · `test_scan_mixing_status_domain_fails` · `test_scan_raw_color_fails` · `test_scan_allowlist` 통과)
  - 인터페이스: 내주는 것 `scan_usage(root: Path) -> list[str]` · `ALLOW_RAW: set[tuple[str, str]]`(경로, 줄 내용)
- [x] T05-1.09 G7 차트 토큰과 쌍 넣기 (`chart.1` ~ `chart.6` 모드별, 쌍: 각각 on bg.surface · bg.canvas ui · 1.02 통과)
- [x] T05-1.10 생성물 다시 만들고 lint 확인하기 (`python nova.py tokens` "대비 N쌍 통과" · `python nova.py lint` 통과 · `python nova.py kmp-build` 컴파일 — ColorTokens 새 속성)

**단계 관문**: `python nova.py quick --stage T05-1` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 2단계 · 웹 토큰 소비 부품
- [x] T05-2.01 ui-smoke 에 단계 선택 `--only <이름>` 추가하기 (`ui_smoke.py --only design` 이 갤러리 단계만 돈다 · 인자 없으면 지금과 같은 전체 흐름)
  - 파일: 고치기 `scripts/ui_smoke.py`
- [x] T05-2.02 "갤러리 — 토큰 부품" ui-smoke 단계 먼저 쓰기 (솔리드 배지 · AI 표식(aria-label "AI 생성") · 도메인 태그 · 차트 범례 6 · 딥 사이드바 미리보기(aria-current) 단언 — 지금은 실패)
- [x] T05-2.03 Badge · StatusBadge 에 `solid` 추가하기 (`.badge.solid.<tone>` 은 *Solid · onSolid 토큰만 · 2.02 의 솔리드 단언 통과)
  - 인터페이스: `Badge({tone, solid?: boolean})` · `StatusBadge({code, map, solid?})`
- [x] T05-2.04 AppShell 사이드바를 `Sidebar` 로 뽑고 `navTone` 추가하기 (동작 보존 — 기존 ui-smoke 전체 통과 · `AppConfig.navTone?: "default" | "deep"` · deep 은 nav 토큰만 · 활성 · 포커스 대비 쌍 그대로)
  - 인터페이스: 내주는 것 `Sidebar({links: NavLink[], current: string, tone?: "default" | "deep"})`
- [x] T05-2.05 `AiMark` 만들기 (✦ + "AI" 글자 · ai.* 토큰만 · `aria-label="AI 생성"` · 단언 통과)
- [x] T05-2.06 `DomainTag` 만들기 (`map: Record<string,{label: string; slot: 1|2|3|4|5|6}>` · domain.* 토큰만 · status 클래스와 합치지 않음 → `scan_usage` 통과)
- [x] T05-2.07 차트 색 `chartColor(i)` 를 Sparkline · Bars 에 잇기 (`chartColor(i) = var(--color-chart-${(i % 6) + 1})` · `Bars` 항목별 `series?` · 기본은 지금과 같은 색 · 2.02 전부 통과 · `npm run typecheck` 통과)

## 3단계 · 웹 템플릿 · 부품
- [x] T05-3.01 `DashboardPage` 만들기 — ui-smoke 단계 "대시보드" 먼저 (Stat 줄 · 블록 격자 · 블록 하나 오류여도 다른 블록 보임 · 갱신 시각 · `source` 또는 `data` · 통과)
  - 인터페이스: `DashboardPage<D>({title, description?, source?: string, data?: D, refreshMs?: number, stats: (d: D) => {label; value; delta?; tone?; solid?}[], blocks: (d: D) => {id; title; wide?: boolean; body: React.ReactNode; error?: unknown}[]})`
- [x] T05-3.02 AppShell `header` 유틸 만들기 — 알림 · 테넌트 전환 (`AppConfig.header?: {notifications?: {count: number; href: string}; tenants?: {current: string; items: {id; label}[]; onSwitch: (id: string) => Promise<void>}}` · 전환 실패 시 현재 유지 · 오류 토스트 · 부품이 x-tenant · 저장소를 건드리지 않음 · ui-smoke 단계 "헤더 유틸" 통과)
- [x] T05-3.03 헤더 검색 `HeaderSearch` 와 `Ctrl+K` 넣기 (`header.search?: {placeholder?; onSearch: (q) => void}` · 입력 칸 안에서 `/` · `n` 단축키 무시 확인 · 검토 초점 5 단언 통과)
- [x] T05-3.04 LoginPage 확장하기 (`rememberId?: boolean`(이메일만 저장, 비밀번호 저장 없음 · 저장소 예외 시 무시) · `links?: {label; href}[]`(찾기 · 전환) · ui-smoke "로그인 확장" 재방문 채움 통과 · 운영 빌드에 데모 버튼 없음 확인)
- [x] T05-3.05 `Column.pii` 와 CSV 직렬화 함수 테스트 먼저 쓰기 (ui-smoke "내보내기" — 다운로드 파일 내용: BOM · 가림 `****` · `=` 로 시작하는 값 앞 `'` · 쉼표 · 줄바꿈 따옴표, 지금은 실패)
  - 인터페이스: `Column<T>.pii?: boolean` · `Column<T>.exportable?: boolean` · `toCsv(rows, columns) -> string`
- [x] T05-3.06 ListPage 내보내기 구현하기 (`ListPageProps.export?: {label?: string; filename: string; max?: number /* 기본 5000 */}` · 같은 query 로 size=100 쪽 순회 · 진행 표시 · 403/오류면 파일 없음 · 상한 초과 안내 · 3.05 통과)
- [x] T05-3.07 `SplitPage` 만들기 (목록(DataTable) 왼쪽 · 상세 오른쪽 · `?sel=` 유지 · ↑↓ 이동 · 900px 아래 위아래 쌓기 · ui-smoke "스플릿" 통과)
  - 인터페이스: `SplitPage<T>({title, source, columns, detail: (row: T) => React.ReactNode, empty?})`
- [x] T05-3.08 `FormDialog` 만들기 (FormPage 필드 렌더 공유 · `size: "sm" | "md" | "lg"` · useDialogFocus 가두기 · Esc · 연 버튼 복귀 · 입력이 있으면 useConfirm 닫기 확인 · ui-smoke "폼 모달" 통과)
  - 인터페이스: `FormDialog({open, title, size?, fields: FormField[], initial?, submitLabel?, onSubmit, onClose})`
- [x] T05-3.09 `SettingsPage` 만들기 (왼쪽 구역 목록 · 오른쪽 슬롯 · `?tab=` 유지 · 구역마다 저장 · ui-smoke "설정" 통과)
  - 인터페이스: `SettingsPage({title, sections: {id; label; description?; render: () => React.ReactNode}[]})`
- [x] T05-3.10 `AiConfirmCard` 만들기 — L2 (`AiMark` 포함 · 대상 · 범위 · 파라미터(KeyValue) · 되돌림(없으면 "되돌릴 수 없습니다" + danger) 모두 필수 props · 기본 포커스 취소 · 렌더만으로 onApprove 호출 없음 · useAction · 머리 주석에 "승인 API 는 require_human" · ui-smoke "AI 확인 카드" 통과(Enter · 새로고침에 실행 없음))
  - 인터페이스: `AiConfirmCard({level: "L2", title, target: string, scope: string, params: {label; value}[], undo: string | null, onApprove: () => Promise<unknown>, onCancel: () => void})`
  - [x] `index.ts` 내보내기 확인 · `npm run typecheck` 통과

## 4단계 · 모바일 대응 (판단 E1 일 때)
- [x] T05-4.01 `Badge(solid)` · `StatusBadge(solid)` 추가하기 (statusXSolid · onSolid 만 · `python nova.py kmp-build` 통과)
  - 파일: 고치기 `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt`
- [x] T05-4.02 `AiMark` · `DomainTag` 만들기 (ai* · domainNMark/Text 만 · contentDescription "AI 생성" · `scan_usage` 통과)
- [x] T05-4.03 `AiConfirmCard` 만들기 (웹과 같은 props 이름 · 렌더만으로 실행 없음 · 취소 항상 · rememberAction · kmp-build 통과)
- [x] T05-4.04 모바일 부품 화면 PNG 찍기 (`python nova.py kmp-snapshots` 에 갤러리 장면 추가 · 라이트 · 다크 PNG 를 직접 읽어 깨짐 없음)

## 5단계 · 갤러리 · 문서 · 원장
- [x] T05-5.01 갤러리 /design 에 새 절 넣기 (솔리드 · AI · 도메인 · 차트 · 폼 모달 · 헤더 유틸 · 딥 사이드바 미리보기 · 내보내기 · AI 확인 카드, 절마다 쓰는 법 한 줄)
  - 파일: 고치기 `web/apps/app/app/design/page.tsx`
- [x] T05-5.02 갤러리 하위 화면 3개 만들기 (`/design/dashboard` · `/design/split` · `/design/settings`, 머리 주석 `/** @screen … · @status 완료 */` · 가짜 데이터)
- [x] T05-5.03 원장 · 대장 맞추기 (`uv run python scripts/registry.py sync --by <이름> --note "REQ-261104-16 부품 · 갤러리 화면"` · `uv run python scripts/ledgers.py` · `ledgers.py --check` 통과)
- [x] T05-5.04 ui.md §3 · §5 고치기 (새 부품 · 템플릿 행 ✅ · 모바일 칸 🗺/✅ · DashboardPage 🗺 → ✅ · 솔리드 남용 · 도메인/상태 분리 · AI L2 규칙 한 줄씩)
- [x] T05-5.05 디자인 시스템 README · nicomms 갭 표 고치기 (README 에 분리 · 토큰 밖 색 검사 설명 · style-map G2 · G4 · G5 · G6 · G7 · C1 · C3 · C4 · C5 · C7 · C8 · C9 판정을 "대응"으로, 미룬 5건은 이유 그대로)
- [x] T05-5.06 ui-smoke 전체 흐름에 새 단계와 다크 캡처 잇기 (`app-design*.png` · `app-design*.dark.png` 저장 · 기존 흐름 회귀 없음)
- [x] T05-5.07 `docs_index.py --check` 통과 확인하기 (링크 · 한국어 · 인덱스) — 2026-11-06 `✓ 문서 인덱스 · 링크 정상`(체크 누락 정리)

## 6단계 · 확인 (종료 조건)
- [x] T05-6.01 E1 판정하기 (`python nova.py test` 통과 출력)
- [x] T05-6.02 E2 판정하기 (`python nova.py lint` 통과 — "WCAG 2.2 AA 대비 N쌍 통과" 숫자 기록)
- [x] T05-6.03 E3 판정하기 (dev_server + `NEXT_PUBLIC_DEV_LOGIN=1` 빌드 3100 + `python nova.py ui-smoke` "브라우저 시나리오 통과")
- [x] T05-6.04 (2026-11-05 — 6쌍 · PNG 29장, 다크 깨짐 0 · 심각도 3 이상 0 · 차이는 계획 §12.1 · 🆕 9.05~9.08) 목업 대비 실제 화면 비교하기 (0단계 PNG 와 `docs/screenshots/app-design*.png` 같은 구도 · 차이 기록)
- [x] T05-6.05 (2026-11-05 — 사용자 "충족" · exit-check 4/4 녹색) E4 사람 확인 받기 (사용자가 갤러리 · 대시보드를 라이트 · 다크로 열어 "충족 YYYY-MM-DD" · `python nova.py exit-check REQ-261104-16` 녹색)

## 작업 중 발견 (단계와 별개)
- [x] 🆕 T05-9.01 (2026-11-06 REQ-261105-10-4 에 흡수 — kmp-smoke · kmp-snapshots 가 `stack` 주소(또는 `NOVA_API`)를 읽어 gradlew 에 `-Papi=` 로 넘긴다 · `nova.py` `_stack_api` · git_261106_01) `python nova.py kmp-snapshots` 가 게이트웨이 주소를 받지 못한다 — 기대: 주소 인자(예: `--api`) 또는 환경 변수로 전달 · 실제: Snapshot.kt 기본값 8080 고정이라 이 PC 에서는 다른 저장소(dayroom2) 게이트웨이에 붙어 기존 장면 5개 실패 · 환경: `nova.py:306` · `apps/kmp/composeApp/src/desktopMain/kotlin/kr/nova/app/Snapshot.kt:22`(2026-11-05 — gradlew 에 `-Papi=…8091` 을 직접 줘서 7장 통과)
- [ ] 🆕 T05-9.02 uikit 부품 단위 테스트 수단이 없다(`kmp-test` 는 shared 만, `compose.uiTest` 미도입) — 4단계 TDD 를 스냅숏 단언 · PNG 로 대신함. 기대: AiConfirmCard '그리기만으로 실행 없음' · '되돌림 null → 위험'을 단위 테스트로(의존성 추가라 사용자 결정 — T04-9.10 웹과 한 묶음으로)
- [ ] 🆕 T05-9.03 한 화면에 AiConfirmCard 가 둘이면 마지막 카드의 취소가 포커스를 가져간다(모바일 갤러리에서 관측) — 기대: 규칙 '한 화면에 카드 하나'(ui.md 규칙 13 에 적음) 또는 첫 카드만 포커스 · 그리고 승인 중 두 버튼이 모두 잠겨 포커스를 잃는 것은 T04-9.08 과 같은 뿌리
- [ ] 🆕 T05-9.04 모바일 `KeyValue` 가 없어 AiConfirmCard 안에 private `AiRow` 로 둠 — 두 번째 쓰임이 생기면 `kr.nova.uikit` 공통 부품으로 올린다(ui.md 규칙 2)
- [ ] 🆕 T05-9.05 `SettingsPage` 에 바뀐 항목 표시 · 되돌리기가 없다(목업 대비 — 심각도 2, H1 · H3) — 기대: 구역마다 '바뀐 항목 n개 — 이 구역만 저장됩니다' · 되돌리기 버튼 · 저장 비활성 조건이 보임. 시연 화면도 좁은 폭 → 넓은 폭 · 구역 5개 · 입력 종류(다중 선택 · 입력칸)로 목업과 맞춤
- [ ] 🆕 T05-9.06 로그인 전 화면 머리줄에 헤더 검색(Ctrl+K)이 보인다(목업에 없음 — 심각도 1) — 기대: 로그인 게이트 앞에서는 `header` 유틸을 그리지 않음 · ui-smoke `login-ext` 에 단언
- [ ] 🆕 T05-9.07 시연 화면이 부품 능력을 다 보이지 않는다(심각도 1 묶음) — 스플릿: 검색 · 건수 · 쪽 넘김 · 상세 동작 · 도메인 태그 열 / 대시보드: 지금 새로 고침 · 주기 표시 · 겹친 추이 차트 / 갤러리: 솔리드 타일 · 딥 사이드바 포커스 링(`border.focusOnNav`) · 내보내기 진행 표시 · AI 카드 '왜 확인이 필요한가' 상자(§4.1 H10) / 로그인: 찾기 · 전환 링크 2개. SplitPage 쪽 넘김은 인터페이스 확장이 필요(§12.1 3단계)
- [ ] 🆕 T05-9.08 같은 개념(예: '자산')이 차트 막대(차트색)와 태그(도메인색)에서 다른 색으로 보인다(심각도 1 — 도메인 ≠ 차트 결정의 결과) — 기대: 한 화면에서 같은 개념을 두 축으로 칠하지 않는 규칙을 ui.md 규칙 12 에 덧붙이거나, 대시보드 시연에서 막대를 도메인 색으로(사용자 결정 — T05 도메인 색 (다)와 함께)
