# tasks_REQ_02 · 운영 · 인프라 준비 — 할 일 체크리스트

계획: [plan_REQ_02 v1.0](../plan_REQ_02.md) · 화면 미리보기는 계획 §4 · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일 · `~~취소~~ — 이유` 하지 않기로 함

## 1단계 · 기반 — version 원천 · 검증기 확장
- [x] T02-1.01 `nova.project.json` 에 `version` 키를 두고 gen_k3s 가 읽게 만들기 (테스트 test_missing_version_fails 통과)
  - 파일: 고치기 `nova.project.json`(`"version": "0.1.0"`) · `scripts/gen_k3s.py`(`Ctx.version` — 없으면 SystemExit, 기본값 금지) · 테스트 `tests/test_infra.py`
  - 인터페이스: 내주는 것 `Ctx.version: str`
  - [x] 실패 테스트 작성 → `uv run pytest tests/test_infra.py::test_missing_version_fails` 실패 확인
  - [x] 최소 구현 → 같은 명령 통과 확인
  - [x] 커밋 `feat(infra): 판본 버전 원천을 nova.project.json 으로` · `git_record.py`
- [x] T02-1.02 prod images `newTag` · Helm `Chart.yaml` version/appVersion · `values.yaml` `image.tag` 를 `Ctx.version` 으로 바꾸기 (테스트 test_image_tag_comes_from_project_version 통과 — `"0.1.0"` 글자가 gen_k3s.py 에 남지 않음)
  - 파일: 고치기 `scripts/gen_k3s.py:432` · `:487-488` · `:496` · 테스트 `tests/test_infra.py`
  - 인터페이스: 받는 것 `Ctx.version`
  - [x] 실패 테스트(meta version 을 바꿔 생성 → 세 곳 모두 따라오는지) → 실패 확인
  - [x] 최소 구현 → 통과 확인
  - [x] 커밋 `feat(infra): 운영 이미지 태그를 판본 버전에서`
- [x] T02-1.03 `new_project` 가 새 프로젝트 meta 의 `version` 을 `"0.1.0"` 으로 되돌리기 (test_new_project::test_meta_and_identity 단언 추가 통과)
- [x] T02-1.04 `release.ship()` 이 version 기록 직후 인프라 생성물을 다시 만들기 (테스트 test_release_ship_regenerates_infra 통과)
  - 파일: 고치기 `scripts/release.py`(`regen_infra(root)` — `root/scripts/gen_k3s.py` 가 있으면 실행하고 실패면 SystemExit) · 테스트 `tests/test_parallel.py`
  - [x] 실패 테스트(ship 뒤 gen 이 불렸는지 — subprocess 대역) → 실패 확인
  - [x] 최소 구현 → 통과 확인
  - [x] 커밋 `fix(release): 판본 기록 뒤 인프라 생성물 재생성`
- [x] T02-1.05 `validate_infra` 가 CronJob(`spec.jobTemplate.spec.template`) 참조 · 이미지를 검사하고 ExternalSecret `target.name` 을 Secret 으로 인정하게 하기 (테스트 test_validator_reads_cronjob_and_external_secret 통과)
  - 파일: 고치기 `scripts/validate_infra.py`(`check_refs` · `check_prod_render` 의 파드 사양 꺼내기를 함수 `pod_spec(doc) -> dict` 하나로) · 테스트 `tests/test_infra.py`
  - 인터페이스: 내주는 것 `pod_spec(doc)` — 뒤 task 가 쓴다
  - [x] 실패 테스트(합성 문서: `:latest` CronJob 이 잡히는지 · ExternalSecret 대상 참조가 통과하는지) → 실패 확인
  - [x] 최소 구현 → 통과 확인
  - [x] 커밋 `fix(infra): 검증기가 CronJob · ExternalSecret 을 본다`
- [x] 🆕 T02-1.07 `release ship` 이 판본 기록 · 생성물 재생성 → 커밋 → 태그 순서로 하게 고치기 (P-3 — 태그가 판본 기록 커밋을 가리킨다 · tests/test_parallel.py::test_release_ship_tags_after_commit 통과)
- [x] T02-1.06 `validate_infra.check_prod_readiness(docs) -> list[str]` 만들기 — DB 계정 Job · 백엔드 서비스마다 NetworkPolicy · Deployment 마다 PDB 가 없으면 오류(아직 main 에 연결하지 않음) (테스트 test_prod_readiness_check_flags_missing 통과)
  - 인터페이스: 받는 것 `load_kustomization()` 결과 / 내주는 것 오류 문자열 목록 — T02-7.01 이 연결

