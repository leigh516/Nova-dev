# tasks_REQ_04 · 화면 · 모바일 · 보안 · 데이터 정리 — 할 일 체크리스트

계획: [plan_REQ_04 v1.0](../plan_REQ_04.md) · 화면 미리보기는 계획 §4 · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일 · `~~취소~~ — 이유` 하지 않기로 함
서비스 테스트는 서비스 폴더에서 돌린다: `cd services/<이름> && uv run pytest tests/<파일>::<이름>`

## 1단계 · 결정 · ADR · 목업 (구현 전 관문)
- [x] T04-1.01 ([ADR-013](../../adr/ADR-013-sample-table-fix.md) 채택 2026-11-05) 샘플 표 구조 정정 ADR 본문 초안 쓰기 (main 이 `docs_new.py adr` 로 번호 · 사용자 확인)
  - 내용: item_activity UUIDv7 기본키 · tenant_id · at→recorded_at(API 키 포함) · created_by/updated_by ref_column · 개발 DB 재생성 근거(운영 데이터 없음 · R6 이전) · 되돌리기
- [x] T04-1.02 ([ADR-014](../../adr/ADR-014-web-httponly-cookie.md) 채택 2026-11-05) 웹 인증 httpOnly 쿠키 단일화 ADR 본문 초안 쓰기 (사용자 확인)
  - 내용: HttpOnly · SameSite=Lax · Path=/v1 · 운영 Secure · Max-Age=토큰 수명 · Origin 검사(CSRF) · 와일드카드 CORS 거부 · 모바일 Bearer 유지 · Expand→Migrate→Contract · 같은 사이트 배포 전제 · 되돌리기
- [x] T04-1.03 (2026-11-04 결정 — kotlinx-datetime 0.6.1, 요구 '확인한 결정') KMP 시간대 의존성 결정 받기 (A kotlinx-datetime 0.6.1 / B expect·actual — 요구 '미결 질문'에 답 기록)
- [x] T04-1.04 (2026-11-04 결정 — 1~7단계 녹색 뒤 · 토큰 7일 유지, 요구 '확인한 결정') R16 전환 시점 · 토큰 수명(7일 유지 여부) 결정 받기 (요구 '미결 질문'에 답 기록)
- [x] T04-1.05 항목 상세 목업 만들기 (`docs/plans/mockups/REQ_04/app-item-detail.html` — 상한 안내 · '보관 풂' 기록을 mock-new 로 → `python nova.py mockups` PNG 를 직접 열어 확인)
- [x] T04-1.06 로그인 목업 만들기 (`docs/plans/mockups/REQ_04/app-login.html` — 이메일 형식 칸 오류 → PNG 확인)
- [x] T04-1.07 운영 모니터링 목업 만들기 (`docs/plans/mockups/REQ_04/app-ops.html` — 상태 배지 라벨 · 스켈레톤 → PNG 확인)
- [x] T04-1.08 (2026-11-05 — 평가자 2명: 평가자 2 통과 · 평가자 1 심각도 3 1건(운영 화면 갱신 시각이 aria-live 안 · 멈춤 없음, WCAG 2.2.2) → DashboardPage 에서 시각을 알림 영역 밖으로 · 자동 갱신 멈춤 버튼 추가로 고침. 심각도 2 는 🆕 T04-9.11) 계획 §4.1 UX 점검표를 목업 PNG 로 확인하기 (심각도 3 이상 0 · 평가자 2명 — ux-heuristics)

## 2단계 · 샘플 데이터 모델 (P2 · P5 — REQ-261104-12-5 · 7)
- [x] T04-2.01 item_activity 기본키를 id_column 으로 바꾸기 (test_activity_pk_is_uuid7 통과)
  - 파일: 고치기 `services/sample/sample/models.py` · 테스트 `services/sample/tests/test_items.py`
  - 인터페이스: 내주는 것 `ItemActivity.id: str`(UUIDv7)
  - [ ] 실패 테스트 작성 → `uv run pytest tests/test_items.py::test_activity_pk_is_uuid7` 실패 확인
  - [ ] 최소 구현 → 같은 명령 통과 확인
