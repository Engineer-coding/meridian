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

const MEMBER_TENANT = "44444444-4444-4444-8444-444444444444";

let conversations = {};
let messages = {};
let sources = {};
let collections = {};
let apiKeys = [];
let agentRuns = {};
let challenge;
let state = { interrupted: 0, tokenRefreshes: 0, lastAuthorization: null, sourceTenants: [], tickets: 0, agentInterrupted: 0 };
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

function searchStep(observation = SOURCE.content) {
  return { thought: "Belgelerde arıyorum", action: "search_knowledge", input: { query: "başvuru" }, observation, sources: [SOURCE] };
}

async function agentApi(req, res, [, tenantId, runId, approval]) {
  const runs = (agentRuns[tenantId] ??= []);
  if (req.method === "GET" && !runId) return json(res, 200, runs);
  if (req.method === "GET") {
    const found = runs.find((item) => item.id === runId);
    return found ? json(res, 200, found) : json(res, 404, { title: "Not Found", status: 404 });
  }
  const body = JSON.parse(await readBody(req));

  let run;
  let steps = [];
  if (approval) {
    run = runs.find((item) => item.id === runId);
    if (!run || run.status !== "waiting_approval") return json(res, 409, { title: "Conflict", status: 409 });
    if (body.approved) state.tickets += 1;
    steps = [
      {
        thought: run.pending.thought,
        action: "create_ticket",
        input: { title: run.pending.title, description: run.pending.description },
        observation: body.approved ? "Ticket oluşturuldu" : "Kullanıcı reddetti",
        approved: body.approved,
      },
    ];
    run.pending = null;
    run.status = "running";
  } else {
    if (body.goal.includes("meşgul")) return json(res, 409, { title: "Conflict", status: 409 });
    if (body.goal.includes("kota dolu")) return json(res, 429, { title: "Too Many Requests", status: 429 });
    run = { id: id(), goal: body.goal, status: "running", steps: [], pending: null, answer: null, cited: [], sources: [], stopReason: null, model: "m", tokens: 0, createdAt: new Date().toISOString() };
    runs.unshift(run);
    const hostile = '<img src=x onerror="window.__pwned=1"> ![d](http://localhost:4010/leak.png)';
    steps = [searchStep(body.goal.includes("zararlı") ? hostile : SOURCE.content)];
  }

  res.writeHead(200, { "Content-Type": "text/event-stream" });
  const send = (event, data) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  let closed = false;
  res.on("close", () => {
    if (!res.writableEnded) {
      closed = true;
      state.agentInterrupted += 1;
      run.status = "interrupted";
    }
  });

  send("run", { id: run.id });
  for (const step of steps) {
    await sleep(100);
    run.steps.push(step);
    send("step", step);
  }
  await sleep(run.goal.includes("yavaş") ? 15000 : 150);
  if (closed) return;

  if (!approval && run.goal.includes("ticket")) {
    run.status = "waiting_approval";
    run.pending = { thought: "Ticket öneriyorum", title: "Disk dolu", description: "Sunucu diski doldu.\nİkinci satır." };
    run.tokens = 500;
  } else if (run.goal.includes("bütçe")) {
    run.status = "budget_exceeded";
    run.stopReason = "step_budget";
  } else {
    run.status = "completed";
    run.answer = approval ? "Ticket açıldı." : "Başvuru **otuz gün** içinde sonuçlandırılır [1].";
    run.cited = approval ? [] : [1];
    run.sources = approval ? [] : [SOURCE];
    run.tokens += 1115;
  }
  send("end", run);
  res.end();
}

/** Durum birkaç okumada ilerler: panel kendini yeniliyorsa sonucu sayfa yenilenmeden görür. */
function advance(source) {
  source.reads = (source.reads ?? 0) + 1;
  if (source.status === "pending" && source.reads >= 2) source.status = "indexing";
  else if (source.status === "indexing" && source.reads >= 3) {
    if (source.repository === "yok/yok") {
      source.status = "failed";
      source.lastError = "depo veya dal bulunamadı";
    } else {
      source.status = "ready";
      source.documentCount = 12;
      source.lastIndexedAt = new Date().toISOString();
    }
  }
  return source;
}

function view(source) {
  const { id, name, collectionId, type, status, documentCount, lastError, lastIndexedAt, createdAt } = source;
  return { id, name, collectionId, type, status, documentCount, lastError, lastIndexedAt, createdAt };
}

function auditPage(url) {
  const all = Array.from({ length: 60 }, (_, index) => ({
    id: `55555555-5555-4555-8555-${String(index).padStart(12, "0")}`,
    action: index === 1 ? "source.delete" : "source.create",
    outcome: index === 1 ? "denied" : "allowed",
    actorUserId: "33333333-3333-4333-8333-333333333333",
    actorEmail: "alice@acme.test",
    apiKeyId: index === 2 ? "66666666-6666-4666-8666-666666666666" : null,
    targetId: index === 1 ? null : "77777777-7777-4777-8777-777777777777",
    createdAt: new Date(Date.now() - index * 60000).toISOString(),
  }));
  const start = Number(url.searchParams.get("cursor") ?? 0);
  const limit = Number(url.searchParams.get("limit") ?? 20);
  const next = start + limit;
  return { items: all.slice(start, next), nextCursor: next < all.length ? String(next) : null };
}

