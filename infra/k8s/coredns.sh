#!/usr/bin/env bash
# Küme içinde uygulama adını ingress denetleyicisine yönlendirir (ADR-0009): pod'lar da OIDC issuer'a
# tarayıcıyla aynı adresten ulaşır, uygulama kodu ayrı bir iç adres bilmez. Tekrar çalıştırmak güvenli.
#   bash infra/k8s/coredns.sh meridian.localtest.me
set -euo pipefail

HOST=${1:?host}
TARGET=${2:-traefik.traefik.svc.cluster.local}
RULE="rewrite name exact $HOST $TARGET"

corefile=$(kubectl -n kube-system get configmap coredns -o jsonpath='{.data.Corefile}')
if grep -qF "$RULE" <<<"$corefile"; then
  echo "CoreDNS: $HOST zaten yönlendiriliyor"
  exit 0
fi

updated=$(awk -v rule="    $RULE" '{print} /^\.:53 \{/ && !done {print rule; done=1}' <<<"$corefile")
kubectl -n kube-system create configmap coredns --from-literal=Corefile="$updated" --dry-run=client -o yaml \
  | kubectl apply -f - >/dev/null
kubectl -n kube-system rollout restart deployment coredns >/dev/null
kubectl -n kube-system rollout status deployment coredns --timeout=120s >/dev/null
echo "CoreDNS: $HOST → $TARGET"
