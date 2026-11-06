// Testler için sahte Keycloak + çekirdek API. Gerçek OIDC kod akışını ve SSE davranışını taklit eder.
import { createServer } from "node:http";
import { createHash } from "node:crypto";

const PORT = 4010;
const ISSUER = `http://localhost:${PORT}/realms/meridian`;
const TENANT = "11111111-1111-4111-8111-111111111111";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const b64 = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");

const SOURCE = {
  number: 1,
  documentPath: "kvkk/6698.md",
  title: "KVKK",
  section: "Madde 13",
  content: "Veri sorumlusu başvuruyu en geç otuz gün içinde sonuçlandırır.",
};

let conversations = {};
let messages = {};
let challenge;
let state = { interrupted: 0, tokenRefreshes: 0, lastAuthorization: null };
let seq = 0;

const id = () => `22222222-2222-4222-8222-${String(++seq).padStart(12, "0")}`;

function json(res, status, body, headers = {}) {
  res.writeHead(status, { "Content-Type": "application/json", ...headers });
  res.end(JSON.stringify(body));
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks).toString();
}

function idToken() {
  const now = Math.floor(Date.now() / 1000);
  const claims = { iss: ISSUER, aud: "meridian-web", sub: "alice", iat: now, exp: now + 300 };
  return `${b64({ alg: "RS256", typ: "JWT" })}.${b64(claims)}.c2ln`;
}

async function answer(req, res, conversationId, content) {
  const list = (messages[conversationId] ??= []);
  list.push({ id: id(), role: "user", content, status: "complete", createdAt: new Date().toISOString() });
  res.writeHead(200, { "Content-Type": "text/event-stream" });
  const send = (event, data) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

  const hostile = content.includes("zararlı");
  const slow = content.includes("yavaş");
  const abstain = content.includes("bilinmeyen");
  const text = hostile
    ? '<img src=x onerror="window.__pwned=1"> ![d](http://localhost:4010/leak.png) Sonuç [1].'
    : "Başvuru **otuz gün** içinde sonuçlandırılır [1].";
  const words = abstain ? [] : text.split(/(?<= )/);

  let closed = false;
  let partial = "";
  res.on("close", () => {
    closed = true;
    if (!res.writableEnded) {
      state.interrupted += 1;
      list.push({ id: id(), role: "assistant", content: partial, status: "interrupted", sources: [SOURCE], cited: [], createdAt: new Date().toISOString() });
    }
  });

  send("sources", { sources: [SOURCE] });
  await sleep(200);
  for (const word of words) {
    if (closed) return;
    partial += word;
    send("token", { text: word });
    await sleep(slow ? 700 : 40);
  }
  if (closed) return;
  const messageId = id();
  const final = abstain ? "BİLMİYORUM" : text;
  list.push({
    id: messageId,
    role: "assistant",
    content: final,
    status: "complete",
    sources: [SOURCE],
    cited: abstain ? [] : [1],
    abstained: abstain,
    degraded: false,
    createdAt: new Date().toISOString(),
  });
  send("done", { messageId, answer: final, cited: abstain ? [] : [1], abstained: abstain, degraded: false });
  res.end();
}

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;

  if (path === "/health") return json(res, 200, { ok: true });
  if (path === "/__state") return json(res, 200, state);
  if (path === "/__reset") {
    conversations = {};
    messages = {};
    state = { interrupted: 0, tokenRefreshes: 0, lastAuthorization: null };
    return json(res, 200, {});
  }

  // --- OIDC ---
  if (path === "/realms/meridian/.well-known/openid-configuration") {
    return json(res, 200, {
      issuer: ISSUER,
      authorization_endpoint: `http://localhost:${PORT}/authorize`,
      token_endpoint: `http://localhost:${PORT}/token`,
      end_session_endpoint: `http://localhost:${PORT}/logout`,
      jwks_uri: `http://localhost:${PORT}/jwks`,
      response_types_supported: ["code"],
      subject_types_supported: ["public"],
      id_token_signing_alg_values_supported: ["RS256"],
      code_challenge_methods_supported: ["S256"],
    });
  }
  if (path === "/authorize") {
    if (url.searchParams.get("code_challenge_method") !== "S256") return json(res, 400, { error: "pkce" });
    challenge = url.searchParams.get("code_challenge");
    const back = new URL(url.searchParams.get("redirect_uri"));
    back.searchParams.set("code", "kod");
    back.searchParams.set("state", url.searchParams.get("state"));
    res.writeHead(302, { Location: back.href });
    return res.end();
  }
  if (path === "/token") {
    const form = new URLSearchParams(await readBody(req));
    if (form.get("grant_type") === "authorization_code") {
      const expected = createHash("sha256").update(form.get("code_verifier") ?? "").digest("base64url");
      if (expected !== challenge) return json(res, 400, { error: "invalid_grant" });
    } else {
      state.tokenRefreshes += 1;
    }
    return json(res, 200, {
      access_token: "erisim-token",
      refresh_token: "yenileme-token",
      id_token: idToken(),
      token_type: "Bearer",
      // Her istekte yenileme denensin diye kısa ömürlü değil: yenileme birim testinin konusu değil.
      expires_in: 300,
    });
  }
  if (path === "/logout") {
    res.writeHead(204);
    return res.end();
  }

  // --- API ---
  state.lastAuthorization = req.headers.authorization ?? null;
  if (req.headers.authorization !== "Bearer erisim-token") return json(res, 401, { title: "Unauthorized", status: 401 });
  if (path === "/v1/me") {
    return json(res, 200, {
      id: "33333333-3333-4333-8333-333333333333",
      email: "alice@acme.test",
      displayName: "Alice Acme",
      memberships: [
        { tenantId: TENANT, tenantName: "Acme", role: "owner" },
        { tenantId: "44444444-4444-4444-8444-444444444444", tenantName: "Beta", role: "member" },
      ],
    });
  }
  const match = path.match(/^\/v1\/tenants\/([^/]+)\/conversations(?:\/([^/]+)\/messages)?$/);
  if (match) {
    const [, tenantId, conversationId] = match;
    const tenantConversations = (conversations[tenantId] ??= []);
    if (!conversationId && req.method === "GET") return json(res, 200, tenantConversations);
    if (!conversationId && req.method === "POST") {
      await readBody(req);
      const conversation = { id: id(), createdAt: new Date().toISOString() };
      tenantConversations.unshift(conversation);
      return json(res, 201, conversation);
    }
    if (req.method === "GET") return json(res, 200, messages[conversationId] ?? []);
    const { content } = JSON.parse(await readBody(req));
    const conversation = tenantConversations.find((item) => item.id === conversationId);
    if (conversation && !conversation.title) conversation.title = content.slice(0, 60);
    if (content.includes("sınır")) return json(res, 429, { title: "Too Many Requests", status: 429 }, { "Retry-After": "7" });
    return answer(req, res, conversationId, content);
  }
  return json(res, 404, { title: "Not Found", status: 404 });
}).listen(PORT);
