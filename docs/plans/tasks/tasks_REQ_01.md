# tasks_REQ_01 · 공통개발플랫폼 구축 — 할 일 체크리스트

계획: [plan_REQ_01 v1.1](../plan_REQ_01.md) · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일 · `~~취소~~ — 이유` 하지 않기로 함

## 1단계 · 저장소 기반 + 문서 프로세스
- [x] T01-1.01 `.gitattributes`(LF) · `.gitignore` · `.env.example` · `nova.project.json` 만들기 (파일 있음)
- [x] T01-1.02 문서 폴더와 템플릿 · 인덱스 만들기 — requirement · plans · history · git · session · reviews · verification · adr (docs_index 통과)
- [x] T01-1.03 계획 규칙 README · 계획/task 템플릿 옮기기 (§4 형식 하나)
- [x] T01-1.04 `docs_new.py` 만들기 — 번호 · 템플릿 · 인덱스 자동 (테스트 test_docs 통과)
- [x] T01-1.05 `docs_index.py --check` 만들기 (인덱스와 파일 불일치 시 실패)
- [x] T01-1.06 `git_record.py` 만들기 — 원격 URL 계산 (기록 파일 생성 확인)
- [x] T01-1.07 슬래시 명령 5개 만들기 — session-start · session-end(tasks 스캔) · req-new · plan-new · history-new
- [x] T01-1.08 `CLAUDE.md` · `README.md` 쓰기
- [x] T01-1.09 `nova.py` 진입점 만들기 (`python nova.py help` 동작)
- [x] T01-1.10 REQ-261103-01 · master_plan v1.0 · 이 계획 기록하기
- [x] 🆕 T01-1.11 REQ-261103-02 UX 휴리스틱 규칙 `ux-heuristics.md` 쓰고 계획 §4.1 · 검토 템플릿에 연결하기
- [x] 🆕 T01-1.13 REQ-261103-03 uv 전환 — 루트 pyproject · .python-version · uv.lock · nova.py install=uv sync · ADR-002
- [x] T01-1.12 1단계 커밋 · git 기록 · 푸시 (`354912f`)

## 2단계 · nova_common
- [x] T01-2.01 `nova_common` 모듈 11개 옮기고 이름 바꾸기 (import 성공)
- [x] T01-2.02 업무 결합 제거 — LEDGER 메트릭 · `_won` · DEV_FEATURES 목록 → `register_dev_feature`
- [x] T01-2.03 설정화 — ISSUER · 시간대 · 슈퍼역할 · 매 호출 env
- [x] T01-2.04 `services.json`(gateway · sample) · catalog `routes` 필드 추가
- [x] T01-2.05 `events/envelope.avsc` · README 옮기기
- [x] T01-2.06 테스트 옮기기 — test_common · test_catalog (전부 통과)
- [x] 🆕 T01-2.08 UUIDv7 — ids.py · id_column · 이벤트 ID · 샘플 · 템플릿 (REQ-261103-06, test_ids 통과)
- [x] T01-2.07 2단계 커밋 · 기록 · 푸시 (3단계와 함께 — 카탈로그 테스트가 services/ 를 요구)

## 3단계 · 서비스 골격 · 게이트웨이 · 스캐폴드
- [x] T01-3.01 게이트웨이 옮기기 — 인증 · RBAC 캐시 · 레이트리밋 · 프록시 · 모니터링, 라우트는 카탈로그에서 (테스트 통과)
- [x] T01-3.02 게이트웨이 개발용 로그인 · 메뉴 API 만들기
- [x] T01-3.03 sample 서비스 만들기 — 모듈형 레이아웃 · CRUD · 이벤트 (테스트 통과)
- [x] T01-3.04 `services/_template` · `new_service.py` 만들기 (새 서비스 테스트 통과)
- [x] T01-3.05 devstack · dev_server · run_local · local_db_setup 옮기기 (dev_server 실호출 확인 · local_db_setup 은 MariaDB 미실행 — 문법만)
- [x] T01-3.06 통합 테스트 harness · 샘플 흐름 테스트 (게이트웨이 경유 통과)
- [x] T01-3.07 `test_topic_catalog` 옮기기 (토픽 정규식은 카탈로그에서)
- [x] T01-3.08 3단계 커밋 · 기록 · 푸시

## 4단계 · 인프라 · 관측 생성기
- [x] T01-4.01 `gen_k3s.py` 일반화 — nova.project.json 에서 이름 · 레지스트리 · 도메인 (`--check` 통과)
- [x] T01-4.02 Dockerfile.service · Dockerfile.web · k3s base(kafka · mariadb · ingress) · overlays 옮기기
- [x] T01-4.03 helm/nova 옮기기
- [x] T01-4.04 관측 — RED · 이벤트 규칙 · 알림, `ServiceDown` 정규식 생성
- [x] T01-4.05 `gen_dashboards.py`(overview · events) · `validate_infra.py` 옮기기 (통과)
- [x] T01-4.06 docker-compose · e2e_kafka 옮기기 (생성 · 문법 확인 — 실제 Kafka 실행은 🆕 T01-4.08)
- [x] T01-4.07 4단계 커밋 · 기록 · 푸시
- [ ] 🆕 T01-4.08 Linux/WSL 에서 `python nova.py e2e-kafka` · `docker compose up` 실제 실행 확인

