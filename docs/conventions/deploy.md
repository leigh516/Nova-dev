# 배포 규약 — 운영(k3s prod 오버레이)

운영 배포물은 `infra/k3s/overlays/prod` 를 렌더한 것이다. 이 폴더의 파일은 `scripts/gen_k3s.py` 가 만든 생성물이라 손으로 고치지 않는다 — 원천(`services.json` · `nova.project.json` · 생성기 상수)을 고치고 `python nova.py gen`. 운영 클러스터에 실제로 적용하는 일은 사람이 확인한 뒤에 한다.

> 비밀값(비밀번호 · 접속 URL 실값)은 이 문서에 쓰지 않는다. 아래 명령은 비밀번호를 **파드 안의 환경 변수**로만 읽는다 — 터미널 · 셸 기록에 남기지 않는다.

## 첫 배포 준비

운영 클러스터에 처음 올리기 전에 한 번 한다. 하나라도 빠지면 `apply` 는 되지만 파드가 기동 거부(시크릿 없음) · 인증서 없음 · 이미지 못 받음으로 멈춘다. 이름의 `<slug>` · `<domain>` · `<image_registry>` 는 `nova.project.json` 값이다.

| 준비 | 할 일 | 확인 |
|---|---|---|
| 시크릿 저장소 | External Secrets Operator 를 설치하고 ClusterSecretStore `<slug>-secrets`(Vault · 클라우드 Secret Manager 등)를 만든다 — 생성물은 이 이름만 가리킨다 | `kubectl get clustersecretstore <slug>-secrets` 가 Ready |
| 원격 키 | `uv run python scripts/gen_k3s.py --list-secrets` 가 내는 원격 키 · property 를 저장소에 모두 채운다(값은 출력에 없다). `jwt-secret` 은 32자 이상 무작위 — 기본값 · 짧은 값이면 운영 안전장치가 기동을 거부한다 | `kubectl get externalsecret -A` 가 모두 동기화됨(SecretSynced) |
| TLS | `nova.project.json` 에 `tls.cluster_issuer`(cert-manager ClusterIssuer 이름)를 적고 `python nova.py gen` — 또는 issuer 없이 인증서 시크릿 `tls.secret`(없으면 자리표시 `<slug>-tls`)을 인그레스가 있는 네임스페이스(게이트웨이 네임스페이스 · `observability`)마다 직접 넣는다 | `kubectl get secret <시크릿> -n <네임스페이스>` · cert-manager 면 `kubectl get certificate -A` 가 Ready |
| HTTPS 전용 · HSTS | 운영 인그레스는 `websecure` 만 받고 HSTS 미들웨어(`overlays/prod/ingress-tls.yaml`)를 단다. `http://` 로 온 요청을 HTTPS 로 돌리는 것은 Traefik 전역 설정(k3s 는 HelmChartConfig `traefik`)의 web → websecure 리다이렉트로 한다 — 키 이름은 클러스터에 든 Traefik 차트 판본을 보고 정한다. HSTS preload 는 넣지 않았다(목록 등록은 되돌리기 어렵다 — 사람이 정한다) | `curl -sI https://<domain>/` 에 `strict-transport-security` 헤더 |
| DNS | 인그레스 호스트 전부(`api.<domain>` · `<domain>` · 웹 앱 `<이름>.<domain>` · `grafana.<domain>`)를 인그레스 컨트롤러 주소로 | `kubectl -n <게이트웨이 네임스페이스> get ingress` · `kubectl -n observability get ingress` 의 HOSTS 와 DNS 응답이 같다 |
| 레지스트리 권한 | 노드가 `<image_registry>` 에서 판본 태그 이미지를 받을 수 있어야 한다. 비공개 레지스트리면 서비스 · 웹 네임스페이스마다 docker-registry 시크릿을 만들고 기본 ServiceAccount 에 붙인다(`kubectl -n <네임스페이스> patch serviceaccount default -p '{"imagePullSecrets":[{"name":"<시크릿>"}]}'`). 생성물에 imagePullSecrets 칸은 🗺 없음 | 파드에 `ImagePullBackOff` 가 없다 |
| 경보 수신처 | 원격 키 `alertmanager-receivers` 의 `oncall-url`(위 `--list-secrets` 목록에 있다) — 없어도 기동하지만 oncall 로는 알림이 안 간다 | Alertmanager 로그에 oncall 발송 오류가 없다 |

DB 연결 예산은 생성기가 미리 센다 — 서비스별 (최대 복제본 + 롤링 1) × 파드당 풀이 `infra/k3s/base/mariadb.yaml` `--max-connections` 를 넘으면 `python nova.py gen` 이 이유와 함께 멈춘다(`gen_k3s.py` `check_db_budget`).

