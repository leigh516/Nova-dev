# tasks_REQ_07 · 공통개발플랫폼 적합성 보강 — 할 일 체크리스트

| 항목 | 값 |
|---|---|
| 문서 ID | tasks_REQ_07 |
| 생성 | 2026-11-05 · `docs_new.py plan` |
| 위치 | `docs/plans/tasks/tasks_REQ_07.md` |
| 원천 | [review_261105_02](../../reviews/review_261105_02.md) |
| 연결 | [plan_REQ_07](../plan_REQ_07.md) · [REQ-261105-05](../../requirement/requirement_261105_05.md) |

계획: [plan_REQ_07 v1.0](../plan_REQ_07.md) · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일(판정 `지금 — <깨는 종료 조건>` / `다음 판본`) · `~~취소~~ — 이유`

## 0단계 · 보안 치명
- [x] T07-0.01 (2026-11-05 — `tests/test_infra.py::test_helm_chart_has_same_service_netpols` · validate_infra 렌더 검사 · 실제 helm template 렌더 확인) Helm 차트에 서비스 단위 NetworkPolicy 를 같은 원천에서 생성하기 (`tests/test_infra.py` — 차트 렌더에 서비스마다 게이트웨이 · allow_from 만 여는 정책 · validate_infra 통과)

**단계 관문**(단계 마지막 task 뒤 한 번): `python nova.py quick --stage T07-0` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 1단계 · 다중 복제본 안전장치 · 이벤트 루프
- [x] T07-1.01 기동 마이그레이션을 잠금으로 감싸기 (MariaDB `GET_LOCK` · SQLite 는 건너뜀 · `packages/common-py/tests/test_migrate_lock.py`)
- [x] T07-1.02 아웃박스 릴레이가 행을 `FOR UPDATE SKIP LOCKED` 로 집기 (SQLite 는 그대로 · `packages/common-py/tests/test_outbox_relay.py`)
- [x] T07-1.03 소비 · 릴레이 · 정리의 DB 부분을 `asyncio.to_thread` 로 넘기기 (동기 핸들러 계약 유지 · `packages/common-py/tests/test_event_loop_free.py` — 느린 핸들러 중에도 `/healthz` 응답)
- [x] T07-1.04 서비스 간 호출 4xx 를 오류 봉투로 그대로 전달하고 `call()` 이 공유 연결을 쓰게 하기 (`packages/common-py/tests/test_clients.py`)
- [x] T07-1.05 DB 연결 예산을 생성기가 계산해 MariaDB 상한을 넘으면 멈추기 (`tests/test_infra.py`)

**단계 관문**: `python nova.py quick --stage T07-1` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 2단계 · 운영 기본값
- [ ] T07-2.01 공통 접속기록 미들웨어 넣기 (계정 · 시각 · 출발지 · 경로 · 결과 · actor_type · tenant · request id, 본문 제외 · 구조화 로그 · `packages/common-py/tests/test_access_log.py`)
- [x] T07-2.02 운영 매니페스트에 `NOVA_ENV=prod` 를 넣고 운영 렌더에 없으면 실패하게 하기 (로컬 `nova.py run` 은 그대로 dev · `tests/test_infra.py`)
- [ ] T07-2.03 (선행: 운영 기동 검사 `runtime.py:73-75` 가 모든 서비스에 JWT 키를 요구 — 먼저 그 검사를 키를 쓰는 서비스로 좁히는 일이 필요, 2026-11-05 담당 보고) 서명 키를 게이트웨이(와 `/auth` 소유 서비스)에만 주입하기 (`tests/test_infra.py`)
- [x] T07-2.04 운영 인그레스에 TLS 블록 · HTTPS 전용 · HSTS 넣기 (`tests/test_infra.py`)
- [x] T07-2.05 observability 허용을 Prometheus · Alertmanager 파드로 좁히기 (`tests/test_infra.py`)
- [x] T07-2.06 백업 CronJob 실패 경보 넣기 (kube-state-metrics 없으면 Job 실패를 Pushgateway 없이 잡는 방법을 먼저 정하고 — 못 하면 판정 불가로 남김 · `tests/test_infra.py`)
- [x] T07-2.07 deploy.md 에 '첫 배포 준비' 절과 `gen_k3s --list-secrets` 넣기 (`tests/test_infra.py`)

**단계 관문**: `python nova.py quick --stage T07-2` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 3단계 · 화면 공통 (tasks_REQ_04 웹 · KMP 담당이 끝난 뒤)
- [x] T07-3.01 폼 입력 종류에 select · switch · checkbox · date 넣기 (`FormField` 값 타입 확장 · FormPage · FormDialog · ui-smoke 단계) — 2026-11-06 `form.tsx` 종류별 타입 · `checkField` · `useFormModel<V>` · FormPage · FormDialog 제네릭 · 갤러리 '폼 입력 종류' · ui-smoke `design-form-kinds` · web-build 통과 · ui-smoke 전체 18단계 통과(main 재실행) · 웹 단위 테스트 틀 없음(T04-9.10)
- [ ] T07-3.02 SDK 가 FormData 를 보내고 blob 을 받게 하기 (`web/packages/sdk` · typecheck · web-build)
- [x] T07-3.03 모바일 템플릿 ListScreen · DetailScreen · FormScreen · LoginScreen 만들기 (상태 3종 내장 · composeApp 화면이 템플릿 호출로 · kmp-build · kmp-snapshots) — 2026-11-06 `uikit/Templates.kt` · shared `ViewPhase` · `FormModel` · 앱 로그인 · 목록 · 상세가 템플릿 호출(`SignInScreen` 개명) · kmp-test 48 통과(main 재실행) · kmp-build · 스냅숏 9장 판정(담당)
  - [ ] 🆕 T07-3.03a 모바일 템플릿 남은 형 — FormScreen 서버 칸별 오류(422) · ListScreen 검색 · 쪽 나눔 · 내보내기 · LoginScreen 아이디 저장 · ErrorState 두 줄 정렬 (판정: 다음 판본 — 웹 대응은 있어 묶음끼리 갈라지지 않는 보강)
