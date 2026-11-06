# 화면 구성 규약 (웹 · 모바일 공통)

목표: **유지보수성**(한 곳 수정 → 모든 화면 반영) · **확장성**(새 화면 = 템플릿 + 데이터 정의) · **일관성**(같은 상황은 같은 동작) · **통일성**(같은 모양 · 문구 · 색).
UX 원칙은 [ux-heuristics.md](ux-heuristics.md)(닐슨 10대 휴리스틱) — 이 규약의 컴포넌트가 그 [자동] 항목을 구현한다.

## 1. 3층 구조 — 화면은 위층만 조립한다
| 층 | 웹 (`web/packages/ui/src`) | 모바일 (`apps/kmp/uikit`) | 내용 |
|---|---|---|---|
| ① 토큰 | `tokens.css`(생성물) | `DesignTokens.kt`(생성물) | 원천 `design/tokens/brand.tokens.json` → `scripts/gen_tokens.py`. **값을 화면에 직접 쓰지 않는다** ([디자인 시스템](../design-system/README.md)) |
| ② 컴포넌트 | `components/*.tsx` | `kr/nova/uikit/*.kt`(`Components.kt` · `AiConfirmCard.kt`) | Button · Card · Badge · DataTable · EmptyState · ErrorState … |
| ③ 템플릿 | `templates/*.tsx` | `kr/nova/uikit/Templates.kt` — ListScreen · DetailScreen · FormScreen · LoginScreen(웹 ListPage · DetailPage · FormPage · LoginPage 대응). 데이터는 AppStore 의 `Loadable` 을 받고 상태 판정은 shared `ViewPhase` | 화면 유형별 골격: AppShell · ListPage · DetailPage · FormPage · LoginPage · DashboardPage · SplitPage · SettingsPage |
| 화면 | `web/apps/<app>/app/**/page.tsx` | `apps/kmp/composeApp/src/commonMain/kotlin/…/Screens.kt` | **템플릿 호출 + 이 화면만의 데이터 정의(컬럼 · 필드 · 액션)** |

