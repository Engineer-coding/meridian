#!/usr/bin/env bash
# Canlı demoyu açar (ADR-0009): kalıcı IP (bir kez) → k3s sunucusu (Terraform) → Meridian (infra/k8s/up.sh demo).
# Tekrar çalıştırmak güvenli: aynı sunucu kalır, süre (expires-at) yeniden belirlenir, sırlar korunur.
#   HCLOUD_TOKEN=... make demo-up                 (ANTHROPIC_API_KEY ortamda ya da kökteki .env'de)
#   DEMO_HOURS=4  DEMO_TLS=prod|staging  DEMO_REVISION=<commit>  ACME_EMAIL=...  SSH_KEY=~/.ssh/id_ed25519
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
# shellcheck source=/dev/null
. "$ROOT/infra/versions.env"
DEMO_HOURS=${DEMO_HOURS:-4}
DEMO_SECRETS=${DEMO_SECRETS:-$ROOT/infra/gitops/demo/secrets.env}
DEMO_KUBECONFIG=${DEMO_KUBECONFIG:-$ROOT/infra/terraform/demo/kubeconfig}
DEMO_ENV_FILE=${DEMO_ENV_FILE:-$ROOT/.env}
SSH_KEY=${SSH_KEY:-$HOME/.ssh/id_ed25519}
SSH_PUBLIC_KEY=${SSH_PUBLIC_KEY:-$SSH_KEY.pub}
KNOWN_HOSTS=${DEMO_KNOWN_HOSTS:-$ROOT/infra/terraform/demo/known_hosts}

die() { echo "HATA: $*" >&2; exit 1; }
log() { echo "==> $*"; }
# shellcheck source=/dev/null
. "$ROOT/infra/demo/lib.sh"

# --- ön kontroller: hiçbir şey açılmadan durur --------------------------------------------------
[ -n "${HCLOUD_TOKEN:-}" ] || die "HCLOUD_TOKEN gerekli (Hetzner projesinin API token'ı; runbook: docs/runbooks/demo.md)"
if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -f "$DEMO_ENV_FILE" ]; then
  ANTHROPIC_API_KEY=$(grep -E '^ANTHROPIC_API_KEY=' "$DEMO_ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\r' || true)
fi
[ -n "${ANTHROPIC_API_KEY:-}" ] || die "ANTHROPIC_API_KEY gerekli: demoda model yalnızca Claude Haiku (ortam ya da .env)"
[ -f "$SSH_PUBLIC_KEY" ] || die "SSH açık anahtarı yok: $SSH_PUBLIC_KEY (SSH_KEY=... ile değiştirin)"
case "${DEMO_TLS:-prod}" in prod | staging) ;; *) die "DEMO_TLS prod ya da staging olmalı" ;; esac

# Kurulacak commit ve imajları: GHCR'da yoksa (images iş akışı bitmemiş, başarısız ya da paketler özel)
# sunucu açılmadan durulur; yoksa ücretli sunucu ImagePullBackOff'ta bekler.
revision=${DEMO_REVISION:-$(git -C "$ROOT" ls-remote origin refs/heads/main | cut -f1)}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || die "main'in commit'i bulunamadı (DEMO_REVISION=<40 karakter> verin)"
for image in api ai web; do
  ref="ghcr.io/engineer-coding/meridian-$image:sha-${revision:0:7}"
  docker manifest inspect "$ref" >/dev/null 2>&1     || die "$ref yok ya da herkese açık değil (images iş akışını ve GHCR paket görünürlüğünü kontrol edin)"
done

# Unutulan sunucuyu silen iş açık mı? GitHub, etkinliği olmayan herkese açık repoda zamanlanmış işleri
# 60 gün sonra kapatır; HCLOUD_TOKEN sırrı yoksa iş her saat "başarılı" görünür ama hiçbir şey silmez.
if command -v gh >/dev/null; then
  state=$(gh workflow view demo-reaper.yml --json state --jq .state 2>/dev/null || echo bilinmiyor)
  [ "$state" = active ] || echo "UYARI: demo-reaper iş akışı açık değil ($state): sunucuyu kendiniz kapatın (make demo-down) ya da Actions'tan etkinleştirin" >&2
  gh secret list 2>/dev/null | grep -q '^HCLOUD_TOKEN'     || echo "UYARI: demo-reaper için HCLOUD_TOKEN repo sırrı yok: süresi geçen sunucu silinmez" >&2
