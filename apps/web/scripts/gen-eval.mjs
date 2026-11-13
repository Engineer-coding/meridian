// Değerlendirme raporlarından panelin okuduğu küçük özeti üretir; --check güncelliği denetler (CI).
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../../packages/eval/", import.meta.url));
const output = fileURLToPath(new URL("../src/features/admin/evalData.json", import.meta.url));
const read = (name) => JSON.parse(readFileSync(root + name, "utf8"));

const RETRIEVAL = ["recall@3", "recall@5", "mrr"];
const ANSWERS = [
  "correct",
  "correct_when_answered",
  "abstain_when_unanswerable",
  "abstain_when_answerable",
  "gold_in_context",
  "gold_cited",
  "invalid_citation_rate",
  "median_total_seconds",
];
const pick = (from, keys) => Object.fromEntries(keys.filter((key) => from?.[key] !== undefined).map((key) => [key, from[key]]));

function current(file, version) {
  const report = read(`reports/${file}.json`);
  const config = report.answers.retrieval;
  return {
    version,
    commit: report.git_commit,
    date: report.created_at,
    golden: report.golden.file.match(/(v\d+)\.jsonl$/)[1],
    questions: report.questions.total,
    config,
    retrieval: pick(report.summary[config].overall, RETRIEVAL),
    answers: pick(report.answers.summary, ANSWERS),
  };
}

const thresholds = read("thresholds.json");
const data = {
  metrics: { retrieval: RETRIEVAL, answers: ANSWERS },
  thresholds: {
    min: { ...thresholds.retrieval.min, ...thresholds.answers.min },
    max: thresholds.answers.max,
  },
  releases: [...read("history.json"), current("answers", "v0.4.0"), current("answers-bge-m3", "v0.4.0 + bge-m3"), current("answers-haiku", "v0.7.0 · Haiku")],
};
const text = `${JSON.stringify(data, null, 2)}\n`;

if (process.argv.includes("--check")) {
  if (readFileSync(output, "utf8").replace(/\r\n/g, "\n") !== text) {
    console.error("evalData.json güncel değil: npm run gen:eval");
    process.exit(1);
  }
} else {
  writeFileSync(output, text);
}
