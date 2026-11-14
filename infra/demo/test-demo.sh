#!/usr/bin/env bash
# infra/demo/up.sh ve down.sh, sahte terraform/ssh/kubectl/git/curl ile: Hetzner'e ya da ağa dokunmaz.
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SHA=fedcba9876543210fedcba9876543210fedcba98
failures=0
check() { if eval "$2"; then echo "tamam: $1"; else echo "BAŞARISIZ: $1"; failures=$((failures + 1)); fi; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
LOG=$TMP/calls.log

# terraform: dizin adıyla kaydeder; kalıcı IP ilk apply'dan sonra "var" olur.
cat > "$TMP/bin/terraform" <<EOF
#!/usr/bin/env bash
dir=\$(basename "\$PWD")
echo "terraform \$dir \$*" >> "$LOG"
case "\$dir \$*" in
  "persistent output -raw ip") [ -f "$TMP/ip" ] && echo 1.2.3.4 || exit 1 ;;
  "persistent apply"*) touch "$TMP/ip" ;;
  "demo output -raw ip") echo 1.2.3.4 ;;
  "demo output -raw host") echo meridian.1.2.3.4.sslip.io ;;
esac
exit 0
EOF
cat > "$TMP/bin/ssh" <<EOF
#!/usr/bin/env bash
echo "ssh \$*" >> "$LOG"
case "\$*" in *"cat /etc/rancher/k3s/k3s.yaml"*) printf 'clusters:\n- cluster:\n    server: https://127.0.0.1:6443\n' ;; esac
exit 0
EOF
cat > "$TMP/bin/kubectl" <<EOF
#!/usr/bin/env bash
echo "kubectl \$*" >> "$LOG"
[ -n "\${FAKE_NO_CLUSTER:-}" ] && exit 1
case "\$*" in *"get secret meridian-tls"*) printf 'apiVersion: v1\nkind: Secret\nmetadata:\n  name: meridian-tls\n  uid: abc\n  resourceVersion: "1"\n' ;; esac
exit 0
EOF
cat > "$TMP/bin/git" <<EOF
#!/usr/bin/env bash
echo "git \$*" >> "$LOG"
case "\$*" in *"ls-remote"*) printf '%s\trefs/heads/main\n' "$SHA" ;; esac
exit 0
EOF
printf '#!/usr/bin/env bash\necho "curl $*" >> "%s"\necho 203.0.113.7\n' "$LOG" > "$TMP/bin/curl"
cat > "$TMP/k8s-up.sh" <<EOF
#!/usr/bin/env bash
echo "k8s-up \$* APP_HOST=\$APP_HOST KUBECONFIG=\$KUBECONFIG DEMO_SECRETS=\$DEMO_SECRETS" >> "$LOG"
EOF
chmod +x "$TMP/bin/"* "$TMP/k8s-up.sh"
printf 'ANTHROPIC_API_KEY=sk-test\n' > "$TMP/dotenv"
touch "$TMP/id.pub"

demo() { # demo <up|down> [ortam...]
  local script=$1; shift
  env PATH="$TMP/bin:$PATH" TF_CMD=terraform HCLOUD_TOKEN=t DEMO_ENV_FILE="$TMP/dotenv" \
    DEMO_SECRETS="$TMP/secrets.env" DEMO_KUBECONFIG="$TMP/kubeconfig" DEMO_TLS_BACKUP="$TMP/tls-backup.yaml" \
    DEMO_UP_K8S="$TMP/k8s-up.sh" SSH_PUBLIC_KEY="$TMP/id.pub" DEMO_SSH_WAIT=1 "$@" \
    bash "$ROOT/infra/demo/$script.sh" > "$TMP/out.log" 2>&1
}

# --- eksik anahtarlar: hiçbir şey açılmaz -------------------------------------------------------
: > "$LOG"; demo up HCLOUD_TOKEN=
check "HCLOUD_TOKEN yoksa durur" "[ $? -ne 0 ] && grep -q HCLOUD_TOKEN '$TMP/out.log'"
check "HCLOUD_TOKEN yoksa terraform çağrılmaz" "! grep -q '^terraform' '$LOG'"
: > "$LOG"; printf 'OTHER=1\n' > "$TMP/empty.env"; demo up DEMO_ENV_FILE="$TMP/empty.env" ANTHROPIC_API_KEY=
check "ANTHROPIC_API_KEY yoksa durur" "[ $? -ne 0 ] && grep -q ANTHROPIC_API_KEY '$TMP/out.log'"
check "ANTHROPIC_API_KEY yoksa terraform çağrılmaz" "! grep -q '^terraform' '$LOG'"

