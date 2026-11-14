#!/usr/bin/env bash
# Canlı demoyu kapatır (ADR-0009): yalnızca demo state'i (sunucu, güvenlik duvarı, SSH anahtarı) silinir.
# Kalıcı IP kalır, link değişmez. Önce TLS sertifikası yedeklenir: Let's Encrypt aynı ad için haftada 5 sertifika verir.
#   HCLOUD_TOKEN=... make demo-down
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
# shellcheck source=/dev/null
. "$ROOT/infra/versions.env"
DEMO_KUBECONFIG=${DEMO_KUBECONFIG:-$ROOT/infra/terraform/demo/kubeconfig}
DEMO_TLS_BACKUP=${DEMO_TLS_BACKUP:-$ROOT/infra/gitops/demo/tls-backup.yaml}
SSH_KEY=${SSH_KEY:-$HOME/.ssh/id_ed25519}
SSH_PUBLIC_KEY=${SSH_PUBLIC_KEY:-$SSH_KEY.pub}
KNOWN_HOSTS=$ROOT/infra/terraform/demo/known_hosts

die() { echo "HATA: $*" >&2; exit 1; }
log() { echo "==> $*"; }
# shellcheck source=/dev/null
. "$ROOT/infra/demo/lib.sh"

[ -n "${HCLOUD_TOKEN:-}" ] || die "HCLOUD_TOKEN gerekli"

log "TLS sertifikası yedekleniyor"
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
if KUBECONFIG=$DEMO_KUBECONFIG kubectl -n meridian get secret meridian-tls -o yaml > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
  # Kümeye özgü kimlik alanları atılır: yedek yeni kümede olduğu gibi uygulanır.
  umask 077
  grep -vE '^\s+(uid|resourceVersion|creationTimestamp|managedFields):' "$tmp" > "$DEMO_TLS_BACKUP"
  echo "    yedek: $DEMO_TLS_BACKUP"
else
  echo "    UYARI: yedek alınamadı (küme kapalı ya da sertifika henüz yok); sonraki kurulum yeni sertifika ister"
fi

log "demo sunucusu siliniyor (kalıcı IP kalır)"
tf demo init -input=false >/dev/null
# destroy de değişkenleri ister; değerleri silinecek kaynakları etkilemez.
tf demo destroy -auto-approve -input=false -var "expires_at=0" -var "operator_cidr=0.0.0.0/32" \
  -var "k3s_version=$K3S_VERSION" -var "ssh_public_key_path=$(tf_key_path)"
rm -f "$DEMO_KUBECONFIG" "$KNOWN_HOSTS"
echo "Demo kapatıldı. Kalıcı IP duruyor; tekrar açmak için: make demo-up"
