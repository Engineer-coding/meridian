#!/usr/bin/env bash
# Demo realm'i gerçek Keycloak'a içe aktarılır: demo-admin'in parolası Secret'tan gelen ortam değişkeniyle
# (${DEMO_ADMIN_PASSWORD}) çözülmeli; yer tutucunun kendisi parola olarak çalışmamalı.
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))
# shellcheck source=/dev/null
. "$ROOT/infra/versions.env" 2>/dev/null || true
IMAGE=quay.io/keycloak/keycloak:26.8.0
NAME=meridian-kc-placeholder-$RANDOM
PORT=18299
PASSWORD="kc-$(openssl rand -hex 16)"
DIR=$(mktemp -d)
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1; rm -rf "$DIR"; }
trap cleanup EXIT

helm template meridian "$ROOT/infra/helm/meridian" -f "$ROOT/infra/helm/meridian/values-demo.yaml" \
  --set appUrl=https://meridian.1.2.3.4.sslip.io --set image.tag=test -s templates/keycloak.yaml \
  | PYTHONUTF8=1 python -c "import sys,yaml; [print(d['data']['meridian-realm.json']) for d in yaml.safe_load_all(sys.stdin) if d and d.get('kind')=='ConfigMap']" \
  > "$DIR/meridian-realm.json" || { echo "BAŞARISIZ: realm üretilemedi"; exit 1; }

mount=$DIR
command -v cygpath >/dev/null && mount=$(cygpath -m "$DIR")
docker run -d --name "$NAME" -p "127.0.0.1:$PORT:8080" -e DEMO_ADMIN_PASSWORD="$PASSWORD" \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
  -v "$mount:/opt/keycloak/data/import:ro" "$IMAGE" start-dev --import-realm >/dev/null || exit 1

URL="http://127.0.0.1:$PORT/realms/meridian/protocol/openid-connect/token"
for _ in $(seq 1 90); do
  curl -sf "http://127.0.0.1:$PORT/realms/meridian" >/dev/null && break
  sleep 2
done

token() {
  curl -s "$URL" -d grant_type=password -d client_id=meridian-dev-cli -d scope=openid \
    -d username=demo-admin --data-urlencode "password=$1" | grep -c '"access_token"'
}

failures=0
[ "$(token "$PASSWORD")" = 1 ] || { echo "BAŞARISIZ: demo-admin Secret'taki parolayla giremiyor"; failures=1; }
[ "$(token '${DEMO_ADMIN_PASSWORD}')" = 0 ] || { echo "BAŞARISIZ: yer tutucunun kendisi parola olarak çalışıyor"; failures=1; }
if ((failures)); then
  docker logs "$NAME" 2>&1 | grep -iE "import|placeholder|error" | tail -5
  exit 1
fi
echo "yer tutucu çalışıyor"
