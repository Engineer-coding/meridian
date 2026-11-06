"""Değerlendirme hattı: metrikler, alaka eşleştirmesi, arama ve rapor kapısı."""

import importlib.util
import json
import re
from uuid import uuid4

import pytest

from meridian_ai.answering import EVIDENCE_PROMPTS
from meridian_ai.db import create_pool
from meridian_ai.embedding import HashEmbedder
from meridian_ai.evaluation import gate, metrics, runner
from meridian_ai.evaluation.candidates import check as check_candidates
from meridian_ai.evaluation.corpus import EVAL_DIR, REPO_ROOT, Corpus
from meridian_ai.evaluation.database import Database
from meridian_ai.evaluation.golden import (
    Question,
    SourceRef,
    answer_correct,
    keyword_hit,
    load_golden,
    matches,
)
from meridian_ai.fetchers import RawDocument
from meridian_ai.retrieval import Mode, Retriever

# --- metrikler -------------------------------------------------------------------------------


def judged(*ranks: set[int], sources: int) -> metrics.Judged:
    return metrics.Judged([frozenset(r) for r in ranks], sources)


def test_single_source_found_at_rank_three() -> None:
    j = judged(set(), set(), {0}, {0}, sources=1)
    assert metrics.recall_at(j, 1) == 0
    assert metrics.recall_at(j, 3) == 1
    assert metrics.reciprocal_rank(j) == pytest.approx(1 / 3)
    assert metrics.ndcg_at(j, 10) == pytest.approx(0.5)


def test_repeated_chunks_of_one_section_count_once() -> None:
    j = judged({0}, {0}, {0}, sources=2)
    assert metrics.recall_at(j, 10) == 0.5
    assert metrics.ndcg_at(j, 10) == pytest.approx(1 / (1 + 1 / 1.584962500721156))


def test_multi_hop_needs_every_source() -> None:
    j = judged({1}, set(), {0}, sources=2)
    assert metrics.recall_at(j, 1) == 0.5
    assert metrics.recall_at(j, 3) == 1
    assert metrics.reciprocal_rank(j) == 1


def test_nothing_found_scores_zero() -> None:
    j = judged(set(), set(), sources=1)
    assert (metrics.recall_at(j, 10), metrics.reciprocal_rank(j), metrics.ndcg_at(j, 10)) == (0, 0, 0)


def test_one_chunk_covering_two_sources_is_capped_at_ideal() -> None:
    assert metrics.ndcg_at(judged({0, 1}, sources=2), 10) == 1.0


# --- alaka eşleştirmesi ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ref", "doc", "section", "expected"),
    [
        (
            SourceRef("kvkk/6698.md", "Madde 13"),
            "kvkk/6698.md",
            "KVKK > Dördüncü Bölüm > Madde 13 – Başvuru",
            True,
        ),
        (
            SourceRef("kvkk/6698.md", "Madde 13"),
            "kvkk/6698.md",
            "KVKK > Altıncı Bölüm > Madde 130 – Yok",
            False,
        ),
        (SourceRef("kvkk/6698.md", "Madde 13"), "başka.md", "KVKK > Madde 13 – Başvuru", False),
        (SourceRef("svc.md", "type: ClusterIP"), "svc.md", "Service > Publishing > `type: ClusterIP`", True),
        (SourceRef("svc.md", "Pod phase"), "svc.md", "Pod Lifecycle > Pod phase > Pending", True),
        (SourceRef("secret.md", "Giriş (caution notu)"), "secret.md", "Secrets", True),
        (SourceRef("secret.md", "Giriş (caution notu)"), "secret.md", "Secrets > Uses", False),
        (SourceRef("doc.md", "Secrets"), "doc.md", "Secrets", False),
    ],
)
def test_reference_matching(ref: SourceRef, doc: str, section: str, expected: bool) -> None:
    assert matches(ref, doc, section) is expected


def test_alternative_section_satisfies_the_same_source() -> None:
    ref = SourceRef("lifecycle.md", "Liveness probe", (SourceRef("probes.md", "Liveness probe"),))
    assert matches(ref, "probes.md", "Probes > Types of probe > Liveness probe")
    assert matches(ref, "lifecycle.md", "Pod Lifecycle > Container probes > Liveness probe")
    assert not matches(ref, "probes.md", "Probes > Readiness probe")


