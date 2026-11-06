# 백엔드 규약 (서비스 · 이벤트 · DB · API)

## 1. 서비스 구조
- 서비스 목록의 단일 원천: `packages/common-py/nova_common/services.json`. 추가 · 통합 · 이름 변경은 여기만 고치고 `uv run python scripts/gen_k3s.py` 로 인프라를 다시 만든다
- 새 서비스는 직접 만들지 않고 `python nova.py new-service <이름> --group <그룹> --scope <범위>`
- 패키지 레이아웃(모듈형, `services/_template` 이 원본):
  ```
  services/<svc>/<pkg>/models.py   Base(NovaBase) + ORM 모델 — 제약 이름 규칙 · 서비스마다 자기 MetaData(§4)
  services/<svc>/<pkg>/app.py      svc = create_service("<svc>", Base, "<제목>"); app = svc.app
  services/<svc>/<pkg>/<기능>.py   router = APIRouter(); @router.get(...); @svc.on("<토픽>")
  services/<svc>/<pkg>/main.py     기능 모듈 import + app.include_router(...)  ← 진입점 <pkg>.main:app
  services/<svc>/migrations/       env.py(run_env 한 줄) · versions/0001_initial.py … — 서비스 분기(§4)
  services/<svc>/tests/            conftest.py(DATABASE_URL_<SVC>=sqlite://) · test_*.py
  ```
  import 순서 `models → app → 기능 → main` 으로 순환 import 를 막는다
- 진입점 `<pkg>.main` 은 `app` 과 `svc` 를 반드시 export 한다(devstack · 카탈로그 테스트가 의존)

## 2. 경계 원칙
- 서비스는 **자기 DB 만** 쓴다. 다른 서비스 표를 조인 · 조회하지 않는다
- 동기 호출: `nova_common.clients.call("<svc>", "GET", "/internal/...")` — 내부 API 는 `/internal/` 접두어, 게이트웨이가 외부로 노출하지 않는다
- 직접 호출은 `k8s.allow_from` 에 올린 서비스만 — 아니면 운영에서 막힌다. 받는 서비스의 `services.json` `k8s.allow_from` 에 부르는 서비스 이름을 적는다(서비스 단위 NetworkPolicy `allow-<서비스>` 가 게이트웨이 · 허용 목록 · 관측만 들인다. 목록에 없는 이름은 `gen_k3s` 가 멈춘다)
- 비동기: 이벤트. 다른 서비스 상태를 바꾸고 싶으면 이벤트를 발행하고 그 서비스가 소비한다
- 코드 · 상태값은 설정 API 에서 읽는다(enum 하드코딩 금지)

## 3. 이벤트
- 토픽 이름: [naming.md](naming.md) §3.2(3단 과거형 · 테넌트는 봉투). f-string 금지(정적 검사 대상)
- 모든 토픽은 `infra/k3s/base/kafka-topics.txt` 에 등록(`이름 파티션 보존일`). `<토픽>.dlq` 는 자동
- 발행은 반드시 아웃박스: `svc.emit(session, topic, key, data)` — 같은 트랜잭션에서 업무 데이터와 함께 커밋
- 소비는 `@svc.on(topic)` — `processed_event` 로 멱등. 한 토픽에 핸들러 여러 개 가능(한 트랜잭션)
- **중복 제거 키는 봉투 `idempotency_key`** — 소비 측은 (소비 서비스, `idempotency_key`)가 이미 기록돼 있으면 건너뛴다(동시에 두 인스턴스가 처리해 UNIQUE 가 충돌해도 중복으로 본다 · [ADR-012](../adr/ADR-012-event-dedup-503-ax.md))
  - 기본값은 `{source}:{topic}:{key}:{event_id}` — 이벤트마다 다르다. 그래서 키를 주지 않으면 **같은 이벤트의 재전달만** 걸러지고, 같은 집계의 다음 이벤트는 버려지지 않는다
  - 같은 업무 사건이 다른 이벤트로 다시 발행될 수 있으면(재시도 · 재발행) **업무 키를 명시**한다: `svc.emit(s, topic, key, data, idempotency_key=f"sample:{T_UPDATED}:{item.id}:{item.updated_at.isoformat()}")`. 키에 집계 ID 만 넣으면 그 집계의 두 번째 이벤트가 조용히 사라진다
  - `idempotency_key` 칸이 빈 옛 처리 기록은 `event_id` 로 판정한다 — 다음 판본(Contract)에서 대체 판정을 지우고 NOT NULL 로 조인다