## 2. 규칙
1. **템플릿 먼저**: 새 화면은 맞는 템플릿을 고르고 설정만 넘긴다. 맞는 템플릿이 없으면 템플릿을 먼저 추가한다(화면 안에 골격을 직접 짜지 않는다).
2. **두 번 나오면 컴포넌트**: 같은 마크업 · 로직이 두 화면 이상에 나오면 공통 컴포넌트로 올린다. 화면 파일에 `table` · `thead`, 버튼 묶음, 상태 배지 색 매핑을 직접 쓰지 않는다.
3. **표는 선언형**: 목록은 `DataTable` / `DataList` 에 `columns`(키 · 제목 · 정렬 · 렌더러)와 `rowActions` 를 넘긴다.
4. **액션은 한 가지 방식**: 서버 호출 버튼은 `useAction`(웹) / `rememberAction`(모바일)으로 감싼다 — 진행 중 비활성(중복 제출 방지) · 성공 토스트 · 오류 토스트(`ApiError.message`) · 후속 새로고침이 항상 같다. 되돌릴 수 없는 액션은 `confirm` 옵션으로 공통 확인 대화상자, 되돌릴 수 있는 액션은 `undo` 옵션으로 실행 취소 토스트(`window.confirm` · `prompt` · `alert` 금지).
5. **상태 3종 고정**: 데이터 화면은 템플릿이 로딩(스켈레톤) · 빈 상태(`EmptyState`) · 오류(`ErrorState` + 다시 시도)를 자동으로 그린다. 화면에서 따로 만들지 않는다.
6. **코드 · 상태 표시는 매핑 컴포넌트로**: 상태 배지는 `StatusBadge` — 라벨 · 색(tone)은 서버 설정에서 읽은 매핑을 넘기고, 화면에 enum · 색 하드코딩 금지.
7. **시각 · 숫자 표시 일원화**: 날짜 · 시각은 `fmtAt()`(프로젝트 시간대 · locale), 숫자 · 금액은 `fmtNumber()` · `fmtMoney()` — 화면에서 `slice()` 로 자르지 않는다.
8. **문구 통일**: 버튼 · 토스트 · 빈 상태 문구는 컴포넌트 기본값을 쓴다(저장 · 취소 · 삭제 · 다시 시도). 바꿀 때만 넘긴다. 도메인 용어는 `docs/conventions/glossary.md`.
9. **웹 · 모바일 대응 이름**: 같은 개념은 같은 이름(웹 `DataTable` ↔ 모바일 `DataList`, `PageHeader` ↔ `ScreenHeader`) — 한쪽에 추가하면 다른 쪽에도 추가하거나 계획에 남긴다.
10. **앱별 차이는 설정으로**: 앱 차이는 `AppShell` 설정(브랜드 · 메뉴 채널 · 허용 역할 · 레이아웃 · 푸터 · `navTone` · `header`)으로만 둔다. 앱마다 셸을 새로 만들지 않는다.
11. **솔리드는 경보 강조에만**: `solid` 배지 · 지표(`*Solid` + `onSolid`)는 화면당 한 곳 권장 — 남발하면 강조가 사라진다(UX H8).
12. **상태색과 식별색을 섞지 않는다**: 상태(성공 · 경고 · 위험)는 `StatusBadge`, 모듈 · 도메인 식별은 `DomainTag` · 차트는 `chartColor()`. 한 요소에 두 축을 겹치지 않는다 — `gen_tokens` 분리 · 사용 검사가 lint 로 막는다.
13. **AI 쓰기(L2)는 확인 카드 + 서버 승인**: AI 가 바꾸려는 것은 `AiConfirmCard`(대상 · 범위 · 파라미터 · 되돌림 필수, 기본 포커스 취소, 그리기만으로 실행 없음)로 보이고, 승인 API 는 서버에서 `require_human`. 한 화면에 카드는 하나. AI 산출물에는 `AiMark` 를 붙인다(사람 콘텐츠에는 붙이지 않는다).
14. **입력 상한 · 이메일 형식은 서버 계약에서**: 칸 길이 상한은 웹 `LIMITS.<스키마>.<칸>.maxLength`(`web/apps/<app>/lib/contract.gen.ts`) · 모바일 `Contract.<스키마>_<칸>_MAX`, 이메일은 `EMAIL_PATTERN`(`@nova/sdk` · `Contract`) — 원천은 서비스 요청 스키마(pydantic `Field`) · `nova_common.validate`, 생성은 `scripts/gen_contract.py`(`python nova.py gen`, lint 가 `--check`). 화면에 상한 숫자를 쓰지 않는다.

## 3. 컴포넌트 목록
상태: ✅ 플랫폼에 있음 · 🗺 로드맵(필요한 프로젝트가 먼저 만들고 Nova 로 역제안)