## 2단계 · R1 운영 DB 계정 프로비저닝 Job
- [x] T02-2.01 운영 DB 시크릿을 원격 property `password` 하나에서 받고 url 은 ExternalSecret `target.template` 으로 조립하게 바꾸기 (테스트 test_prod_db_secret_single_password_source 통과 — §11 P-4 권고안 A)
  - 파일: 고치기 `scripts/gen_k3s.py`(`overlays()` secrets 루프) · 테스트 `tests/test_infra.py`
  - [x] 실패 테스트(db 시크릿의 remoteRef property 가 password · 템플릿 url 에 `mariadb.infra.svc.cluster.local:3306/<db>` · 실제 비밀번호 글자 없음) → 실패 확인
  - [x] 최소 구현 → 통과 확인
- [x] T02-2.02 infra 네임스페이스 ExternalSecret `<slug>-db-provision`(서비스마다 `<db>-password` 키 — 같은 원격 키)을 생성하기 (같은 테스트에 단언 추가 · delete-dev-secrets 와 겹치지 않음)
- [x] T02-2.03 `overlays/prod/db-provision.sh` 를 생성하기 — DB 서비스마다 `CREATE USER IF NOT EXISTS` · `ALTER USER … IDENTIFIED BY` 환경 변수 값 · `GRANT ALL PRIVILEGES ON <db>.*`, 비밀번호 글자는 파일에 없음 (테스트 test_prod_has_db_provision_job_for_every_db_service 의 스크립트 단언 통과)
  - 인터페이스: 받는 것 `catalog.services()` 의 `db` · `db_name` — 손 목록 금지
- [x] T02-2.04 `overlays/prod/db-provision-job.yaml` Job 을 생성하고 prod kustomization `resources` · `configMapGenerator` 에 넣기 — `mariadb:11.4` · root 비밀번호 `mariadb-root` · `envFrom` 프로비저닝 시크릿 · `backoffLimit: 6` · `ttlSecondsAfterFinished: 600` · 보안 컨텍스트 · 라벨 `app: db-provision` (테스트 test_prod_has_db_provision_job_for_every_db_service 통과 · `kubectl kustomize overlays/prod` 렌더 성공)
  - [x] 실패 테스트 → 실패 확인
  - [x] 최소 구현 → 통과 · 렌더 확인
- [x] T02-2.05 `mariadb-from-services` 정책에 infra 네임스페이스의 `app in (db-provision, mariadb-backup)` 파드 허용을 더하기 (테스트 test_mariadb_policy_admits_provision_and_backup 통과)
- [x] T02-2.06 prod `mariadb-init.sql` 머리 주석의 "수동으로 만든다 · 후속 과제"를 "db-provision Job 이 만든다"로 고치고 test_generated_comments_do_not_claim_missing_automation 을 "Job 이 있을 때만 그렇게 쓴다"로 바꾸기 (테스트 통과)

**단계 관문**: `python nova.py quick --stage T02-2` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 3단계 · R3 운영 MariaDB 백업 · 복원 절차
- [x] T02-3.01 (2026-11-04 사용자 결정 — plan §11.9: P-1 A 덤프 CronJob · P-2 A 같은 노드 PVC + 노드 밖 복사는 절차) §11 P-1(백업 방식) · P-2(보관 위치) 사용자 결정을 받아 plan §11.4 에 적기 (결정 한 줄 · 날짜) — B(관리형)면 3.02~3.03 을 취소하고 ADR 초안으로 바꾼다
- [x] T02-3.02 `overlays/prod/mariadb-backup.yaml` 을 생성하기 — PVC `mariadb-backup`(local-path) + CronJob(`mariadb:11.4` · `timeZone` = nova.project.json `timezone` · 매일 03:00 · `concurrencyPolicy: Forbid` · `mariadb-dump --single-transaction --databases <DB 서비스 전부>` → gzip · 보관 7일 지난 파일 삭제 · 라벨 `app: mariadb-backup`). 일정 · 보관일은 gen_k3s 상수 `BACKUP` 하나에 (테스트 test_prod_backup_cronjob 통과 · 렌더 성공 · T02-1.05 검사기로 이미지 확인)
  - [x] 실패 테스트 → 실패 확인
  - [x] 최소 구현 → 통과 확인
