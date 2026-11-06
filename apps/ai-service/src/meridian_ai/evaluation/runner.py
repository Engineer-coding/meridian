"""Değerlendirme: korpusu gerçek indeksleme hattından geçirir, altın sorularla arar, metrikleri hesaplar."""

import json
import statistics
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg

from meridian_ai.answering import Answerer, Done, Source, SourcesFound
from meridian_ai.db import create_pool
from meridian_ai.embedding import Embedder
from meridian_ai.evaluation import metrics
from meridian_ai.evaluation.corpus import Corpus, StaticFetcher
from meridian_ai.evaluation.database import SUPERUSER, Database
from meridian_ai.evaluation.golden import Question, answer_correct, matches
from meridian_ai.events import Event
from meridian_ai.indexer import Indexer
from meridian_ai.llm import LLM
from meridian_ai.reranking import Reranker
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
    answer_llm: LLM | None = None,
    answer_sources: int = 3,
    rerankers: Mapping[str, Reranker] | None = None,
    answer_config: str = Mode.VECTOR,
) -> dict[str, Any]:
    """Her yapılandırma = ilk aşama (``modes``) ya da ilk aşama + reranker (ablasyon, ADR-0007).

    ``rerankers``: kısa ad → reranker; her biri vektör ve hibrit ilk aşamanın üstünde denenir.
    ``answer_config``: cevap değerlendirmesinin kullanacağı yapılandırma, ör. ``vector+bge-m3``.
    """
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

        configs: dict[str, tuple[Retriever, Mode, Reranker | None]] = {
            str(mode): (Retriever(pool, embedder), mode, None) for mode in modes
        }
        for short, reranker in (rerankers or {}).items():
            for mode in (Mode.VECTOR, Mode.HYBRID):
                configs[f"{mode}+{short}"] = (Retriever(pool, embedder, reranker=reranker), mode, reranker)
        depth = max(ks)
        runs: dict[str, list[dict[str, Any]]] = {}
        for name, (retriever, mode, reranker) in configs.items():
            runs[name] = [await _ask(retriever, tenant, q, mode, depth, reranker) for q in questions]
            print(f"arama: {name}", flush=True)
        answers = None
        if answer_llm is not None:
            retriever, mode, reranker = configs[answer_config]
            answerer = Answerer(
                retriever, answer_llm, k=answer_sources, mode=mode, rerank=reranker is not None
            )
            answers = []
            for i, q in enumerate(questions, start=1):
                answers.append(await _respond(answerer, answer_llm, tenant, q))
                print(f"cevap {i}/{len(questions)} {q.id}", flush=True)
        chunk_count = _scalar(database, "SELECT count(*) FROM core.chunks")
        document_count = _scalar(database, "SELECT count(*) FROM core.documents")
    finally:
        await pool.close()

    report = {
        "corpora": [{"id": c.id, "version": c.version, "documents": len(c.documents)} for c in corpora],
        "index": {"documents": document_count, "chunks": chunk_count, "seconds": round(indexing_seconds, 1)},
        "questions": {"total": len(questions), "answerable": sum(q.answerable for q in questions)},
        "ks": list(ks),
        "summary": {mode: _summarize(results, questions, ks) for mode, results in runs.items()},
        "per_question": runs,
    }
    if answers is not None:
        report["answers"] = {
            "model": answer_llm.name,
            "retrieval": answer_config,
            "sources": answer_sources,
            "summary": _summarize_answers(answers, questions),
            "per_question": answers,
        }
    return report