else
  echo "UYARI: demo-reaper durumu denetlenemedi (gh yok): sunucuyu kapatmayı unutmayın" >&2
fi

# --- sırlar: yalnızca ilk kurulumda üretilir ------------------------------------------------------
if [ ! -f "$DEMO_SECRETS" ]; then
  log "demo sırları üretiliyor ($DEMO_SECRETS, git dışında)"
  mkdir -p "$(dirname "$DEMO_SECRETS")"
  umask 077
  {
    echo "POSTGRES_DB=meridian"
    echo "POSTGRES_USER=meridian"
    echo "RABBITMQ_USER=meridian"
    for key in POSTGRES_PASSWORD DB_OWNER_PASSWORD DB_APP_PASSWORD DB_RELAY_PASSWORD DB_AI_PASSWORD \
      RABBITMQ_PASSWORD KEYCLOAK_ADMIN_PASSWORD GRAFANA_ADMIN_PASSWORD AI_INTERNAL_TOKEN DEMO_ADMIN_PASSWORD; do
      echo "$key=$(openssl rand -hex 24)"
    done
    echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
    github=$(grep -E '^GITHUB_TOKEN=.' "$DEMO_ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' || true)
    [ -n "$github" ] && echo "GITHUB_TOKEN=$github"
  } > "$DEMO_SECRETS"
fi

# --- Terraform: kalıcı IP ve sunucu ------------------------------------------------------------------
operator_cidr=${OPERATOR_CIDR:-$(curl -s -m 10 https://checkip.amazonaws.com | tr -d '[:space:]')/32}
[[ "$operator_cidr" =~ ^[0-9.]+/[0-9]+$ ]] || die "operatör IP'si bulunamadı; OPERATOR_CIDR=<ip>/32 verin"
expires_at=$(($(date +%s) + DEMO_HOURS * 3600))

if ! ip=$(tf persistent output -raw ip 2>/dev/null) || [ -z "$ip" ]; then
  log "kalıcı IP oluşturuluyor (bir kez)"
  tf persistent init -input=false >/dev/null
  tf persistent apply -auto-approve -input=false
  ip=$(tf persistent output -raw ip)
fi

log "demo sunucusu ($ip, $DEMO_HOURS saat)"
tf demo init -input=false >/dev/null
tf demo apply -auto-approve -input=false -var "expires_at=$expires_at" -var "operator_cidr=$operator_cidr" \
  -var "k3s_version=$K3S_VERSION" -var "ssh_public_key_path=$(tf_key_path)"
host=$(tf demo output -raw host)
# Sunucu yeniden kurulmuş olabilir (aynı IP, yeni host anahtarı; ör. silme işinden sonra): eski anahtar unutulur.
rm -f "$KNOWN_HOSTS"

# --- k3s hazır olunca kubeconfig ------------------------------------------------------------------------
log "k3s bekleniyor"
ready=""
for _ in $(seq 1 "${DEMO_SSH_WAIT:-60}"); do
  if demo_ssh "$ip" 'test -f /etc/rancher/k3s/k3s.yaml' 2>/dev/null; then ready=1; break; fi
  sleep 10
done
[ -n "$ready" ] || die "k3s 10 dakikada hazır olmadı (ssh root@$ip 'cloud-init status --long')"
umask 077
demo_ssh "$ip" 'cat /etc/rancher/k3s/k3s.yaml' | sed "s|https://127.0.0.1:6443|https://$ip:6443|" > "$DEMO_KUBECONFIG"

# --- Meridian ----------------------------------------------------------------------------------------
KUBECONFIG=$(native_path "$DEMO_KUBECONFIG") APP_HOST=$host DEMO_SECRETS=$DEMO_SECRETS DEMO_TLS=${DEMO_TLS:-prod} \
  bash "${DEMO_UP_K8S:-$ROOT/infra/k8s/up.sh}" demo argo "$revision"

until_local=$(date -d "@$expires_at" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "$expires_at")
echo
echo "Demo hazır: https://$host"
echo "  giriş: demo / meridian-demo"
echo "  sunucu $until_local'de otomatik silinir; kapatmak için: make demo-down"
echo "  maliyet: CPX32 ~€0,05/saat (+ kalıcı IP); Haiku soru başına ~\$0,0005"