- [ ] T07-3.04 화면 대장이 모바일 화면도 모으기 (`@screen` 머리 주석 · `scripts/ledgers.py` · `tests/test_ledgers.py`)
- [ ] T07-3.05 ui.md 를 실제와 맞추기 (모바일 템플릿 상태 · `HelpLink` · `useToast` · 빠진 부품 이름 · 흔한 화면 5유형 🗺 행 — 숫자 박지 않기)

**단계 관문**: `python nova.py quick --stage T07-3` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 4단계 · 프로세스 · 원격 CI
- [ ] T07-4.01 원격 CI 워크플로 만들기 (PR · 푸시에 `nova.py check`, 태그 `v*` 에 서비스 · 웹 이미지 빌드 — 푸시는 레지스트리 설정이 있을 때만 · 복제본이 물려받음 · `tests/test_new_project.py` 에서 워크플로 존재 확인)
- [ ] T07-4.02 `nova.py check` 가 축별 소요 시간을 찍게 하기 (`tests/test_nova_cli.py` 또는 기존 테스트)
- [ ] T07-4.03 tasks ID 중복을 `quick_check --check-tasks` 가 잡게 하기 (`tests/test_quick_check.py`)
- [ ] T07-4.04 마무리 흐름에서 check 를 한 번만(같은 커밋에서 이미 녹색이면 건너뜀) — `/docs-write` · `/finish` · `/round-close` 문서와 `docs_write.py` (`tests/test_docs_write.py`)
- [ ] T07-4.05 `docs-write grade` 가 규모 프로파일의 이력 하한을 읽게 하기 (`tests/test_profile.py`)
- [ ] T07-4.06 DB 칸 '추가'(nullable)는 [보통], 지우기 · 이름 · 형 바꾸기만 [DEEP] 으로 superpowers.md 크기 판정 고치기
- [ ] T07-4.07 마스터플랜 공통 영역 'CI' 줄의 증거를 원격 CI 로 바꾸기 (`masterplan` 규칙대로 — 판본 변경이 필요하면 drafts 초안)
- [ ] T07-4.08 상류 기준선을 원격에 있는 커밋으로 정하기 (`new_project.upstream_meta` 가 `merge-base HEAD origin/main` · 원격에 없으면 경고 · `tests/test_new_project_copy.py`)
- [ ] T07-4.09 미커밋 작업이 있으면 공통부 목록을 경고하고 생성 결과에 기록하기 (복사는 지금처럼 — Claude 판단: 거부보다 되돌리기 쉬움 · `tests/test_new_project_copy.py`)
- [ ] T07-4.10 복제본에서 Nova 기록 지우기 — `docs/releases/v*.md` · `.claude/soul/USER.md` 를 자리표시로 · 교훈 근거를 원본 링크로 · `--remote` 없으면 `image_registry` 를 비우고 doctor 가 경고 (`tests/test_new_project.py` 확인 항목 추가)
- [ ] T07-4.11 첫 걸음 안내를 하나로(`/kickoff`) 맞추고 `new-service --group` 허용값 · kickoff 의 프로파일 문장 상충 고치기 (문서 · 출력 문구)

**단계 관문**: `python nova.py quick --stage T07-4` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 5단계 · 갈림길 결정 받기 (결정 전 구현하지 않는다)
- [ ] T07-5.01 D1 인증 — 직접 iam 서비스 vs 외부 OIDC 결정 받기 → ADR · 새 요구
- [ ] T07-5.02 D2 · D3 다중 프로젝트 — 클러스터 분리 vs slug 네임스페이스, DB 이름 `<slug>_<svc>` 통일 결정 받기
- [ ] T07-5.03 D4 · D5 공통 기능 · 개인정보 — 감사 표 · 파일 · 스케줄 · 알림 · 칸 암호화 · 가림 · 보관 기간 결정 받기
- [ ] T07-5.04 D6 · D7 · D8 · D9 — 토큰 수명 · CI 비용 · 화면 유형 우선순위 · 로그 백엔드 결정 받기

## 작업 중 발견 (단계와 별개)
- [ ] 🆕 T07-9.01 (판정: 다음 판본 — 병렬 게이트가 열릴 때) psg05 `.claude/workflows/open-round.mjs`(병렬 회차 묶음마다 원장 등록 → 충전 → 커밋 → worktree → 카드 → 상태를 순서대로)를 Nova `/dispatch` · `/worktree-new` 위에 워크플로로 얹을지 검토. 2026-11-05 대조: `gates-parallel` · `drive-phase` · `record-req` 는 Nova 의 `check` · `quick --stage` · `docs_new` 가 같은 일을 해서 채택 안 함
