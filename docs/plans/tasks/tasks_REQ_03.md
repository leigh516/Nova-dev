# tasks_REQ_03 · 공통 라이브러리 · 계약 보강 — 할 일 체크리스트

계획: [plan_REQ_03 v1.0](../plan_REQ_03.md) · 화면 미리보기는 계획 §4 · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일 · `~~취소~~ — 이유` 하지 않기로 함
TDD: 코드 task 는 모두 실패 테스트 → 최소 구현 → 같은 명령 통과 → 커밋 `<type>(범위): 요약` · `git_record.py`(하위 줄을 생략한 task 도 같다)

## 1단계 · 결정 관문
- [x] T03-1.01 마이그레이션 ADR 본문 초안 쓰기 (선택지 A Alembic 플랫폼/서비스 분기 · B 자체 러너 · C create_all 유지 + 문서, 대가 · 옛 DB stamp · 되돌리기, 상태 '제안') — ADR-011
  - 파일: 만들기 `docs/adr/ADR-NNN-*.md`(`docs_new.py adr` — main)
- [x] T03-1.02 계약 ADR 본문 초안 쓰기 (P1 중복 제거 키 · 기본 키에 event_id · Expand/Migrate/Contract 조건, P10 503 + Retry-After 단계, P4 범위, D3 처분) — ADR-012
- [x] T03-1.03 사용자 결정을 받아 두 ADR 채택하기 (README 인덱스 '채택' · 요구 E4 판정 '충족 YYYY-MM-DD') — 사용자 권고 채택 2026-11-04
- [x] T03-1.04 Alembic 의존성 추가하기 — 사용자 승인 뒤 (`uv add --package nova-common alembic` · uv.lock 갱신 · `python nova.py test` 통과) — alembic 1.20.1 · uv.lock

## 2단계 · 마이그레이션 체계 (REQ-261104-11-1)
- [x] T03-2.01 제약 이름 규칙 만들기 (test_constraint_names_follow_convention 통과)
  - 파일: 고치기 `packages/common-py/nova_common/db.py` · 테스트 `packages/common-py/tests/test_migrations.py`
  - 인터페이스: 내주는 것 `db.NAMING_CONVENTION: dict[str, str]` · `db.NovaBase`(MetaData(naming_convention=…) 를 가진 DeclarativeBase)
  - [x] 실패 테스트 작성 → `uv run pytest packages/common-py/tests/test_migrations.py::test_constraint_names_follow_convention` 실패 확인
  - [x] 최소 구현 → 같은 명령 통과 확인
  - [x] 커밋 `feat(common): 제약 이름 규칙 NovaBase` · `git_record.py`
- [x] T03-2.02 템플릿 · 샘플 · 게이트웨이 Base 를 NovaBase 로 옮기기 (tests/test_constraint_names.py::test_all_service_constraints_named 통과)
  - 파일: 고치기 `services/_template/__PKG__/models.py` · `services/sample/sample/models.py` · `services/gateway/gateway/app.py` · 테스트 `tests/test_constraint_names.py`
- [x] T03-2.03 마이그레이션 실행기 만들기 — 플랫폼 + 서비스 분기 heads, 빈 DB 는 upgrade, 표는 있고 alembic_version 이 없으면 baseline stamp 뒤 upgrade (test_upgrade_empty_db · test_upgrade_stamps_legacy_create_all_db 통과)
  - 파일: 만들기 `packages/common-py/nova_common/migrate.py` · 테스트 `test_migrations.py`
  - 인터페이스: 내주는 것 `migrate.upgrade(db: Database, base, service_dir: Path | None) -> None` · `migrate.status(...) -> dict`
  - [x] 실패 테스트(빈 메모리 DB · create_all 로 만든 파일 DB에 행 1개) → 실패 확인
  - [x] 최소 구현 → 통과 · 기존 행 보존 단언
  - [x] 커밋 `feat(common): 마이그레이션 실행기`
