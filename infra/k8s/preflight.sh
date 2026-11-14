#!/usr/bin/env bash
# Argo CD kipinde kurulacak commit'i belirler (ADR-0009). Argo yalnızca GitHub'daki commit'i görür:
# yerel ağaç ondan farklıysa (commit'lenmemiş değişiklik, push edilmemiş commit) kurulum başlamadan durur,
# yoksa yeni imajlar eski manifestlerle sessizce çalışır. Başarıda tam commit SHA'sını yazar.
#   bash infra/k8s/preflight.sh argo <dal|40 karakterlik SHA>
set -euo pipefail

MODE=${1:?argo ya da helm}
REVISION=${2:?revision}
die() { echo "HATA: $*" >&2; exit 1; }

[ "$MODE" = argo ] || exit 0

if [ "$REVISION" = HEAD ]; then
  die "revision HEAD olamaz (ayrık HEAD?): K8S_REVISION=<dal ya da 40 karakterlik commit> verin"
fi

if [[ "$REVISION" =~ ^[0-9a-f]+$ ]]; then
  [ ${#REVISION} -eq 40 ] || die "commit SHA'sı 40 karakter olmalı: $REVISION"
  git fetch --quiet --depth=1 origin "$REVISION" 2>/dev/null || die "commit '$REVISION' uzak depoda yok"
  echo "$REVISION"
  exit 0
fi

remote=$(git ls-remote origin "refs/heads/$REVISION" "refs/tags/$REVISION" | head -1 | cut -f1)
[ -n "$remote" ] \
  || die "revision '$REVISION' uzak depoda yok; Argo CD GitHub'dan okur: önce push edin ya da make k8s-dev kullanın"

# Çalışılan dal kuruluyorsa imajlar bu ağaçtan derlenir: ağaç uzak commit'le aynı olmalı.
if [ "$REVISION" = "$(git rev-parse --abbrev-ref HEAD)" ]; then
  git diff --quiet HEAD -- || die "commit'lenmemiş değişiklikler var; Argo CD yalnızca push edilmiş commit'i kurar: commit + push edin ya da make k8s-dev kullanın"
  [ "$(git rev-parse HEAD)" = "$remote" ] \
    || die "yerel '$REVISION' origin/$REVISION ile aynı değil (push ya da pull gerekli)"
fi
echo "$remote"
