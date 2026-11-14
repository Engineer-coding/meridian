#!/usr/bin/env bash
# Kümedeki Meridian'ın duman testi (ADR-0009): adres, kimlik, iç ağ ve ağ politikası.
#   bash infra/k8s/smoke.sh http://meridian.localtest.me alice alice
set -uo pipefail

APP=${1:?appUrl}
USER_NAME=${2:?kullanıcı}
USER_PASSWORD=${3:?parola}
NS=${K8S_NAMESPACE:-meridian}
ISSUER="$APP/auth/realms/meridian"
CURL_IMAGE=curlimages/curl:8.17.0

failures=0
step() { echo "== $*"; }
ok() { echo "   tamam: $*"; }
fail() { echo "   BAŞARISIZ: $*"; failures=$((failures + 1)); }

# Geçici bir pod içinde komut; etiket ağ politikasını sınamak için verilir. Çıktı loglardan okunur:
# `kubectl run -i --rm` kısa süren kapsayıcının çıktısını bağlanmadan kaçırabiliyor. Çıkış kodu pod'unkidir.
in_cluster() {
  local name="$1-$RANDOM$RANDOM" component=$2 phase=""
  shift 2
  kubectl -n "$NS" run "$name" --restart=Never --quiet --image="$CURL_IMAGE" \
    --labels="app.kubernetes.io/component=$component" --command -- "$@" >/dev/null 2>&1 || return 1
  for _ in $(seq 1 120); do
    phase=$(kubectl -n "$NS" get pod "$name" -o jsonpath='{.status.phase}' 2>/dev/null)
    [ "$phase" = Succeeded ] || [ "$phase" = Failed ] && break
    sleep 1
  done
  kubectl -n "$NS" logs "$name" 2>/dev/null
  kubectl -n "$NS" delete pod "$name" --wait=false >/dev/null 2>&1
  [ "$phase" = Succeeded ]
}

step "1. web sayfası"
code=$(curl -s -o /dev/null -w '%{http_code}' "$APP/signed-out")
[ "$code" = 200 ] && ok "/signed-out 200" || fail "/signed-out $code"

step "2. issuer tarayıcıdan"
issuer=$(curl -s "$ISSUER/.well-known/openid-configuration" | sed -n 's/.*"issuer":"\([^"]*\)".*/\1/p')
[ "$issuer" = "$ISSUER" ] && ok "issuer $issuer" || fail "issuer '$issuer' (beklenen $ISSUER)"

step "3. issuer küme içinden (CoreDNS yönlendirmesi)"
inner=$(in_cluster issuer smoke curl -s -m 10 "$ISSUER/.well-known/openid-configuration" | sed -n 's/.*"issuer":"\([^"]*\)".*/\1/p')
[ "$inner" = "$ISSUER" ] && ok "pod issuer'a ulaşıyor" || fail "pod issuer'a ulaşamıyor ('$inner')"

step "4. API hazır"
ready=$(in_cluster api web curl -s -m 10 http://meridian-api:8080/actuator/health/readiness)
case "$ready" in *'"UP"'*) ok "readiness UP" ;; *) fail "readiness: $ready" ;; esac

step "5. ağ politikası: web, AI servisine ulaşamaz"
if in_cluster netpol web curl -s -m 5 -o /dev/null http://meridian-ai:8090/health/live; then
  fail "web etiketli pod meridian-ai:8090'a ulaştı"
else
  ok "web → ai engellendi"
fi
if in_cluster netpol-api api curl -s -m 5 -o /dev/null http://meridian-ai:8090/health/live; then
  ok "api → ai açık"
else
  fail "api etiketli pod meridian-ai:8090'a ulaşamadı"
fi

if [ -f "$(dirname "$0")/smoke-seed.sh" ] && [ "${SMOKE_SEED:-1}" = 1 ]; then
  # shellcheck source=/dev/null
  . "$(dirname "$0")/smoke-seed.sh"
fi

if ((failures)); then
  echo "$failures adım başarısız"
  exit 1
fi
echo "duman testi geçti"