| 분류 | 웹 | 모바일 | 상태 |
|---|---|---|---|
| 레이아웃 | `AppShell`(헤더 · 내비 top/side · 콘텐츠 · 푸터 · 로그인 게이트 · `navTone` default/deep) · `Sidebar` · `PageHeader` · `Section` · `Content`(width narrow · default · wide) | `NovaTheme` + Material `Scaffold`(하단 탭 = 서버 메뉴) · `ScreenHeader` | ✅ |
| 헤더 유틸 | `HeaderSearch`(Ctrl+K) · `NotificationLink` · `TenantSwitcher`(실패 시 현재 유지) · `HeaderUtils` — AppShell `config.header` | — | ✅ 웹 · 🗺 모바일 |
| 버튼 | `Button`(variant primary · secondary · ghost · danger, size sm · md · lg, loading) — 서버 호출은 `useAction` | `NovaButton`(같은 variant · loading) — 서버 호출은 `rememberAction` | ✅ |
| 피드백 | `useToast`(토스트 — 실행 취소 버튼 포함) · `ConfirmDialog`(useConfirm) · `FormDialog`(size sm · md · lg — FormPage 필드 공유) · `EmptyState` · `ErrorState` · `Forbidden`(권한 없음) · `Skeleton` · `Spinner` | 스낵바(`Notice` · 실행 취소) · `ConfirmDialog` · `EmptyState` · `ErrorState` · `Loading` | ✅ · 🗺 모바일 `FormDialog` |
| AI | `AiMark` · `AiConfirmCard`(L2) | `AiMark` · `AiConfirmCard`(L2 — 같은 props 이름, `notify` 추가) | ✅ |
| 목록 | `DataTable`(columns · rowActions · 정렬 · 행 클릭 · 키보드 · `Column.pii` · `exportable`) · `Pagination` · `toCsv` | `DataList` | ✅ |
| 표시 | `Card` · `Badge`(`solid`) · `StatusBadge`(`solid`) · `Stat`(`solid`) · `KeyValue` · `DomainTag` | `Card` · `Badge`(`solid`) · `StatusBadge`(`solid`) · `DomainTag` · `Title` · `Muted` | ✅ |
| 입력 | `Field`(label · help · error · `inline` 칸 옆 라벨) · `TextInput` · `TextArea` · `Select` · `Switch` · `Segmented` — 폼 모델 `FormField` 의 `type`: text · textarea · email · number · select(`options`) · date(`min` · `max`) · switch · checkbox. 값 `FormValues` 는 글 · 선택 · 날짜(YYYY-MM-DD)가 문자열, switch · checkbox 가 참 · 거짓. select · date 는 고를 수 있는 값만(목록 밖 · 범위 밖은 칸 오류) | `NovaTextField` · `FormField`(shared — 문자열 칸만, 🗺 선택 · 스위치 · 날짜는 웹 모양을 따라) | ✅ 기본 · 기본 날짜 칸(`type: date`) ✅ · 🗺 달력 부품 `DatePicker` · `Form`(스키마 → 필드 자동 배치) · `FilterBar` · `SearchBar` 자동완성 |
| 인증 | `LoginPanel`(아이디 저장 · 링크) | `LoginScreen`(uikit 템플릿 — 데모 계정 · 도움 문구, 🗺 아이디 저장 · 링크) | ✅ 이메일 · 🗺 휴대폰 인증 · 소셜 로그인 · 분할 레이아웃 |
| 도움말 · 환경 | `ShortcutHelp`(`?` 키) · `ThemeToggle`(라이트 · 다크) · 🗺 `HelpLink` | — | ✅ 웹(`HelpLink` 제외) · 🗺 모바일 |
| 차트 | `Sparkline` · `Bars` · `ChartLegend` · `chartColor()`(차트 1~6) | — | ✅ 웹 · 🗺 모바일 |
| 도움말 | `Tooltip`(아이콘 · 칸 옆 짧은 설명 — 키보드 초점에도 열림) | — | 🗺 — 근거 newtype 킷 갭 REQ-261106-04 |
| 입력 | `PeriodSearch` 기간 검색(오늘 · 1주 · 1개월 빠른 선택 + 시작 · 끝 날짜 — 목록 위 검색 줄) | — | 🗺 — 근거 newtype 킷 갭 REQ-261106-04 |
| 피드백 | 약관 창(약관 전문 스크롤 · 끝까지 읽음 · 동의 체크 — `FormDialog` 위에) | — | 🗺 — 근거 newtype 킷 갭 REQ-261106-04 |
| 입력 | 입력 마스크(전화 · 사업자 번호 · 카드처럼 모양이 정해진 칸 — `TextInput` 확장) | — | 🗺 — 근거 newtype 킷 갭 REQ-261106-04 |
| 목록 | `DataTable` 행 선택(체크 칸 · 전체 선택 · 선택한 건 일괄 처리) | — | 🗺 — 근거 newtype 킷 갭 REQ-261106-04 |

## 4. 목록 · 페이지네이션 API 계약 (서버 공통)
- 요청: `?page=1&size=20&sort=-created_at&q=...&<필터 키>=...` (page 1부터, size 기본 20 · 최대 100)
- 응답: `{"items": [...], "total": 123, "page": 1, "size": 20}` — `nova_common.paging.paginate(session, query, page, *, sortable, to_dict)` 로 만든다(`page` 는 `Page` 의존성 — `page: Page = Depends()`, `sortable` 은 허용 정렬 필드 → 컬럼, 목록 밖 `sort` 는 400 `invalid_sort`)
- `DataTable` 은 배열 응답과 페이지 응답을 둘 다 받는다(배열이면 클라이언트 측 페이지 분할)

