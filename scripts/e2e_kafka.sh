#!/usr/bin/env bash
# 실제 Kafka(KRaft 단일 브로커) + 서비스별 프로세스(nova_common/services.json)로 E2E — python nova.py e2e-kafka
#   KAFKA_HOME=/path/to/kafka_2.13-3.9.1 bash scripts/e2e_kafka.sh
# 필요: bash · curl · Java 17+ (Linux · WSL · macOS). Windows 기본 셸은 지원하지 않는다.
# KAFKA_HOME 이 없으면 archive.apache.org 에서 3.9.1 바이너리를 받는다(Docker 불필요).
set -euo pipefail
cd "$(dirname "$0")/.."
WORK=${E2E_DIR:-$(mktemp -d)}
mkdir -p "$WORK"
KAFKA_HOME=${KAFKA_HOME:-$WORK/kafka_2.13-3.9.1}
if [ ! -x "$KAFKA_HOME/bin/kafka-server-start.sh" ]; then
  curl -sSL -o "$WORK/k.tgz" https://archive.apache.org/dist/kafka/3.9.1/kafka_2.13-3.9.1.tgz
  tar xzf "$WORK/k.tgz" -C "$WORK"
fi
PORT=${KAFKA_PORT:-19092}
cat > "$WORK/server.properties" <<EOP
process.roles=broker,controller
node.id=1
controller.quorum.voters=1@127.0.0.1:$((PORT+1))
listeners=PLAINTEXT://127.0.0.1:$PORT,CONTROLLER://127.0.0.1:$((PORT+1))
advertised.listeners=PLAINTEXT://127.0.0.1:$PORT
controller.listener.names=CONTROLLER
listener.security.protocol.map=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
log.dirs=$WORK/kafka-data
auto.create.topics.enable=false
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
group.initial.rebalance.delay.ms=0
EOP
export KAFKA_HEAP_OPTS="-Xms256m -Xmx512m"
unset JAVA_TOOL_OPTIONS 2>/dev/null || true
"$KAFKA_HOME/bin/kafka-storage.sh" format -t "$("$KAFKA_HOME/bin/kafka-storage.sh" random-uuid)" -c "$WORK/server.properties" >/dev/null
"$KAFKA_HOME/bin/kafka-server-start.sh" "$WORK/server.properties" > "$WORK/kafka.log" 2>&1 &
KPID=$!
export RUN_DIR="$WORK/run"
cleanup() { bash scripts/run_local.sh stop >/dev/null 2>&1 || true; kill $KPID 2>/dev/null || true; wait $KPID 2>/dev/null || true; }
trap cleanup EXIT
B=127.0.0.1:$PORT
for _ in $(seq 1 60); do "$KAFKA_HOME/bin/kafka-broker-api-versions.sh" --bootstrap-server $B >/dev/null 2>&1 && break; sleep 1; done
echo "Kafka 기동 ($B) — 토픽 생성"
grep -v '^#' infra/k3s/base/kafka-topics.txt | while read -r t p _d; do
  [ -z "$t" ] && continue
  echo "--create --if-not-exists --topic $t --partitions $p"
  echo "--create --if-not-exists --topic $t.dlq --partitions 1"
done > "$WORK/topics.args"
while read -r line; do "$KAFKA_HOME/bin/kafka-topics.sh" --bootstrap-server $B $line >/dev/null; done < "$WORK/topics.args"
echo "토픽: $("$KAFKA_HOME/bin/kafka-topics.sh" --bootstrap-server $B --list | wc -l)"
# 각 서비스 전용 SQLite 파일(서비스별 DB) — MariaDB 대신
PY=${PY:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python )}
for s in $("$PY" -m nova_common.catalog db | tr -d '\r' | tr - _); do export "DATABASE_URL_${s^^}=sqlite:///$WORK/db/$s.db"; done
mkdir -p "$WORK/db"
KAFKA_BOOTSTRAP=$B bash scripts/run_local.sh
"$PY" scripts/e2e_check.py http://127.0.0.1:8080/v1
LAG=$("$KAFKA_HOME/bin/kafka-consumer-groups.sh" --bootstrap-server $B --describe --all-groups 2>/dev/null | awk '$6 ~ /^[0-9]+$/ {s+=$6} END {print s+0}')
echo "컨슈머 그룹 lag 합계: $LAG"
