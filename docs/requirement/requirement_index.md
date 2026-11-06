# 요구사항 인덱스

새 요구는 `uv run python scripts/docs_new.py req "<제목>"` 로 만든다(번호·인덱스 자동). 상태: 진행 중 · 완료 · 적용됨(상시 규칙) · 보류 · 취소

| ID | 일자 | 제목 | 상태 | 계획 |
|---|---|---|---|---|
| [REQ-261103-01](requirement_261103_01.md) | 2026-11-03 | 공통개발플랫폼 구축 — dayroom2 공통부 추출 | 진행 중 | [plan_REQ_01](../plans/plan_REQ_01.md) |
| [REQ-261103-02](requirement_261103_02.md) | 2026-11-03 | UI/UX 규칙 — 닐슨 10대 휴리스틱과 보완 절차 | 적용됨(상시 규칙) | [ux-heuristics](../conventions/ux-heuristics.md) |
| [REQ-261103-03](requirement_261103_03.md) | 2026-11-03 | Python 가상환경은 uv 로 관리 | 적용됨(상시 규칙) | [ADR-002](../adr/ADR-002-python-env-uv.md) |
| [REQ-261103-04](requirement_261103_04.md) | 2026-11-03 | project-start-guide-05 registry 대장 · docs/std 표준 채택 | 완료 | [plan_REQ_01](../plans/plan_REQ_01.md) 9단계 |
| [REQ-261103-05](requirement_261103_05.md) | 2026-11-03 | 모든 대화와 기록은 한국어 | 적용됨(상시 규칙) | [CLAUDE.md](../../CLAUDE.md) |
| [REQ-261103-06](requirement_261103_06.md) | 2026-11-03 | DB UUID 는 version 7 | 적용됨(상시 규칙) | [ADR-003](../adr/ADR-003-uuid-v7-ids.md) |
| [REQ-261104-01](requirement_261104_01.md) | 2026-11-04 | Superpowers 설치 · 활용 — 고객 인터뷰 · 요구 분석부터 전 과정 | 적용됨(상시 규칙) | [superpowers](../conventions/superpowers.md) |
| [REQ-261104-02](requirement_261104_02.md) | 2026-11-04 | 자료 창고 입고 분석 → 부족분 인터뷰 → PRD · foundation · SPEC | 적용됨(상시 규칙) | [product](../product/README.md) |
| [REQ-261104-03](requirement_261104_03.md) | 2026-11-04 | 요구 체크리스트 — 클릭형 계층 폼 · 자료 역분석 자동 채움 · json + md | 적용됨(상시 규칙) | [checklist](../warehouse/inbound/checklist/README.md) |
| [REQ-261104-04](requirement_261104_04.md) | 2026-11-04 | 체크리스트 확장 — 기술 결정 · 설명 · 원본 질의 반영 · 건너뛰기 스위치 · 임시저장 | 적용됨(상시 규칙) | [checklist](../warehouse/inbound/checklist/README.md) |
| [REQ-261104-05](requirement_261104_05.md) | 2026-11-04 | 체크리스트 디자인 보완 — 색 견본 · 직접 지정 · 세밀 조정 · 대비 · 미리보기 · 디자인 질의 확장 | 적용됨(상시 규칙) | [checklist](../warehouse/inbound/checklist/README.md) |
| [REQ-261104-06](requirement_261104_06.md) | 2026-11-04 | 체크리스트 — 목업 채택 · 화면 부품 고르기/요청 · Nova 보기(실제 모습) · 외부 디자인 · 스킬 채택 | 적용됨(상시 규칙) | [checklist](../warehouse/inbound/checklist/README.md) |
| [REQ-261104-07](requirement_261104_07.md) | 2026-11-04 | 다축 심층 감사 명령 /deep-audit — psg05 를 Nova 에 맞게 | 적용됨(상시 규칙) | [superpowers](../conventions/superpowers.md) |
| [REQ-261104-08](requirement_261104_08.md) | 2026-11-04 | SOUL 레이어 · PROJECT · INTENT — psg05 를 Nova 에 맞게 | 적용됨(상시 규칙) | [ADR-007](../adr/ADR-007-soul-layer.md) |
| [REQ-261104-09](requirement_261104_09.md) | 2026-11-04 | 병렬 개발 · 메시지 버스 · 종료 조건(exit) · 버전 릴리스 · 마스터플랜 판본 봉인 | 적용됨(상시 규칙) | [ADR-008](../adr/ADR-008-parallel-bus-release.md) |
| [REQ-261104-10](requirement_261104_10.md) | 2026-11-04 | 감사 후속 ① 운영 · 인프라 준비 (R1~R5 · P6) | 완료(종료 조건 충족 2026-11-04 · v0.2.0 대상) | [review_261104_01](../reviews/review_261104_01.md) |
| [REQ-261104-11](requirement_261104_11.md) | 2026-11-04 | 감사 후속 ② 공통 라이브러리 · 계약 보강 (R6~R12 · P1 · P4 · P8 · P10) | 완료(종료 조건 충족 2026-11-04 · v0.2.0 대상) | [review_261104_01](../reviews/review_261104_01.md) |
| [REQ-261104-12](requirement_261104_12.md) | 2026-11-04 | 감사 후속 ③ 화면 · 모바일 · 보안 · 데이터 정리 (R13~R16 · P2 · P3 · P5 · P7 · P9) | 승인됨(v0.2.0 대상) | [review_261104_01](../reviews/review_261104_01.md) |
| [REQ-261104-13](requirement_261104_13.md) | 2026-11-04 | psg05 명령 · 스킬 · 에이전트를 Nova 에 맞게 채택 · 연결 | 적용됨(상시 규칙) | [ADR-009](../adr/ADR-009-commands-skills-agents.md) |
| [REQ-261104-14](requirement_261104_14.md) | 2026-11-04 | 명명 규약 · 분야별 확장 · 개념 원장 — psg05 를 Nova 에 맞게 | 적용됨(상시 규칙) | [naming](../conventions/naming.md) |
| [REQ-261104-15](requirement_261104_15.md) | 2026-11-04 | GitHub 템플릿 저장소로 새 프로젝트 시작 | 적용됨 | [README](../../README.md) |
| [REQ-261104-16](requirement_261104_16.md) | 2026-11-04 | nicomms 갭 채택 — 토큰 5 · 부품 7 · DashboardPage (v0.2.0) | 완료 | [design-system](../design-system/README.md) |
| [REQ-261104-17](requirement_261104_17.md) | 2026-11-04 | 개발 속도 보정 — 검사 두 단 · 기록 크기 맞춤 · git 기록 푸시 묶음 | 승인됨 | - |
| [REQ-261104-18](requirement_261104_18.md) | 2026-11-04 | 요구 체크리스트 보강 — 디자인 · 화면 부품 선택지 확장 · 부품 원천 대조 · AI · 비기능 · 데이터 문항 | 승인됨 | - |
| [REQ-261105-01](requirement_261105_01.md) | 2026-11-05 | 도구 호출 직전 진행 알림의 영어 줄을 막는 장치(PreToolUse 훅) | 완료 | [plan_REQ_06](../plans/plan_REQ_06.md) |
| [REQ-261105-02](requirement_261105_02.md) | 2026-11-05 | 교훈 원장을 JSONL 원천 + MD 보기로 바꾸고 승급 흐름을 soul-review 에 잇기 | 승인됨 | - |
| [REQ-261105-03](requirement_261105_03.md) | 2026-11-05 | 리뷰 · 감사 · 작업 중 발견의 개선에 목표 · 완료 조건 · 하지 않는 것과 한 세대 규칙 두기 | 적용됨(상시 규칙) | [plans README §5](../plans/README.md) |
| [REQ-261105-04](requirement_261105_04.md) | 2026-11-05 | 모든 기록 문서에 원천 · 저장 위치 · 연결 문서 · 생성일 추적 칸 두기 | 완료 | - |
| [REQ-261105-05](requirement_261105_05.md) | 2026-11-05 | 공통개발플랫폼 적합성 보강 — 전체 분석 반영 | 승인됨 | [plan_REQ_07](../plans/plan_REQ_07.md) |
| [REQ-261105-06](requirement_261105_06.md) | 2026-11-05 | 판본 릴리스 체계 — SemVer 규칙 · 최신 정식 릴리스에서 시작 · 마스터플랜 연결 · CHANGELOG | 진행 중 | - |
| [REQ-261105-07](requirement_261105_07.md) | 2026-11-05 | psg05 훅 채택 — 비밀 읽기 금지 · 되돌림 · 셸 쓰기 · SOUL 편집 · 호출 기록 · 컨텍스트 인계 · 세션 스냅샷 | 진행 중 | - |
| [REQ-261105-08](requirement_261105_08.md) | 2026-11-05 | 에이전트 운영 보완 — 검토 보고서 파일 · 모델 등급 · 호출 기록 원장 · 운영 가이드 | 구현 완료(E1 · E2 · E3 녹색 2026-11-05 · E4 사람 확인 대기) | [agents.md](../conventions/agents.md) |
| [REQ-261105-09](requirement_261105_09.md) | 2026-11-05 | 계획 자동 진행 — main 운전자 · 병렬 배치 · 재개 · 안전장치 | 승인됨(2026-11-05) | [plan_REQ_08](../plans/plan_REQ_08.md) |
| [REQ-261105-10](requirement_261105_10.md) | 2026-11-05 | 개발 속도 — 테스트 병렬 · 원격 CI · 검토 무게 · 실행 환경 자동화 · 병렬 게이트 · 플랫폼 개선 동결 | 진행 중 | - |
| [REQ-261106-01](requirement_261106_01.md) | 2026-11-06 | 메시지 버스 문서 · 동작 정합 — 끝내기 권한 · escalation 덮어쓰기 · 자동 발송 · 표시 상태 | 적용됨 · E3 확인 대기 | - |
| [REQ-261106-02](requirement_261106_02.md) | 2026-11-06 | 릴리스 관리 보완 — 체크포인트 · 되돌리기 · 판본 작게 자주 | 진행 중 | - |
| [REQ-261106-03](requirement_261106_03.md) | 2026-11-06 | 리버스 엔지니어링 도구 REA 도입 — 대상 분석 결과를 입고 자료로 | 진행 중 | - |
| [REQ-261106-04](requirement_261106_04.md) | 2026-11-06 | 표준 디자인 킷 — 킷 선택 · 토큰 한 벌 · 체크리스트 채택(newtype) | 진행 중 | - |