- [x] T04-2.02 item_activity 에 tenant_column 추가하고 소비자가 봉투 tenant 를 저장하기 (test_activity_records_event_tenant 통과)
  - 파일: 고치기 `models.py` · `items.py`(record_activity) · 테스트 `test_items.py`
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-2.03 상세 조회가 활동을 tenant_filter 로 거르기 (test_activity_tenant_isolation 통과 — 같은 item_id 를 가진 다른 테넌트 활동이 섞이지 않음)
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-2.04 at 을 recorded_at 으로 바꾸고 정렬을 (recorded_at, id) 로 하기 (API 키 `recorded_at` · test_activity_order_recorded_at 통과)
  - 인터페이스: 내주는 것 응답 `activity: [{kind, recorded_at}]`
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-2.05 웹 · KMP 가 응답 키 recorded_at 을 쓰게 맞추기 (`web/apps/app/lib/app.ts` Item 타입 · items/[id]/page.tsx · KMP Model.kt `@SerialName("recorded_at")` · `web-build` · `kmp-test` 통과)
- [x] T04-2.06 샘플 · 템플릿 created_by · updated_by 를 ref_column(nullable=True, index=False) 로 바꾸기 (test_items · tests/test_new_service.py 통과)
  - 파일: 고치기 `services/sample/sample/models.py` · `services/_template/__PKG__/models.py`
- [x] T04-2.07 naming.json 에 참조 칸 형식 column_ref 넣기 (_id · _by 로 끝나는 칸 → VARCHAR(36), 예외 tenant_id(tenant_column 헬퍼 — 별도 요구) · baseline outbox.event_id · processed_event.event_id, baseline 128-129 두 줄 삭제 · `python nova.py naming --write` · `naming check` 통과 · tests/test_naming.py 에 검출 테스트)
  - [ ] 실패 테스트(String(40) 의 created_by 를 잡는다) → 실패 확인 · [ ] 구현 → 통과
- [x] T04-2.08 (2026-11-05 — 이 PC MariaDB 에 Nova 스키마 `nova` · `nova_sample` 없음을 확인 · 표 변경은 마이그레이션 s0002 로 · DROP 불필요 · 메모리 DB 재기동으로 GET /v1/sample/items 200 확인) 개발 DB 재생성하기 (메모리 · sqlite 는 재기동만, 개발 MariaDB 는 sample 스키마 item · item_activity 를 DROP 한 뒤 재기동 — **사용자 확인 후** · `dev_server.py` 기동 뒤 GET /v1/sample/items 200)
- [x] T04-2.09 원장 · 대장 다시 만들기 (`registry.py sync --by <이름> --note "REQ-261104-12 P2 · P5"` → `ledgers.py` → db-dictionary 에 tenant_id · recorded_at · VARCHAR(36) 확인)

**단계 관문**: `python nova.py quick --stage T04-2` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 3단계 · 샘플 이벤트 (P3 — REQ-261104-12-6)
- [x] T04-3.01 kafka-topics.txt 에 sample.item.restored · sample.item.deleted 넣고 생성물 다시 만들기 (`python nova.py gen` · tests/test_topic_catalog.py 통과)
- [x] T04-3.02 보관 풀기가 sample.item.restored 를 한 번만 내기 (멱등 키 `sample:<토픽>:<id>:<updated_at>` · test_restore_emits_restored_once 통과 — 이미 active 면 이벤트 없음)
  - 파일: 고치기 `services/sample/sample/items.py`(T_RESTORED) · 테스트 `test_items.py`
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-3.03 소비자가 restored 를 활동으로 기록하기 (test_consumer_records_restored 통과 · kind comment 에 restored 추가)
- [x] T04-3.04 삭제가 같은 트랜잭션에서 활동을 지우고 sample.item.deleted 를 내기 (test_delete_removes_activity_and_emits_deleted 통과)
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-3.05 소비자가 없는 항목의 늦은 이벤트를 건너뛰기 (test_late_event_after_delete_is_skipped 통과 — 활동 0 · 처리 기록은 남음)
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-3.06 웹 · KMP 활동 라벨에 restored '보관 풂' 넣기 (lib/app.ts ACTIVITY_LABEL · Screens.kt ACTIVITY_LABEL · web-build · kmp-build 통과)
- [x] T04-3.07 통합 흐름 테스트에 보관 풀기 · 삭제 넣고 원장 · 이벤트 대장 갱신하기 (tests/integration/test_sample_flow.py 통과 · `registry.py sync` · `ledgers.py` — events.md 에 restored 구독 sample · deleted 구독 —)