## 네트워크 정책

서비스는 게이트웨이가 붙인 `x-user-id` · `x-role` 헤더를 믿으므로, 서비스 네임스페이스는 기본 거부(`default-deny-ingress`)이고 서비스마다 `allow-<서비스>` 가 게이트웨이 파드 · `services.json` `k8s.allow_from` 의 파드 · observability 의 Prometheus 파드만 들인다(게이트웨이는 인그레스 컨트롤러 · Prometheus · Alertmanager 파드만 — 웹훅). observability 네임스페이스 통째로는 열지 않는다(관측 파드 목록은 `gen_k3s.py` `OBS_APPS`). k3s 는 `infra/k3s/base/networkpolicy.yaml`, **Helm 차트도 같은 원천에서 같은 정책을 갖는다** — `values.yaml` `networkPolicy` · 서비스별 `ingressFrom`(생성물)을 `templates/networkpolicy.yaml` 이 그린다. 허용을 늘리려면 `allow_from` 을 고치고 `python nova.py gen`.

## 백업 · 복원

출처: [plan_REQ_02](../plans/plan_REQ_02.md) §11.9 결정 — P-1 A(덤프 CronJob) · P-2 A(같은 노드 PVC + 노드 밖 복사는 이 절차).

### 무엇이 · 언제 · 어디에
| 항목 | 값 | 원천 |
|---|---|---|
| 방식 | `mariadb-dump --single-transaction --databases <DB 서비스 전부>` → gzip | `gen_k3s.py` `BACKUP_SH` — DB 목록은 `services.json` 의 `db: true` 서비스(새 서비스도 자동 포함) |
| 일정 | 매일 03:00 (`nova.project.json` `timezone` 기준) | `gen_k3s.py` 상수 `BACKUP["schedule"]` |
| 보관 | 7일 — 새 덤프가 **성공한 뒤에만** 7일 지난 파일을 지운다(백업이 계속 실패하면 옛 파일이 남는다) | `BACKUP["keep_days"]` |
| 위치 | PVC `infra/mariadb-backup`(local-path · MariaDB 와 **같은 노드**) 안 `mariadb-YYYYMMDD-HHMMSS.sql.gz` | `overlays/prod/mariadb-backup.yaml` |
| 실패 | Job 이 Failed 로 남고(최근 3개), 스크립트가 Alertmanager 에 critical 경보 `MariaDBBackupFailed` 를 직접 보낸다(kube-state-metrics · Pushgateway 없이 — 운영 수신처 gateway · oncall). 다음 백업이 성공하면 해제, 아니면 `BACKUP["alert_hold_hours"]` 뒤 저절로 풀린다. **일정 자체가 돌지 않은 경우(CronJob 정지 · 스케줄 실패)는 경보가 없다** — 아래 '매일 확인'으로 본다 | `gen_k3s.py` `BACKUP_SH` · `BACKUP` |

같은 노드의 PVC 는 **노드가 죽으면 DB 와 함께 사라진다**. 그래서 노드 밖 복사(아래)가 백업의 일부다 — 빠뜨리면 백업이 없는 것과 같다.

### 매일 확인
```bash
kubectl -n infra get cronjob mariadb-backup        # LAST SCHEDULE 이 오늘 03:00 근처인가
kubectl -n infra get jobs -l app=mariadb-backup    # 실패(Failed) 가 없는가
kubectl -n infra logs job/<가장 최근 Job 이름>     # "✓ 백업 /backup/mariadb-…sql.gz (크기)" 줄
```
지금 바로 한 번 더 뜨려면: `kubectl -n infra create job --from=cronjob/mariadb-backup mariadb-backup-manual-$(date +%s)`

### 노드 밖 복사
1. 백업 파일이 있는 노드와 폴더를 찾는다.
   ```bash
   PV=$(kubectl -n infra get pvc mariadb-backup -o jsonpath='{.spec.volumeName}')
   kubectl get pv "$PV" -o jsonpath='{.spec.hostPath.path}{.spec.local.path}{"\n"}'   # 노드 안 폴더
   kubectl get pv "$PV" -o jsonpath='{.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0]}{"\n"}'  # 노드 이름
   ```
2. **노드 밖 보관 서버에서 당겨 온다**(pull) — 하루 한 번, 덤프가 끝난 뒤(예: 04:00). 노드가 보관 서버에 쓰게(push) 하지 않는다: 노드가 뚫려도 노드 밖 사본을 지울 수 없게.
   ```bash
   rsync -a --ignore-existing <노드>:<노드 안 폴더>/ /srv/backup/mariadb/   # 지난 파일은 덮어쓰거나 지우지 않는다
   ```
