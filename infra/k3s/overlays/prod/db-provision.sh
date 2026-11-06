#!/bin/bash
# 생성 파일 — scripts/gen_k3s.py (services.json · nova.project.json). 직접 고치지 않는다.
# 운영 DB 서비스 계정 프로비저닝(db-provision Job) — 서비스마다 스키마 · 계정 · 비밀번호 동기화 · 자기 스키마 권한.
# 멱등: IF NOT EXISTS · ALTER USER 라 다시 돌면 계정은 그대로, 비밀번호는 지금 시크릿 값으로 맞춘다(교체 절차).
# 비밀번호는 이 파일에 없다 — 프로비저닝 시크릿(키 <db>-password)과 root 비밀번호(MYSQL_PWD ← mariadb-root)는 환경 변수로만 받는다.
set -euo pipefail
HOST="${DB_HOST:-mariadb.infra.svc.cluster.local}"
q="'"
b='\'
sql_str() {  # SQL 문자열 리터럴 안에 넣을 수 있게 \ 와 ' 를 겹쳐 쓴다
  local s="${1//"$b"/"$b$b"}"
  printf '%s' "${s//"$q"/"$q$q"}"
}
secret() {  # 키에 '-' 가 있어 $이름 으로 읽지 못한다 — printenv 로 읽고, 없거나 비면 멈춘다(빈 비밀번호 계정을 만들지 않는다)
  local v
  if ! v="$(printenv "$1")" || [ -z "$v" ]; then
    echo "✗ 프로비저닝 시크릿 키 $1 없음 — ExternalSecret nova-db-provision 동기화를 확인한다" >&2
    exit 1
  fi
  sql_str "$v"
}
for i in $(seq 1 30); do  # MariaDB 기동 대기(최대 60초) — 그 뒤 실패는 Job backoffLimit 이 다시 돌린다
  if mariadb-admin --protocol=tcp -h "$HOST" -u root ping >/dev/null 2>&1; then break; fi
  if [ "$i" = 30 ]; then echo "✗ MariaDB($HOST) 응답 없음" >&2; exit 1; fi
  sleep 2
done

# sample
PW_sample="$(secret sample-password)"
mariadb --protocol=tcp -h "$HOST" -u root <<SQL
CREATE DATABASE IF NOT EXISTS sample CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'sample'@'%' IDENTIFIED BY '${PW_sample}';
ALTER USER 'sample'@'%' IDENTIFIED BY '${PW_sample}';
GRANT ALL PRIVILEGES ON sample.* TO 'sample'@'%';
FLUSH PRIVILEGES;
SQL
echo "✓ sample 계정 · 권한"