## 5. 템플릿 목록
| 템플릿 | 용도 | 받는 것 | 상태 |
|---|---|---|---|
| `AppShell` | 앱 골격 | app 정의 `{id, brand, roles, menuChannel, layout: top · side, footer, fallbackLinks}` | ✅ 웹 · 🗺 모바일 |
| `LoginPage` | 로그인 | 제목 · 부제 · 데모 계정(개발 빌드만) · `rememberId` · `links` | ✅ 웹 · ✅ 모바일(LoginScreen — 🗺 rememberId · links) |
| `ListPage` | 목록(검색 + DataTable + Pagination) | 제목 · 데이터 경로 · columns · rowActions · 빈 상태 문구 · 주 행동 · `export`(CSV, 기본 상한 5000) | ✅ 웹 · ✅ 모바일(ListScreen — 🗺 검색 · 쪽 나눔 · 내보내기) |
| `DetailPage` | 단건 상세 | 데이터 경로 · 섹션 · 액션 | ✅ 웹 · ✅ 모바일(DetailScreen) |
| `FormPage` | 입력 · 수정 | 필드 · 제출 액션 | ✅ 웹(글 · 선택 · 날짜 · 스위치 · 체크박스 — FormDialog 와 같은 칸) · ✅ 모바일(FormScreen — 문자열 칸, 🗺 서버 칸별 오류 표시) |
| `DashboardPage` | KPI · 차트 | `stats` · `blocks`(블록 하나 실패는 그 블록만) · `source` 또는 `data` · `refreshMs` | ✅ 웹 · 🗺 모바일 |
| `SplitPage` | 목록 + 상세(스플릿) | `columns` · `detail` · `source` 또는 `rows` · `?sel` 유지 · ↑↓ | ✅ 웹 · 🗺 모바일 |
| `SettingsPage` | 설정(구역 목록 + 슬롯) | `sections` · `?tab` 유지 · 구역마다 저장 | ✅ 웹 · 🗺 모바일 |
| 🗺 마법사 · 단계 | 여러 단계 입력 | — | 🗺 — 처음 필요한 프로젝트가 만들고 역제안 |
| 🗺 캘린더 · 일정 | 날짜 격자 · 일정 목록 | — | 🗺 |
| 🗺 트리 · 계층 | 계층 탐색 · 관리(밀러 칼럼) | — | 🗺(지금은 표 들여쓰기) |
| 🗺 결재 · 단계 이력 | 승인 단계 · 타임라인 | — | 🗺 |
| 🗺 역할 × 권한 표 · 일괄 처리 | 행 선택 · 일괄 행동(`DataTable` 행 선택 필요) | — | 🗺 |

## 6. 리뷰 체크리스트 (PR 마다 — [ux-heuristics §5](ux-heuristics.md#5-pr-체크리스트-복사해서-쓴다) 와 함께)
- [ ] 화면 파일에 표 · 버튼 묶음 · 상태 색 매핑을 직접 썼는가? → 컴포넌트로
- [ ] try/catch + toast 를 직접 썼는가? → `useAction`
- [ ] 로딩/빈/오류 상태를 화면에서 직접 그렸는가? → 템플릿
- [ ] 색 · 간격 값을 직접 썼는가? → 토큰
- [ ] 원시 `<button>` · `<input>` · `<select>` 를 화면에 직접 썼는가? → `Button` · 필드 컴포넌트
- [ ] 목록이 길어질 수 있는데 `Pagination` 이 없는가?
- [ ] 앱 셸(헤더 · 푸터 · 내비)을 앱 쪽에서 새로 짰는가? → `AppShell` 설정
- [ ] 웹에 만든 컴포넌트 · 템플릿의 모바일 대응이 있는가(또는 계획에 있는가)?
- [ ] 새 컴포넌트 · 화면을 만들었으면 `uv run python scripts/registry.py sync` 했는가?
