# DB 사전 (1행 = 1컬럼)

> 생성 파일 — `uv run python scripts/ledgers.py` 가 코드에서 파생한다(ADR-004). 직접 고치지 않는다 — 원천(코드 · 선언)을 고친다.

현재 상태의 조회용 정본 — `grep <컬럼>` 으로 바로 찾는다. '의미'는 모델의 `mapped_column(comment=…)`. 소유 서비스만 쓰고, 다른 서비스는 API · 이벤트로만 접근한다(backend.md §2).
공통 표(`outbox` · `processed_event`)는 모든 DB 서비스에 같은 모양으로 있다 — 맨 아래 한 번만 적는다.

| 표 | 컬럼 | 타입 | 의미 | 제약 | 소유 서비스 |
|---|---|---|---|---|---|
| item | id | VARCHAR(36) | 항목 식별자(UUIDv7) | PK | sample |
| item | tenant_id | VARCHAR(40) | 테넌트(STD-TENANCY-001) | INDEX NULL | sample |
| item | name | VARCHAR(100) | 항목 이름 | — | sample |
| item | memo | TEXT | 메모 | NULL | sample |
| item | status | VARCHAR(20) | 상태 active\|archived | INDEX | sample |
| item | created_at | DATETIME | 만든 시각(UTC) | — | sample |
| item | created_by | VARCHAR(36) | 만든 사용자 | NULL | sample |
| item | updated_at | DATETIME | 고친 시각(UTC) | — | sample |
| item | updated_by | VARCHAR(36) | 고친 사용자 | NULL | sample |
| item_activity | id | VARCHAR(36) | 활동 식별자(UUIDv7) | PK | sample |
| item_activity | tenant_id | VARCHAR(40) | 테넌트(STD-TENANCY-001) | INDEX NULL | sample |
| item_activity | item_id | VARCHAR(36) | 대상 항목(item.id) | INDEX | sample |
| item_activity | kind | VARCHAR(40) | 활동 종류 created\|archived\|restored | — | sample |
| item_activity | event_id | VARCHAR(36) | 원인 이벤트 ID(멱등 추적) | — | sample |
| item_activity | recorded_at | DATETIME | 기록 시각(UTC) | — | sample |

## 공통 표 (모든 DB 서비스)

| 표 | 컬럼 | 타입 | 의미 | 제약 |
|---|---|---|---|---|
| outbox | id | INTEGER | 일련번호 | PK |
| outbox | event_id | VARCHAR(40) | 이벤트 ID(UUIDv7) | UNIQUE |
| outbox | topic | VARCHAR(120) | 토픽 | INDEX |
| outbox | key | VARCHAR(80) | 파티션 키(집계 ID) | — |
| outbox | payload | JSON | 봉투 전체(JSON) | — |
| outbox | created_at | DATETIME | 적재 시각(UTC) | — |
| outbox | sent_at | DATETIME | 발행 시각 — 비면 미발행 | INDEX NULL |
| outbox | attempts | INTEGER | 발행 시도 횟수 | — |
| outbox | last_error | TEXT | 마지막 발행 오류 | NULL |
| outbox | is_parked | BOOLEAN | 독 메시지 격리(재처리 대기) | INDEX |
| processed_event | event_id | VARCHAR(40) | 처리한 이벤트 ID | PK |
| processed_event | consumer | VARCHAR(80) | 소비 서비스 | PK |
| processed_event | topic | VARCHAR(120) | 토픽 | — |
| processed_event | idempotency_key | VARCHAR(320) | 중복 제거 키(봉투 idempotency_key) | NULL |
| processed_event | is_ok | BOOLEAN | 처리 성공 | — |
| processed_event | processed_at | DATETIME | 처리 시각(UTC) | — |
