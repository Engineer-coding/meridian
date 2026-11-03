"""Kiracı kapsamlı arama: vektör, sözcüksel ve ikisinin RRF birleşimi (ADR-0003, ADR-0007).

Yetki filtresi aramanın kendisindedir: sorgu kiracı bağlamlı bir işlemde çalışır ve RLS başka
kiracının parçalarını hiç döndürmez. İstenirse koleksiyon kimlikleriyle daha da daraltılır.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from meridian_ai.db import tenant_transaction
from meridian_ai.embedding import Embedder

if TYPE_CHECKING:
    from meridian_ai.reranking import Reranker


class Mode(StrEnum):
    VECTOR = "vector"
    LEXICAL = "lexical"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class Hit:
    chunk_id: UUID
    document_path: str
    title: str
    url: str | None
    section: str
    content: str
    score: float


_WORD = re.compile(r"\w+", re.UNICODE)
# Sözcüksel aramada sıralamayı bozan en sık kelimeler ('simple' yapılandırması bunları tutar).
_STOPWORDS = frozenset(
    """a an and are as at be by can do does for from has have how i if in is it its of on or
    that the their there this to was what when where which who why will with without you your
    acaba ama bir bu bunu da daha de den diğer en gibi göre hangi hangisi her için ile ise kaç
    ki mi midir mu mı mıdır ne neden nedir nasıl o olan olarak olur sadece şu ve veya ya""".split()
)

# Koleksiyon filtresi isteğe bağlıdır: NULL verilirse tüm (kiracının) koleksiyonlar aranır.
_VECTOR = """
    SELECT c.id, d.path, d.title, d.url, c.section, c.content, c.score
    FROM (SELECT id, document_id, section, content, 1 - (embedding <=> %(vector)s::vector) AS score
          FROM chunks
          WHERE %(collections)s::uuid[] IS NULL OR collection_id = ANY(%(collections)s::uuid[])
          ORDER BY embedding <=> %(vector)s::vector
          LIMIT %(limit)s) c
    JOIN documents d ON d.id = c.document_id
    ORDER BY c.score DESC
"""

_LEXICAL = """
    SELECT c.id, d.path, d.title, d.url, c.section, c.content, c.score
    FROM (SELECT id, document_id, section, content, ts_rank(content_tsv, q, 1) AS score
          FROM chunks, to_tsquery('simple', %(terms)s) q
          WHERE content_tsv @@ q
            AND (%(collections)s::uuid[] IS NULL OR collection_id = ANY(%(collections)s::uuid[]))
          ORDER BY score DESC
          LIMIT %(limit)s) c
    JOIN documents d ON d.id = c.document_id
    ORDER BY c.score DESC
"""


class Retriever:
    def __init__(
        self,
        pool: AsyncConnectionPool,
        embedder: Embedder,
        candidates: int = 50,
        rrf_k: int = 60,
        reranker: "Reranker | None" = None,
        rerank_candidates: int = 20,
    ) -> None:
        self._pool = pool
        self._embedder = embedder
        self._candidates = candidates
        self._rrf_k = rrf_k
        self._reranker = reranker
        self._rerank_candidates = rerank_candidates

    async def search(
        self,
        tenant_id: UUID,
        query: str,
        k: int = 10,
        # Baseline (packages/eval/reports/baseline.md): vektör recall@5/@10'da önde, hibrit
        # recall@1/MRR'de. Cevap üretimi ilk birkaç parçayı kullanacağı için varsayılan vektör;
        # nihai seçim reranking ile birlikte ADR-0007'de.
        mode: Mode = Mode.VECTOR,
        collection_ids: Sequence[UUID] | None = None,
        rerank: bool = False,
    ) -> list[Hit]:
        """``rerank``: ilk aşamanın ilk ``rerank_candidates`` adayı çapraz kodlayıcıyla yeniden sıralanır."""
        if rerank and self._reranker is None:
            raise ValueError("reranker yapılandırılmamış")
        depth = max(k, self._rerank_candidates) if rerank else k
        vector = await self._embedder.embed_query(query) if mode != Mode.LEXICAL else None
        async with tenant_transaction(self._pool, tenant_id) as conn:
            match mode:
                case Mode.VECTOR:
                    hits = await self._vector(conn, vector, depth, collection_ids)
                case Mode.LEXICAL:
                    hits = await self._lexical(conn, query, depth, collection_ids)
                case Mode.HYBRID:
                    dense = await self._vector(conn, vector, self._candidates, collection_ids)
                    sparse = await self._lexical(conn, query, self._candidates, collection_ids)
                    hits = self._fuse([dense, sparse], depth)
        # Yeniden sıralama işlem dışında: model saniyeler sürer, bağlantı tutulmaz.
        return await rerank_hits(self._reranker, query, hits, k) if rerank else hits

    async def _vector(
        self,
        conn: AsyncConnection,
        vector: list[float] | None,
        limit: int,
        collections: Sequence[UUID] | None,
    ) -> list[Hit]:
        # Filtreli HNSW eksik sonuç döndürebilir (ADR-0003); iterative scan yeterli aday bulunana
        # kadar taramayı sürdürür. relaxed_order sırayı bozabildiği için dış sorgu yeniden sıralar.
        await conn.execute("SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true)")
        await conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(max(40, limit * 2)),))
        params = {"vector": vector, "limit": limit, "collections": _ids(collections)}
        return await self._rows(conn, _VECTOR, params)

    async def _lexical(
        self, conn: AsyncConnection, query: str, limit: int, collections: Sequence[UUID] | None
    ) -> list[Hit]:
        # Kelimeler VEYA ile bağlanır: soru cümlesindeki her kelimenin belgede geçmesi beklenmez.
        # Belirteçler yalnızca \w+ olduğundan tsquery sözdizimine kaçamaz.
        terms = [t for t in _WORD.findall(query) if t.casefold() not in _STOPWORDS and len(t) > 1]
        if not terms:
            return []
        params = {"terms": " | ".join(terms), "limit": limit, "collections": _ids(collections)}
        return await self._rows(conn, _LEXICAL, params)

    def _fuse(self, rankings: list[list[Hit]], k: int) -> list[Hit]:
        """Reciprocal Rank Fusion: skorlar farklı ölçeklerde olduğu için yalnızca sıralar birleştirilir."""
        scores: dict[UUID, float] = {}
        hits: dict[UUID, Hit] = {}
        for ranking in rankings:
            for rank, hit in enumerate(ranking, start=1):
                scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (self._rrf_k + rank)
                hits.setdefault(hit.chunk_id, hit)
        best = sorted(scores, key=scores.__getitem__, reverse=True)[:k]
        return [Hit(**{**hits[i].__dict__, "score": scores[i]}) for i in best]

    @staticmethod
    async def _rows(conn: AsyncConnection, sql: str, params: dict) -> list[Hit]:
        cursor = await conn.execute(sql, params)
        return [Hit(*row[:6], score=float(row[6])) for row in await cursor.fetchall()]


def _ids(collections: Sequence[UUID] | None) -> list[UUID] | None:
    return list(collections) if collections else None


async def rerank_hits(reranker: "Reranker", query: str, hits: Sequence[Hit], k: int) -> list[Hit]:
    from meridian_ai.reranking import rerank

    return await rerank(reranker, query, hits, k)