- 실패 3회 → `<topic>.dlq`. 핸들러는 **같은 이벤트를 두 번 받아도 결과가 같게** 쓴다
- 봉투(`Envelope`): `id · type · source · key · idempotency_key · occurred_at · version · trace_id · tenant · actor_type · data`. 스키마 변경은 하위 호환(새 필드는 기본값), 필드 삭제 · 타입 변경 · 의미 변경은 새 토픽(봉투 `version` 도 올린다 — `packages/common-py/events/README.md`)

### 3.1 추적 ID — 요청 → 서비스 호출 → 이벤트 → 소비 (REQ-261104-11-6)
- 헤더 이름은 `x-request-id` 하나다(W3C `traceparent` 는 추적 백엔드와 함께 정한다 — 범위 밖). 손으로 나르지 않는다 — 테넌트 · 행위자와 같은 길로 자동 전파된다
- **들어올 때**: 게이트웨이(`new_request_id`)와 서비스 공통 미들웨어가 `context.trace_from_header(값)` 으로 정한다. 형식 `[A-Za-z0-9-]{8,64}` 에 맞으면 그대로, 없거나 형식 밖이면 새 ID(UUIDv7) — 추적 실패가 요청 실패가 되지 않게 거절하지 않고 바꾼다. 게이트웨이는 정한 ID 를 요청 헤더에 다시 심어 자신의 원천 호출(권한 · 플래그)도 같은 ID 로 나가게 한다
- **응답**: 게이트웨이 · 서비스 모두 응답 헤더 `x-request-id` 로 돌려준다 — 사용자가 알려 준 ID 로 로그를 찾는다
- **서비스 간 호출**: `clients.call` 이 `context.current_trace_id()` 를 헤더 `x-request-id` 로 붙인다
- **이벤트**: `svc.emit` 이 봉투 `trace_id` 에 현재 추적 ID 를 넣고, Kafka 발행은 같은 값을 메시지 헤더 `trace_id` 로도 붙인다(봉투를 풀지 않는 도구 — kcat · UI — 에서 찾게). 소비는 봉투 `trace_id` 로 `context.scope(..., trace_id=)` 를 열어 핸들러 안의 emit · clients.call 이 같은 ID 를 잇는다
- `context.scope()` 에 `trace_id` 를 주지 않으면 그 블록의 추적 ID 는 없음(None)이다 — 바깥 값을 물려받지 않는다(테넌트와 같은 방식). 배경 작업에서 추적을 잇고 싶으면 명시로 준다

### 3.2 방송 구독 — 복제본마다 받는 토픽 (REQ-261104-11-4)
- 일반 구독 `@svc.on(topic)` 은 소비자 그룹 = 서비스 이름이라 **서비스당 한 번** 받는다. 권한 · 플래그 캐시 무효화처럼 **모든 복제본이 알아야 하는 일**은 `@svc.on(topic, broadcast=True)` 로 구독한다 — 그룹이 `<서비스>.<인스턴스>` 라 복제본마다 받는다
- 인스턴스 이름: `KAFKA_INSTANCE_ID` → `HOSTNAME`(파드 이름) → 임의 값 순. 임의 값이면 재시작마다 새 그룹이 생기고, 비어 남은 그룹은 Kafka 가 `offsets.retention.minutes`(기본 7일) 뒤 지운다
- 시작 위치는 **latest** — 새 복제본은 기동할 때 원천(권한 표 · 플래그)을 처음부터 받으므로 지난 방송을 다시 읽지 않는다. 그래서 방송 핸들러는 '원천을 다시 읽어라' 같은 **무효화 신호**로만 쓴다(놓쳐도 기동 때 메워지는 일만). 놓치면 안 되는 업무 이벤트는 일반 구독으로
- 처리 기록(`processed_event.consumer`) 소비자 이름도 방송은 `<서비스>.<인스턴스>` — DB 를 함께 쓰는 복제본의 두 번째가 '중복'으로 건너뛰지 않게. 칸 길이(80자)를 넘으면 앞부분 + `~` + 전체 이름 해시 10자로 줄인다(결정적 — 재전달 멱등 유지, `Service._consumer_name`). Kafka 그룹 이름은 줄이지 않는다
- 한 토픽에 방송 · 일반 구독을 섞으면 `ValueError` — 한 서비스 안에서 한 토픽의 받는 방식은 하나다
- 방송 소비 루프가 죽으면 `/healthz` 가 503 → 파드 재시작(낡은 캐시로 계속 응답하지 않게)