3. 노드 밖 사본은 노드보다 오래 둔다(보관 기한은 프로젝트의 개인정보 처리 방침에 맞춘다). 오래된 사본 정리는 보관 서버 쪽 일이다.

### 개인정보 — 백업은 운영 DB 와 같은 등급
- 덤프에는 모든 테넌트의 개인정보가 **평문 SQL** 로 들어 있다. 노드 밖 사본은 암호화해 둔다(디스크 암호화 또는 `age` · `gpg` 로 파일 암호화)
- 노드 폴더 · 보관 서버 · PVC 를 읽을 수 있는 사람(노드 SSH · `kubectl exec` 권한)은 운영 DB 를 읽을 수 있는 사람이다 — 접근자 목록을 최소로 두고, 접근 기록을 남긴다(ISMS-P 접근 통제)
- 복원 연습 · 분석에 운영 덤프를 개발 PC 로 옮기지 않는다

### 복원 — DB 전체 단위
멀티테넌시 M1(공유 스키마 — [STD-TENANCY-001](../std/STD-TENANCY-001.md))이라 한 DB 에 모든 테넌트가 함께 있다. 이 덤프로는 **DB 전체**를 덤프 시점으로 되돌린다 — 테넌트 하나만 되살리지 못한다(덤프 시점 뒤 다른 테넌트의 변경도 함께 사라진다). 복원 전에 그 손실을 사람이 확인한다.

순서를 지킨다 — 서비스가 살아 있는 채 복원하면 쓰던 데이터와 복원 데이터가 섞인다.

0. **지금 상태를 한 번 더 뜬다**(복원이 잘못됐을 때 돌아갈 자리) · 정기 백업을 멈춘다.
   ```bash
   kubectl -n infra create job --from=cronjob/mariadb-backup mariadb-backup-before-restore
   kubectl -n infra wait --for=condition=complete job/mariadb-backup-before-restore --timeout=30m
   kubectl -n infra patch cronjob mariadb-backup -p '{"spec":{"suspend":true}}'
   ```
1. **DB 를 쓰는 서비스를 0 레플리카로** — `services.json` 에서 `db: true` 인 서비스마다(HPA 는 0 레플리카에서는 다시 늘리지 않는다).
   ```bash
   kubectl -n <네임스페이스> scale deploy/<서비스> --replicas=0     # 예: kubectl -n core scale deploy/sample --replicas=0
   kubectl -n <네임스페이스> wait --for=delete pod -l app=<서비스> --timeout=5m
   ```
2. **복원** — 고른 덤프 파일(노드 폴더 또는 노드 밖 사본)을 작업 PC 로 가져온 뒤, 복원할 DB 를 지우고 덤프를 넣는다. `--databases` 덤프는 `CREATE DATABASE` · `USE` 를 담고 있지만 DB 를 지우지는 않는다 — 지우지 않으면 덤프 뒤에 생긴 표가 남는다.
   ```bash
   kubectl -n infra exec -i mariadb-0 -- sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb -u root -e "DROP DATABASE IF EXISTS <db>"'   # DB 마다
   gunzip -c mariadb-YYYYMMDD-HHMMSS.sql.gz | kubectl -n infra exec -i mariadb-0 -- sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb -u root'
   ```
3. **계정 Job 다시 돌리기** — 덤프에는 계정(`mysql` 스키마)이 없다. 계정 · 권한 · 비밀번호를 지금 시크릿 값으로 맞춘다(멱등).
   ```bash
   kubectl -n infra delete job db-provision --ignore-not-found
   kubectl kustomize infra/k3s/overlays/prod | kubectl apply -l app=db-provision -f -
   kubectl -n infra wait --for=condition=complete job/db-provision --timeout=5m
   ```
4. **레플리카 복구** — 운영 렌더 값으로 되돌린다(핵심 경로는 2 이상).
   ```bash
   kubectl kustomize infra/k3s/overlays/prod | kubectl apply -l app=<서비스> -f -   # 또는 scale --replicas=<운영 렌더 값>
   kubectl -n <네임스페이스> rollout status deploy/<서비스> --timeout=5m
   ```
5. **readyz 확인** — 서비스마다 200 이어야 끝이다(DB 를 못 읽으면 503 `db_unavailable`).
   ```bash
   kubectl -n <네임스페이스> port-forward svc/<서비스> 18000:8000 &
   curl -fsS http://localhost:18000/readyz
   ```
   정기 백업을 다시 켠다: `kubectl -n infra patch cronjob mariadb-backup -p '{"spec":{"suspend":false}}'`

복원 리허설(실제 덤프 → 복원 → readyz)은 k3s + 실데이터가 있어야 판정할 수 있다 — 첫 운영 전에 한 번 하고 결과를 `docs/verification/` 에 남긴다.

