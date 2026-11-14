#!/usr/bin/env bash
# Küme içinde uygulama adını ingress denetleyicisine yönlendirir (ADR-0009): pod'lar da OIDC issuer'a
# tarayıcıyla aynı adresten ulaşır, uygulama kodu ayrı bir iç adres bilmez. Tekrar çalıştırmak güvenli.
#   bash infra/k8s/coredns.sh meridian.localtest.me
# k3s'te coredns ConfigMap'ini eklenti yöneticisi geri yazar; orada coredns-custom (*.override) kullanılır.
set -euo pipefail

HOST=${1:?host}
TARGET=${2:-traefik.traefik.svc.cluster.local}
RULE="rewrite name exact $HOST $TARGET"

restart() {
  kubectl -n kube-system rollout restart deployment coredns >/dev/null
  kubectl -n kube-system rollout status deployment coredns --timeout=120s >/dev/null
}

if kubectl get nodes -o jsonpath='{.items[*].status.nodeInfo.kubeletVersion}' 2>/dev/null | grep -q '+k3s'; then
  current=$(kubectl -n kube-system get configmap coredns-custom -o jsonpath='{.data.meridian\.override}' 2>/dev/null || true)
  if [ "$current" = "$RULE" ]; then
    echo "CoreDNS: $HOST zaten yönlendiriliyor"
    exit 0
  fi
  kubectl -n kube-system create configmap coredns-custom --from-literal=meridian.override="$RULE" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  restart
  echo "CoreDNS (k3s): $HOST → $TARGET"
  exit 0
fi

corefile=$(kubectl -n kube-system get configmap coredns -o jsonpath='{.data.Corefile}')
if grep -qF "$RULE" <<<"$corefile"; then
  echo "CoreDNS: $HOST zaten yönlendiriliyor"
  exit 0
fi

updated=$(awk -v rule="    $RULE" '{print} /^\.:53 \{/ && !done {print rule; done=1}' <<<"$corefile")
kubectl -n kube-system create configmap coredns --from-literal=Corefile="$updated" --dry-run=client -o yaml \
  | kubectl apply -f - >/dev/null
restart
echo "CoreDNS: $HOST → $TARGET"