## 4. DB
- URL 우선순위: `DATABASE_URL_<SVC>` → `DATABASE_URL` → `sqlite:///./data/<svc>.db`
- 로컬 MariaDB: `NOVA_DB_ROOT_PASSWORD=... uv run python scripts/local_db_setup.py` → 스키마 `<slug>_<svc>` + 전용 계정, 접속 정보는 `.env`(git 제외)
- **식별자는 UUIDv7**([ADR-003](../adr/ADR-003-uuid-v7-ids.md)): 기본키 `id_column()`, 다른 개체를 가리키는 칸 `ref_column()`, 직접 만들 때 `new_id()`. 접두어 ID 금지 — 사람이 읽는 업무 코드는 별도 `code` 칸(UNIQUE)
- 시각은 UTC 저장(`utcnow()`), 화면 표시만 프로젝트 시간대
- 표 · 칸 · 기본키 · 참조 칸 · 타입 표지(`_at` · `is_`) 이름: [naming.md](naming.md) §3.1 — 새 표 전에 `python nova.py naming lookup <개념>`. 모든 DB 서비스에 `outbox` · `processed_event` 자동 추가(플랫폼 분기가 만든다)

### 4.1 마이그레이션 ([ADR-011](../adr/ADR-011-migrations-alembic.md))
- **스키마는 마이그레이션으로 만든다** — 서비스 기동(`Service.init_db`)이 `nova_common.migrate.upgrade` 로 두 분기를 heads 까지 올린다. 표 · 칸을 바꾸면 마이그레이션을 쓴다(`create_all` 로 우회하지 않는다)
  | 분기 | 자리 | 이름표 · 리비전 | 담는 것 |
  |---|---|---|---|
  | 플랫폼 | `packages/common-py/nova_common/migrations/versions/` | `platform` · `p0001` … | `outbox` · `processed_event` — 한 번 쓰면 모든 서비스에 간다(서비스마다 복제하지 않는다) |
  | 서비스 | `services/<svc>/migrations/versions/` | `service` · `s0001` … | 그 서비스 표만 |
- **migrations 폴더가 없는 서비스**(게이트웨이 — 상태 없는 메모리 DB)는 예전대로 `create_all`. 폴더는 서비스 패키지 옆 `migrations/` 를 자동으로 찾는다(`Service(..., migrations_dir=)` 로 지정도 된다)
- **옛 DB**(create_all 로 만든 DB — 표는 있는데 `alembic_version` 이 없다): 각 분기의 첫 리비전(baseline)으로 stamp 한 뒤 올린다. 기존 행은 그대로 둔다
- 명령: `python nova.py migrate <svc> status`(DB 리비전 · 최신 리비전 · 모델과 차이) · `up`(올리기) · `new "<설명>"`(모델과 비교해 다음 `s000N` 을 만든다 — 차이가 없으면 만들지 않는다, 데이터 이전은 `--empty`). `new` 는 메모리 DB 로 비교하고 실제 DB 를 건드리지 않으며, 플랫폼 표 변경은 서비스 리비전에 넣지 않는다
- 리비전마다 **downgrade 를 쓴다**(되돌리기 경로). 칸에는 모델과 같은 `comment=`. 배포된 리비전 파일은 고치지 않고 다음 리비전을 더한다. 운영 DB 의 `up` · `downgrade` 는 사용자 확인 뒤에만
- 서비스 tests 에 `마이그레이션 = 모델` 검사를 둔다(`migrate.drift(db, Base) == []` — 템플릿 `tests/test_migrations.py` 가 준다). 모델만 고치고 리비전을 안 쓰면 여기서 실패한다
- 실패하면 기동을 거부한다(readyz 가 열리지 않는다) — 반쯤 바뀐 스키마로 쓰기 시작하지 않게. SQLite 는 칸 변경을 표 복사(batch)로 한다

### 4.2 제약 · 인덱스 이름
- 모든 서비스 Base 는 `class Base(NovaBase): pass`(`nova_common.db`). `NovaBase` 가 서비스마다 제약 이름 규칙(`db.NAMING_CONVENTION`)을 가진 자기 MetaData 를 만든다 — DB 가 임의로 지은 이름은 DB 마다 달라 마이그레이션으로 지우거나 바꿀 수 없다
  | 종류 | 이름 | 예 |
  |---|---|---|
  | 기본키 | `pk_<표>` | `pk_item` |
  | 인덱스 | `ix_<표>_<칸…>` | `ix_item_status` |
  | UNIQUE | `uq_<표>_<칸…>` | `uq_outbox_event_id` · `uq_processed_event_consumer_idempotency_key` |
  | FK | `fk_<표>_<칸…>_<가리키는 표>` | `fk_item_line_item_id_item`(같은 서비스 DB 안에서만 — §2) |
  | CHECK | `ck_<표>_<이름>` | `ck_item_qty_not_negative` — CHECK 는 `name=` 을 반드시 준다(없으면 오류) |
