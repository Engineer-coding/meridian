"""``python -m meridian_ai.evaluation``: altın set v0 üzerinde retrieval değerlendirmesi.

Geçici bir PostgreSQL başlatır, korpusu üretimdeki indeksleme hattıyla indeksler, her soru
için vektör / sözcüksel / hibrit aramayı çalıştırır ve raporu packages/eval/reports altına yazar.
Embedding'ler diskte önbelleklenir: ilk çalıştırma saatler, sonrakiler dakikalar sürer.
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from meridian_ai.chunking import MAX_CHARS, OVERLAP_CHARS
from meridian_ai.embedding import DEFAULT_MODEL, E5Embedder, HashEmbedder
from meridian_ai.evaluation import corpus, database, runner
from meridian_ai.evaluation.cache import CachingEmbedder
from meridian_ai.evaluation.golden import load_golden

CACHE = Path.home() / ".cache" / "meridian"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str | None:
    """Ölçülen kod sürümü; commit edilmemiş değişiklik varsa "-dirty" eklenir."""

    def git(*args: str) -> str:
        return subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=corpus.REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    try:
        commit = git("rev-parse", "--short", "HEAD")
        dirty = git("status", "--porcelain", "--", "apps", "packages/eval/corpus", "packages/eval/golden")
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{commit}-dirty" if dirty else commit


def markdown(report: dict) -> str:
    ks = report["ks"]
    corpora = ", ".join(f"{c['id']}@{c['version'][:12]} ({c['documents']} belge)" for c in report["corpora"])
    columns = [*(f"recall@{k}" for k in ks), "mrr", *(f"ndcg@{k}" for k in (5, 10) if k in ks)]
    lines = [
        f"# Retrieval değerlendirmesi — {report['name']}",
        "",
        f"- Tarih: {report['created_at']} · commit `{report['git_commit']}`",
        f"- Model: `{report['embedding']['model']}` · parça ≤ {report['chunking']['max_chars']} karakter, "
        f"örtüşme {report['chunking']['overlap_chars']}",
        f"- Korpus: {corpora} → {report['index']['chunks']} parça",
        f"- Altın set: {report['questions']['answerable']} cevaplı / {report['questions']['total']} soru "
        f"(`{report['golden']['file']}`, sha256 `{report['golden']['sha256'][:12]}`)",
        "",
        "## Genel (cevaplı sorular)",
        "",
        "| Yöntem | " + " | ".join(columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for mode, summary in report["summary"].items():
        lines.append(f"| {mode} | " + " | ".join(f"{summary['overall'][c]:.3f}" for c in columns) + " |")
    lines += ["", "## Kırılımlar (recall@5 / MRR)", ""]
    modes = list(report["summary"])
    lines += ["| Grup | n | " + " | ".join(modes) + " |", "|---|---|" + "---|" * len(modes)]
    for group in report["summary"][modes[0]]["groups"]:
        cells = [
            "{recall@5:.2f} / {mrr:.2f}".format_map(report["summary"][m]["groups"][group]) for m in modes
        ]
        n = report["summary"][modes[0]]["groups"][group]["n"]
        lines.append(f"| {group} | {n} | " + " | ".join(cells) + " |")
    if "vector" in report["summary"]:
        top = report["summary"]["vector"]["top_score"]
        lines += [
            "",
            "## En iyi vektör skoru (cevaplı ve cevapsız sorular)",
            "",
            "| | ortalama | en düşük | en yüksek |",
            "|---|---|---|---|",
            *(f"| {name} | {v['mean']:.3f} | {v['min']:.3f} | {v['max']:.3f} |" for name, v in top.items()),
        ]
    lines += ["", "## Kaçırılan kaynaklar (hibrit, ilk 10'da yok)", ""]
    for row in report["per_question"].get("hybrid", []):
        if None in row["source_ranks"]:
            first = row["top"][0] if row["top"] else "—"
            lines.append(f"- `{row['id']}` sıralar {row['source_ranks']} — ilk sonuç: {first}")
    return "\n".join(lines) + "\n"


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m meridian_ai.evaluation")
    parser.add_argument("--name", default="latest", help="rapor adı (packages/eval/reports/<ad>.json)")
    parser.add_argument("--embedder", choices=["e5", "hash"], default="e5")
    parser.add_argument("--golden", type=Path, default=corpus.EVAL_DIR / "golden" / "v0.jsonl")
    args = parser.parse_args(argv)

    if args.embedder == "e5":
        model = os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
        inner = E5Embedder(model, CACHE / "fastembed", batch_size=16)
        embedder = CachingEmbedder(inner, model, CACHE / "eval" / "embeddings.sqlite")
    else:
        # Modelsiz, saniyeler süren duman testi: hattı doğrular, kaliteyi ölçmez.
        model, embedder = "hash", None

    corpora = await corpus.load(CACHE / "eval", github_token=os.environ.get("GITHUB_TOKEN"))
    questions = load_golden(args.golden)
    print(f"korpus: {[(c.id, len(c.documents)) for c in corpora]} · {len(questions)} soru", flush=True)
    with database.ephemeral() as db:
        report = runner.public(await runner.run(db, corpora, questions, embedder or HashEmbedder()))
    if embedder is not None:
        print(f"embedding önbelleği: {embedder.hits} isabet, {embedder.misses} yeni", flush=True)
        embedder.close()

    report = {
        "name": args.name,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "git_commit": _git_commit(),
        "embedding": {"model": model},
        "chunking": {"max_chars": MAX_CHARS, "overlap_chars": OVERLAP_CHARS},
        "golden": {
            "file": args.golden.relative_to(corpus.REPO_ROOT).as_posix(),
            "sha256": _sha256(args.golden),
        },
        "manifest_sha256": _sha256(corpus.EVAL_DIR / "corpus" / "manifest.json"),
    } | report

    out = corpus.EVAL_DIR / "reports"
    out.mkdir(exist_ok=True)
    (out / f"{args.name}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    summary = markdown(report)
    (out / f"{args.name}.md").write_text(summary, encoding="utf-8", newline="\n")
    print(summary)
    return 0


if __name__ == "__main__":
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    sys.exit(asyncio.run(main(sys.argv[1:]), loop_factory=loop_factory))