- [x] T02-3.03 `docs/conventions/deploy.md` 를 만들고 §백업 · 복원을 쓰기 — 백업 위치 · 노드 밖 복사 절차 · 복원 명령 순서(서비스 0 레플리카 → 복원 → 계정 Job 재실행 → 레플리카 복구 → readyz 확인) · M1 테넌시라 DB 전체 단위 복원 · 개인정보 백업 접근 주의, 비밀값 없음 (`docs_index.py --check` 통과)
- [ ] T02-3.04 판정 불가 — 실제 백업 → 복원 리허설 (필요한 것: k3s + MariaDB 실데이터 — 릴리스 노트 '알려진 문제'로 넘긴다)

**단계 관문**: `python nova.py quick --stage T02-3` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 4단계 · R4 서비스 단위 NetworkPolicy
- [x] T02-4.01 `ServiceSpec.allow_from -> tuple[str, ...]` 을 `services.json` `k8s.allow_from`(선택 · 기본 빈 값)에서 읽게 만들기 (테스트 test_catalog.py::test_allow_from_default_empty 통과)
  - 파일: 고치기 `packages/common-py/nova_common/catalog.py` · `services.json` `$comment` 에 키 설명 한 줄 · 테스트 `packages/common-py/tests/test_catalog.py`
  - 인터페이스: 내주는 것 `ServiceSpec.allow_from`
- [x] T02-4.02 `netpols()` 에서 서비스 네임스페이스 공통 `allow-services-and-observability` 를 없애고, 백엔드 서비스마다 `allow-<서비스>`(대상 `app: <서비스>` · 게이트웨이 파드 = 같은 from 원소 안 `namespaceSelector <ld>/ns: <게이트웨이 ns>` + `podSelector app: <게이트웨이>` · `allow_from` 서비스 파드 · observability 네임스페이스 · 포트 8000)을 생성하기 (테스트 test_backend_policy_admits_only_gateway_and_allowlist 통과 — 카탈로그 백엔드 전부를 돈다)
  - [x] 실패 테스트 → 실패 확인
  - [x] 최소 구현 → 통과 확인
- [x] T02-4.03 게이트웨이 네임스페이스 정책을 만들기 — 게이트웨이 파드는 kube-system(인그레스) · observability(스크레이프 · Alertmanager 웹훅) · 웹 파드(웹 SSR 이 게이트웨이를 부를 때만 — `web/apps` 코드로 먼저 확인), 웹 파드는 kube-system 만 (같은 테스트 단언 추가 · 확인 결과를 커밋 메시지에)
- [x] T02-4.04 `allow_from` 에 카탈로그에 없는 이름이 있으면 gen_k3s 가 실패하게 하기 (테스트 test_unknown_allow_from_fails 통과)
- [x] T02-4.05 `docs/conventions/backend.md` 서비스 간 통신 절에 "직접 호출은 `k8s.allow_from` 에 올린 서비스만 — 아니면 운영에서 막힌다" 한 줄 더하기 (`docs_index.py --check` 통과)
- [ ] T02-4.06 판정 불가 — 실제 k3s 에서 허용 목록 밖 파드가 sample 을 직접 부르면 거부되는지 (필요한 것: k3s 정책 컨트롤러 — 릴리스 노트 '알려진 문제'로 넘긴다)

**단계 관문**: `python nova.py quick --stage T02-4` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 5단계 · R2 알림 수신처 이중화 · 영속 보관
- [x] T02-5.01 Alertmanager v0.27 `webhook_configs.url_file` 지원 여부를 공식 문서로 확인하기 (근거 링크를 plan §12.1 에 — 없으면 5.02 를 "설정 파일 전체를 시크릿에서"로 바꾼다)
- [x] T02-5.02 `overlays/prod/alertmanager.yml` 을 생성하기 — 수신처 `gateway`(지금 URL) + `oncall`(webhook `url_file: /etc/alertmanager/receivers/oncall-url` · `send_resolved`) · critical · warning 모두 두 곳(`continue: true`) (테스트 test_prod_alertmanager_two_receivers_and_volume 의 설정 단언 통과)
- [x] T02-5.03 prod 오버레이에 `alertmanager-config` `behavior: replace` · `EXTRA_SECRETS` 에 `alertmanager-receivers`(observability · `oncall-url`) · Deployment 패치(수신처 시크릿 `optional: true` 마운트 · `data` 볼륨을 PVC `alertmanager-data` 로) · PVC 를 생성하기 (test_prod_alertmanager_two_receivers_and_volume 통과 · 렌더 성공)
  - [x] 실패 테스트 → 실패 확인
  - [x] 최소 구현 → 통과 · 렌더 확인