- 여러 칸이면 칸 이름을 밑줄로 잇는다. 이름은 [naming.md](naming.md) §3.1 의 표 · 칸 이름을 그대로 쓰므로 따로 짓지 않는다. 마이그레이션에서는 `op.f("<이름>")` 로 규칙 이름을 그대로 적는다
- 검사: `tests/test_constraint_names.py`(카탈로그의 모든 서비스 Base 가 NovaBase 이고 실제 제약 이름이 규칙대로)

## 5. API
- 외부 경로는 게이트웨이 `/v1/<서비스 경로>`. 서비스 경로 접두어는 `services.json` 의 `routes`
- 오류 형식: `{"error": {"code": "<개체>_<사유>", "message": "사람이 읽는 문장"}}`(코드 형식 · 경로 마디 형식은 [naming.md](naming.md) §3.4) — `raise ApiError(404, "item_not_found", "항목을 찾을 수 없습니다")`. `message` 는 화면에 그대로 보여 줄 수 있게 쓴다(UX H9)
- 목록: `?page&size&sort&q` → `{items, total, page, size}` (`nova_common.paging.paginate`)
- 인증 · 권한: 게이트웨이가 JWT 를 검증하고 `x-user-id · x-role · x-roles` 헤더를 붙인다. 서비스는 `principal(request).require("admin")`
- 헬스: `/healthz`(살아 있음 · 소비 루프) · `/readyz` · `/metrics` 는 팩토리가 자동 제공

### 5.1 웹 인증 쿠키 — 배포 전제 ([ADR-014](../adr/ADR-014-web-httponly-cookie.md) · T04-8.10)
웹은 토큰을 저장하지 않는다. 게이트웨이 로그인이 httpOnly 쿠키를 심고, 웹 SDK 는 `credentials: "include"` 로 보낸다. 모바일(KMP)은 응답 본문 `token` 을 Bearer 로 그대로 쓴다.

| 항목 | 값 · 동작 |
|---|---|
| 쿠키 | `nova_token`(이름은 `GW_TOKEN_COOKIE`) · HttpOnly · SameSite=Lax · Path=/v1 · Max-Age = 토큰 수명(지금 7일) |
| Secure | `GW_COOKIE_SECURE` — 없으면 `NOVA_ENV=prod` 일 때 켬. 운영은 https 이므로 켠 채로 둔다 |
| 로그인 | `POST /v1/auth/login` — 익명이어도 `Origin` 헤더가 있으면 `GW_CORS_ORIGINS` 에 있어야 한다(아니면 403 `csrf_origin`). `Origin` 이 없는 요청(모바일 · 서버 호출)은 통과. 개발 로그인은 `Content-Type: application/json` 이 아니면 415 `unsupported_media_type` |
| 로그아웃 | `POST /v1/auth/logout` — 쿠키 Max-Age=0 · 비로그인 · 깨진 · 만료 쿠키도 204(허용 밖 Origin 은 403) |
| CSRF | 쿠키로 인증된 쓰기 요청(POST · PUT · PATCH · DELETE)은 `Origin` 이 `GW_CORS_ORIGINS` 에 있을 때만 — 아니면 403 `csrf_origin`. Bearer 요청은 면제. 쿠키를 심고 지우는 로그인 · 로그아웃은 인증 여부와 무관하게 위 Origin 검사를 받는다(로그인 CSRF 차단) |
| CORS | `GW_CORS_ORIGINS` 는 **정확한 출처 목록**(예: `https://app.example.kr`). `*` 가 있으면 게이트웨이가 **기동을 거부**한다 |

- **같은 사이트에 배포한다** — 웹과 게이트웨이가 같은 등록 도메인 아래(예: `app.example.kr` · `api.example.kr`)여야 SameSite=Lax 쿠키가 실린다. 개발도 둘 다 `localhost` 로 맞춘다(`localhost` 와 `127.0.0.1` 을 섞으면 다른 사이트라 로그인이 유지되지 않는다)
- **같은 출처 배포도 자기 출처를 `GW_CORS_ORIGINS` 에 넣는다** — 웹과 게이트웨이가 한 호스트(예: `https://nova.local/v1`)여도 브라우저가 로그인 POST 에 `Origin` 을 보내므로 목록에 없으면 403 으로 로그인되지 않는다
- **다른 사이트에 배포해야 하면** 이 절로 해결되지 않는다 — 새 요구로 올린다(SameSite=None · 이중 제출 토큰 · BFF 중 결정, ADR-014 '검토한 대안')
- 옛 localStorage `<접두어>_token` 키는 SDK 가 처음 쓰일 때 지운다 — 이 정리 코드와 웹의 Bearer 경로는 Contract 단계(다음 판본)에서 걷는다

