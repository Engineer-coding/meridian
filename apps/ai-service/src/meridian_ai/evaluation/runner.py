"""Değerlendirme: korpusu gerçek indeksleme hattından geçirir, altın sorularla arar, metrikleri hesaplar."""

import json
import statistics
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg

from meridian_ai.db import create_pool
from meridian_ai.embedding import Embedder
from meridian_ai.evaluation import metrics
from meridian_ai.evaluation.corpus import Corpus, StaticFetcher
from meridian_ai.evaluation.database import SUPERUSER, Database
from meridian_ai.evaluation.golden import Question, matches
from meridian_ai.events import Event
from meridian_ai.indexer import Indexer
from meridian_ai.retrieval import Hit, Mode, Retriever

DEFAULT_KS = (1, 3, 5, 10)


class GoldenMismatch(Exception):
    """Altın setteki bir kaynak indekste hiçbir parçayla eşleşmiyor: metrik anlamsız olurdu."""


async def run(
    database: Database,
    corpora: Sequence[Corpus],
    questions: Sequence[Question],
    embedder: Embedder,
    modes: Sequence[Mode] = tuple(Mode),
    ks: Sequence[int] = DEFAULT_KS,
) -> dict[str, Any]:
    tenant = _seed_tenant(database)
    pool = create_pool(database.conninfo("meridian_ai"))
    await pool.open(wait=True)
    try:
        started = time.monotonic()
        fetchers = {c.source_type: StaticFetcher(c.documents) for c in corpora}
        indexer = Indexer(pool, embedder, fetchers)
        for corpus in corpora:
            source = _seed_source(database, tenant, corpus)
            await indexer.handle(
                Event(
                    event_id=uuid4(),
                    type="source.created",
                    tenant_id=tenant,
                    aggregate_id=source,
                    occurred_at=datetime.now(UTC),
                    data={},
                )
            )
        indexing_seconds = time.monotonic() - started
        _check_golden(database, questions)

        retriever = Retriever(pool, embedder)
        depth = max(ks)
        runs: dict[str, list[dict[str, Any]]] = {}
        for mode in modes:
            runs[mode] = [await _ask(retriever, tenant, q, mode, depth) for q in questions]
        chunk_count = _scalar(database, "SELECT count(*) FROM core.chunks")
        document_count = _scalar(database, "SELECT count(*) FROM core.documents")
    finally:
        await pool.close()

    return {
        "corpora": [{"id": c.id, "version": c.version, "documents": len(c.documents)} for c in corpora],
        "index": {"documents": document_count, "chunks": chunk_count, "seconds": round(indexing_seconds, 1)},
        "questions": {"total": len(questions), "answerable": sum(q.answerable for q in questions)},
        "ks": list(ks),
        "summary": {mode: _summarize(results, questions, ks) for mode, results in runs.items()},
        "per_question": runs,
    }


async def _ask(
    retriever: Retriever, tenant: UUID, question: Question, mode: Mode, depth: int
) -> dict[str, Any]:
    hits = await retriever.search(tenant, question.question, k=depth, mode=mode)
    judged = metrics.judge(
        hits, question.sources, lambda ref, hit: matches(ref, hit.document_path, hit.section)
    )
    return {
        "id": question.id,
        "source_ranks": [judged.first_ranks().get(i) for i in range(len(question.sources))],
        "top_score": round(hits[0].score, 4) if hits else None,
        "top": [_brief(hit) for hit in hits[:3]],
        "_judged": judged,
    }


def _brief(hit: Hit) -> str:
    return f"{hit.document_path} § {hit.section}"


def _summarize(
    results: list[dict[str, Any]], questions: Sequence[Question], ks: Sequence[int]
) -> dict[str, Any]:
    by_id = {q.id: q for q in questions}
    answerable = [r for r in results if by_id[r["id"]].answerable]

    def scores(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
        rows = list(rows)
        if not rows:
            return {}
        judged = [r["_judged"] for r in rows]
        out = {f"recall@{k}": statistics.fmean(metrics.recall_at(j, k) for j in judged) for k in ks}
        out["mrr"] = statistics.fmean(metrics.reciprocal_rank(j) for j in judged)
        out |= {f"ndcg@{k}": statistics.fmean(metrics.ndcg_at(j, k) for j in judged) for k in ks}
        return {name: round(value, 4) for name, value in out.items()} | {"n": len(rows)}

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in answerable:
        q = by_id[row["id"]]
        for key in (f"corpus={q.corpus}", f"type={q.type}", f"lang={q.lang}"):
            groups[key].append(row)

    top_scores = {
        "answerable": [r["top_score"] for r in answerable if r["top_score"] is not None],
        "unanswerable": [
            r["top_score"] for r in results if not by_id[r["id"]].answerable and r["top_score"] is not None
        ],
    }
    return {
        "overall": scores(answerable),
        "groups": {key: scores(rows) for key, rows in sorted(groups.items())},
        # Cevapsız sorularda en iyi skorun cevaplı sorulardan ayrışıp ayrışmadığı: Faz 4'teki
        # "bilmiyorum" eşiği için ilk veri (yalnızca vektör skorunda anlamlıdır).
        "top_score": {
            name: {"mean": round(statistics.fmean(v), 4), "min": min(v), "max": max(v)}
            for name, v in top_scores.items()
            if v
        },
    }


def _check_golden(database: Database, questions: Sequence[Question]) -> None:
    rows = _query(
        database,
        "SELECT d.path, c.section FROM core.chunks c JOIN core.documents d ON d.id = c.document_id",
    )
    # Alternatifler dahil her aday tek tek denetlenir: yanlış yazılmış bir alternatif sessizce
    # yok sayılmasın.
    missing = [
        f"{q.id}: {candidate.doc} § {candidate.section}"
        for q in questions
        for ref in q.sources
        for candidate in ref.candidates()
        if not any(matches(candidate, path, section) for path, section in rows)
    ]
    if missing:
        raise GoldenMismatch("indekste karşılığı olmayan altın kaynaklar:\n  " + "\n  ".join(missing))


def _seed_tenant(database: Database) -> UUID:
    tenant = uuid4()
    _execute(
        database,
        "INSERT INTO core.tenants (id, slug, name) VALUES (%s, %s, 'Değerlendirme')",
        tenant,
        f"eval-{tenant}",
    )
    return tenant


def _seed_source(database: Database, tenant: UUID, corpus: Corpus) -> UUID:
    collection, source = uuid4(), uuid4()
    _execute(
        database,
        "INSERT INTO core.collections (id, tenant_id, name) VALUES (%s, %s, %s)",
        collection,
        tenant,
        corpus.id,
    )
    _execute(
        database,
        """INSERT INTO core.sources (id, tenant_id, collection_id, name, type, config)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        source,
        tenant,
        collection,
        corpus.id,
        corpus.source_type,
        json.dumps({"type": corpus.source_type}),
    )
    return source


def _query(database: Database, sql: str, *params: Any) -> list[tuple]:
    with psycopg.connect(database.conninfo(SUPERUSER), autocommit=True) as conn:
        cursor = conn.execute(sql, params)
        return cursor.fetchall() if cursor.description else []


def _execute(database: Database, sql: str, *params: Any) -> None:
    _query(database, sql, *params)


def _scalar(database: Database, sql: str) -> int:
    return _query(database, sql)[0][0]


def public(report: dict[str, Any]) -> dict[str, Any]:
    """Rapordan iç alanları (``_judged``) çıkarır."""
    return report | {
        "per_question": {
            mode: [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]
            for mode, rows in report["per_question"].items()
        }
    }