- [x] T03-2.04 플랫폼 첫 마이그레이션 쓰기 — outbox · processed_event 지금 모양 그대로 (test_platform_migration_matches_models: compare_metadata 차이 0)
  - 파일: 만들기 `packages/common-py/nova_common/migrations/versions/p0001_platform_baseline.py`(downgrade 포함)
- [x] T03-2.05 Service.init_db 를 바꾸기 — 서비스에 migrations 폴더가 있으면 upgrade, 없으면 create_all (test_init_db_uses_migrations_when_present · 게이트웨이 테스트 그대로 통과)
  - 파일: 고치기 `packages/common-py/nova_common/service.py` · `db.py`
  - 인터페이스: 받는 것 `migrate.upgrade` / 내주는 것 `Service(..., migrations_dir: Path | None = None)`(기본: 서비스 패키지 옆 `migrations/` 자동 탐색)
- [x] T03-2.06 템플릿 서비스 migrations 만들기 — env.py 는 `nova_common.migrate` 를 부르는 몇 줄, versions/0001 은 record 표 (new-service 생성물 테스트 · 새 서비스 tests 통과)
  - 파일: 만들기 `services/_template/migrations/env.py` · `services/_template/migrations/versions/0001_initial.py` · 고치기 `scripts/new_service.py`(치환 대상에 포함) · 테스트 `tests/test_new_service.py`
- [x] T03-2.07 샘플 서비스 첫 마이그레이션 만들기 (services/sample/tests/test_migrations.py::test_sample_migration_matches_models 통과)
- [x] T03-2.08 `python nova.py migrate <svc> new "<설명>" | up | status` 명령 만들기 (tests/test_migrate_cli.py 통과 · `python nova.py help` 에 보임)
  - 파일: 고치기 `nova.py` · 테스트 `tests/test_migrate_cli.py`
- [x] T03-2.09 backend.md §4 에 마이그레이션 · 제약 이름 절 쓰기 (create_all 문구 정정 · `docs_index.py --check` 통과)
- [x] 🆕 T03-2.10 (2026-11-04 Claude 판단 — 되돌릴 수 있는 CLI 이름: `python nova.py parked <서비스> list | requeue`, 모듈은 계획대로 `nova_common.outbox_admin`) T03-4.06 명령 이름 정하기 — `python nova.py outbox` 가 이미 메시지 버스(collab)용이라 겹친다(T03 2단계 담당 보고)
- [ ] 🆕 T03-2.11 NovaBase 의 SQLAlchemy 내부 속성 `_sa_registry` 의존을 회귀 테스트로 지키기 — SQLAlchemy 를 올릴 때 깨지는 자리

**단계 관문**: `python nova.py quick --stage T03-2` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 3단계 · 처리 기록 보강 · 중복 제거 키 (REQ-261104-11-8 · L3)
- [x] T03-3.01 [Expand] processed_event.idempotency_key 칸(NULL 허용) + UNIQUE(consumer, idempotency_key) 플랫폼 마이그레이션 p0002 쓰기 (test_p0002_adds_column_and_unique · downgrade 테스트 통과)
  - 파일: 만들기 `nova_common/migrations/versions/p0002_processed_event_idempotency_key.py` · 고치기 `db.py`(칸 comment="중복 제거 키(봉투 idempotency_key)")
- [x] T03-3.02 [Expand] 소비할 때 idempotency_key 를 함께 기록하기 (test_idempotency.py::test_processed_event_records_idempotency_key 통과)
- [x] T03-3.03 [Migrate] emit 기본 키를 `{source}:{topic}:{key}:{event_id}` 로 바꾸기 — D2 결정대로 (test_default_idempotency_key_unique_per_event 통과 · 샘플 명시 키는 그대로)
  - 파일: 고치기 `nova_common/outbox.py` · `packages/common-py/events/envelope.avsc` 설명
- [x] T03-3.04 [Migrate] 소비 중복 판정을 (consumer, idempotency_key) 로 바꾸고, 칸이 빈 옛 행은 event_id 로 판정하기 (test_same_key_different_event_consumed_once · test_legacy_row_without_key_still_dedupes 통과 · test_common 기존 멱등 테스트 통과)
  - 파일: 고치기 `nova_common/service.py` `_consume`