## 되돌리기

출처: [plan_REQ_02](../plans/plan_REQ_02.md) §5 생애주기(운영 배포 → 이상 → 이전 태그의 `overlays/prod` 로 apply). 판본 = git 태그 `vX.Y.Z` = 운영 이미지 태그(`nova.project.json` `version` → 생성기가 `overlays/prod` `images.newTag` 에 넣는다). 그래서 **이전 태그의 `overlays/prod` 를 렌더하면 그 판본의 이미지 · 설정이 그대로 나온다.** 릴리스 노트의 '되돌리기' 절은 이 절을 가리키고, 그 판본에서 다른 점(마이그레이션 유무 등)만 적는다.

### 먼저 판단한다 — 데이터가 바뀌었나
| 이번 판본에 | 되돌리는 법 |
|---|---|
| 마이그레이션 없음 · 설정 · 코드만 | 아래 '전체 되돌리기' 또는 '이미지만 되돌리기' |
| 마이그레이션 있음(스키마 · 데이터 변경) | 이미지 · 오버레이를 되돌리고 **DB 는 배포 직전 백업으로 복원** — [백업 · 복원](#백업--복원) 절. DB 를 되돌리는 다른 길(손 SQL · 마이그레이션 downgrade)은 쓰지 않는다 |

서비스는 기동할 때 마이그레이션을 자기 heads 까지 올린다. 새 판본이 스키마를 올린 뒤 옛 이미지만 띄우면 옛 코드가 모르는 리비전이 DB 에 있어 **기동을 거부하거나**, 기동해도 새 스키마를 옛 코드가 쓰게 된다. 그래서 마이그레이션이 든 판본을 낼 때는 배포 직전에 수동 백업을 한 번 뜬다(`kubectl -n infra create job --from=cronjob/mariadb-backup mariadb-backup-before-vX.Y.Z`) — 그 덤프가 되돌아갈 자리다.

### 전체 되돌리기 — 이전 태그의 `overlays/prod` 로 apply
작업 트리를 건드리지 않게 이전 태그를 따로 꺼내 렌더한다.
```bash
git fetch --tags
git worktree add ../rollback-vX.Y.Z vX.Y.Z                      # X.Y.Z = 돌아갈 판본
kubectl kustomize ../rollback-vX.Y.Z/infra/k3s/overlays/prod > rollback.yaml
grep -n "image:" rollback.yaml | sort -u -k2                     # 서비스 · 웹 이미지 태그가 모두 :X.Y.Z 인지 눈으로 확인
kubectl apply -f rollback.yaml
kubectl -n <네임스페이스> rollout status deploy/<서비스> --timeout=5m   # 서비스 · 웹마다
git worktree remove ../rollback-vX.Y.Z
```
- `apply` 는 지우지 않는다 — 새 판본에서 **추가된** 리소스(새 서비스 · CronJob 등)는 남는다. 남으면 안 되는 것은 새 판본 노트의 '바뀐 것'을 보고 사람이 지운다
- 시크릿은 ExternalSecret 이 원격 저장소에서 다시 가져온다 — 새 판본에서 시크릿 키를 바꿨다면 원격 값도 함께 되돌렸는지 확인한다

### 이미지만 되돌리기 — 설정은 그대로, 코드만
설정 · 매니페스트는 맞고 코드만 문제일 때(마이그레이션 없는 판본만). 그 서비스만 이전 판본 이미지로 바꾼다.
```bash
kubectl -n <네임스페이스> set image deploy/<서비스> app=<image_registry>/<서비스>:X.Y.Z   # 웹은 컨테이너 이름 web
kubectl -n <네임스페이스> rollout status deploy/<서비스> --timeout=5m
```
이 상태는 git 의 생성물과 어긋난다(다음 apply 가 다시 새 이미지로 덮는다). 임시 조치다 — 고친 판본을 내거나 '전체 되돌리기'로 맞춘다. 바로 앞 배포로만 돌아가면 될 때는 `kubectl -n <네임스페이스> rollout undo deploy/<서비스>` 도 같은 효과다.

### 확인 지점 — readyz
되돌린 서비스마다 `/readyz` 가 200 이어야 끝이다. DB 에 닿지 못하면 503 `{"status": "db_unavailable"}` — DB 복원 · 계정 Job([백업 · 복원](#백업--복원) 절 3단계)을 먼저 본다.
```bash
kubectl -n <네임스페이스> port-forward svc/<서비스> 18000:8000 &
curl -fsS http://localhost:18000/readyz
```
게이트웨이 · 웹은 인그레스로 한 번 더 연다(로그인 화면이 뜨는가). 되돌린 사실(판본 · 이유 · 데이터 손실 여부)은 `/issue` 로 남긴다.