**단계 관문**: `python nova.py quick --stage T04-3` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 4단계 · 서버 계약에서 생성 (P9 — REQ-261104-12-9)
- [x] T04-4.01 nova_common 에 이메일 공통 검증 만들기 (`nova_common/validate.py` EMAIL_PATTERN · `Email` Annotated 타입 — 앞뒤 공백 제거 · 소문자 · 254자 상한 · packages/common-py/tests/test_validate.py 통과)
  - 인터페이스: 내주는 것 `EMAIL_PATTERN: str`(JS · Kotlin 정규식과 호환되는 부분만) · `Email`
  - [ ] 실패 테스트(" User@Nova.dev " 통과 · "user@" 거부) → 실패 확인 · [ ] 구현 → 통과
- [x] T04-4.02 게이트웨이 개발 로그인이 Email 타입으로 받기 (형식 오류는 422 invalid_input + fields · test_gateway::test_login_rejects_malformed_email 통과)
- [x] T04-4.03 계약 생성기 만들기 (`scripts/gen_contract.py` — 서비스 OpenAPI 의 문자열 min/maxLength + EMAIL_PATTERN → `web/apps/app/lib/contract.gen.ts` · `web/packages/sdk/src/validate.gen.ts` · `apps/kmp/shared/src/commonMain/kotlin/kr/nova/shared/Contract.kt`, 머리에 '생성 파일' 표시 · tests/test_gen_contract.py 통과)
  - 인터페이스: 내주는 것 `LIMITS.ItemIn.name.maxLength` · `EMAIL_PATTERN`(TS) · `Contract.ITEM_NAME_MAX` · `Contract.EMAIL_PATTERN`(Kotlin)
  - [ ] 실패 테스트(생성 결과 · --check 불일치 검출) → 실패 확인 · [ ] 구현 → 통과
- [x] T04-4.04 gen_contract 를 gen · lint 에 연결하기 (nova.py cmd_gen · cmd_lint `--check` · `python nova.py lint` 통과)
- [x] T04-4.05 항목 만들기 화면이 생성 상한을 쓰게 하기 (items/new/page.tsx 의 손 숫자 100 · 2000 제거 · web-build 통과)
- [x] T04-4.06 LoginPage 가 공통 이메일 패턴으로 검사하기 (칸 오류 "이메일 형식이 아닙니다. 예: name@example.com" · ui_smoke 에 단계 추가 · 목업 app-login 과 비교)
- [x] T04-4.07 KMP 새 항목 이름 · 로그인 이메일이 생성 상한 · 패턴을 쓰게 하기 (shared Validate.kt + ValidateTest.kt · `kmp-test` · `kmp-build` 통과)

**단계 관문**: `python nova.py quick --stage T04-4` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 5단계 · 화면 토큰 정리 (R14 · R15 — REQ-261104-12-2 · 3) — plan_REQ_05 토큰 작업과 직렬
- [x] T04-5.01 토큰 밖 값 검사기 만들기 (`scripts/ui_check.py` + 선언 `web/ui-check.json`(예외 · 이유 필수) — tsx 의 hex · rgb() · hsl() · style 의 px 숫자, css 의 var() 밖 색 · tests/test_ui_check.py 통과 · 지금 위반 목록 출력)
  - [ ] 실패 테스트(위반 견본 파일을 잡는다 · 이유 없는 예외 거부) → 실패 확인 · [ ] 구현 → 통과
