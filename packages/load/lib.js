// Ortak yardımcılar: Keycloak'tan token, kiracı ve kaynak kurulumu (ADR-0019).
import http from "k6/http";
import { check, fail, sleep } from "k6";

export const API = __ENV.API_URL || "http://host.docker.internal:18080";
const KEYCLOAK = __ENV.KEYCLOAK_URL || "http://host.docker.internal:18180";
// Yerel geliştirme kullanıcısı ve istemcisi (infra/helm/meridian/files/keycloak/meridian-realm.json). Yalnızca yerel ortam.
const USER = __ENV.LOAD_USER || "alice";

export function login() {
  const response = http.post(
    `${KEYCLOAK}/realms/meridian/protocol/openid-connect/token`,
    { grant_type: "password", client_id: "meridian-dev-cli", username: USER, password: USER, scope: "openid" },
    { tags: { name: "login" } },
  );
  if (!check(response, { "giriş 200": (r) => r.status === 200 })) fail(`giriş başarısız: ${response.status}`);
  return { token: response.json("access_token"), issuedAt: Date.now() };
}

// Access token 5 dakika geçerli; sanal kullanıcı süresi dolmadan yeniden alır.
let session = null;
export function bearer() {
  if (session === null || Date.now() - session.issuedAt > 200_000) session = login();
  return session.token;
}

export function key() {
  let value = "";
  for (let i = 0; i < 32; i++) value += Math.floor(Math.random() * 16).toString(16);
  return value;
}

export function headers(token, extra = {}) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...extra };
}

export function post(path, body, token, name, extra = {}) {
  return http.post(`${API}${path}`, JSON.stringify(body), {
    headers: headers(token, { "Idempotency-Key": key(), ...extra }),
    tags: { name },
  });
}

export function get(path, token, name) {
  return http.get(`${API}${path}`, { headers: headers(token), tags: { name } });
}

/** Yük için ayrı bir çalışma alanı ve koleksiyon. */
export function workspace(token) {
  const suffix = key().slice(0, 8);
  const tenant = post("/v1/tenants", { name: `Yük ${suffix}`, slug: `load-${suffix}` }, token, "setup");
  if (tenant.status !== 201) fail(`kiracı oluşturulamadı: ${tenant.status} ${tenant.body}`);
  const tenantId = tenant.json("id");
  const collection = post(`/v1/tenants/${tenantId}/collections`, { name: "Yük" }, token, "setup");
  if (collection.status !== 201) fail(`koleksiyon oluşturulamadı: ${collection.status}`);
  return { tenantId, collectionId: collection.json("id") };
}

export function addSource(token, tenantId, collectionId, name) {
  const config = { type: "github", repository: "acme/yuk", branch: "main" };
  const source = post(`/v1/tenants/${tenantId}/sources`, { name, collectionId, config }, token, "source");
  if (source.status !== 202) fail(`kaynak eklenemedi: ${source.status} ${source.body}`);
  return source.json("id");
}

/** Kaynak hazır olana dek bekler; saniye cinsinden süreyi ya da null (zaman aşımı, hata) döner. */
export function waitReady(token, tenantId, sourceId, timeoutSeconds) {
  const started = Date.now();
  while ((Date.now() - started) / 1000 < timeoutSeconds) {
    const response = get(`/v1/tenants/${tenantId}/sources/${sourceId}`, token, "source-status");
    const status = response.status === 200 ? response.json("status") : null;
    if (status === "ready") return (Date.now() - started) / 1000;
    if (status === "failed") return null;
    sleep(1);
  }
  return null;
}