- [ ] T02-5.04 판정 불가 — oncall 수신처 실제 발송 · 재시작 뒤 침묵 유지 (필요한 것: k3s + 수신 웹훅 — '알려진 문제'로 넘긴다)

**단계 관문**: `python nova.py quick --stage T02-5` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 6단계 · R5 준비 확인 · 웹 · Helm · npm ci + R17 신뢰 홉
- [x] T02-6.01 `Database.ping() -> bool`(`SELECT 1`, 예외면 False — 이유를 로그로) 을 만들고, DB 서비스의 `/readyz` 가 실패하면 503 `{"status":"db_unavailable"}` 를 내게 하기 — `/healthz` 는 그대로 (테스트 test_hardening.py::test_readyz_reports_db_down_but_healthz_ok 통과)
  - 파일: 고치기 `packages/common-py/nova_common/db.py` · `service.py:451-455` · 테스트 `packages/common-py/tests/test_hardening.py`
  - [x] 실패 테스트 → `uv run pytest packages/common-py/tests/test_hardening.py::test_readyz_reports_db_down_but_healthz_ok` 실패 확인
  - [x] 최소 구현 → 통과 확인
- [x] T02-6.02 `web()` 생성물에 startup · liveness probe · `seccompProfile: RuntimeDefault` · 컨테이너 보안 컨텍스트(`allowPrivilegeEscalation: false` · `drop: [ALL]` · `readOnlyRootFilesystem: true`) · emptyDir(`/tmp` · `/web/apps/<앱>/.next/cache`) · PDB 를 더하기 (테스트 test_web_has_probes_security_and_pdb 통과 · §11 P-6 확인은 별도)
- [x] T02-6.03 Helm `templates/services.yaml` 에 k3s 서비스와 같은 startupProbe · readiness `failureThreshold` · seccomp · 컨테이너 보안 컨텍스트 · `/tmp` emptyDir · PDB 를 더하기 (테스트 test_helm_template_matches_k3s_hardening 텍스트 검사 통과 — helm 이 있으면 check_helm_render 도)
- [x] T02-6.04 `Dockerfile.web` 을 `npm ci --workspaces --include-workspace-root` 만 쓰게 하고 잠금 파일 COPY 를 필수로 바꾸기(`package-lock.json*` → `package-lock.json`) (테스트 test_web_dockerfile_uses_npm_ci_only 통과)
- [x] T02-6.05 prod configmap 패치에 `GW_TRUSTED_HOPS: "1"` 을 더하기 — 값의 뜻(Traefik 단독)을 주석으로 (테스트 test_prod_sets_trusted_hops 통과 · §11 P-5)
- [x] T02-6.06 Helm `values.yaml` `trustedHops: "1"` · 템플릿 env `GW_TRUSTED_HOPS` 를 더하기 (같은 테스트에 Helm 단언 추가)

**단계 관문**: `python nova.py quick --stage T02-6` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 7단계 · 연결 · 되돌리기 문서 · 종료 판정
- [x] T02-7.01 `check_prod_readiness` 를 `validate_infra.main()` 의 prod 오버레이 단계에 연결하고 `운영 준비: DB 계정 Job N · 서비스 정책 N/N · PDB N/N` 을 찍기 (테스트 test_prod_readiness_passes_on_generated 통과 · `uv run python scripts/validate_infra.py` 통과 — E3)
- [x] T02-7.02 `deploy.md` §되돌리기(이전 태그 `vX.Y.Z` 의 `overlays/prod` 로 apply · 이미지만 되돌릴 때 · DB 는 백업 복원으로만 · 확인 지점 readyz)를 쓰고 `docs/releases/_template.md` 되돌리기 자리표시에 그 절 링크를 넣기 (`docs_index.py --check` 통과)
- [x] T02-7.03 `python nova.py gen` 으로 생성물을 다시 만들고 `python nova.py test` · `python nova.py lint` 녹색 확인하기 (E1 · E2 출력 숫자를 커밋 메시지에)
- [x] T02-7.04 `python nova.py exit-check REQ-261104-10` 녹색 확인하기 (E1~E3 모두 통과)
- [x] T02-7.05 판정 불가 4건(3.04 · 4.06 · 5.04 · 실제 Helm 렌더)과 §11 P-3 · P-6 처분을 main 에 넘기기 (v0.2.0 노트 '알려진 문제' · not_doing 초안 — 기록은 main 이 쓴다)