# --- ilk kurulum ---------------------------------------------------------------------------------
: > "$LOG"; before=$(date +%s); demo up DEMO_HOURS=4; rc=$?
check "ilk kurulum başarıyla biter" "[ $rc -eq 0 ]"
check "kalıcı IP yoksa bir kez kurulur" "grep -q '^terraform persistent apply' '$LOG'"
exp=$(grep -o 'expires_at=[0-9]*' "$LOG" | head -1 | cut -d= -f2)
check "sunucu DEMO_HOURS kadar ömürle açılır" "[ -n '$exp' ] && [ \$(( $exp - $before )) -ge 14390 ] && [ \$(( $exp - $before )) -le 14420 ]"
check "güvenlik duvarı kurulumu yapanın IP'sine açılır" "grep -q 'operator_cidr=203.0.113.7/32' '$LOG'"
check "k3s sürümü versions.env'den" "grep -q 'k3s_version=v1.37.1+k3s1' '$LOG'"
check "sırlar dosyası oluşturulur" "[ -f '$TMP/secrets.env' ]"
for key in POSTGRES_PASSWORD DB_OWNER_PASSWORD DB_APP_PASSWORD DB_RELAY_PASSWORD DB_AI_PASSWORD RABBITMQ_PASSWORD \
  KEYCLOAK_ADMIN_PASSWORD GRAFANA_ADMIN_PASSWORD AI_INTERNAL_TOKEN DEMO_ADMIN_PASSWORD; do
  check "sırlar: $key rastgele ve uzun" "grep -qE '^$key=[A-Za-z0-9]{24,}\$' '$TMP/secrets.env'"
done
check "sırlar: Anthropic anahtarı .env'den" "grep -q '^ANTHROPIC_API_KEY=sk-test\$' '$TMP/secrets.env'"
check "kubeconfig sunucunun IP'sini gösterir" "grep -q 'server: https://1.2.3.4:6443' '$TMP/kubeconfig'"
check "küme main'in son commit'iyle kurulur" "grep -q 'k8s-up demo argo $SHA APP_HOST=meridian.1.2.3.4.sslip.io' '$LOG'"
check "adres ve kapatma hatırlatması yazılır" "grep -q 'https://meridian.1.2.3.4.sslip.io' '$TMP/out.log' && grep -q 'make demo-down' '$TMP/out.log'"

# --- ikinci kurulum: aynı IP, sırlar korunur, süre yenilenir -------------------------------------
cp "$TMP/secrets.env" "$TMP/secrets.before"
: > "$LOG"; demo up DEMO_HOURS=2
check "ikinci kurulumda kalıcı IP yeniden kurulmaz" "! grep -q '^terraform persistent apply' '$LOG'"
check "ikinci kurulumda sırlar değişmez" "cmp -s '$TMP/secrets.env' '$TMP/secrets.before'"
exp2=$(grep -o 'expires_at=[0-9]*' "$LOG" | head -1 | cut -d= -f2)
check "ikinci kurulum süreyi yeniden belirler" "[ -n '$exp2' ] && [ '$exp2' -lt '$exp' ]"

# --- kapatma -------------------------------------------------------------------------------------
: > "$LOG"; demo down
check "kapatma yalnızca demo state'ini siler" "grep -q '^terraform demo destroy' '$LOG' && ! grep -q '^terraform persistent' '$LOG'"
check "TLS sertifikası yedeklenir (kimlik alanları olmadan)" "grep -q 'name: meridian-tls' '$TMP/tls-backup.yaml' && ! grep -qE 'uid:|resourceVersion:' '$TMP/tls-backup.yaml'"
check "yedek destroy'dan önce alınır" "[ \$(grep -n 'get secret meridian-tls' '$LOG' | cut -d: -f1) -lt \$(grep -n 'demo destroy' '$LOG' | cut -d: -f1) ]"

rm -f "$TMP/tls-backup.yaml"
: > "$LOG"; demo down FAKE_NO_CLUSTER=1; rc=$?
check "küme yoksa uyarıp yine de kapatır" "[ $rc -eq 0 ] && grep -q '^terraform demo destroy' '$LOG' && grep -qi 'yedek' '$TMP/out.log'"
check "küme yoksa boş yedek yazılmaz" "[ ! -s '$TMP/tls-backup.yaml' ]"

if ((failures)); then
  echo "--- son çıktı:"; tail -5 "$TMP/out.log"
  echo "$failures denetim başarısız"
  exit 1
fi
echo "demo betik denetimleri geçti"
