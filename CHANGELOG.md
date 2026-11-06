# 변경 이력 (CHANGELOG)

> 생성물 — 원천은 판본 원장 `docs/releases/releases.json` 과 노트 `docs/releases/v<버전>.md`. 손으로 고치지 않는다: `python nova.py release changelog`
> 형식 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) · 번호 규칙 [판본 규약](docs/conventions/versioning.md)

## [Unreleased]

열린 판본 없음 — `python nova.py release draft <버전> --goal …`

## [0.2.0](docs/releases/v0.2.0.md) — 2026-11-06

목표: 운영 준비 판본 — 공통 모듈(공통 라이브러리 · 화면 공통 부품 · DB 마이그레이션)을 완성해 병렬 게이트를 열 수 있게 하고, 운영 배포 첫날 사고 5종을 생성물 기본값으로 막는다. nicomms 운영 콘솔 형태를 토큰 · 부품만으로 조립한다 (마스터플랜 v1.3 · 묶인 요구 REQ-261104-10 · REQ-261104-11 · REQ-261104-16)

### 추가 (Added)
- **DB 마이그레이션 체계** — `NovaBase` 제약 이름 · 플랫폼 p0001~p0004 · 서비스 분기 · `python nova.py migrate`(옛 DB baseline stamp · 잠금 · drift) — ADR-011
- **공통 라이브러리** — 중복 제거 키(consumer, idempotency_key) · 처리 기록 정리 · 격리 지표 · 재처리 `python nova.py parked` · 추적 ID · 방송 소비 · AI 쓰기 사람 승인 · 503 전환
- **운영 준비 인프라** — 운영 DB 계정 프로비저닝 Job · 일일 백업 CronJob · 서비스 단위 NetworkPolicy · 알림 수신처 이중화 · 준비 확인 DB 점검 · Helm 강화 · 신뢰 홉 · `deploy.md`
- **화면 공통 모듈** — 웹 템플릿 DashboardPage · SplitPage · SettingsPage · 헤더 유틸 · FormDialog · 폼 입력 종류(select · date · switch · checkbox) · 모바일 템플릿 ListScreen · DetailScreen · FormScreen · LoginScreen · 모바일 부품(Badge · StatusBadge solid · AiMark · DomainTag · AiConfirmCard)
- **디자인 토큰** — nicomms 갭 토큰(솔리드 상태 · 딥 사이드바 · AI · 도메인 · 차트) · **표준 디자인 킷**(`design/tokens/kits` · `python nova.py kit list|use|show` · 체크리스트 `design.kit` 선택 → `/foundation` 확인) — ADR-016
- **웹 인증 httpOnly 쿠키**(Expand · Migrate) — 로그인 쿠키 · 로그아웃 · CSRF Origin 검사 · SDK 토큰 저장 제거 — ADR-014
- **릴리스 체크포인트 · 되돌리기** — `python nova.py release checkpoint` · `release rollback`(폐기 보존 브랜치 · 코드만 되돌리는 새 커밋) — ADR-015
- **개발 도구** — 실행 스택 `stack up|status|down` · `worktree-new --scratch` · `worktree-prune` · `/task-run --auto` · `task_batch` · 검사 두 단(quick · 단계 관문) · 규모 프로파일 · 도구 호출 전 한국어 검사 훅 · 기록 문서 추적 칸 5개

### 변경 (Changed)
- 서비스 DB 는 `create_all` 대신 **마이그레이션 우선** — 기존 DB 는 첫 실행 때 baseline 으로 stamp 된다(`python nova.py migrate`)
- 웹은 토큰을 localStorage 에 두지 않고 쿠키로 — 게이트웨이 · 웹 출처 설정(`GW_CORS_ORIGINS`) 확인. 옛 `<접두어>_token` 키 삭제는 다음 판본(Contract)
- 목록 API 의 모르는 `status` 필터는 200 빈 목록이 아니라 400 `invalid_status`(정렬 오류와 같은 봉투)
- 릴리스 판정이 요구 상태의 머리말(`완료` · `적용됨`)로 — 꼬리 붙은 완료 상태도 통과
- 세션 인계 권고는 statusLine 이 남긴 실제 컨텍스트 창을 분모로 · 임계 65%

### 수정 (Fixed)
- 메모리 DB 를 배경 루프와 함께 써 생기던 간헐 실패(견본 테스트 경로) · 정리 주기 시간 의존 테스트
- Alertmanager v0.28.1(url_file 웹훅 panic) · 로그아웃 우회 응답 CORS · 로그인 CSRF
- worktree-prune 이 전체 공지를 받은함 미처리로 세던 것 · 새 프로젝트가 git 무시 파일을 옮기던 것

되돌리기: [v0.2.0 노트 §되돌리기](docs/releases/v0.2.0.md#되돌리기)

## [0.1.0](docs/releases/v0.1.0.md) — 2026-11-04

목표: Nova 공통개발플랫폼 첫 판본 — 새 프로젝트를 만들면 첫날부터 test · lint 가 녹색이고, 문서 프로세스 · 공통 코드 · 화면 규칙 · AI 축(SOUL)이 함께 선다 (마스터플랜 v1.2)

### 추가 (Added)
- **시작하는 길 둘**: `python nova.py new-project` · GitHub 템플릿(Use this template → `python nova.py init` 또는 Actions "Nova 프로젝트 초기화")
- **문서 프로세스**: 요구(INTENT · 종료 조건) → 마스터플랜(판본 봉인) → 계획 · task → 이력 · git 기록 · 세션 인수인계, 단일 기록자
- **공통 코드**: `nova_common`(서비스 · 아웃박스 · 멱등 소비 · JWT · 팩 포트) · 게이트웨이 · 샘플 · 서비스 템플릿 · `@nova/ui` · `@nova/sdk` · `kr.nova.uikit`
- **단일 원천 → 생성**: 서비스 목록 · 토픽 · 디자인 토큰(WCAG 검사) · 프로젝트 메타 · k3s/Helm/compose/관측
- **원장 · 대장**: 생성물 원장 · 대장 4종 · 명명 규약과 개념 원장 · 결함 원장 · 교훈 원장 · 릴리스 원장
- **3층 작업 체계**: 명령(30여 개) · 스킬(Nova 9) · 에이전트(폴더형 8개 폴더 · 팩마다 도메인 에이전트)
- **병렬 개발**: 병렬 게이트 · worktree · 메시지 버스 · 수렴 · 상류 판본 받기
- **고객 요구**: 체크리스트 폼 · 입고 분석 · PRD · foundation · SPEC
- **SOUL 레이어 · 한국어 규칙 훅**

### 변경 (Changed)
- 첫 판본이라 올릴 이전 판본이 없다

### 수정 (Fixed)
- 심층 감사 ① 31건(review_261104_01 §3) · 템플릿 리허설로 찾은 새 프로젝트 첫 마스터플랜 채택 멈춤 · docs → `.claude` 링크가 복사본에서 깨지던 것(이제 문서 검사가 막는다)

되돌리기: [v0.1.0 노트 §되돌리기](docs/releases/v0.1.0.md#되돌리기)
