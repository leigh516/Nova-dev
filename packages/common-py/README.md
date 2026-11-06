# nova-common — Nova 공통 라이브러리

모든 Nova 서비스가 같은 규칙으로 동작하게 하는 최소 공통 기반. 규약: [docs/conventions/backend.md](../../docs/conventions/backend.md)

| 모듈 | 제공 |
|---|---|
| `__init__.py` | 공개 이름(`Service` · `create_service` · `Principal` · `ApiError` · `principal` · `Envelope` · `EventBus` · `InMemoryBus` · `make_bus` · `emit` · `id_column` · `new_id` · `ref_column` · `catalog` · `runtime`)을 **지연 적재**(PEP 562 `__getattr__`)로 낸다 — `from nova_common import catalog` 는 fastapi · sqlalchemy 를 불러오지 않는다(스크립트 하위 프로세스 시간 절감). `from nova_common import X` 는 그대로 된다 |
| `service.py` | `create_service(name, Base, title)` — FastAPI 앱 · 수명주기 · `/healthz` `/readyz`(DB 서비스는 DB 에 못 닿으면 503 `db_unavailable`) `/metrics` · 소비 `@svc.on(topic, *, broadcast=False)`(방송은 인스턴스마다 받음 · 동기 핸들러는 스레드에서 돌아 이벤트 루프를 막지 않음) · 아웃박스 릴레이(MariaDB · PostgreSQL 은 `FOR UPDATE SKIP LOCKED` — 복제본마다 중복 발행 없음) · 처리 기록 정리 `purge_infra()` · 격리 행 `parked_rows()` · `requeue_parked(ids)` · 잡지 않은 `UpstreamError` 는 상대 4xx 그대로 · 5xx · 연결 실패 502 · 시간 초과 504 봉투 · 요청 미들웨어가 `x-request-id` 를 심고 돌려줌 · `principal(request)` → `Principal.require_human(what)`(AI 실행 거부) |
| `events.py` | `Envelope`(`trace_id` · `tenant` · `actor_type` 포함) · `EventBus` · `InMemoryBroker`/`InMemoryBus`(테스트 · 개발) · `KafkaBus`(운영 — 일반 · 방송 두 소비자, Kafka 헤더 `trace_id`) · `instance_id()` |
| `outbox.py` | `emit(session, Outbox, ...)` 트랜잭셔널 아웃박스 — 기본 중복 제거 키 `{source}:{topic}:{key}:{event_id}`(ADR-012) · 봉투에 현재 `trace_id` |
| `db.py` | `Database` (`DATABASE_URL_<SVC>` → `DATABASE_URL` → SQLite) · `ping()` · `NovaBase`(제약 이름 규칙 · 서비스마다 MetaData) · `utcnow` · `local_now` · `add_infra_tables` |
| `clients.py` | 서비스 간 동기 호출 `call(svc, method, path)`(공유 연결 사용 · 4xx · 5xx 는 `UpstreamError`, 연결 실패 `UpstreamUnavailable`, 시간 초과 `UpstreamTimeout`) · 공유 연결 `pooled(service)` · 종료 시 `aclose_all()` · 테스트용 `override` |
| `validate.py` | 입력 공통 검증 — `EMAIL_PATTERN` · `Email`(Annotated — 앞뒤 공백 제거 · 소문자 · 254자 상한) · `EMAIL_MAX` |
| `catalog.py` | `services.json` 읽기 · `routes()` · `route_for(path)` · CLI `python -m nova_common.catalog names` |
| `auth.py` | HS256 JWT `encode` · `decode` (`JWT_SECRET` · `JWT_ISSUER`) |
| `runtime.py` | `NOVA_ENV` · `register_dev_feature` · 운영 안전장치(fail-closed) · `super_role` · `tz_offset_hours` |
| `metrics.py` | Prometheus 메트릭(접두어 `nova_`) |
| `context.py` | 요청 컨텍스트 — `current_tenant()` · `current_actor_type()` · `current_trace_id()` · `trace_from_header(value)` · `scope(tenant, actor_type, *, trace_id)` · `tenant_filter(…)` · `headers()`(`x-request-id` 전파) |
| `packs.py` | 도메인 팩 포트 — `@port(name)` · `@implement(name)` · `get(name)` · `load(package)` · `active()` (STD-DOMAIN-PACK-001) |
| `paging.py` | 목록 API 계약 `paginate(session, query, page: Page, *, sortable, to_dict)` → `{items, total, page, size}` · 허용 밖 정렬은 400 `invalid_sort` |
| `ids.py` | UUIDv7(RFC 9562) — `new_id()` · `id_column()` · `ref_column()` · `uuid7_time()` · `require_uuid7(value)`(정규형이 아니면 404 — 조회 전에) (ADR-003) |
| `seed.py` | 시드 JSON 로더(부르는 곳 없음 — 연결 · 제거는 T03-9.02) |
| `migrate.py` | 마이그레이션 — 플랫폼(`p000N`) + 서비스(`s000N`) 분기 · `upgrade`(MariaDB 는 `GET_LOCK` `<서비스>:migrate` 안에서 — 복제본 동시 기동에도 한 번만, 못 얻으면 기동 실패) · `migration_lock(conn, service)` · `status` · `drift` · `new_revision` · `platform_head()` · 명령 `python -m nova_common.migrate <svc> up · status · new`(= `python nova.py migrate`) (ADR-011) |
| `outbox_admin.py` | 격리 행 재처리 명령 `python -m nova_common.outbox_admin <svc> list · requeue (--id N … 또는 --all)`(= `python nova.py parked`) |

