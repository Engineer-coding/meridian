#!/usr/bin/env bash
# smoke.sh'in seed adımları (6–7): izleyici kullanıcı seed kiracısında soru sorar; Keycloak yeniden
# başlasa da giriş ve üyelik geçerli kalır; seed yeniden çalışınca kaynaklar çoğalmaz.
# smoke.sh tarafından kaynak gösterilir (source); in_cluster, ok, fail ve değişkenler oradan gelir.

VIEWER=${SMOKE_VIEWER:-bob}
VIEWER_PASSWORD=${SMOKE_VIEWER_PASSWORD:-bob}
SLUG=${SMOKE_TENANT:-acme-demo}
API=http://meridian-api:8080
SOURCE_COUNT=0
TENANT=""

token_for() {
  curl -s -m 10 "$ISSUER/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=meridian-dev-cli -d scope=openid \
    --data-urlencode "username=$1" --data-urlencode "password=$2" \
    | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'
}

api() { # api <method> <path> [body] — web etiketli geçici pod üzerinden (ağ politikası API'ye izin verir)
  local method=$1 path=$2 body=${3:-}
  in_cluster api-call web curl -s -m 60 -X "$method" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' ${body:+--data "$body"} "$API$path"
}

seed_tenant_id() {
  local me
  me=$(api GET /v1/me)
  for id in $(grep -o '"tenantId":"[^"]*"' <<<"$me" | cut -d'"' -f4); do
    api GET "/v1/tenants/$id" | grep -q "\"slug\":\"$SLUG\"" && { echo "$id"; return; }
  done
}

ask_question() {
  local tenant=$1 conversation stream
  conversation=$(api POST "/v1/tenants/$tenant/conversations" '{}' | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$conversation" ] || { fail "konuşma açılamadı"; return; }
  stream=$(api POST "/v1/tenants/$tenant/conversations/$conversation/messages" \
    '{"content":"Veri sorumlusu başvuruyu kaç gün içinde sonuçlandırır?"}')
  if grep -q '^event: *done' <<<"$stream" && ! grep -q '"degraded": *true' <<<"$stream"; then
    ok "soru akışla cevaplandı (done, degraded değil)"
  else
    fail "akış done ile bitmedi ya da degraded: $(tail -c 300 <<<"$stream")"
  fi
}

viewer_round() {
  TOKEN=$(token_for "$VIEWER" "$VIEWER_PASSWORD")
  [ -n "$TOKEN" ] || { fail "$VIEWER token alamadı"; return 1; }
  TENANT=$(seed_tenant_id)
  [ -n "$TENANT" ] || { fail "$VIEWER, '$SLUG' kiracısını görmüyor"; return 1; }
  ok "$VIEWER '$SLUG' kiracısının üyesi"
  local sources
  sources=$(api GET "/v1/tenants/$TENANT/sources")
  SOURCE_COUNT=$(grep -o '"status":"[a-z]*"' <<<"$sources" | wc -l)
  if [ "$SOURCE_COUNT" -gt 0 ] && ! grep -o '"status":"[a-z]*"' <<<"$sources" | grep -qv '"ready"'; then
    ok "$SOURCE_COUNT kaynağın hepsi ready"
  else
    fail "kaynaklar hazır değil: $(grep -o '"status":"[a-z]*"' <<<"$sources" | sort | uniq -c | tr '\n' ' ')"
  fi
  ask_question "$TENANT"
}

step "6. seed kiracısında izleyici soru sorar"
viewer_round

step "7a. Keycloak yeniden başlayınca giriş ve üyelik"
kubectl -n "$NS" delete pod -l app.kubernetes.io/component=keycloak --wait=true >/dev/null
# rollout status, silinen pod'un yerine yenisi hazır olmadan dönebilir: token verene kadar beklenir.
for _ in $(seq 1 60); do
  [ -n "$(token_for "$VIEWER" "$VIEWER_PASSWORD")" ] && break
  sleep 5
done
before=$SOURCE_COUNT
viewer_round

step "7b. seed yeniden çalışınca kaynaklar çoğalmaz"
rerun="seed-rerun-$RANDOM"
kubectl -n "$NS" create job "$rerun" --from=cronjob/meridian-seed >/dev/null
if kubectl -n "$NS" wait --for=condition=complete "job/$rerun" --timeout=600s >/dev/null; then
  ok "seed yeniden çalıştı"
else
  fail "seed yeniden çalışırken başarısız: $(kubectl -n "$NS" logs "job/$rerun" --tail=5 2>&1)"
fi
kubectl -n "$NS" delete job "$rerun" >/dev/null 2>&1
after=$(grep -o '"status":"[a-z]*"' <<<"$(api GET "/v1/tenants/$TENANT/sources")" | wc -l)
[ "$after" = "$before" ] && ok "kaynak sayısı aynı ($after)" || fail "kaynak sayısı $before → $after"
