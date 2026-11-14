#!/usr/bin/env bash
# Yerel ya da CI kind kümesini kurar (ADR-0009). Tekrar çalıştırmak güvenli.
#   bash infra/k8s/up.sh <local|ci> <argo|helm> [revision]
#   argo: Argo CD chart'ı GitHub'daki revision'dan senkronlar (dal push edilmiş olmalı).
#   helm: aynı chart'ı çalışma ağacından doğrudan kurar (hızlı deneme, Argo yok).
set -euo pipefail

ENV=${1:?local ya da ci}
MODE=${2:?argo ya da helm}
REVISION=${3:-$(git rev-parse --abbrev-ref HEAD)}
# Windows (Git Bash): yerel araçlar (kind.exe, helm.exe) C:/... biçiminde yol ister.
ROOT=$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))
CLUSTER=meridian
NS=meridian
HOST=${APP_HOST:-meridian.localtest.me}
# shellcheck source=/dev/null
. "$ROOT/infra/versions.env"

die() { echo "HATA: $*" >&2; exit 1; }
log() { echo "==> $*"; }

case "$ENV" in local | ci) ;; *) die "ortam local ya da ci olmalı: $ENV" ;; esac
case "$MODE" in argo | helm) ;; *) die "kip argo ya da helm olmalı: $MODE" ;; esac

# --- ön kontroller: küme kurulmadan önce durur -----------------------------------------------
for tool in docker kind kubectl helm openssl; do
  command -v "$tool" >/dev/null || die "$tool bulunamadı (README: Kubernetes'te çalıştırma)"
done
cluster_exists() { kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; }
if ! cluster_exists && (exec 3<>/dev/tcp/127.0.0.1/80) 2>/dev/null; then
  die "127.0.0.1:80 kullanımda; kind bu portu Traefik'e bağlar. Portu kullanan süreci kapatın."
fi
if [ "$MODE" = argo ]; then
  # Dal adı yerine tam commit: Argo tam olarak imajların derlendiği ağacı kurar (preflight.sh).
  REVISION=$(cd "$ROOT" && bash infra/k8s/preflight.sh argo "$REVISION") || exit 1
fi

# --- küme ve imajlar ----------------------------------------------------------------------------
if cluster_exists; then
  log "kind kümesi '$CLUSTER' zaten var"
else
  log "kind kümesi oluşturuluyor ($KIND_NODE_IMAGE)"
  kind create cluster --config "$ROOT/infra/kind/cluster.yaml" --image "$KIND_NODE_IMAGE" --wait 120s
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

ai_image=meridian-ai:local
[ "$ENV" = ci ] && ai_image=meridian-ai-test:local
log "imajlar yükleniyor"
kind load docker-image --name "$CLUSTER" meridian-api:local "$ai_image" meridian-web:local
# Etiket hep ":local": manifest değişmediği için pod'lar yeni imajı kendiliğinden almaz. Yeniden açılan
# pod düğümdeki yeni imajla başlar (IfNotPresent); manifest aynı kaldığı için Argo bir fark görmez.
if kubectl get namespace "$NS" >/dev/null 2>&1; then
  kubectl -n "$NS" delete pod -l 'app.kubernetes.io/component in (api,ai,web)' --wait=false >/dev/null 2>&1 || true
fi

env_file="$ROOT/.env"
[ "$ENV" = ci ] && env_file="$ROOT/.env.example"
[ -f "$env_file" ] || die "$env_file yok (cp .env.example .env)"
bash "$ROOT/infra/k8s/secrets.sh" "$env_file"

values=(-f "$ROOT/infra/helm/meridian/values-local.yaml")
[ "$ENV" = ci ] && values+=(-f "$ROOT/infra/helm/meridian/values-ci.yaml")

render_app() {
  sed -e "s|REVISION|$REVISION|g" -e "s|TRAEFIK_CHART_VERSION|$TRAEFIK_CHART_VERSION|g" "$1"
}

# --- ingress denetleyicisi -----------------------------------------------------------------------
if [ "$MODE" = argo ]; then
  log "Argo CD $ARGOCD_VERSION"
  kubectl get namespace argocd >/dev/null 2>&1 || kubectl create namespace argocd >/dev/null
  kubectl apply -n argocd --server-side --force-conflicts \
    -f "https://raw.githubusercontent.com/argoproj/argo-cd/$ARGOCD_VERSION/manifests/install.yaml" >/dev/null
  kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=300s
  kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=300s
  log "Traefik (Argo CD ile)"
  render_app "$ROOT/infra/gitops/bootstrap/traefik.yaml" | kubectl apply -f - >/dev/null
  until kubectl -n traefik get deployment traefik >/dev/null 2>&1; do sleep 3; done
else
  log "Traefik (helm)"
  helm upgrade --install traefik traefik --repo https://traefik.github.io/charts \
    --version "$TRAEFIK_CHART_VERSION" -n traefik --create-namespace \
    -f "$ROOT/infra/gitops/bootstrap/traefik-values.yaml" >/dev/null
fi
kubectl -n traefik rollout status deployment/traefik --timeout=300s
bash "$ROOT/infra/k8s/coredns.sh" "$HOST"

# --- Meridian ------------------------------------------------------------------------------------
if [ "$MODE" = argo ]; then
  log "Meridian (Argo CD, revision $REVISION)"
  render_app "$ROOT/infra/gitops/$ENV/meridian.yaml" | kubectl apply -f - >/dev/null
  # Bu commit beklenir, önceki kurulumun durumu sayılmaz:
  # - Argo bu commit'i karşılaştırmış ve küme ona eşit (Synced) olmalı;
  # - bu commit için bir senkron işlemi varsa (chart değişmişse olur) bitmiş olmalı. PostSync seed kancası
  #   işlemin parçasıdır: seed bitince "Succeeded", başarısızsa hemen "Failed".
  # Chart değişmeyen bir commit'te Argo yeni işlem başlatmaz; o durumda Synced olmak yeterlidir.
  log "Argo CD senkronu ve seed bekleniyor (ilk indeksleme CPU'da dakikalar sürer)"
  app() { kubectl -n argocd get application meridian -o jsonpath="$1" 2>/dev/null; }
  ready=""
  for _ in $(seq 1 360); do
    compared=$(app '{.status.sync.revision}')
    status=$(app '{.status.sync.status}')
    op_revision=$(app '{.status.operationState.syncResult.revision}')
    phase=$(app '{.status.operationState.phase}')
    if [ "$op_revision" = "$REVISION" ]; then
      case "$phase" in
        Failed | Error) die "Argo CD senkronu '$phase' (seed: kubectl -n $NS logs job/meridian-seed; ayrıntı: kubectl -n argocd get application meridian -o yaml)" ;;
        Running | Terminating) sleep 5; continue ;;
      esac
    fi
    if [ "$compared" = "$REVISION" ] && [ "$status" = Synced ]; then
      ready=1
      break
    fi
    sleep 5
  done
  [ -n "$ready" ] || die "Argo CD $REVISION commit'ine 30 dakikada eşitlenmedi (kubectl -n argocd get application meridian -o yaml)"
  kubectl -n argocd wait application/meridian --for=jsonpath='{.status.health.status}'=Healthy --timeout=900s
else
  log "Meridian (helm, çalışma ağacı)"
  helm upgrade --install meridian "$ROOT/infra/helm/meridian" -n "$NS" "${values[@]}" --wait --timeout 15m
fi
log "hazır: http://$HOST"