## 6. 테스트
- 서비스 단위: `TestClient(app)` + `sqlite://`. 이벤트는 `asyncio.run(svc._consume(Envelope(...)))` 로 주입하고 `svc.Outbox` 로 발행 확인
- 통합: `tests/integration` — `devstack.build()` 로 모든 서비스를 한 프로세스에, 게이트웨이 경유로 시나리오 검증
- 순수 계산(요금 · 규칙)은 골든 테스트(입력 → 기대 출력 표)
- 체크(`- [x]`)는 테스트로 확인한 뒤에만

## 7. 테넌트 · 행위자 · 도메인 팩 (표준 — [docs/std](../std/README.md))
- **테넌트**(STD-TENANCY-001): 업무 표는 `tenant_id = tenant_column()`, 조회는 `tenant_filter(select(M), M)`, 단건은 다른 테넌트면 404. 테넌트는 `nova_common.context.current_tenant()` 로만 얻는다 — **함수 인자로 나르지 않는다**(게이트웨이 → 미들웨어 → clients.call · 이벤트 봉투로 자동 전파)
- **행위자**(STD-AX-001): `principal(request).actor_type` · 이벤트 봉투 `actor_type`(human · ai · system). AI 가 직접 하면 안 되는 쓰기 · 승인은 `principal(request).require_human("<작업>")`
- **도메인 팩**(STD-DOMAIN-PACK-001): 업종마다 다른 규칙은 `@packs.port("<패키지>.<이름>")` 로 가변점을 내고 `packs.get(...)` 으로 쓴다. 코어에서 `if 업종 ==` 분기 · `import packs` 금지(lint)

## 8. 운영 안전
- `NOVA_ENV=prod` 에서 기본 JWT 키 · 짧은 키 · 개발 기능(`register_dev_feature`)이 켜져 있으면 기동 거부
- 비밀은 `.env`(로컬) · External Secrets(prod)만. 코드 · 문서 · 커밋에 쓰지 않는다

### 8.1 처리 기록 정리 · 격리 행 재처리 (REQ-261104-11-2 · -3)
- **정리**: 서비스가 기동 직후 한 번, 그 뒤 주기마다 보관 기간이 지난 행을 batch 로 지운다(`Service.purge_infra`). 보낸 발행 행과 처리 기록만 지우고, **보내지 않은 행 · 격리 행은 지우지 않는다**
  | 환경 변수 | 기본 | 뜻 |
  |---|---|---|
  | `OUTBOX_RETENTION_DAYS` | 7 | 보낸 발행(outbox) 행을 남기는 날 수 |
  | `PROCESSED_EVENT_RETENTION_DAYS` | 14 | 처리 기록(processed_event)을 남기는 날 수 — **토픽 최대 보존일보다 길어야 한다**(짧으면 재전달된 이벤트를 다시 처리한다 · 테스트가 `kafka-topics.txt` 와 대조) |
  | `NOVA_PURGE_INTERVAL` | 3600 | 정리 주기(초). 0 이하이면 배경 정리를 끈다(외부 잡으로 정리할 때) |
- **격리(parked)**: 발행이 정해진 횟수 넘게 실패한 행은 `is_parked` 로 격리되어 릴레이가 더 보내지 않는다. 지표 `nova_outbox_quarantined{service}` 로 보이고(대기 `nova_outbox_pending` 에서는 빠진다), 원인을 고친 뒤 사람이 다시 보낸다
- **재처리**(원인을 고친 뒤 — 해제하면 `attempts` 0 · `last_error` 는 남는다 · 해제 건수는 로그):
  ```bash
  # 로컬
  python nova.py parked <서비스> list                 # 격리 행 보기(--limit N)
  python nova.py parked <서비스> requeue --id 12 15   # 골라서 다시 보내기
  python nova.py parked <서비스> requeue --all        # 전부
  # 운영(k3s) — 서비스 파드 안에서 같은 모듈을 부른다(<ns> 는 services.json 의 그 서비스 네임스페이스)
  kubectl -n <ns> exec deploy/<서비스> -- python -m nova_common.outbox_admin <서비스> list
  kubectl -n <ns> exec deploy/<서비스> -- python -m nova_common.outbox_admin <서비스> requeue --id 12
  ```
  `--id` 와 `--all` 중 하나는 반드시 준다(둘 다 없으면 종료 코드 2 — 실수로 전부 다시 보내지 않게). 같은 원인으로 다시 실패하면 다시 격리된다