def test_golden_v1_differs_from_v0_only_by_alternatives() -> None:
    v0 = {q.id: q for q in load_golden(EVAL_DIR / "golden" / "v0.jsonl")}
    v1 = {q.id: q for q in load_golden(EVAL_DIR / "golden" / "v1.jsonl")}
    assert v0.keys() == v1.keys()
    for qid, q in v1.items():
        stripped = tuple(SourceRef(s.doc, s.section) for s in q.sources)
        assert (q.question, stripped) == (v0[qid].question, v0[qid].sources), qid
    assert {qid for qid, q in v1.items() if any(s.alternatives for s in q.sources)} == {"k8s-002", "k8s-005"}


def test_golden_set_loads_with_expected_shape() -> None:
    questions = load_golden(EVAL_DIR / "golden" / "v1.jsonl")
    assert len(questions) == 30
    assert all(q.sources for q in questions if q.answerable)
    assert not any(q.sources for q in questions if not q.answerable)


# --- arama -----------------------------------------------------------------------------------

DOCS = [
    RawDocument(
        "docs/probes.md",
        "u1",
        "v",
        "# Probes\n\n## Liveness probe\n\nThe kubelet restarts a container when the liveness probe fails.\n\n"
        "## Readiness probe\n\nTraffic is sent only to pods whose readiness probe succeeds.",
    ),
    RawDocument(
        "kvkk/6698.md",
        "u2",
        "v",
        "# KVKK\n\n### Madde 13 – Başvuru\n\nVeri sorumlusu başvuruyu en geç otuz gün içinde sonuçlandırır.",
    ),
]

QUESTIONS = [
    Question("q1", "When does the kubelet restart a container?", "en", "single_hop", "k8s",
             (SourceRef("docs/probes.md", "Liveness probe"),)),
    Question("q2", "Başvuru kaç gün içinde sonuçlandırılır?", "tr", "single_hop", "kvkk",
             (SourceRef("kvkk/6698.md", "Madde 13"),)),
    Question("q3", "Liveness ve readiness probe farkı?", "tr", "multi_hop", "k8s",
             (SourceRef("docs/probes.md", "Liveness probe"), SourceRef("docs/probes.md", "Readiness probe"))),
    Question("q4", "Kurul kaç saat içinde bildirim ister?", "tr", "unanswerable", "kvkk", ()),
]  # fmt: skip


async def test_evaluation_runs_end_to_end_through_the_real_pipeline(database: Database) -> None:
    corpora = [Corpus("k8s", "github", "v", DOCS[:1]), Corpus("kvkk", "upload", "v", DOCS[1:])]

    report = runner.public(await runner.run(database, corpora, QUESTIONS, HashEmbedder()))

    assert report["index"] == report["index"] | {"documents": 2, "chunks": 3}
    assert report["questions"] == {"total": 4, "answerable": 3}
    for mode in Mode:
        overall = report["summary"][mode]["overall"]
        assert overall["n"] == 3
        assert 0 <= overall["recall@1"] <= overall["recall@3"] <= overall["recall@10"] <= 1
    assert report["summary"]["lexical"]["overall"]["recall@3"] == 1.0
    assert {"corpus=k8s", "corpus=kvkk", "lang=tr", "type=multi_hop"} <= set(
        report["summary"]["hybrid"]["groups"]
    )
    assert "_judged" not in report["per_question"]["hybrid"][0]
    json.dumps(report)


async def test_golden_reference_missing_from_the_index_fails_loudly(database: Database) -> None:
    corpora = [Corpus("k8s", "github", "v", DOCS[:1])]
    broken = [Question("x", "?", "en", "single_hop", "k8s", (SourceRef("docs/probes.md", "Startup probe"),))]

    with pytest.raises(runner.GoldenMismatch, match="Startup probe"):
        await runner.run(database, corpora, broken, HashEmbedder())

    typo = SourceRef("docs/probes.md", "Liveness probe", (SourceRef("docs/probes.md", "Livenes probe"),))
    with pytest.raises(runner.GoldenMismatch, match="Livenes probe"):
        await runner.run(
            database, corpora, [Question("y", "?", "en", "single_hop", "k8s", (typo,))], HashEmbedder()
        )


