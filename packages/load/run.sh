#!/usr/bin/env bash
# Yük testi (ADR-0019): atılabilir altyapı (compose.e2e), gerçek API ve AI servisi, k6 Docker'da.
#   SCENARIO=chat     500 eşzamanlı sohbet (VUS, RAMP, HOLD ile değişir)
#   SCENARIO=indexing 50 eşzamanlı indeksleme işi (JOBS)
# Model ve embedding sahtedir: ölçülen, sistemin kapasitesidir, modelin değil. Model gecikmesi MODEL_DELAY
# ("kanıt,ilk_token,toplam" saniye) ile taklit edilir.
#
# AI servisi üretimdeki gibi Linux kapsayıcısında çalışır. Windows'ta psycopg'nin istediği select() döngüsü
# ~512 soketle sınırlı; 500 eşzamanlı akışta "too many file descriptors" ile istek kaybediyordu (denemede).
# API, JVM'de bu sınır olmadığı için doğrudan çalışır.
set -euo pipefail
[ -n "${LOAD_DEBUG:-}" ] && set -x

SCENARIO=${SCENARIO:-chat}
MODEL_DELAY=${MODEL_DELAY:-1,0.5,3}
SAMPLING=${SAMPLING:-0.1}
DB_POOL_SIZE=${DB_POOL_SIZE:-4}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
REPORTS=$ROOT/packages/load/reports
LOGS=$REPORTS/logs
mkdir -p "$LOGS"
export MSYS_NO_PATHCONV=1
# Docker ve Java Windows yolu ister; Git Bash'in /c/... biçimi yol çevirisi kapalıyken tanınmaz.
ROOT_W=$(cygpath -m "$ROOT" 2>/dev/null || echo "$ROOT")
COMPOSE="docker compose -f $ROOT_W/infra/compose/compose.e2e.yaml --env-file $ROOT_W/.env.example"
NETWORK=meridian-e2e_default
AI_CONTAINER=meridian-load-ai

# Yerel geliştirme parolaları; yük ortamı atılabilirdir.
set -a
# shellcheck disable=SC1091
source <(grep -v '^#' "$ROOT/.env.example" | sed 's/\r$//')
set +a

