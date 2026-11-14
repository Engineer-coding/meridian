#!/usr/bin/env bash
# preflight.sh sınaması: Argo CD yalnızca GitHub'daki commit'i kurar; yerel ağaç farklıysa kurulum başlamamalı.
# Geçici bir git deposu ve onun "origin"i (çıplak depo) üzerinde çalışır; gerçek depoya dokunmaz.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
failures=0
expect() { # expect <ok|fail> <açıklama> <revision> [beklenen mesaj parçası]
  local want=$1 what=$2 revision=$3 needle=${4:-} out rc
  out=$(cd "$WORK" && bash "$HERE/preflight.sh" argo "$revision" 2>&1)
  rc=$?
  if { [ "$want" = ok ] && [ $rc -eq 0 ]; } || { [ "$want" = fail ] && [ $rc -ne 0 ]; }; then
    if [ -n "$needle" ] && ! grep -qF "$needle" <<<"$out"; then
      echo "BAŞARISIZ: $what: mesajda '$needle' yok: $out"; failures=$((failures + 1)); return
    fi
    echo "tamam: $what"
  else
    echo "BAŞARISIZ: $what (çıkış $rc): $out"; failures=$((failures + 1))
  fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git init -q --bare "$TMP/origin.git"
git init -q -b work "$TMP/work"
WORK=$TMP/work
git -C "$WORK" -c user.email=t@t -c user.name=t commit -q --allow-empty -m one
git -C "$WORK" remote add origin "$TMP/origin.git"
git -C "$WORK" push -q origin work

pushed=$(git -C "$WORK" rev-parse HEAD)
expect ok "push edilmiş dal kabul edilir ve commit'e çözülür" work
[ "$(cd "$WORK" && bash "$HERE/preflight.sh" argo work 2>/dev/null)" = "$pushed" ] \
  || { echo "BAŞARISIZ: dal, push edilmiş commit'e çözülmedi"; failures=$((failures + 1)); }
expect ok "tam commit SHA'sı kabul edilir" "$pushed"
expect fail "HEAD reddedilir" HEAD "HEAD"
expect fail "uzakta olmayan dal reddedilir" no-such-branch "uzak depoda yok"
expect fail "kısa SHA reddedilir" "${pushed:0:7}" "40 karakter"

echo change > "$WORK/file.txt"
git -C "$WORK" add file.txt
expect fail "commit'lenmemiş değişiklik reddedilir" work "commit'lenmemiş"
git -C "$WORK" -c user.email=t@t -c user.name=t commit -q -m two
expect fail "push edilmemiş commit reddedilir" work "origin/work ile aynı değil"

if ((failures)); then
  echo "$failures denetim başarısız"
  exit 1
fi
echo "preflight denetimleri geçti"
