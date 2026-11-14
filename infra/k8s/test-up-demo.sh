#!/usr/bin/env bash
# up.sh'in demo ortamı, sahte kubectl/kind/helm/git ile: hangi komutlar hangi değerlerle çağrılıyor?
# Gerçek bir kümeye ya da ağa dokunmaz.
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SHA=0123456789abcdef0123456789abcdef01234567
failures=0
check() { if eval "$2"; then echo "tamam: $1"; else echo "BAŞARISIZ: $1"; failures=$((failures + 1)); fi; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
LOG=$TMP/calls.log
APPLIED=$TMP/applied.yaml

# Sahte kubectl: çağrıları yazar, stdin'den uygulananları biriktirir, Argo durumunu "bu commit senkron" verir.
cat > "$TMP/bin/kubectl" <<EOF
#!/usr/bin/env bash
echo "kubectl \$*" >> "$LOG"
case "\$*" in
  *"apply"*"-f -"*) cat >> "$APPLIED"; echo "---" >> "$APPLIED" ;;
  *"get secret meridian-secrets"*) exit 1 ;;
  *"get nodes"*) echo "v1.37.1+k3s1" ;;
  *"{.status.sync.revision}"*) echo "$SHA" ;;
  *"{.status.sync.status}"*) echo "Synced" ;;
  *"operationState.syncResult.revision"*) echo "$SHA" ;;
  *"operationState.phase"*) echo "Succeeded" ;;
  *"create secret"*|*"create configmap"*) [ -n "\${STUB_DRY:-}" ] || true; echo "apiVersion: v1" ;;
esac
exit 0
EOF
for tool in kind helm docker; do
  printf '#!/usr/bin/env bash\necho "%s $*" >> "%s"\n' "$tool" "$LOG" > "$TMP/bin/$tool"
done
cat > "$TMP/bin/git" <<EOF
#!/usr/bin/env bash
echo "git \$*" >> "$LOG"
case "\$*" in *"rev-parse --abbrev-ref HEAD"*) echo feat ;; esac
exit 0
EOF
chmod +x "$TMP/bin/"*

SECRETS=$TMP/secrets.env
printf 'POSTGRES_DB=meridian\nPOSTGRES_USER=meridian\nPOSTGRES_PASSWORD=x\nANTHROPIC_API_KEY=k\nDEMO_ADMIN_PASSWORD=y\n' > "$SECRETS"
touch "$TMP/kubeconfig"

run() { # run [ortam değişkenleri...]
  : > "$LOG"; : > "$APPLIED"
  env PATH="$TMP/bin:$PATH" KUBECONFIG="$TMP/kubeconfig" APP_HOST=meridian.1.2.3.4.sslip.io \
    DEMO_SECRETS="$SECRETS" DEMO_TLS_BACKUP="$TMP/tls-backup.yaml" "$@" \
    bash "$ROOT/infra/k8s/up.sh" demo argo "$SHA" > "$TMP/out.log" 2>&1
}

run
[ -n "${DEBUG:-}" ] && { cat "$TMP/out.log"; cat "$LOG"; }
check "demo kurulumu başarıyla biter" "grep -q 'hazır: https://meridian.1.2.3.4.sslip.io' '$TMP/out.log'"
check "kind hiç çağrılmaz" "! grep -q '^kind ' '$LOG'"
check "uygulama GHCR imaj etiketiyle uygulanır" "grep -q 'value: sha-0123456' '$APPLIED'"
check "uygulama https adresiyle uygulanır" "grep -q 'value: https://meridian.1.2.3.4.sslip.io' '$APPLIED'"
check "uygulama bu commit'e sabitlenir" "grep -q 'targetRevision: $SHA' '$APPLIED'"
check "cert-manager sabit sürümden kurulur" "grep -q 'cert-manager/releases/download/v1.21.3/cert-manager.yaml' '$LOG'"
check "üretim sertifikası istenir" "grep -q 'value: letsencrypt\$' '$APPLIED'"
check "k3s'te CoreDNS özel ConfigMap'le yönlendirilir" "grep -q 'create configmap coredns-custom --from-literal=meridian.override=rewrite name exact meridian.1.2.3.4.sslip.io' '$LOG'"
check "Secret demo sırlar dosyasından kurulur" "grep -q 'create secret generic meridian-secrets' '$LOG'"

run DEMO_TLS=staging
check "staging'de staging sertifikası istenir" "grep -q 'value: letsencrypt-staging' '$APPLIED'"

echo "apiVersion: v1" > "$TMP/tls-backup.yaml"
run
first_restore=$(grep -n "tls-backup.yaml" "$LOG" | head -1 | cut -d: -f1)
first_argo=$(grep -n "argocd" "$LOG" | head -1 | cut -d: -f1)
check "TLS yedeği Argo'dan önce geri yüklenir" "[ -n '$first_restore' ] && [ '$first_restore' -lt '$first_argo' ]"
rm -f "$TMP/tls-backup.yaml"

: > "$LOG"
env -u KUBECONFIG PATH="$TMP/bin:$PATH" APP_HOST=meridian.1.2.3.4.sslip.io DEMO_SECRETS="$SECRETS" \
  bash "$ROOT/infra/k8s/up.sh" demo argo "$SHA" > "$TMP/out.log" 2>&1
rc=$?
check "KUBECONFIG yoksa durur" "[ $rc -ne 0 ] && grep -q KUBECONFIG '$TMP/out.log'"
check "KUBECONFIG yoksa kubectl çağrılmaz" "! grep -q '^kubectl' '$LOG'"

if ((failures)); then
  echo "--- son çıktı:"; tail -5 "$TMP/out.log"; echo "--- çağrılar:"; head -12 "$LOG"
  echo "$failures denetim başarısız"
  exit 1
fi
echo "demo up denetimleri geçti"
