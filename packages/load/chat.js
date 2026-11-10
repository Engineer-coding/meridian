// Eşzamanlı sohbet (ADR-0019): her sanal kullanıcı konuşma açar, soru sorar ve akışı sonuna kadar okur.
// Model sahtedir ve gecikmesi E2E_MODEL_DELAY ile taklit edilir; ölçülen, modelin değil sistemin kapasitesidir.
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

import { API, addSource, bearer, headers, key, login, post, waitReady, workspace } from "./lib.js";

const VUS = Number(__ENV.VUS || 500);
const answered = new Rate("chat_answered");
const answerSeconds = new Trend("chat_answer_seconds");
const firstEventSeconds = new Trend("chat_first_event_seconds");

export const options = {
  setupTimeout: "180s",
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
  scenarios: {
    chat: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: __ENV.RAMP || "60s", target: VUS },
        { duration: __ENV.HOLD || "180s", target: VUS },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "60s",
      gracefulStop: "60s",
    },
  },
  thresholds: {
    chat_answered: ["rate>0.995"],
    "http_req_failed{name:message}": ["rate<0.005"],
    // Plan hedefi tam cevap p95 < 8 sn; sahte modelin kendi süresi (E2E_MODEL_DELAY) bunun içindedir.
    chat_answer_seconds: ["p(95)<8"],
  },
};

export function setup() {
  const { token } = login();
  const { tenantId, collectionId } = workspace(token);
  const sourceId = addSource(token, tenantId, collectionId, "Politikalar");
  const seconds = waitReady(token, tenantId, sourceId, 150);
  if (seconds === null) throw new Error("kaynak indekslenmedi");
  return { tenantId };
}

export default function (data) {
  const token = bearer();
  const conversation = post(`/v1/tenants/${data.tenantId}/conversations`, { title: "Yük" }, token, "conversation");
  if (!check(conversation, { "konuşma 201": (r) => r.status === 201 })) {
    answered.add(false);
    sleep(1);
    return;
  }
  const response = http.post(
    `${API}/v1/tenants/${data.tenantId}/conversations/${conversation.json("id")}/messages`,
    JSON.stringify({ content: "Başvuru ne kadar sürede sonuçlanır?" }),
    {
      headers: headers(token, { Accept: "text/event-stream", "Idempotency-Key": key() }),
      tags: { name: "message" },
      timeout: "120s",
    },
  );
  // Akış "done" ile biter; model kesilip yalnızca kaynak dönerse "degraded" işaretlenir.
  const ok =
    response.status === 200 &&
    response.body.includes("event: done") &&
    !response.body.includes('"degraded":true');
  check(response, { "cevap tamam": () => ok });
  answered.add(ok);
  if (ok) {
    answerSeconds.add(response.timings.duration / 1000);
    firstEventSeconds.add(response.timings.waiting / 1000);
  }
  sleep(1);
}