function usageSummary() {
  const today = Date.UTC(2026, 10, 30);
  const days = Array.from({ length: 30 }, (_, index) => ({
    date: new Date(today - (29 - index) * 86400000).toISOString().slice(0, 10),
    tokens: index === 29 ? 170000 : index % 3 === 0 ? 40000 + index * 1000 : 0,
    answers: index === 29 ? 40 : index % 3 === 0 ? 12 : 0,
  }));
  return {
    plan: "free",
    dailyTokenLimit: 200000,
    tokensToday: 170000,
    resetsAt: new Date(today + 86400000).toISOString(),
    estimatedTokens: 1200,
    costUsd: 0,
    days,
  };
}

async function adminApi(req, res, url, [, tenantId, area, itemId, retry]) {
  const isMemberTenant = tenantId === MEMBER_TENANT;
  const forbidden = () => json(res, 403, { title: "Forbidden", status: 403 });

  if (area === "usage") return isMemberTenant ? forbidden() : json(res, 200, usageSummary());
  if (area === "audit-log") return isMemberTenant ? forbidden() : json(res, 200, auditPage(url));

  if (area === "collections") {
    const list = (collections[tenantId] ??= [{ id: id(), name: "Genel", createdAt: new Date().toISOString() }]);
    if (req.method === "GET") return json(res, 200, list);
    const { name } = JSON.parse(await readBody(req));
    const created = { id: id(), name, createdAt: new Date().toISOString() };
    list.push(created);
    return json(res, 201, created);
  }

  if (area === "api-keys") {
    if (isMemberTenant) return forbidden();
    if (req.method === "GET") return json(res, 200, apiKeys);
    if (req.method === "DELETE") {
      const key = apiKeys.find((item) => item.id === itemId);
      if (key) key.revokedAt = new Date().toISOString();
      res.writeHead(204);
      return res.end();
    }
    const body = JSON.parse(await readBody(req));
    const key = {
      id: id(),
      name: body.name,
      prefix: "mrd_gizli",
      scopes: body.scopes,
      createdAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + body.expiresInDays * 86400000).toISOString(),
      lastUsedAt: null,
      revokedAt: null,
    };
    apiKeys.unshift(key);
    return json(res, 201, { key, secret: "mrd_gizli-deger" });
  }

  const list = (sources[tenantId] ??= []);
  if (!state.sourceTenants.includes(tenantId)) state.sourceTenants.push(tenantId);
  if (req.method === "GET" && !itemId) {
    return json(res, 200, { items: list.filter((item) => !item.removed).map(advance).map(view), nextCursor: null });
  }
  if (req.method === "POST" && !itemId) {
    const body = JSON.parse(await readBody(req));
    const source = {
      id: id(),
      name: body.name,
      collectionId: body.collectionId,
      type: body.config.type,
      repository: body.config.repository,
      status: "pending",
      documentCount: 0,
      createdAt: new Date().toISOString(),
    };
    list.unshift(source);
    return json(res, 202, view(source));
  }
  const source = list.find((item) => item.id === itemId);
  if (!source) return json(res, 404, { title: "Not Found", status: 404 });
  if (retry) {
    source.status = "pending";
    source.reads = 0;
    delete source.lastError;
    return json(res, 202, view(source));
  }
  if (req.method === "DELETE") {
    source.removed = true;
    res.writeHead(202);
    return res.end();
  }
  return json(res, 200, view(source));
}

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;

  if (path === "/health") return json(res, 200, { ok: true });
  if (path === "/__state") return json(res, 200, state);
  if (path === "/__reset") {
    conversations = {};
    messages = {};
    sources = {};
    collections = {};
    apiKeys = [];
    agentRuns = {};
    state = { interrupted: 0, tokenRefreshes: 0, lastAuthorization: null, sourceTenants: [], tickets: 0, agentInterrupted: 0 };
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
  const agent = path.match(/^\/v1\/tenants\/([^/]+)\/agent-runs(?:\/([^/]+))?(\/approval)?$/);
  if (agent) return agentApi(req, res, agent);
  const admin = path.match(/^\/v1\/tenants\/([^/]+)\/(sources|collections|usage|api-keys|audit-log)(?:\/([^/]+))?(\/retry)?$/);
  if (admin) return adminApi(req, res, url, admin);
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
    if (content.includes("kota dolu")) {
      return json(res, 429, { type: "https://meridian.dev/problems/quota-exceeded", title: "Too Many Requests", status: 429 }, { "Retry-After": "40000" });
    }
    if (content.includes("sınır")) return json(res, 429, { title: "Too Many Requests", status: 429 }, { "Retry-After": "7" });
    return answer(req, res, conversationId, content);
  }
  return json(res, 404, { title: "Not Found", status: 404 });
}).listen(PORT);