- [x] T03-3.05 동시 중복(UNIQUE 충돌)을 duplicate 로 처리하기 (test_concurrent_same_key_is_duplicate · test_handler_integrity_error_is_not_mistaken_for_duplicate 그대로 통과)
- [x] T03-3.06 (D3 이 '이번에'일 때만) baseline 칸 이름 3건 바꾸기 — p0003: outbox.parked → is_parked · processed_event.ok → is_ok · processed_event.at → processed_at, 코드 · 테스트 참조 변경, naming baseline 3줄 삭제 (`python nova.py naming check` 통과 · 마이그레이션 차이 0). D3 이 '다음에'면 `~~취소~~ — 사유`
- [x] T03-3.07 backend.md §3 멱등 문구 고치기 (idempotency_key 가 중복 제거 키 · 기본값 · 업무 키는 명시 · `docs_index.py --check` 통과)

**단계 관문**: `python nova.py quick --stage T03-3` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 4단계 · 데이터 수명 · 격리 재처리 (REQ-261104-11-2 · -3)
- [x] T03-4.01 Service.purge_infra 만들기 — 보관 기간이 지난 발행 행 · 처리 기록을 batch 개씩 지운다 (test_lifecycle.py::test_purge_deletes_only_expired_sent_rows · ::test_purge_keeps_unsent_and_parked · ::test_purge_respects_batch 통과)
  - 파일: 고치기 `nova_common/service.py` · 테스트 `packages/common-py/tests/test_lifecycle.py`
  - 인터페이스: 내주는 것 `Service.purge_infra(now: datetime | None = None, batch: int = 1000) -> dict[str, int]` · 환경 변수 `OUTBOX_RETENTION_DAYS`(7) · `PROCESSED_EVENT_RETENTION_DAYS`(14)
- [x] T03-4.02 처리 기록 보관 기간이 토픽 최대 보존일보다 긴지 검사하기 (test_processed_retention_covers_topic_retention — kafka-topics.txt 를 읽음, 통과)
- [x] T03-4.03 정리 배경 작업 등록하기 — 시작 직후 1회 · NOVA_PURGE_INTERVAL(3600초) 주기 · 실패는 로그 후 다음 주기 (test_purge_loop_runs_and_survives_error 통과)
- [x] T03-4.04 nova_outbox_quarantined 지표 만들고 pending 에서 격리 행 빼기 (test_quarantined_gauge_counts_parked · test_pending_excludes_parked 통과)
  - 파일: 고치기 `nova_common/metrics.py` · `service.py` flush_outbox
- [x] T03-4.05 Service.parked_rows · requeue_parked 만들기 — parked 해제 · attempts 0 · last_error 보존 · 해제 건수 로그(한국어) (test_requeue_parked_releases_and_publishes · test_requeued_row_failing_again_parks_again 통과)
  - 인터페이스: 내주는 것 `Service.parked_rows(limit: int = 100) -> list[dict]` · `Service.requeue_parked(ids: list[int] | None = None) -> int`(None = 전부)
- [x] T03-4.06 재처리 명령 만들기 — `python -m nova_common.outbox_admin <svc> parked | requeue (--id N … | --all)`, 서비스는 catalog 패키지의 `<pkg>.main:svc` 로 연다, `python nova.py parked …` 로 연결(T03-2.10 — `outbox` 는 메시지 버스가 쓴다) (test_outbox_admin_cli_requeue · --id 와 --all 둘 다 없으면 종료 코드 2)
  - 파일: 만들기 `nova_common/outbox_admin.py` · 고치기 `nova.py`
- [x] T03-4.07 OutboxQuarantined 알림 규칙 만들기 — monitoring.THRESHOLDS 에 outbox_quarantined 0, gen_k3s 가 alert_rules 에 `max by (service) (nova_outbox_quarantined) > 0` 5분 warning 생성, 게이트웨이 직접 수집 경보도 같은 판단 (`python nova.py gen` · lint --check · tests/test_infra.py::test_outbox_quarantined_alert_rule 통과)
  - 파일: 고치기 `services/gateway/gateway/monitoring.py` · `scripts/gen_k3s.py` · 생성 `infra/observability/prometheus/alert_rules.yml`
