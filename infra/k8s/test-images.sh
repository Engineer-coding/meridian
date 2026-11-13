#!/usr/bin/env bash
# Üretim imajlarının temel sözleşmesi: root olmayan kullanıcı, beklenen port, beklenen dosyalar.
set -uo pipefail

failures=0
fail() { echo "BAŞARISIZ: $*"; failures=$((failures + 1)); }

check_image() {
  local image=$1 port=$2
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    fail "$image yok (make images)"
    return
  fi
  local user
  user=$(docker image inspect --format '{{.Config.User}}' "$image")
  case "$user" in
    "" | root | 0 | 0:*) fail "$image root olarak çalışıyor (User='$user')" ;;
  esac
  docker image inspect --format '{{json .Config.ExposedPorts}}' "$image" | grep -q "\"$port/tcp\"" \
    || fail "$image $port portunu açmıyor"
}

has_file() {
  local image=$1 path=$2
  docker run --rm --entrypoint sh "$image" -c "test -f '$path'" 2>/dev/null || fail "$image içinde $path yok"
}

check_image meridian-api:local 8080
check_image meridian-ai:local 8090
check_image meridian-ai-test:local 8090
check_image meridian-web:local 3000
has_file meridian-ai-test:local /app/tests/e2e_stack.py
has_file meridian-web:local /app/server.js

if ((failures)); then
  echo "$failures denetim başarısız"
  exit 1
fi
echo "imaj denetimleri geçti"