pids=()
script_started=$(date +%s)
cleanup() {
  # Yalnızca bu betiğin başlattıkları kapanır, Windows süreç kimliğiyle ağacıyla birlikte. Git Bash'in kill'i
  # alt süreçleri yetim bırakıyor, porta göre kapatmak ise sistem süreçlerini hedef alıyordu (denemede).
  for pid in "${pids[@]}"; do taskkill /T /F /PID "$pid" >/dev/null 2>&1 || true; done
  # Süreç kimliği java'da her zaman tutmadı (denemede bir API süreci kaldı ve jar'ı kilitledi).
  powershell -NoProfile -ExecutionPolicy Bypass -File "$ROOT_W/packages/load/stop.ps1" -StartedUnix "$script_started" || true
  docker logs "$AI_CONTAINER" >"$LOGS/ai-$SCENARIO.log" 2>&1 || true
  docker rm -f "$AI_CONTAINER" >/dev/null 2>&1 || true
  # KEEP=1: izler ve metrikler incelenebilsin diye altyapı ayakta kalır (Grafana http://127.0.0.1:13001).
  [ -n "${KEEP:-}" ] || $COMPOSE down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

# 18080 boş olmalı: başka bir süreç dinliyorsa ölçüm ona gider. Sahibi 0 olan kayıtlar ölmüş süreçlerden kalır.
if powershell -NoProfile -Command 'if (Get-NetTCPConnection -State Listen -LocalPort 18080 -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 0 }) { exit 0 } else { exit 1 }'; then
  echo "18080 portu kullanımda; önce o süreci kapatın." >&2
  trap - EXIT
  exit 1
fi
docker rm -f "$AI_CONTAINER" >/dev/null 2>&1 || true
$COMPOSE down -v >/dev/null 2>&1 || true
$COMPOSE up -d --wait
(cd "$ROOT/apps/api" && ./mvnw -B -q -DskipTests package)
# İmaj yalnızca yoksa ya da BUILD=1 ise derlenir: derleme temel imaj için ağa çıkar.
if [ -n "${BUILD:-}" ] || ! docker image inspect meridian-ai:load >/dev/null 2>&1; then
  docker build -q -t meridian-ai:load "$ROOT_W/apps/ai-service" >/dev/null
fi

# Tek kullanıcıyla yük üretildiği için kullanıcı başına oran sınırı ve günlük kota yük ortamında kaldırılır.
env OTEL_EXPORT=true OTEL_ENDPOINT=http://127.0.0.1:14318 OTEL_SAMPLING="$SAMPLING" DEPLOYMENT_ENVIRONMENT=load \
  SERVER_PORT=18080 \
  SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:15432/meridian \
  SPRING_RABBITMQ_PORT=15673 \
  SPRING_DATA_REDIS_PORT=16379 \
  SPRING_SECURITY_OAUTH2_RESOURCESERVER_JWT_ISSUER_URI=http://localhost:18180/realms/meridian \
  MERIDIAN_AI_URL=http://127.0.0.1:18090 \
  MERIDIAN_CHAT_RATE_CAPACITY=1000000 \
  MERIDIAN_CHAT_RATE_REFILL_PER_MINUTE=1000000 \
  MERIDIAN_USAGE_DAILY_TOKENS_FREE=100000000000 \
  API_DB_POOL_SIZE="${API_POOL_SIZE:-20}" \
  java -jar "$ROOT_W/apps/api/target/api-0.0.1-SNAPSHOT.jar" >"$LOGS/api-$SCENARIO.log" 2>&1 &
pids+=("$(cat /proc/$!/winpid)")

# Sahte model ve embedding'li AI servisi (tests/e2e_stack.py) üretim imajında, altyapıyla aynı ağda.
# AI_DOCKER_ARGS: ör. profil için "--cap-add SYS_PTRACE".
# shellcheck disable=SC2086
docker run -d --name "$AI_CONTAINER" --network "$NETWORK" -p 127.0.0.1:18090:8090 ${AI_DOCKER_ARGS:-} \
  -v "$ROOT_W/apps/ai-service/tests/e2e_stack.py:/stack/e2e_stack.py:ro" \
  -e RABBITMQ_USER -e RABBITMQ_PASSWORD -e DB_AI_PASSWORD -e AI_INTERNAL_TOKEN \
  -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 -e RABBITMQ_HOST=rabbitmq -e RABBITMQ_PORT=5672 \
  -e API_URL=http://host.docker.internal:18080 \
  -e OTEL_EXPORT=true -e OTEL_ENDPOINT=http://otel-collector:4318 -e OTEL_SAMPLING="$SAMPLING" \
  -e DEPLOYMENT_ENVIRONMENT=load -e DB_POOL_SIZE="$DB_POOL_SIZE" \
  -e E2E_MODEL_DELAY="$MODEL_DELAY" -e E2E_PAGES=10 -e HTTP_HOST=0.0.0.0 -e HTTP_PORT=8090 \
  -e AI_WORKERS="${AI_WORKERS:-2}" \
  meridian-ai:load python /stack/e2e_stack.py >/dev/null

wait_for() {
  for _ in $(seq 1 120); do
    # -o /dev/null kullanılmaz: yol çevirisi kapalıyken Windows curl bu yolu açamaz.
    curl -fs "$1" >/dev/null && return 0
    sleep 1
  done
  echo "hazır olmadı: $1" >&2
  return 1
}
wait_for http://127.0.0.1:18080/actuator/health/readiness
wait_for http://127.0.0.1:18090/health/ready

# İşlemci süresi (saniye) "api ai": API Windows sürecinden, AI kapsayıcının cgroup sayacından.
cpu() {
  local api ai
  api=$(powershell -NoProfile -ExecutionPolicy Bypass -File "$ROOT_W/packages/load/cpu.ps1" | tr -d '\r')
  ai=$(docker exec "$AI_CONTAINER" sh -c "awk '/usage_usec/ {print \$2 / 1000000}' /sys/fs/cgroup/cpu.stat")
  echo "$api $ai"
}

start=$(date +%s)
cpu_start=$(cpu)
status=0
docker run --rm -i \
  -v "$ROOT_W/packages/load:/load" \
  -e VUS -e RAMP -e HOLD -e JOBS \
  grafana/k6:2.3.0 run --quiet --summary-export="/load/reports/$SCENARIO-summary.json" "/load/$SCENARIO.js" \
  | tee "$REPORTS/$SCENARIO-k6.txt" || status=$?
end=$(date +%s)
cpu_end=$(cpu)

# Metrikler 15 sn'de bir gönderilir; son turun da Prometheus'a ulaşması beklenir.
sleep 35
(cd "$ROOT/apps/ai-service" && PYTHONUTF8=1 uv run python "$ROOT_W/packages/load/server_metrics.py" "$SCENARIO" \
  "$start" "$end" "$cpu_start" "$cpu_end" "$MODEL_DELAY" "$SAMPLING" "$DB_POOL_SIZE" "${AI_WORKERS:-2}" "${API_POOL_SIZE:-20}" >"$REPORTS/$SCENARIO-server.json")
echo "rapor: packages/load/reports/$SCENARIO-*.json (k6 çıkış kodu $status)"
exit "$status"