- [x] T03-4.08 backend.md §8 에 정리 환경 변수 · 격리 행 재처리 절차(kubectl exec 예) 쓰기 (`docs_index.py --check` 통과)

**단계 관문**: `python nova.py quick --stage T03-4` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 5단계 · 추적 ID · 방송 소비 (REQ-261104-11-6 · -4)
- [x] T03-5.01 context 에 추적 ID 넣기 (test_trace.py::test_scope_sets_and_resets_trace_id · ::test_trace_from_header_rejects_bad_format 통과)
  - 파일: 고치기 `nova_common/context.py` · 테스트 `packages/common-py/tests/test_trace.py`
  - 인터페이스: 내주는 것 `current_trace_id() -> str | None` · `scope(tenant, actor_type=None, *, trace_id=None)` · `trace_from_header(value: str | None) -> str`(`[A-Za-z0-9-]{8,64}` 밖이면 새 ID)
- [x] T03-5.02 서비스 미들웨어가 x-request-id 를 받아 심고 응답 헤더로 돌려주기 (test_request_id_header_roundtrip · 헤더 없을 때 새 ID 통과)
  - 파일: 고치기 `nova_common/service.py` request_context
- [x] T03-5.03 clients.call 이 x-request-id 를 붙이게 하기 (test_clients_propagate_request_id 통과)
  - 파일: 고치기 `nova_common/context.py` headers · `clients.py`
- [x] T03-5.04 emit 봉투에 trace_id 를 싣고, 소비 scope 에서 되살리고, Kafka 헤더에 trace_id 넣기 (test_emit_carries_trace_and_consumer_restores · test_kafka_publish_headers_include_trace 통과)
  - 파일: 고치기 `nova_common/outbox.py` · `service.py` _consume · `events.py` KafkaBus.publish
- [x] T03-5.05 게이트웨이 new_request_id 를 context.trace_from_header 로 통일하기 (test_gateway 기존 통과 + test_gateway_request_id_reaches_upstream)
  - 파일: 고치기 `services/gateway/gateway/routing.py`
- [x] T03-5.06 통합 테스트 쓰기 — 게이트웨이 → 샘플 생성 → 아웃박스 → 소비까지 같은 trace_id (tests/integration/test_trace_flow.py 통과)
- [x] T03-5.07 방송 구독 만들기 — `@svc.on(topic, broadcast=True)` · `EventBus.subscribe(..., broadcast=)`, InMemory 는 인스턴스마다 그룹 (test_broadcast.py::test_broadcast_reaches_every_instance · ::test_normal_topic_once_per_group 통과)
  - 파일: 고치기 `nova_common/events.py` · `service.py` · 테스트 `packages/common-py/tests/test_broadcast.py`
  - 인터페이스: 내주는 것 `Service.on(topic: str, *, broadcast: bool = False)`
- [x] T03-5.08 KafkaBus 방송 소비자 만들기 — 그룹 `<service>.<instance>`(KAFKA_INSTANCE_ID → HOSTNAME → 임의), latest, 소비 루프 · lag · healthy 를 두 소비자 모두에 (test_kafka_group_ids · test_kafka_broadcast_starts_from_latest · test_kafka_bus_unhealthy_when_broadcast_loop_died 통과 — 실제 Kafka 없이 가짜 소비자)
- [x] T03-5.09 게이트웨이 권한 · 플래그 무효화 핸들러를 broadcast 로 바꾸기 (test_gateway.py::test_rbac_changed_event_invalidates_every_replica — 두 인스턴스 · 같은 key 두 번 모두 무효화, 통과)
  - 파일: 고치기 `services/gateway/gateway/main.py`