(작은 task 는 한 줄만 써도 된다. 하위 줄은 /task-run 이 superpowers 로 실행할 때 쓰는 단계 — superpowers.md §5)

**단계 관문**: `python nova.py quick --stage T02-7` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 작업 중 발견 (단계와 별개)
- (착수 전 발견) `release ship` 이 커밋 전에 태그를 만든다(`scripts/release.py:143`) — plan §11.4 P-3 처분 대기. A 로 정하면 T02-1.07 🆕 로 더한다
- [ ] 🆕 T02-8.01 compose 게이트웨이 `/internal/*` 외부 노출 막기 — 재현: compose 로 띄우고 같은 LAN 에서 `POST <호스트>:8080/internal/alertmanager` · 기대: 게이트웨이 앱 자체가 루프백 · 내부망 밖 `/internal` 을 거부(가드가 `dev_server.py:82` 에만 있음) · 실제: 통과 · 환경: Docker Desktop(review_261104_02 C-F6)
- [ ] 🆕 T02-8.02 게이트웨이 포트 8080 을 `services.json local_port` 한 곳에서 — `dev_server.py:106` · `gen_k3s.py:639` 와 클라이언트 기본값 9곳이 직접 적음(review_261104_02 C-F1)
- [ ] 🆕 T02-8.03 (같은 형태: `kafka-from-services` 도 서비스 네임스페이스 전체 · infra 를 연다 — T02 4단계 담당 보고) DB 서비스가 없는 프로젝트에서 `mariadb-from-services` 가 infra 네임스페이스 전체를 연다 — `c.db_ns or ["infra"]` 대체값(`scripts/gen_k3s.py`). 기대: DB 서비스가 없으면 정책 자체를 만들지 않거나 아무도 허용하지 않음(T02 2단계 담당 보고)
- [x] 🆕 T02-8.04 (2026-11-04 Claude 판단 — 검사 대상을 서비스 · 웹 네임스페이스로 좁힘: E3 의 PDB 는 서비스 PDB · observability 는 레플리카 1이라 PDB 가 drain 을 막는다) `check_prod_readiness` 가 observability Deployment(grafana · alertmanager)에도 PDB 를 요구한다 — T02-7.01 연결 전에 6단계 R5 범위인지 확인하고, 아니면 검사 대상을 서비스 네임스페이스로 좁힌다(T02 2단계 담당 보고)
- [x] 🆕 T02-8.05 (2026-11-04 사용자 결정 (A) — 개발 · 운영 모두 v0.28.1: `gen_k3s.py` compose · 손 관리 `infra/observability/k8s/alertmanager.yaml` · test_alertmanager_image_has_url_file_fix RED → GREEN · amtool v0.28.1 운영 · 개발 설정 3개 SUCCESS) Alertmanager v0.27.0 의 `url_file` 웹훅 결함 — 수신처가 2xx 가 아닌 응답을 내면 프로세스 전체가 nil 포인터 panic(이슈 prometheus/alertmanager#3798, 0.28.0 에서 수정). oncall 이 4xx · 5xx 를 내면 게이트웨이 수신까지 끊겨 이중화 목적이 깨진다 — 이미지 판본 결정 필요(사용자 · 의존성 변경)
- [ ] 🆕 T02-8.06 DB 가 내려가 있는 동안 `/readyz` 가 5초마다 불려 `nova.db` WARNING 이 5초마다 한 줄씩 쌓인다 — 기대: 상태가 바뀔 때만(정상 → 실패 · 실패 → 정상) 남기거나 같은 원인은 주기 묶음(T02-6.01 담당 보고)
- [ ] 🆕 T02-8.07 웹 이미지가 `readOnlyRootFilesystem` 에서 실제로 뜨는지 — `CMD npm run start` 가 `~/.npm/_logs` 에 쓰려 하고 Next telemetry 가 설정 파일을 쓴다. 걸리면 `npm_config_cache=/tmp/.npm` · `NEXT_TELEMETRY_DISABLED=1`(판정 불가 → Docker 로 웹 이미지를 띄워 판정, T02-6 담당 보고)
- [ ] 🆕 T02-8.08 문서 검사가 `#앵커` 가 붙은 링크를 건너뛴다(`docs_index.py:19` 정규식) — deploy.md 의 `#되돌리기` · `#백업--복원` 은 손으로 맞췄고 기계 판정이 없다. 기대: 같은 문서 · 다른 문서 앵커가 제목에서 나오는지 검사(T02-7 담당 보고)