async def test_search_is_scoped_to_the_tenant_and_collection(database: Database) -> None:
    corpora = [Corpus("k8s", "github", "v", DOCS[:1]), Corpus("kvkk", "upload", "v", DOCS[1:])]
    await runner.run(database, corpora, QUESTIONS[:1], HashEmbedder())
    [(tenant, kvkk_collection)] = runner._query(
        database,
        "SELECT tenant_id, id FROM core.collections WHERE name = 'kvkk' ORDER BY created_at DESC LIMIT 1",
    )

    pool = create_pool(database.conninfo("meridian_ai"))
    await pool.open(wait=True)
    try:
        retriever = Retriever(pool, HashEmbedder())
        for mode in Mode:
            assert await retriever.search(uuid4(), "kubelet restarts container", mode=mode) == []
            scoped = await retriever.search(
                tenant, "otuz gün kubelet", mode=mode, collection_ids=[kvkk_collection]
            )
            assert {hit.document_path for hit in scoped} == {"kvkk/6698.md"}
        assert await retriever.search(tenant, "ve bir mi", mode=Mode.LEXICAL) == [], (
            "yalnızca durak kelimeleri"
        )
    finally:
        await pool.close()


# --- rapor kapısı (ADR-0010) ----------------------------------------------------------------


def _report(name: str) -> dict:
    return json.loads((EVAL_DIR / "reports" / f"{name}.json").read_text(encoding="utf-8"))


def test_committed_retrieval_report_is_current_and_meets_thresholds() -> None:
    """Sonucu etkileyen kod, altın set ya da korpus değişip ölçüm yenilenmediyse CI kırılır."""
    report = _report("baseline")
    golden = REPO_ROOT / report["golden"]["file"]

    assert golden.name == "v2.jsonl"
    assert report["fingerprint"] == gate.fingerprint(golden, gate.RETRIEVAL_CODE), (
        "arama kodu, altın set ya da manifest değişti: make eval NAME=baseline ile yeniden ölçün"
    )
    answerable = {q.id for q in load_golden(golden) if q.answerable}
    for mode in Mode:
        assert {row["id"] for row in report["per_question"][mode]} >= answerable
    floors = gate.thresholds()["retrieval"]
    assert gate.violations(report["summary"][floors["config"]]["overall"], floors["min"]) == []


def test_committed_answer_report_is_current_and_meets_thresholds() -> None:
    report = _report("answers")
    golden = REPO_ROOT / report["golden"]["file"]

    assert report["fingerprint"] == gate.fingerprint(golden, gate.ANSWER_CODE), (
        "cevap kodu, altın set ya da manifest değişti: make eval-answers NAME=answers ile yeniden ölçün"
    )
    limits = gate.thresholds()["answers"]
    assert gate.violations(report["answers"]["summary"], limits["min"], limits["max"]) == []


def test_gate_reports_low_missing_and_too_high_metrics() -> None:
    found = gate.violations({"a": 0.5, "c": 0.9}, {"a": 0.6, "b": 0.1}, {"c": 0.8})
    assert len(found) == 3
    assert gate.violations({"a": 0.6, "c": 0.8}, {"a": 0.6}, {"c": 0.8}) == []


def test_fingerprint_changes_with_the_golden_set(tmp_path) -> None:
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    first.write_bytes(b"x\n")
    second.write_bytes(b"x\r\n")
    third = tmp_path / "c.jsonl"
    third.write_bytes(b"y\n")

    assert gate.fingerprint(first, gate.RETRIEVAL_CODE) == gate.fingerprint(second, gate.RETRIEVAL_CODE)
    assert gate.fingerprint(first, gate.RETRIEVAL_CODE) != gate.fingerprint(third, gate.RETRIEVAL_CODE)
    assert gate.fingerprint(first, gate.RETRIEVAL_CODE) != gate.fingerprint(first, gate.ANSWER_CODE)


# --- cevap değerlendirmesi --------------------------------------------------------------------


class ScriptedLLM:
    name = "scripted"

    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, messages, *, max_tokens):
        """Kanıt aşamasında ilk kaynağın ilk cümlesini alıntılar; "saat" sorusunda alıntı yoktur."""
        self.calls += 1
        context = messages[1].content
        if messages[-1].content in EVIDENCE_PROMPTS.values():
            yield "YOK" if "saat" in context else re.search(r"\[1\] [^\n]*\n([^.\n]+)", context).group(1)
        else:
            yield "Cevap kaynakta [1]."


