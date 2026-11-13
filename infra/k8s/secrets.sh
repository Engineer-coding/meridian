#!/usr/bin/env bash
# meridian-secrets'ı bir env dosyasından oluşturur (ADR-0009). Secret zaten varsa DOKUNMAZ:
# PostgreSQL rolleri ilk açılışta bu parolalarla kurulur; parolayı değiştirmek veriyle uyuşmazlık yaratır.
#   bash infra/k8s/secrets.sh .env
set -euo pipefail

ENV_FILE=${1:?env dosyası}
NS=${K8S_NAMESPACE:-meridian}
NAME=meridian-secrets

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS" >/dev/null
if kubectl -n "$NS" get secret "$NAME" >/dev/null 2>&1; then
  echo "$NAME zaten var; değiştirilmedi"
  exit 0
fi

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
# Yorumlar, boş satırlar ve CRLF ayıklanır; oturum anahtarı her kümeye özel üretilir.
grep -E '^[A-Z_][A-Z0-9_]*=' "$ENV_FILE" | tr -d '\r' | grep -v '^SESSION_SECRET=' > "$tmp"
grep -q '^ANTHROPIC_API_KEY=' "$tmp" || echo "ANTHROPIC_API_KEY=" >> "$tmp"
echo "SESSION_SECRET=$(openssl rand -base64 32)" >> "$tmp"

# Windows (Git Bash): kubectl.exe /tmp yolunu tanımaz.
file=$tmp
command -v cygpath >/dev/null && file=$(cygpath -m "$tmp")
kubectl -n "$NS" create secret generic "$NAME" --from-env-file="$file" >/dev/null
echo "$NAME oluşturuldu ($(wc -l < "$tmp") anahtar)"
