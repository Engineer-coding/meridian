/** Saf kurallar: API vekilinin neyi geçirip neyi durduracağı (test edilebilir, Next'e bağlı değil). */

const FORWARDED_REQUEST_HEADERS = ["accept", "content-type", "idempotency-key", "if-match", "if-none-match", "last-event-id"];
const FORWARDED_RESPONSE_HEADERS = ["content-type", "etag", "location", "retry-after", "cache-control"];

/** Çerezle kimlik doğrulanan vekil CSRF'e açıktır: durum değiştiren istek aynı kökenden gelmeli. */
export function isAllowedOrigin(method: string, origin: string | null, appUrl: string): boolean {
  if (method === "GET" || method === "HEAD") return true;
  return origin !== null && origin === new URL(appUrl).origin;
}

/** `..` ile vekilin izin verdiği `/v1` önekinden çıkılamaz. */
export function upstreamUrl(apiUrl: string, path: string[], search: string): URL | null {
  if (path.some((part) => part === "." || part === ".." || part === "" || /[\\/]/.test(part))) return null;
  const url = new URL(`/v1/${path.map(encodeURIComponent).join("/")}`, apiUrl);
  url.search = search;
  return url;
}

export function requestHeaders(incoming: Headers, accessToken: string): Headers {
  const headers = new Headers({ Authorization: `Bearer ${accessToken}` });
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = incoming.get(name);
    if (value !== null) headers.set(name, value);
  }
  return headers;
}

export function responseHeaders(upstream: Headers): Headers {
  const headers = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.get(name);
    if (value !== null) headers.set(name, value);
  }
  if (upstream.get("content-type")?.startsWith("text/event-stream")) {
    headers.set("Cache-Control", "no-cache, no-transform");
    headers.set("X-Accel-Buffering", "no");
  }
  return headers;
}
