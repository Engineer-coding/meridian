# infra/demo betiklerinin ortak yardımcıları (kaynak gösterilir). ROOT, SSH_KEY, SSH_PUBLIC_KEY, KNOWN_HOSTS
# ve TERRAFORM_VERSION çağıranda tanımlıdır.

# Terraform: TF_CMD verilmişse o komut (testler, kurulu terraform), yoksa sabit sürümlü Docker imajı.
tf() {
  local dir=$1
  shift
  if [ -n "${TF_CMD:-}" ]; then
    (cd "$ROOT/infra/terraform/$dir" && "$TF_CMD" "$@")
    return
  fi
  local root=$ROOT keydir
  keydir=$(dirname "$SSH_PUBLIC_KEY")
  if command -v cygpath >/dev/null; then
    root=$(cygpath -m "$ROOT")
    keydir=$(cygpath -m "$keydir")
  fi
  MSYS_NO_PATHCONV=1 docker run --rm -e HCLOUD_TOKEN -v "$root/infra/terraform:/tf" -v "$keydir:/ssh:ro" \
    -w "/tf/$dir" "hashicorp/terraform:$TERRAFORM_VERSION" "$@"
}

# Terraform'un gördüğü açık anahtar yolu (Docker'da /ssh altına bağlanır).
tf_key_path() {
  if [ -n "${TF_CMD:-}" ]; then echo "$SSH_PUBLIC_KEY"; else echo "/ssh/$(basename "$SSH_PUBLIC_KEY")"; fi
}

# Sunucu her demo-up'ta yeniden kurulabilir (aynı IP, yeni anahtar): ayrı known_hosts, demo-down siler.
demo_ssh() {
  local ip=$1
  shift
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$KNOWN_HOSTS" \
    -o ConnectTimeout=5 -o BatchMode=yes "root@$ip" "$@"
}
