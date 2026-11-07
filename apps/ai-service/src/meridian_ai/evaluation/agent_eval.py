"""Ajan ölçümü: gerçek modelle senaryo seti, ADR-0015. Ticket onayı sayılır ama hiçbir şey yazılmaz.

    python -m meridian_ai.evaluation.agent_eval --llm ollama/llama3.2:3b --name agent-llama32

Sonuç önbelleğe alınmaz: model kararı geçmişe bağlıdır ve CPU'da görev başına dakikalar sürer. CI'da
çalışmaz; rapor elle üretilir ve depoya eklenir.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from meridian_ai.agent import Agent, ApprovalRequired, Budget, RunFinished, StepDone
from meridian_ai.answering import ABSTAIN
from meridian_ai.db import create_pool
from meridian_ai.embedding import DEFAULT_MODEL, E5Embedder
from meridian_ai.evaluation import corpus, database, runner
from meridian_ai.evaluation.__main__ import CACHE, _git_commit
from meridian_ai.evaluation.cache import CachingEmbedder
from meridian_ai.evaluation.golden import answer_correct, load_golden
from meridian_ai.llm import UsageCounter, build_chain, usage_counter
from meridian_ai.retrieval import Retriever


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def run_task(agent: Agent, tenant, task: dict[str, Any]) -> dict[str, Any]:
    usage = UsageCounter()
    usage_counter.set(usage)
    started = time.monotonic()
    steps: list[dict[str, Any]] = []
    proposed: dict[str, str] | None = None
    final: RunFinished | None = None
    try:
        async for event in agent.run(tenant, task["goal"]):
            match event:
                case StepDone(data=step):
                    steps.append(step)
                case ApprovalRequired(title=title, description=description):
                    proposed = {"title": title, "description": description}
                case RunFinished() as finished:
                    final = finished
    except Exception as e:  # noqa: BLE001 - ölçüm tek görev yüzünden düşmez; hata satıra yazılır
        return {"id": task["id"], "kind": task["kind"], "error": type(e).__name__}

    actions = [step["action"] for step in steps]
    answer = final.answer if final else ""
    abstained = answer == ABSTAIN
    kind = task["kind"]
    if kind == "ticket":
        success = proposed is not None
    elif kind == "abstain":
        success = abstained
    else:
        success = not abstained and answer_correct(answer, tuple((keyword,) for keyword in task["keywords"]))
    return {
        "id": task["id"],
        "kind": kind,
        "success": success,
        "status": "waiting_approval" if proposed else (final.status if final else "none"),
        "stop_reason": str(final.stop_reason) if final and final.stop_reason else None,
        "actions": actions,
        "expected_tool_used": task.get("tool") is None or task["tool"] in actions,
        "invalid_outputs": actions.count("invalid"),
        "abstained": abstained,
        "cited": final.cited if final else [],
        "unasked_ticket": proposed is not None and kind != "ticket",
        "ticket": proposed,
        "answer": answer[:300],
        "tokens": usage.prompt_tokens + usage.completion_tokens,
        "seconds": round(time.monotonic() - started, 1),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    done = [row for row in rows if "error" not in row]
    rate = lambda items, key: round(sum(1 for row in items if row[key]) / len(items), 3) if items else None  # noqa: E731
    by_kind = {
        kind: {"n": len(items), "success": rate(items, "success")}
        for kind in sorted({row["kind"] for row in done})
        if (items := [row for row in done if row["kind"] == kind])
    }
    return {
        "n": len(rows),
        "errors": len(rows) - len(done),
        "success": rate(done, "success"),
        "expected_tool_used": rate(done, "expected_tool_used"),
        "abstained": rate(done, "abstained"),
        "unasked_tickets": sum(1 for row in done if row["unasked_ticket"]),
        "invalid_outputs": sum(row["invalid_outputs"] for row in done),
        "median_steps": statistics.median(len(row["actions"]) for row in done) if done else None,
        "median_tokens": statistics.median(row["tokens"] for row in done) if done else None,
        "median_seconds": statistics.median(row["seconds"] for row in done) if done else None,
        "by_kind": by_kind,
    }


def markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    pct = lambda value: "—" if value is None else f"%{value * 100:.0f}"  # noqa: E731
    lines = [
        f"# Ajan ölçümü: {report['model']}",
        "",
        f"- Tarih: {report['created_at']} · commit `{report['git_commit']}`",
        f"- {s['n']} görev (`{report['tasks_file']}`), bütçe {report['budget']}. Senaryolar sentetik ve az: "
        "sonuç yön gösterir, kesin kalite iddiası değildir.",
        "",
        "| Ölçüt | Değer |",
        "|---|---|",
        f"| Görev başarısı | {pct(s['success'])} |",
        f"| Beklenen araç kullanıldı | {pct(s['expected_tool_used'])} |",
        f'| "Bilmiyorum" | {pct(s["abstained"])} |',
        f"| İstenmeyen ticket önerisi | {s['unasked_tickets']} |",
        f"| Geçersiz çıktı | {s['invalid_outputs']} |",
        f"| Ortanca adım / token / süre | {s['median_steps']} / {s['median_tokens']} / "
        f"{s['median_seconds']} sn |",
        "",
        "| Görev | Tür | Başarı | Adımlar | Süre | Cevap |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["rows"]:
        if "error" in row:
            lines.append(f"| `{row['id']}` | {row['kind']} | hata: {row['error']} | | | |")
            continue
        text = " ".join((row["answer"] or (row["ticket"] or {}).get("title", "")).split())[:110].replace(
            "|", "/"
        )
        mark = "✓" if row["success"] else ""
        lines.append(
            f"| `{row['id']}` | {row['kind']} | {mark} | {', '.join(row['actions'])} | "
            f"{row['seconds']} | {text} |"
        )
    return "\n".join(lines) + "\n"


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m meridian_ai.evaluation.agent_eval")
    parser.add_argument("--llm", default="ollama/llama3.2:3b")
    parser.add_argument("--name", required=True)
    parser.add_argument("--tasks", type=Path, default=corpus.EVAL_DIR / "golden" / "agent-v1.jsonl")
    args = parser.parse_args(argv)

    model = os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
    embedder = CachingEmbedder(
        E5Embedder(model, CACHE / "fastembed", batch_size=16), model, CACHE / "eval" / "embeddings.sqlite"
    )
    corpora = await corpus.load(CACHE / "eval", github_token=os.environ.get("GITHUB_TOKEN"))
    tasks = load_tasks(args.tasks)
    questions = load_golden(corpus.EVAL_DIR / "golden" / "v2.jsonl")[:1]
    budget = Budget()

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as http:
        llm = build_chain(args.llm, http, os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
        with database.ephemeral() as db:
            await runner.run(db, corpora, questions, embedder)
            [(tenant,)] = runner._query(
                db, "SELECT tenant_id FROM core.sources ORDER BY created_at DESC LIMIT 1"
            )
            conninfo = (
                f"postgresql://meridian_ai:{database.PASSWORDS['meridian_ai']}@{db.host}:{db.port}/meridian"
            )
            pool = create_pool(conninfo)
            await pool.open(wait=True)
            agent = Agent(pool, Retriever(pool, embedder), llm, budget=budget)
            rows = []
            for task in tasks:
                row = await run_task(agent, tenant, task)
                print(json.dumps(row, ensure_ascii=False)[:400], flush=True)
                rows.append(row)
            await pool.close()

    report = {
        "name": args.name,
        "model": args.llm,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "git_commit": _git_commit(),
        "tasks_file": args.tasks.relative_to(corpus.REPO_ROOT).as_posix(),
        "budget": f"{budget.max_steps} adım, {budget.max_tokens} token, {budget.seconds:.0f} sn",
        "summary": summarize(rows),
        "rows": rows,
    }
    out = corpus.EVAL_DIR / "reports"
    (out / f"{args.name}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (out / f"{args.name}.md").write_text(markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    sys.exit(asyncio.run(main(sys.argv[1:]), loop_factory=loop_factory))
