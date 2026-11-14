#!/usr/bin/env bash
# Açık demonun duman testi: infra/k8s/smoke.sh, demo kullanıcısı ve demo kiracısıyla.
# DEMO_TLS=staging ile kurulduysa curl -k (staging sertifikasıyla uygulama girişi çalışmaz; runbook).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
# shellcheck source=/dev/null
. "$ROOT/infra/versions.env"
SSH_KEY=${SSH_KEY:-$HOME/.ssh/id_ed25519}
SSH_PUBLIC_KEY=${SSH_PUBLIC_KEY:-$SSH_KEY.pub}
KNOWN_HOSTS=$ROOT/infra/terraform/demo/known_hosts
# shellcheck source=/dev/null
. "$ROOT/infra/demo/lib.sh"

host=$(tf demo output -raw host)
insecure=0
[ "${DEMO_TLS:-prod}" = staging ] && insecure=1
KUBECONFIG=$(native_path "${DEMO_KUBECONFIG:-$ROOT/infra/terraform/demo/kubeconfig}") SMOKE_INSECURE=$insecure \
  SMOKE_VIEWER=demo SMOKE_VIEWER_PASSWORD=meridian-demo SMOKE_TENANT=meridian-demo \
  bash "$ROOT/infra/k8s/smoke.sh" "https://$host" demo meridian-demo