async def test_answers_are_scored_against_golden_sources(database: Database) -> None:
    corpora = [Corpus("k8s", "github", "v", DOCS[:1]), Corpus("kvkk", "upload", "v", DOCS[1:])]

    report = await runner.run(
        database, corpora, QUESTIONS, HashEmbedder(), answer_llm=ScriptedLLM(), answer_sources=2
    )

    summary = report["answers"]["summary"]
    assert summary["n"] == 4
    assert summary["abstain_when_unanswerable"] == 1.0
    assert summary["abstain_when_answerable"] == 0.0
    assert summary["invalid_citation_rate"] == 0.0
    by_id = {row["id"]: row for row in report["answers"]["per_question"]}
    assert by_id["q4"]["abstained"] and not by_id["q2"]["abstained"]
    assert by_id["q2"]["cited"] == [1]


async def test_cached_completion_is_replayed_without_calling_the_model(tmp_path) -> None:
    from meridian_ai.evaluation.cache import CachingLLM
    from meridian_ai.llm import Message

    inner = ScriptedLLM()
    cached = CachingLLM(inner, tmp_path / "c.sqlite")
    messages = [Message("system", "s"), Message("user", "soru")]
    first = "".join([t async for t in cached.stream(messages, max_tokens=10)])
    second = "".join([t async for t in cached.stream(messages, max_tokens=10)])
    other = "".join([t async for t in cached.stream(messages, max_tokens=11)])

    assert first == second == other == "Cevap kaynakta [1]."
    assert inner.calls == 2, "farklı ayar yeni bir anahtar"
    assert cached.last_timing is not None
    cached.close()


# --- yeniden sıralama (ADR-0007) ------------------------------------------------------------


class KeywordReranker:
    """Sahte çapraz kodlayıcı: sorudaki kelimelerden kaçının parçada geçtiğini sayar."""

    name = "keyword"

    def __init__(self) -> None:
        self.calls = 0

    async def scores(self, query: str, texts):
        self.calls += 1
        words = set(re.findall(r"\w+", query.lower()))
        return [float(len(words & set(re.findall(r"\w+", t.lower())))) for t in texts]


async def test_rerank_orders_by_score_and_keeps_k() -> None:
    from meridian_ai.reranking import rerank
    from meridian_ai.retrieval import Hit

    hits = [
        Hit(uuid4(), "d", "t", None, s, c, 0.5)
        for s, c in [("a", "x"), ("b", "readiness probe"), ("c", "probe")]
    ]
    ranked = await rerank(KeywordReranker(), "readiness probe", hits, k=2)

    assert [h.section for h in ranked] == ["b", "c"]
    assert [h.score for h in ranked] == [2.0, 1.0]


async def test_ablation_adds_reranked_configurations_and_answers_can_use_them(database: Database) -> None:
    corpora = [Corpus("k8s", "github", "v", DOCS[:1]), Corpus("kvkk", "upload", "v", DOCS[1:])]
    reranker = KeywordReranker()

    report = await runner.run(
        database,
        corpora,
        QUESTIONS,
        HashEmbedder(),
        rerankers={"kw": reranker},
        answer_llm=ScriptedLLM(),
        answer_config="hybrid+kw",
    )

    assert set(report["summary"]) == {"vector", "lexical", "hybrid", "vector+kw", "hybrid+kw"}
    assert report["answers"]["retrieval"] == "hybrid+kw"
    assert reranker.calls == 2 * len(QUESTIONS) + len(QUESTIONS), "iki ilk aşama + cevaplar"


async def test_cached_reranker_scores_only_new_pairs(tmp_path) -> None:
    from meridian_ai.evaluation.cache import CachingReranker

    inner = KeywordReranker()
    cached = CachingReranker(inner, tmp_path / "r.sqlite")
    first = await cached.scores("probe", ["probe a", "b"])
    second = await cached.scores("probe", ["b", "probe a", "probe c"])

    assert first == [1.0, 0.0] and second == [0.0, 1.0, 1.0]
    assert inner.calls == 2
    cached.close()


async def test_search_refuses_rerank_without_a_reranker(database: Database) -> None:
    pool = create_pool(database.conninfo("meridian_ai"))
    await pool.open(wait=True)
    try:
        with pytest.raises(ValueError, match="reranker"):
            await Retriever(pool, HashEmbedder()).search(uuid4(), "soru", rerank=True)
    finally:
        await pool.close()