**단계 관문**: `python nova.py quick --stage T03-5` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 6단계 · 계약 · 검증 (REQ-261104-11-7 · -9 · -10 · -11)
- [x] T03-6.01 ids.require_uuid7 만들기 — UUIDv7 정규형이 아니면 ApiError 404 (test_ids.py::test_require_uuid7_404_envelope 통과)
  - 인터페이스: 내주는 것 `require_uuid7(value: str, *, code: str = "not_found", message: str = "찾는 항목이 없습니다") -> str`(ApiError 는 지연 import — context.require_tenant 와 같은 방식)
- [x] T03-6.02 샘플 `_get` · 템플릿 get_record 에 require_uuid7 적용하기 (test_items.py::test_non_uuid7_path_is_404 — 'abc' · 대문자 · 하이픈 없음 · v4 모두 404, 템플릿 테스트 통과)
- [x] T03-6.03 샘플 쓰기(생성 · 수정 · 보관 · 보관 해제)에 require_human 적용하기 (test_items.py::test_ai_actor_write_rejected — 4경로 403 human_only, 사람은 그대로 통과)
- [x] T03-6.04 템플릿 생성에 require_human 적용하고 머리 주석 고치기 (템플릿 tests 통과 · '되돌릴 수 없는 일' 문구 → 'L1 의 모든 쓰기')
- [x] T03-6.05 쓰기 경로 감시 테스트 만들기 — 샘플 · 템플릿 라우터의 POST/PUT/PATCH/DELETE 처리기가 require_human 을 부르는지 (tests/test_ax_guard.py 통과 · 하나를 빼면 실패 확인)
- [x] T03-6.06 라우터 접두어 = services.json routes 검사 만들기 — /internal · 헬스 빼고 모든 라우트가 자기 routes 접두어 아래, 접두어마다 라우트 1개 이상 (tests/test_route_prefixes.py 통과 · 접두어를 틀리게 한 가짜 서비스로 실패 확인)
- [x] T03-6.07 프록시 오류 테스트 쓰기 (test_gateway.py::test_proxy_timeout_is_504 · ::test_proxy_connect_error_is_502 — clients.override + httpx.MockTransport, 봉투 · service 칸 단언)
- [x] T03-6.08 (kmp-test ApiClientTest rbacUnavailableIsSameRegardlessOfStatus RED → GREEN · web-build 통과 · 지금 게이트웨이는 403) [Expand] 웹 ErrorState · KMP 가 code rbac_unavailable 을 상태와 무관하게 '권한 정보를 잠시 확인할 수 없습니다 · 다시 시도'로 보이게 하기 (`python nova.py web-build` · `kmp-test` ApiClientTest 통과)
  - 파일: 고치기 `web/packages/ui/src/components/feedback.tsx` · `apps/kmp/shared/src/commonMain/kotlin/kr/nova/shared/ApiClient.kt`
- [x] T03-6.09 (403 → 503 + Retry-After = GW_RBAC_RETRY 올림 · RED 3건 assert 403 == 503 → GREEN · 게이트웨이 43 통과) [Migrate] 게이트웨이 rbac_unavailable 을 503 + Retry-After 로 바꾸기 (test_rbac_service_mode_fail_closed · test_rbac_stale_then_fail_closed 를 503 으로, test_rbac_unavailable_has_retry_after 통과)
  - 파일: 고치기 `services/gateway/gateway/routing.py` RbacCache.check
- [x] T03-6.10 (web-build · ui-smoke 8단계 통과 · KMP 분기는 남김) [Contract] 웹 Forbidden 의 rbac_unavailable 분기 지우기 — KMP 는 배포된 앱 때문에 남긴다 (web-build · `python nova.py ui-smoke` 통과)