## 환경 변수
| 변수 | 기본 | 뜻 |
|---|---|---|
| `NOVA_ENV` | dev | prod 이면 안전장치 · 개발 기능 꺼짐 |
| `NOVA_ALLOW_SQLITE` | (없음) | 1 이면 운영에서도 SQLite 허용(단일 노드 시연) |
| `JWT_SECRET` · `JWT_ISSUER` | 개발 키 · nova | 토큰 |
| `NOVA_SUPER_ROLE` | admin | 모든 역할 검사 통과 |
| `NOVA_TZ_OFFSET_HOURS` | 9 | 업무 벽시계 시간대 |
| `KAFKA_BOOTSTRAP` | (없음) | 있으면 Kafka, 없으면 메모리 버스 |
| `DATABASE_URL_<SVC>` · `DATABASE_URL` | SQLite | DB |
| `SVC_<SVC>_URL` | `http://<svc>:8000` | 서비스 간 호출 주소 |
| `NOVA_SKIP_LIFESPAN` | - | 1 이면 수명주기 생략(단일 프로세스 개발 서버) |
| `NOVA_PACKS` · `NOVA_PACKS_ROOT` | (없음) · 위로 찾기 | 켜진 도메인 팩 · packs/ 폴더 위치 |
| `OUTBOX_RETENTION_DAYS` · `PROCESSED_EVENT_RETENTION_DAYS` | 7 · 14 | 보낸 발행 행 · 처리 기록을 남기는 날 수(처리 기록은 토픽 최대 보존일보다 길어야 한다) |
| `NOVA_PURGE_INTERVAL` | 3600 | 정리 주기(초) — 0 이하이면 배경 정리 끔 |
| `NOVA_MIGRATE_LOCK_TIMEOUT` | `migrate.MIGRATE_LOCK_TIMEOUT` | 기동 마이그레이션 잠금을 기다리는 초(MariaDB) — 넘으면 기동 실패 |
| `KAFKA_INSTANCE_ID` | HOSTNAME → 임의 | 방송 소비 그룹 `<서비스>.<인스턴스>` |
| `OUTBOX_RELAY_INTERVAL` · `OUTBOX_MAX_ATTEMPTS` · `LOG_LEVEL` · `ROOT_PATH` · `SEED_PATH` | | |