# --- cevap doğruluğu --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "keyword", "expected"),
    [
        ("Kurula şikâyet edilir", "kurul", True),
        ("KURUL karar verir", "kurul", True),
        ("Görev süresi DÖRT yıldır", "dört", True),
        ("the none value", "one", False),
        ("backoff is 16", "6", False),
        ("backoff is 6.", "6", True),
        ("15.000 TL", "5.000", False),
        ("5.000 TL ceza", "5.000", True),
        ("1.000.000 TL", "1.000", False),
        ("in status.recommendation field", "status.recommendation", True),
        ("the `.status.recommendation` field", "status.recommendation", True),
        ("`ownerReferences.blockOwnerDeletion` field", "blockownerdeletion", True),
        ("3 sunucu vardır [1]", "1", False),
        ("Yalnızca 1 tane [2]", "1", True),
        ("Hayır, kullanamaz", "hayır", True),
        ("No, it is not", "no,", True),
    ],
)
def test_keyword_matching(answer: str, keyword: str, expected: bool) -> None:
    assert keyword_hit(answer, keyword) is expected


def test_answer_needs_every_keyword_group() -> None:
    groups = (("otuz", "30"), ("altmış", "60"))
    assert answer_correct("otuz gün, en geç 60 gün", groups)
    assert not answer_correct("otuz gün", groups)
    assert not answer_correct("otuz gün", ()), "anahtar kelimesiz soru doğru sayılmaz"


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_golden_v2", EVAL_DIR / "scripts" / "build_golden_v2.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_golden_v2_contains_only_human_decided_candidates() -> None:
    def candidate(identifier: str) -> dict:
        return {
            "id": identifier,
            "question": "q",
            "type": "single_hop",
            "expected_answer": "a",
            "keywords": [["a"]],
            "verified": False,
            "forbidden": ["x"],
        }

    v1 = [
        {"id": "old-1", "question": "eski", "type": "single_hop", "expected_answer": "a"},
        {"id": "old-2", "question": "eski", "type": "single_hop", "expected_answer": "a"},
    ]
    decisions = {
        "old-1": {"decision": "approve"},
        "new-ok": {"decision": "approve"},
        "new-edit": {"decision": "edit", "question": "düzeltilmiş", "keywords": [["b"]]},
        "new-no": {"decision": "reject"},
    }
    items, tally = _builder().build(
        decisions,
        v1,
        [candidate("new-ok"), candidate("new-edit"), candidate("new-no"), candidate("new-open")],
        {"old-1": [["k"]], "old-2": [["k"]]},
    )

    by_id = {i["id"]: i for i in items}
    assert set(by_id) == {"old-1", "old-2", "new-ok", "new-edit"}
    assert by_id["old-1"]["keywords"] == [["k"]]
    assert "keywords" not in by_id["old-2"], "onaylanmamış anahtar kelime eklenmez"
    assert by_id["new-ok"]["verified"] is True and "forbidden" not in by_id["new-ok"]
    assert (by_id["new-edit"]["question"], by_id["new-edit"]["keywords"]) == ("düzeltilmiş", [["b"]])
    assert tally["undecided"] == 1 and tally["reject"] == 1


def test_candidate_checks_catch_missing_evidence_and_leaked_terms() -> None:
    document = RawDocument("d.md", "u", "v", "# T\n\n## Bölüm\n\nVeri otuz gün saklanır.")

    def answerable(identifier, section, evidence):
        source = {"doc": "d.md", "section": section, "evidence": evidence}
        return {
            "id": identifier,
            "question": identifier,
            "type": "single_hop",
            "lang": "tr",
            "sources": [source],
        }

    def trap(identifier, question, forbidden):
        return {
            "id": identifier,
            "question": question,
            "type": "unanswerable",
            "lang": "tr",
            "sources": [],
            "forbidden": forbidden,
        }

    items = [
        answerable("a", "Bölüm", "otuz gün saklanır"),
        answerable("b", "Bölüm", "yetmiş gün saklanır"),
        answerable("c", "Yok", "x"),
        trap("d", "d", ["otuz gün"]),
        trap("e", "e", ["gü"]),
        trap("f", "a", []),
    ]

    errors = check_candidates(items, [document]).errors

    assert [e.split(":")[0] for e in errors] == ["b", "c", "d", "f"]
