#!/usr/bin/env bash
# 서비스별 uvicorn 프로세스(목록: nova_common/services.json) + (선택) Kafka — k3s 와 같은 "프로세스 = 서비스" 구성을 로컬에서.
#   bash scripts/run_local.sh                                  # 기동 (Kafka 없으면 서비스마다 메모리 버스 → 서비스 간 이벤트 없음)
#   KAFKA_BOOTSTRAP=localhost:9092 bash scripts/run_local.sh   # Kafka 사용
#   bash scripts/run_local.sh stop                             # 종료
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && { set -a; . ./.env; set +a; }  # 로컬 MariaDB 접속 정보(scripts/local_db_setup.py)
RUN=${RUN_DIR:-.run}
mkdir -p "$RUN" data

# 가상환경(uv sync 가 만든 .venv)을 우선 사용
if [ -z "${PY:-}" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python
  elif [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
  else PY=python; fi
fi
case "$PY" in */*) PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")" ;; esac  # 서비스 폴더로 cd 해도 같은 파이썬

cat_() { "$PY" -m nova_common.catalog "$@" | tr -d '\r'; }

if [ "${1:-}" = "stop" ]; then
  for f in "$RUN"/*.pid; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"; done
  echo "중지됨"; exit 0
fi

declare -A PORT=()
ORDER=()
for kv in $(cat_ ports); do PORT[${kv%%=*}]=${kv#*=}; ORDER+=("${kv%%=*}"); done
GATEWAY=$("$PY" -c "from nova_common import catalog; print(catalog.gateway())" | tr -d '\r')

for s in "${ORDER[@]}"; do export "SVC_$(echo "$s" | tr 'a-z-' 'A-Z_')_URL=http://127.0.0.1:${PORT[$s]}"; done
export PROMETHEUS_URL=${PROMETHEUS_URL:-}
for s in "${ORDER[@]}"; do  # 카탈로그 순서 = 기동 순서(게이트웨이 마지막)
  pkg=$(cat_ package "$s")
  ( cd "services/$s" && exec "$PY" -m uvicorn "$pkg.main:app" --host 127.0.0.1 --port "${PORT[$s]}" --no-access-log ) > "$RUN/$s.log" 2>&1 &
  echo $! > "$RUN/$s.pid"
done
for s in "${ORDER[@]}"; do
  for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:${PORT[$s]}/readyz" >/dev/null && break; sleep 0.5; done
  curl -sf "http://127.0.0.1:${PORT[$s]}/readyz" >/dev/null || { echo "$s 기동 실패"; tail -20 "$RUN/$s.log"; exit 1; }
done
echo "준비됨 — 게이트웨이 http://127.0.0.1:${PORT[$GATEWAY]}/v1 · 버스=${KAFKA_BOOTSTRAP:-inmemory}"