## 5단계 · 생성물 원장
- [x] T01-5.01 `registry.py` 엔진과 `registry.config.json` 분리
- [x] T01-5.02 test_registry 옮기기 (통과)
- [x] T01-5.03 초기 sync · `check` 통과
- [x] T01-5.04 5단계 커밋 · 기록 · 푸시

## 6단계 · 디자인 시스템 · 웹
- [x] T01-6.01 `brand.tokens.json` 중립 팔레트 · `gen_tokens.py` 일반화 (WCAG 통과)
- [x] T01-6.02 web workspaces · tsconfig.base 만들기
- [x] T01-6.03 `@nova/sdk` 만들기
- [x] T01-6.04 `@nova/ui` hooks — useApi · useSession · useToast · useAction · useConfirm · useQueryState
- [x] T01-6.05 `@nova/ui` components · templates — Shell · ErrorState · EmptyState · DataTable · ListPage · ConfirmDialog · 실행 취소 토스트 · 단축키 도움말
- [x] T01-6.06 샘플 앱(로그인 · 아이템 목록) 만들기 (빌드 통과)
- [x] T01-6.07 ui.md · design-system README 일반화, mockup_shots `_shell.json`
- [x] T01-6.08 샘플 앱 UX 점검(H1~H10) 기록
- [x] 🆕 T01-6.11 브라우저 스모크 `ui_smoke.py` · Playwright · `nova.py ui-smoke` (7단계 통과)
- [ ] 🆕 T01-6.10 사람 평가자 1명 휴리스틱 평가 · 행 동작 메뉴(⋯) 검토 (review_261103_01 R3 · R4)
- [x] T01-6.09 6단계 커밋 · 기록 · 푸시

## 7단계 · KMP 골격
- [x] T01-7.01 gradle 설정 · 버전 카탈로그 옮기기
- [x] T01-7.02 shared — ApiClient · Loadable 스토어 (jvmTest 통과)
- [x] T01-7.03 uikit — 생성 토큰 · 공통 컴포넌트 · rememberAction (컴파일)
- [x] T01-7.04 composeApp — 로그인 · 샘플 목록 (컴파일)
- [x] 🆕 T01-7.06 Gradle 래퍼 · nova.py kmp-build/smoke/snapshots · 실연동 스모크 · 화면 스냅샷
- [ ] 🆕 T01-7.07 Android(SDK) · iOS(macOS) 빌드 확인 — 이 PC 에서 불가
- [x] T01-7.05 7단계 커밋 · 기록 · 푸시

## 8단계 · 프로젝트 생성기 · 마무리
- [x] T01-8.01 `new_project.py` 만들기 (생성 프로젝트 test 통과)
- [x] T01-8.02 README · CLAUDE.md 최종화, 템플릿 저장소 안내
- [x] T01-8.03 history · session 기록, 마스터플랜 품질 게이트 체크
- [x] 🆕 T01-8.05 생성 프로젝트에서 다시 생성(2세대) — 브랜드 정규식 치환 · 플랫폼 원본 주소 유지
- [x] 🆕 T01-8.06 물려받은 문서의 깨진 근거 링크 → Nova 원본 저장소 주소
- [x] 🆕 T01-8.07 GitHub 저장소를 템플릿 저장소로 설정 — 사용자 요청(2026-11-04) · `gh repo edit --template` → isTemplate true · `nova.py init` · Actions 초기화 워크플로 · 리허설(init → lint 15단계 통과)
- [x] T01-8.04 8단계 커밋 · 기록 · 푸시

## 9단계 · 대장 · 표준 · 도메인 팩 (REQ-261103-04)
- [x] T01-9.01 대장 형식 판단 ADR 쓰기 — 이력 JSONL · 선언 JSON · 보기 MD
- [x] T01-9.02 화면 대장 — 화면 메타 선언(`screen` export) 스캔 · SCR ID · 라우트 · API · 테이블 · 상태
- [x] T01-9.03 DB 사전 — SQLAlchemy 메타데이터에서 1행 = 1컬럼 파생
- [x] T01-9.04 권한 대장 — 역할 정본(JSON 손 선언) · 권한키 `<도메인>.<개체>.<행위>` 파생
- [x] T01-9.05 이벤트 대장 — 토픽 카탈로그 + 발행/구독 스캔
- [x] T01-9.06 대장 생성 · `check` 드리프트 검사 · 테스트 (통과)
- [x] T01-9.07 규칙 반영 — CLAUDE.md · 계획 템플릿 §0 · §8 · plan-new
- [x] 🆕 T01-9.14 대장이 드러낸 분류 오류 수정 — restore 는 update(rbac overrides), 대장 생성기 환경 변수 누수 수정
- [x] T01-9.08 `docs/std/` 3종 + README 를 Nova 에 맞게 쓰기
- [x] T01-9.09 표준 판정 기록(`nova.project.json` standards) · lint 검사 · 계획 템플릿 §0 판정 칸
- [x] T01-9.10 `nova_common` 테넌트 컨텍스트 전파(게이트웨이 → 헤더 → 서비스 → DB) · 교차 테넌트 테스트
- [x] T01-9.11 도메인 팩 골격 `packs/<도메인>/` · 포트 레지스트리 · `scripts/packs.py new`(`python nova.py new-pack`)
- [x] T01-9.12 AX 등급 선언 · 감사 `actor_type`
- [x] T01-9.13 9단계 커밋 · 기록 · 푸시

## 작업 중 발견 (단계와 별개)