- [x] T04-5.02 대화상자 배경 막 색을 토큰으로 옮기기 (brand.tokens.json `color.overlay.scrim` → `python nova.py tokens` · styles.css:155 rgba 제거)
- [x] T04-5.03 layout.tsx themeColor 를 처리하기 (Next 메타는 CSS 변수를 못 받는다 → ui-check.json 예외 1건 + 값이 color.bg.canvas(dark)와 같은지 ui_check 가 확인)
- [x] T04-5.04 템플릿 · 컴포넌트의 인라인 px 를 클래스 · 간격 토큰으로 바꾸기 (pages.tsx · AppShell.tsx · feedback.tsx · DataTable.tsx · extras.tsx — 필요한 클래스는 styles.css 에 var(--space-*) 로)
- [x] T04-5.05 앱 화면의 인라인 px 를 클래스로 바꾸기 (page.tsx · help · design · items/[id] · ops — `--gap` 값도 var(--space-*))
- [x] T04-5.06 운영 화면 로딩 · 오류를 템플릿으로 옮기기 (선행: plan_REQ_05 DashboardPage · 화면에서 Skeleton · ErrorState 직접 호출 0)
- [x] T04-5.07 운영 화면 상태 → 색을 StatusBadge 매핑으로 바꾸고 ui_check 를 lint 에 연결하기 (lib/app.ts OPS_HEALTH · SERVICE_UP · ALERT_SEVERITY · nova.py cmd_lint · `python nova.py lint` 위반 0)
- [x] T04-5.08 출고 HTML 색을 토큰에서 만들기 (warehouse.py CSS 가 gen_tokens 값으로 :root `--color-*`(light · dark)를 만들고 본문은 var(--color-…) — tests/test_warehouse.py::test_outbound_css_uses_tokens 통과)
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-5.09 출고본을 다시 만들고 토큰 변경을 check 가 잡는지 확인하기 (`warehouse.py out` · test_check_detects_token_change 통과 · `nova.py gen` 에 warehouse out 이 없으면 넣을지 판단해 기록) — 2026-11-05: 실제 출고본 재생성 차이 0 · test_warehouse 9 통과(새 테스트는 5.08 동작을 묶는 확인 테스트라 처음부터 녹색) · gen 에는 이미 있음(`nova.py:234`) — 넣을 것 없음
- [x] T04-5.10 ui-smoke 를 돌리고 운영 · 상세 캡처를 목업과 비교하기 (데모 로그인 빌드 3100 포트 · docs/screenshots 갱신) — 2026-11-05: 게이트웨이 8091 · 웹 3100 · ui-smoke 16단계 통과(종료 0) · 운영은 ui-smoke 가 user 권한 없음만 보므로 관리자 데모 로그인으로 따로 찍음(라이트 · 다크 · 콘솔 오류 0) — 구조 일치(요약 3칸 · 서비스 표 · 갱신 시각), 데이터만 다름(개발 서버 2서비스 · 알림 없음). 상세는 구조 일치 · 활동 순서만 달라 §12.1 대로 목업을 서버 순서(오래된 것 위)로 고쳐 PNG(라이트 · 다크) 다시 찍음

**단계 관문**: `python nova.py quick --stage T04-5` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 6단계 · 성능 (P7 — REQ-261104-12-8) — 측정 → 고침 → 측정
- [x] T04-6.01 측정 스크립트 만들기 (`scripts/perf_probe.py` — 활동 500건 항목 상세 · 프록시 200회 · 운영 개요(가짜 Prometheus 지연 50ms) · 메뉴 200회의 p50 · p95, 읽기 전용 · 출력만)
- [x] T04-6.02 고치기 전 수치 재기 (출력을 main 이 docs/verification 에 기록)
- [x] T04-6.03 상세 활동 목록 상한 50 넣기 (`ACTIVITY_LIMIT = 50` 최신순 · 응답 `activity_truncated: bool` · test_detail_activity_capped 통과)
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-6.04 상세 화면에 상한 안내 넣기 (웹 "최근 50건만 보입니다" · KMP 같은 문구 · 목업 app-item-detail 과 비교 · web-build · kmp-build 통과)
- [x] T04-6.05 서비스 간 HTTP 연결을 공유 클라이언트로 재사용하기 (`clients.pooled(service) -> httpx.AsyncClient` · `clients.aclose_all()` 을 종료 시 · override 유지 · common test_clients_pooled 통과) — REQ-261104-11 R11 과 같은 파일, 병합 순서 확인
  - [ ] 실패 테스트(같은 서비스 = 같은 객체 · 닫으면 새로 만듦) → 실패 확인 · [ ] 구현 → 통과
- [x] T04-6.06 게이트웨이 프록시 · 메트릭 수집이 공유 클라이언트를 쓰게 하기 (routing.py:343 · monitoring.py:80 · test_gateway 전부 통과 · 504/502 테스트 그대로)
- [x] T04-6.07 Prometheus 질의 9개를 클라이언트 하나로 한꺼번에 병렬로 내기 (monitoring.py:31·228-235 · test_prom_queries_concurrent — 가짜 트랜스포트의 최대 동시 수 9)
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-6.08 menu.json 파싱을 파일 수정 시각 기준으로 캐시하기 (권한 거르기는 요청마다 그대로 · test_menu_cache_reload_on_mtime 통과)
- [x] T04-6.09 고친 뒤 수치를 재고 전후 표를 넘기기 (perf_probe 같은 조건 · main 이 docs/verification 에 전후 표)