**단계 관문**: `python nova.py quick --stage T03-6` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 7단계 · 프로젝트 메타 단일 원천 (REQ-261104-11-5)
- [x] T03-7.01 gen_k3s 가 configmap-common · compose 에 NOVA_SUPER_ROLE · NOVA_TZ_OFFSET_HOURS 를 nova.project.json 에서 쓰게 하기 (`python nova.py gen` · lint --check 통과)
- [x] T03-7.02 devstack 이 super_role · tz_offset_hours 를 환경에 setdefault 하게 하기 — NOVA_PACKS 와 같은 방식 (tests/test_project_meta.py::test_devstack_sets_meta_env 통과)
- [x] T03-7.03 gen 이 `web/packages/sdk/src/project.gen.ts`(LOCALE · TIMEZONE)를 만들고, sdk 가 환경 변수 다음 기본값으로 쓰게 하기 (web-build · gen --check 통과)
- [x] T03-7.04 gen_k3s 의 웹 포트 3000 고정 4곳(170 · 183 · 244 · 325)을 web_apps[].port 로 바꾸기 — grafana(348 · 717)는 그대로 (gen --check · validate_infra 통과 · 생성물 차이 없음 확인)
- [x] T03-7.05 복제 검사 테스트 만들기 — runtime 기본값(super_role · tz) · project.gen.ts · package.json dev 포트 · 생성 매니페스트가 nova.project.json 과 같다, 다르면 고칠 파일을 알려 준다 (tests/test_project_meta.py 통과 · 값을 바꾼 임시 메타로 실패 확인)

**단계 관문**: `python nova.py quick --stage T03-7` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 8단계 · 마무리 · 종료 조건
- [x] T03-8.01 (registry sync 변경 없음 · 활성 83 — 칸 변경은 대장 몫 · ledgers 변경 0 · registry check 정상) 생성물 원장 · 대장 갱신하기 (`registry.py sync --by <이름> --note "REQ-261104-11 processed_event 칸"` · `ledgers.py` · lint 원장 단계 통과)
- [x] T03-8.02 (README 모듈 표에 migrate · outbox_admin · ping · require_uuid7 · 추적 · 방송 · 정리 · 환경 변수 4종 · docs_index 정상) packages/common-py/README · backend.md 연결 확인하기 (새 API 6종 표기 · `docs_index.py --check` 통과)
- [x] T03-8.03 전체 테스트 · lint 확인하기 (E1 `python nova.py test` · E2 `python nova.py lint` 종료 코드 0)
- [x] T03-8.04 공통 라이브러리 테스트 확인하기 (E3 `uv run pytest packages/common-py/tests -q` — test_lifecycle · test_trace · test_idempotency · test_broadcast · test_migrations 포함 통과)
- [x] T03-8.05 종료 조건 판정하기 (`python nova.py exit-check REQ-261104-11` 녹색 → 요구 상태 완료 · `/history-new`)