async def _respond(answerer: Answerer, llm: LLM, tenant: UUID, question: Question) -> dict[str, Any]:
    sources: list[Source] = []
    done: Done | None = None
    async for event in answerer.answer(tenant, question.question):
        if isinstance(event, SourcesFound):
            sources = event.sources
        elif isinstance(event, Done):
            done = event
    assert done is not None  # noqa: S101 - Answerer her zaman Done ile biter
    timing = getattr(llm, "last_timing", None) or (done.first_token_seconds, done.total_seconds)

    def supports(numbers: Iterable[int]) -> bool:
        cited = [s for s in sources if s.number in numbers]
        return any(
            matches(ref, s.hit.document_path, s.hit.section) for ref in question.sources for s in cited
        )

    return {
        "id": question.id,
        "answer": done.answer[:600],
        "abstained": done.abstained,
        "degraded": done.degraded,
        "cited": done.cited,
        "invalid_citations": done.invalid_citations,
        # Altın kaynaklardan biri bağlama girdi mi (üst sınır) ve model onu mu kaynak gösterdi?
        "gold_in_context": supports(s.number for s in sources),
        "gold_cited": supports(done.cited),
        "correct": answer_correct(done.answer, question.keywords) if not done.abstained else False,
        "sources": [_brief(s.hit) for s in sources],
        "first_token_seconds": None if timing[0] is None else round(timing[0], 1),
        "total_seconds": round(timing[1], 1),
    }


def _summarize_answers(rows: list[dict[str, Any]], questions: Sequence[Question]) -> dict[str, Any]:
    by_id = {q.id: q for q in questions}
    answerable = [r for r in rows if by_id[r["id"]].answerable]
    unanswerable = [r for r in rows if not by_id[r["id"]].answerable]
    responded = [r for r in answerable if not r["abstained"] and not r["degraded"]]
    graded = [r for r in answerable if by_id[r["id"]].keywords]

    def share(items: list[dict[str, Any]], predicate) -> float | None:
        return round(sum(1 for r in items if predicate(r)) / len(items), 3) if items else None

    fresh = [r for r in rows if r["first_token_seconds"] is not None]
    return {
        # Cevabı olmayan soruda "bilmiyorum" demek doğru davranıştır.
        "abstain_when_unanswerable": share(unanswerable, lambda r: r["abstained"]),
        # Cevabı olan soruda "bilmiyorum" demek gereksiz çekimserliktir.
        "abstain_when_answerable": share(answerable, lambda r: r["abstained"]),
        "gold_in_context": share(answerable, lambda r: r["gold_in_context"]),
        "cites_something": share(responded, lambda r: bool(r["cited"])),
        "gold_cited": share(responded, lambda r: r["gold_cited"]),
        # Yalnızca anahtar kelimesi tanımlı sorular: "bilmiyorum" da doğru sayılmaz.
        "correct": share(graded, lambda r: r["correct"]),
        "correct_when_answered": share(
            [r for r in graded if not r["abstained"] and not r["degraded"]], lambda r: r["correct"]
        ),
        "invalid_citation_rate": share(rows, lambda r: bool(r["invalid_citations"])),
        "degraded": sum(1 for r in rows if r["degraded"]),
        "median_first_token_seconds": (
            round(statistics.median(r["first_token_seconds"] for r in fresh), 1) if fresh else None
        ),
        "median_total_seconds": round(statistics.median(r["total_seconds"] for r in rows), 1)
        if rows
        else None,
        "n": len(rows),
    }


async def _ask(
    retriever: Retriever,
    tenant: UUID,
    question: Question,
    mode: Mode,
    depth: int,
    reranker: Reranker | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    hits = await retriever.search(tenant, question.question, k=depth, mode=mode, rerank=reranker is not None)
    elapsed = time.monotonic() - started
    # Önbellekten gelen yeniden sıralamanın gerçek (ilk ölçülen) süresi eklenir.
    rerank_seconds = getattr(reranker, "last_seconds", 0.0) if reranker else 0.0
    judged = metrics.judge(
        hits, question.sources, lambda ref, hit: matches(ref, hit.document_path, hit.section)
    )
    return {
        "id": question.id,
        "source_ranks": [judged.first_ranks().get(i) for i in range(len(question.sources))],
        "top_score": round(hits[0].score, 4) if hits else None,
        "top": [_brief(hit) for hit in hits[:3]],
        "rerank_seconds": round(rerank_seconds, 2),
        "search_seconds": round(elapsed, 3),
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
        # Yeniden sıralamanın soru başına ölçülmüş süresi (ilk aşama milisaniyeler sürer).
        "rerank_seconds": round(statistics.median(r["rerank_seconds"] for r in results), 1)
        if results
        else 0.0,
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
