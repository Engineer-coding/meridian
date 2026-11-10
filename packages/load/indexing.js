// Eşzamanlı indeksleme (ADR-0019): 50 kullanıcı aynı anda ~10 sayfalık bir kaynak ekler ve hazır olmasını bekler.
// Ölçülen süre, isteğin kabulünden kaynağın "ready" olmasına kadardır: outbox, kuyruk, çekme, parçalama,
// embedding ve yazma dahil. Embedding sahtedir (HashEmbedder); gerçek modelin CPU maliyeti dahil değildir.
import { check } from "k6";
import { Rate, Trend } from "k6/metrics";

import { addSource, login, waitReady, workspace } from "./lib.js";

const JOBS = Number(__ENV.JOBS || 50);
const ready = new Rate("indexing_ready");
const readySeconds = new Trend("indexing_ready_seconds");

export const options = {
  setupTimeout: "60s",
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
  scenarios: {
    indexing: { executor: "per-vu-iterations", vus: JOBS, iterations: 1, maxDuration: "10m" },
  },
  thresholds: {
    indexing_ready: ["rate==1"],
    // Plan hedefi: 10 sayfalık belge p95 < 60 sn.
    indexing_ready_seconds: ["p(95)<60"],
  },
};

export function setup() {
  const { token } = login();
  return workspace(token);
}

export default function (data) {
  const { token } = login();
  const sourceId = addSource(token, data.tenantId, data.collectionId, `Kaynak ${__VU}`);
  const seconds = waitReady(token, data.tenantId, sourceId, 540);
  check(seconds, { "kaynak hazır": (value) => value !== null });
  ready.add(seconds !== null);
  if (seconds !== null) readySeconds.add(seconds);
}