**단계 관문**: `python nova.py quick --stage T03-8` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 작업 중 발견 (단계와 별개)
- [ ] 🆕 T03-9.01 이벤트 봉투 스키마 정합 — `envelope.avsc` 의 `data` 는 `string`, 실제 전송은 JSON 객체(`events.py:43`). 재현: avsc 로 직렬화하면 실패 · 기대: 둘을 대조하는 테스트가 있고 하나로 맞는다 · 실제: 대조 검사 없음 · 환경: 저장소(review_261104_02 C-F3)
- [ ] 🆕 T03-9.02 `nova_common/seed.py` 연결 또는 제거 결정 — 부르는 곳 0 · `seed/seed.json` 없음(review_261104_02 C-F7). 판단은 사용자
- [x] 🆕 T03-9.03 목록 필터 잘못된 값 처리 통일 — 모르는 `status` 는 200 빈 목록, 모르는 `sort` 는 400(`items.py:71` ↔ `paging.py:49`). 기대: 둘 다 같은 오류 봉투 · L2 변경이라 계약 결정 먼저(review_261104_02 C-F9) — 2026-11-06 사용자 결정 400 통일 · 모르는 `status` → 400 `invalid_status` + `allowed`(정렬과 같은 봉투) · 상태 원천 `models.ITEM_STATUSES` · 웹 · KMP 는 status 를 보내지 않아 영향 없음 · sample 테스트 31 통과(main 재실행) · 흔들림 2건(정리 주기 대기 · 메모리 DB 를 함께 쓰는 배경 루프) 함께 고침
- [x] 🆕 T03-9.04 (2026-11-04 사용자 결정 (A) — 320 으로: 255 는 최대 319 를 못 담는다 · p0004 · test_idempotency_key_column_fits_longest_default_key · test_p0004_widens_idempotency_key_and_downgrade_restores 통과) `processed_event.idempotency_key` 길이 결정 — VARCHAR(200) 인데 기본 키(source + topic 120 + key 80 + event_id 36)는 200 을 넘을 수 있다. MariaDB 엄격 모드면 'Data too long' → DLQ. 255 로 올릴지(새 리비전 p0004) 사용자 결정(T03 3단계 담당 보고 · DB 구조 변경이라 [DEEP])
- [x] 🆕 T03-9.05 (naming.json 예외 2 · baseline 2 · `naming check` 통과) ADR-012 D3 의 '기본키 2건을 의도한 예외로 옮김' — baseline pk 2줄이 그대로 남아 있다(T03-3.06 문구에 없어서 빠짐). `registry/naming.json` 예외로 옮기고 `naming check` 통과
- [x] 🆕 T03-9.06 방송 소비 처리 기록 소비자 이름 `<서비스>.<인스턴스>` 가 `processed_event.consumer`(80자)를 넘을 수 있다 — HOSTNAME 이 길면 'Data too long'. 기대: 인스턴스 부분을 줄이거나 해시로 붙여 80자 안을 보장하고 테스트로 고정(T03 5단계 담당 보고)
- [x] 🆕 T03-9.07 backend.md 에 추적 ID(`x-request-id` 전파 · 봉투 `trace_id` · Kafka 헤더)와 방송 구독(`@svc.on(topic, broadcast=True)` · `KAFKA_INSTANCE_ID` · latest 시작) 절 쓰기, 대장(events.md)에 방송 구독 표시할지 결정(`docs_index.py --check`)
- [ ] 🆕 T03-9.08 FastAPI 0.162 가 `include_router` 한 라우터를 `_IncludedRouter` 로 감싸 `app.routes[].path` 로는 업무 라우트가 안 보인다(`effective_route_contexts()` 로 펼쳐야 함) — 라우트를 읽는 다른 도구(대장 `ledgers.py` · 원장 스캐너 · 게이트웨이 라우트 표)가 같은 영향을 받는지 확인(T03-6 담당 보고)
- [ ] 🆕 T03-9.09 웹 포트가 `infra/docker/Dockerfile.web:18,22`(`PORT=3000` · `EXPOSE 3000`)에 남아 있다 — `web_apps[].port` 를 바꾸면 매니페스트는 새 포트, 컨테이너는 3000 에서 듣는다. 기대: Deployment 에 `env PORT` 를 생성하거나 복제 검사(test_project_meta)에 Dockerfile 을 더함(T03 7단계 담당 보고)
- [ ] 🆕 T03-9.10 (감사 C-F1 · C-F10 남은 것) sdk 의 `API_BASE` 기본값(게이트웨이 8080) · 저장 키 접두어 기본값 `"nova"` 를 `project.gen.ts`(SLUG · API_BASE)에서 — 7단계와 같은 방식으로 닫는다
- [ ] 🆕 T03-9.11 (6.09 형제) 권한 원천 장애 중 `RbacCache.allowed` 가 False 라 `/v1/menu` 가 메뉴를 조용히 비운다 — 장애가 '권한 없음'처럼 보인다. 기대: 메뉴도 rbac_unavailable(503)로 알리거나 마지막 메뉴 유지(`services/gateway/gateway/routing.py:224`)
- [ ] 🆕 T03-9.12 (6.09 형제) 기능 플래그 원천이 첫 적재부터 실패하면 `[]` 가 되어 점검 중인 기능도 열린다(fail-open) — 의도된 정책인지 판정 · 점검 503(`main.py:219`) · 429(`main.py:78`)에 `Retry-After` 헤더 · `access-control-expose-headers` 에 Retry-After(웹이 다른 출처에서 읽게)
