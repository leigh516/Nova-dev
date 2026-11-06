# 결정 기록 (ADR) 인덱스

되돌리기 어려운 구조 결정만 기록한다. 새 ADR: `uv run python scripts/docs_new.py adr "<제목>"`. 결정이 바뀌면 지우지 말고 새 ADR 로 대체하고 옛 ADR 상태를 `대체됨(→ ADR-NNN)` 으로 바꾼다.

| ADR | 일자 | 제목 | 상태 |
|---|---|---|---|
| [ADR-001](ADR-001-platform-baseline.md) | 2026-11-03 | 플랫폼 기준 스택과 원칙 | 채택 |
| [ADR-002](ADR-002-python-env-uv.md) | 2026-11-03 | Python 환경 관리 도구 uv | 채택 |
| [ADR-003](ADR-003-uuid-v7-ids.md) | 2026-11-03 | 식별자는 UUID version 7 | 채택 |
| [ADR-004](ADR-004-ledger-formats.md) | 2026-11-04 | 대장 형식 — 이력 JSONL · 선언과 상태 JSON · 보기 MD | 채택 |
| [ADR-005](ADR-005-superpowers-workflow.md) | 2026-11-04 | Superpowers 를 작업 방법론으로 채택 | 채택 |
| [ADR-006](ADR-006-product-canonical-json.md) | 2026-11-04 | 제품 정본 PRD · SPEC 은 JSON, 출고본은 파생 | 채택 |
| [ADR-007](ADR-007-soul-layer.md) | 2026-11-04 | SOUL 레이어 — 정체성 · 말투를 저장소에 두고 자동 로딩 · 훅으로 강제 | 채택 |
| [ADR-008](ADR-008-parallel-bus-release.md) | 2026-11-04 | 병렬 개발 · 메시지 버스 · 종료 조건 · 릴리스 · 마스터플랜 봉인 — psg05 의 핵심만 | 채택 |
| [ADR-009](ADR-009-commands-skills-agents.md) | 2026-11-04 | 명령 · 스킬 · 에이전트 3층 작업 체계 | 채택 |
| [ADR-010](ADR-010-agent-folders.md) | 2026-11-04 | 에이전트 폴더형 편제 — psg05 역할을 폴더로 묶어 대부분 살린다 | 채택 |
| [ADR-011](ADR-011-migrations-alembic.md) | 2026-11-04 | 마이그레이션 체계 — Alembic 플랫폼 · 서비스 분기 | 채택 |
| [ADR-012](ADR-012-event-dedup-503-ax.md) | 2026-11-04 | 이벤트 중복 제거 키 · 권한 원천 장애 503 · AI 쓰기 범위 | 채택 |
| [ADR-013](ADR-013-sample-table-fix.md) | 2026-11-05 | 샘플 표 구조 정정 — 활동 UUIDv7 기본키 · 테넌트 · recorded_at · 참조 칸 | 채택 |
| [ADR-014](ADR-014-web-httponly-cookie.md) | 2026-11-05 | 웹 인증을 httpOnly 쿠키로 단일화 | 채택 |
| [ADR-015](ADR-015-rolled-back.md) | 2026-11-06 | 릴리스 체크포인트와 되돌리기 — rolled_back 재도입 | 채택 |
| [ADR-016](ADR-016-nicomms-g1.md) | 2026-11-06 | 디자인 킷 축 — 토큰 한 벌 덮어쓰기 · nicomms G1 해소 | 채택 |