**단계 관문**: `python nova.py quick --stage T04-6` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 7단계 · 모바일 (R13 — REQ-261104-12-1)
- [x] T04-7.01 KMP 공통 시각 표시 fmtAt 만들기 (`apps/kmp/shared/src/commonMain/kotlin/kr/nova/shared/Format.kt` `fmtAt(iso: String?, tz: TimeZone = 기기 시간대): String` — 웹 sdk fmtAt 과 같은 형식 · Z 없으면 UTC · FormatTest.kt: "2026-11-03T05:05:00Z" + Asia/Seoul → "2026-11-03 14:05" · `kmp-test` 통과)
  - 선행: T04-1.03 결정(A면 shared 에 datetime 의존 연결)
  - [ ] 실패 테스트 → `python nova.py kmp-test` 실패 확인 · [ ] 구현 → 통과
- [x] T04-7.02 화면의 take(16) 3곳을 fmtAt 으로 바꾸기 (Screens.kt:107·129·133 · `kmp-build` 통과 · 화면 코드에 take( 0)
- [x] T04-7.03 화면 스택을 shared BackStack 으로 옮기기 (`BackStack<T>` push · pop · reset · canPop — BackStackTest.kt 통과)
  - [ ] 실패 테스트 → 실패 확인 · [ ] 구현 → 통과
- [x] T04-7.04 시스템 뒤로 가기를 연결하기 (composeApp commonMain `expect fun PlatformBackHandler(enabled: Boolean, onBack: () -> Unit)` · androidMain = androidx.activity.compose.BackHandler · desktop · ios = 빈 구현 · App.kt 에서 canPop 일 때만 활성 · `kmp-build` 통과)
- [x] T04-7.05 폼 단위 오류를 화면 읽기 프로그램에 알리기 (Components.kt 오류 문구 liveRegion = Polite · 로그인 실패 문구 · `kmp-build` 통과)
- [x] T04-7.06 kmp-test · kmp-build · kmp-snapshots 를 돌려 화면 PNG 갱신하기 (kmp-item-detail.png 의 시각이 현지 시각) — 2026-11-05: jvmTest · compileKotlinDesktop BUILD SUCCESSFUL · snapshots OK(게이트웨이 8091 · gradlew 에 `-Papi=http://127.0.0.1:8091/v1` 직접 — 🆕 T05-9.01 그대로) · kmp-item-detail.png 에 "2026-11-05 11:31"(KST — 촬영 시각 UTC 02:31) 직접 확인
- [ ] T04-7.07 Android 에뮬레이터에서 뒤로 가기 · 현지 시각 · TalkBack 오류 읽기 확인하기 (E4 사람 판정 — 이 PC 는 Android SDK 없음, SDK 있는 환경에서 '충족 YYYY-MM-DD')

**단계 관문**: `python nova.py quick --stage T04-7` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 8단계 · 웹 인증 httpOnly 쿠키 (R16 — REQ-261104-12-4) — Expand → Migrate → Contract
- [x] T04-8.01 (Expand) 게이트웨이 로그인이 httpOnly 쿠키를 내려 주기 (`nova_token` HttpOnly · SameSite=Lax · Path=/v1 · Max-Age=토큰 수명 · `GW_COOKIE_SECURE`(운영 기본 켬) · 본문 token 유지 · test_login_sets_httponly_cookie 통과)
  - 파일: 고치기 `services/gateway/gateway/main.py` · 테스트 `services/gateway/tests/test_gateway.py`
  - [x] 실패 테스트 → 실패 확인 · [x] 구현 → 통과
- [x] T04-8.02 /auth 소유 서비스로 넘긴 로그인 응답에서도 쿠키 심기 (응답 본문 token 으로 · test_proxied_login_sets_cookie 통과 — clients.override)
- [x] T04-8.03 POST /v1/auth/logout 만들기 (쿠키 Max-Age=0 · 비로그인도 204 · test_logout_clears_cookie 통과 · registry sync API) — API-GW-0009 · 깨진 · 만료 쿠키로도 204(쿠키를 지울 길을 막지 않음 — 우회에도 CORS 헤더)
- [x] T04-8.04 쿠키로 인증된 쓰기 요청은 Origin 이 허용 목록일 때만 받기 (403 csrf_origin 한국어 문구 · Bearer 는 면제 · test_cookie_write_requires_allowed_origin · test_bearer_exempt_from_origin 통과)
  - [x] 실패 테스트(허용 · 없음 · 다른 출처 · Bearer 4형) → 실패 확인 · [x] 구현 → 통과
- [x] T04-8.05 GW_CORS_ORIGINS 에 `*` 가 있으면 기동 거부하기 (test_cookie_mode_refuses_wildcard_cors 통과) — 2026-11-05 8.01~8.05: 커밋 18bd2bc · 697950e · test_gateway 54 통과(main 재실행) · task 검토 요구 ✅ · 중요 1 고침 · 경미 6 은 최종 검토에서 분류
- [x] T04-8.06 (Migrate) SDK 가 credentials:"include" 로 보내고 토큰을 저장 · 전송하지 않게 하기 (session.token · Bearer 헤더 제거 · 남은 `<접두어>_token` 키 지우기 · login 은 본문 token 무시 · web-build 통과)
- [x] T04-8.07 세션 사용자 확인을 /v1/me 로 하기 (providers.tsx · RequireAuth — 표시용 사용자 캐시만 두고 시작 시 /me 로 확인 · 401 이면 비움 · 하이드레이션 경고 0)
- [x] T04-8.08 로그아웃이 /v1/auth/logout 을 부르게 하기 (AppShell.tsx · sdk logout() async · 실패해도 화면 상태는 비움) — 2026-11-05 8.06~8.08: 커밋 6ed0d94 · 데모 로그인 빌드 통과 · task 검토 승인(경미 3 — 최종 검토에서 분류) · 하이드레이션 경고 0 은 8.09 ui-smoke 콘솔 오류 0 으로 확인
- [x] T04-8.09 ui-smoke 에 쿠키 확인 넣기 (document.cookie 에 nova_token 없음 · localStorage 에 _token 없음 · 새로고침 뒤 로그인 유지 · 로그아웃 뒤 /v1/me 401 · ui-smoke 통과) — 2026-11-05: 커밋 ed49c80 · ui-smoke 17단계 통과(종료 0 · `--api http://localhost:8091/v1` · 새 단계 cookie-session) · task 검토는 8단계 최종 검토에 묶음
- [x] T04-8.10 배포 안내 기록하기 (웹 · 게이트웨이는 같은 사이트 · GW_COOKIE_SECURE · GW_CORS_ORIGINS 정확한 출처 · 다른 사이트면 새 요구 — backend.md 보안 절 · 릴리스 노트 '알려진 것'에 Contract 미룸) — 2026-11-05: backend.md §5.1 · v0.2.0 노트 파일이 아직 없어 판본 정본 `releases.json` v0.2.0 `not_doing` 에 Contract 미룸(노트를 만들 때 '알려진 문제'로 옮겨짐) · release check · docs_index 통과
- [x] T04-8.11 인증 경계 보안 검토 받기 (security-auditor — 쿠키 속성 · CSRF · CORS 재현 경로 · 치명 0) — 2026-11-05: 치명 0 · 중요 2 → 로그인 CSRF 는 고침(007a474 · 익명 로그인 · 로그아웃도 Origin 있으면 허용 목록 · 개발 로그인 JSON 전용 415 · 재검토 처리됨 · test_gateway 56 통과) · 브라우저 응답 본문 token 은 Contract 로(🆕 9.12) · 경미는 9.05 에서 분류 · 보고서 `.claude/state/reports/t04-8.11-*.md` · 단계 관문: 전체 check 에서 test 1 · lint 1 실패(같은 원인 — 아래 🆕 9.13) → 생성물 재생성 뒤 test_checklist 15 통과 · lint 통과

**단계 관문**: `python nova.py quick --stage T04-8` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 9단계 · 마무리 · 종료 조건
- [x] T04-9.01 생성물 · 원장 · 대장 다시 만들고 lint 돌리기 (`python nova.py gen` · `registry.py sync` · `ledgers.py` · E2 `python nova.py lint` 통과)
- [x] T04-9.02 전체 테스트 돌리기 (E1 `python nova.py test` 통과)
- [x] T04-9.03 데모 로그인 빌드로 ui-smoke 돌리고 캡처를 목업과 비교하기 (E3 통과 · 다른 점은 계획 §12.1 에)
- [x] T04-9.04 종료 조건 판정하기 (`python nova.py exit-check REQ-261104-12` — E4 는 T04-7.07 사람 판정 대기로 표시)
- [x] T04-9.05 코드 검토 받기 (/review-request — code-reviewer 전 범위 + R16 은 T04-8.11 결과 첨부 · docs/reviews/) — 2026-11-05: 8단계 브랜치 전체 최종 검토(opus · 보고서 `.claude/state/reports/t04-9.05-final-review.md`) "고친 뒤 병합" 치명 0 · 중요 2 → 병합 전 4건 고침(93bf568 · 6144c56 — 문서 정합 · 스모크 /me 대조와 새 탭 · prod Secure 시험 · 캐시 id 비교) · 재검토 4건 처리됨 · ui-smoke 17단계 · lint 통과 · test 는 test_migrate_cli 1건이 하위 프로세스 비정상 종료(0xC0000005)로 실패 → 같은 파일 3회 재실행 모두 통과 · 이 브랜치는 공통 라이브러리 · 샘플 변경 0(🆕 9.14) · 경미는 다음 판본(보고서 분류 표). 번호 기록 review 문서는 /round-close 에서

## 작업 중 발견 (단계와 별개)
- [x] 🆕 T04-9.01 (감사 L-F1) 받은함 전체 수신(`--to *`) 메시지를 한 세션이 끝내면(`done`) 모든 세션의 받은함에서 사라진다 — 재현: 두 worktree 에 `*` 로 보내고 하나에서 done · 기대: 끝낸 세션에서만 닫힘(받는 사람마다 처리 상태) · 실제: 전체에서 사라짐(재현됨) · 환경: `scripts/collab.py`(review_261104_02)
- [x] 🆕 T04-9.02 (감사 L-F3) 수렴(converge) 범위 검사를 파일 이름 바꾸기(rename)로 우회한다 — 재현: 묶음 경로 밖 파일을 경로 안으로 git mv · 기대: 옛 경로도 범위 검사에 걸림 · 실제: 통과(재현됨) · 환경: `scripts/parallel.py` converge(review_261104_02)
- [x] 🆕 T04-9.03 (감사 L-F10) P0 결함을 deferred 로 돌려 출시 관문을 우회한다 — 기대: P0 는 deferred 로 바꿀 수 없거나 사람 승인 기록이 있어야 함 · 실제: 상태만 바꾸면 release 판정 통과 · 환경: `scripts/issues.py` · `scripts/release.py`(review_261104_02)
- [x] 🆕 T04-9.04 (감사 S2) 템플릿 초기화가 git 무시 파일(.env · data/ 등)까지 지운다 — 기대: 무시 파일은 남기고 추적 파일만 바꿈 · 실제: 지움 · 환경: `scripts/template_init.py`(review_261104_02)
- [x] 🆕 T04-9.05 (ui_smoke '진행 중 버튼 — 포커스 유지 · aria-busy · 중복 호출 없음' RED → GREEN · web-build 통과) (감사 A-F1 · UX-H1 · 3) 진행 중 `disabled` 버튼이 포커스를 잃는다 — 기대: `aria-disabled` + 클릭 막기로 포커스 유지 · 화면 읽기 프로그램에 진행 중 알림 · 실제: 키보드 사용자의 포커스가 문서 처음으로 · 환경: `web/packages/ui` Button · `useAction`(review_261104_02)
- [x] 🆕 T04-9.06 (2026-11-05 — git 무시 경로를 복사에서 뺀다 · 추적 전 새 파일은 옮긴다(upstream 과 같은 경계) · `tests/test_new_project_copy.py` 3건) (T04-9.04 형제) `new_project.create()` 가 빠질 폴더 목록(SKIP_DIRS) 방식이라 git 무시 파일(.env · .collab/ · .claude/settings.local.json)을 새 프로젝트로 옮긴다 — 기대: 추적 파일만 복사 · 실제: 무시 파일도 복사 · 환경: `scripts/new_project.py:40-56`(T04-9 담당 보고)
- [ ] 🆕 T04-9.07 열린 P0 결함이 있을 때 `release ship` 을 막을지 — 막으려면 핫픽스 패치 릴리스를 예외로 둘 규칙이 먼저(새 요구 후보 · 게이트 의미 변경이라 사용자 결정, T04-9 담당 보고)
- [ ] 🆕 T04-9.08 (T04-9.05 형제 · 모바일) KMP `NovaButton` 이 `enabled = enabled && !loading` — 진행 중 포커스를 잃는 같은 형태(`apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt:56` · `:64` · `:68`). 기대: 진행 중에도 포커스 유지 · 중복 호출 막기 · kmp-build 통과
- [x] 🆕 T04-9.09 (2026-11-04 즉시 고침 — 빌드 번들에 지정 주소 0곳 → 1곳) `@nova/sdk` 가 `process.env[k]` 로 동적으로 읽어 Next 빌드에 `NEXT_PUBLIC_API_BASE` · `STORAGE_PREFIX` · `LOCALE` · `TIMEZONE` · `CURRENCY` 가 들어가지 않았다 — 운영 웹이 늘 `localhost:8080` 으로 요청 · 복제본이 저장 키 `nova_` 를 공유(감사 C-F10 의 한 원인). 글자 그대로의 참조로(`web/packages/sdk/src/index.ts`)
- [ ] 🆕 T04-9.10 웹 부품 테스트 틀이 없다(jest · vitest 없음) — T04-9.05 · 9.09 를 브라우저 스모크 · 빌드 번들 검사로만 확인했다. 기대: sdk 의 env 참조 · Button 진행 중 동작을 단위 테스트로(의존성 추가라 사용자 결정)
- [ ] 🆕 T04-9.14 (판정: 다음 판본 — 같은 파일 3회 재실행 통과) `tests/test_migrate_cli.py::test_up_then_status` 가 전체 테스트 중(부하 · 배경 에이전트 동시) 하위 프로세스 `python -m nova_common.migrate sample up` 비정상 종료(반환 3221225477 = 0xC0000005 접근 위반)로 실패 — 2026-11-05 1회 · 지난 세션 관문에서도 이 파일 실패 기록 · 기대: 부하 아래에서도 결정적 · 조사 후보: Windows 에서 sqlite · 하위 프로세스 동시 실행, 테스트 시간 72초(느림 — slow 표시 여부) · 환경: `tests/test_migrate_cli.py:38`
- [x] 🆕 T04-9.13 (2026-11-06 REQ-261105-10-4 에 흡수 — `nova.py ui-smoke` 가 캡처가 바뀌면 `checklist.py build` · `warehouse.py out` 을 자동으로 돌린다 · E5 실행에서 29장 갱신 뒤 폼 재생성 확인 · git_261106_01) (판정: 다음 판본 — 이번은 생성기를 돌려 고침) ui-smoke 가 `docs/screenshots` 를 갱신하면 그것을 그림으로 품는 생성물 `checklist.html`(inbound · outbound)이 낡는데, nova-ui-verify 절차 · quick 이 알려 주지 않는다 — 재현: ui-smoke 실행 → 캡처 커밋 → 전체 check 에서 test_repo_checklist_is_valid · checklist · warehouse 드리프트 실패 · 기대: 캡처를 바꾸면 `checklist.py build` · `warehouse.py out` 안내(또는 quick 이 screenshots 변경에 checklist 검사를 붙임) · 환경: `scripts/ui_smoke.py` · `scripts/checklist.py` · `scripts/quick_check.py`(2026-11-05 8단계 관문)
- [ ] 🆕 T04-9.12 (판정: 다음 판본 — ADR-014 Contract 단계, 응답 계약 변경) (T04-8.11 보안 검토 중요 1) 로그인 응답 본문의 `token` 이 브라우저 요청에도 실린다 — 재현: XSS 가 fetch 를 가로챈 채 강제 로그아웃 → 사용자가 다시 로그인하면 본문 token(7일) 탈취 · 기대: Origin 이 있는 요청(브라우저)에는 본문에서 token 을 빼고 모바일(Origin 없음)만 유지 · 환경: `services/gateway/gateway/main.py` 로그인 · 위임 로그인 · 보고서 `.claude/state/reports/t04-8.11-security.md`
- [ ] 🆕 T04-9.11 (판정: 다음 판본 — T04-1.08 심각도 2 묶음) 상세 '최근 50건' 안내에 다음 행동이 없음(H10) · ~~활동 순서 목업(최신 위) ↔ 서버(오래된 것 위)~~(T04-5.10 에서 목업을 서버 순서로 맞춤)와 `lib/app.ts:25` 주석 '최신부터' 어긋남 · 운영 요약 '주의' ↔ 알림 '위험' 상충(H1) · 운영 스켈레톤 4칸 ↔ 실제 3칸 · 로그인 목업에 아이디 저장 · 찾기 링크 없음 · 목업 셸에 헤더 검색 없음
