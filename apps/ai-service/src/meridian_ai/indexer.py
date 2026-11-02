"""Kaynak olaylarını indekse çevirir: çek → ayrıştır → parçala → göm → tek işlemde yaz (ADR-0012)."""

import hashlib
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import batched
from typing import Any
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from meridian_ai.chunking import Chunk, chunk_document
from meridian_ai.db import tenant_transaction
from meridian_ai.embedding import Embedder
from meridian_ai.events import Event
from meridian_ai.fetchers import Fetcher, RawDocument
from meridian_ai.handlers import PermanentError
from meridian_ai.parsing import parse_markdown

log = logging.getLogger(__name__)

EMBED_BATCH = 64
# Geçici hatanın ayrıntısı (ör. iç adresler) kiracıya gösterilmez.
TRANSIENT_FAILURE = "Kaynak geçici hatalar nedeniyle indekslenemedi."


@dataclass(frozen=True)
class _Source:
    type: str
    config: Mapping[str, Any]
    collection_id: UUID


@dataclass(frozen=True)
class _Document:
    id: UUID
    raw: RawDocument
    title: str
    chunks: list[Chunk]


def embedding_text(chunk: Chunk) -> str:
    """Gömülen metin: başlık yolu parçaya bağlam katar ("Pod Lifecycle > Pod phase")."""
    return f"{chunk.section}\n{chunk.content}"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Indexer:
    """Olayın etkisi, ``processed_events`` kaydıyla aynı işlemde yazılır.

    Aynı olay iki kez gelirse (en az bir kez teslimat) ikinci teslimat ya hiç iş yapmaz ya da
    yazma anında kaydı görüp vazgeçer. Uzun süren çekme ve embedding işlem dışında yapılır;
    veritabanı işlemleri kısa kalır. Kiracı her zaman olaydan gelir ve RLS ile zorlanır: başka
    bir kiracının kaynağına ait bir olay o kaynağı göremez, dolayısıyla hiçbir şey yazmaz.
    """

    def __init__(
        self, pool: AsyncConnectionPool, embedder: Embedder, fetchers: Mapping[str, Fetcher]
    ) -> None:
        self._pool = pool
        self._embedder = embedder
        self._fetchers = fetchers

    async def handle(self, event: Event) -> None:
        match event.type:
            case "source.created":
                await self._index(event)
            case "source.deleted":
                await self._delete(event)
            case _:
                raise PermanentError(f"bilinmeyen olay türü: {event.type}")

    async def failed(self, event: Event, error: Exception) -> None:
        if event.type != "source.created":
            return
        message = str(error) if isinstance(error, PermanentError) else TRANSIENT_FAILURE
        async with tenant_transaction(self._pool, event.tenant_id) as conn:
            await conn.execute(
                """UPDATE sources SET status = 'failed', last_error = %s
                   WHERE id = %s AND status IN ('pending', 'indexing')""",
                (message[:500], event.aggregate_id),
            )

    async def _index(self, event: Event) -> None:
        started = time.monotonic()
        source = await self._begin(event)
        if source is None:
            return
        fetcher = self._fetchers.get(source.type)
        if fetcher is None:
            raise PermanentError(f"'{source.type}' kaynak türü henüz desteklenmiyor")

        documents = []
        for raw in await fetcher.fetch(source.config):
            parsed = parse_markdown(raw.text, raw.path)
            chunks = chunk_document(parsed)
            if chunks:
                documents.append(_Document(uuid4(), raw, parsed.title, chunks))

        texts = [embedding_text(c) for d in documents for c in d.chunks]
        vectors: list[list[float]] = []
        for batch in batched(texts, EMBED_BATCH, strict=False):
            vectors.extend(await self._embedder.embed_passages(list(batch)))

        written = await self._commit(event, source, documents, vectors)
        if written:
            log.info(
                "kaynak indekslendi source=%s tenant=%s belge=%d parça=%d süre=%.1fs",
                event.aggregate_id,
                event.tenant_id,
                len(documents),
                len(texts),
                time.monotonic() - started,
            )

    async def _begin(self, event: Event) -> _Source | None:
        async with tenant_transaction(self._pool, event.tenant_id) as conn:
            if await self._already_processed(conn, event):
                return None
            row = await (
                await conn.execute(
                    "SELECT type, config, status, collection_id FROM sources WHERE id = %s",
                    (event.aggregate_id,),
                )
            ).fetchone()
            if row is None or row[2] == "deleting":
                # Kaynak silinmiş, silinmek üzere ya da bu kiracıya ait değil: yapılacak iş yok.
                log.info("kaynak yok ya da siliniyor, olay atlandı event=%s", event.event_id)
                await self._mark_processed(conn, event)
                return None
            await conn.execute(
                "UPDATE sources SET status = 'indexing', last_error = NULL WHERE id = %s",
                (event.aggregate_id,),
            )
            return _Source(type=row[0], config=row[1], collection_id=row[3])

    async def _commit(
        self, event: Event, source: _Source, documents: list[_Document], vectors: list[list[float]]
    ) -> bool:
        async with tenant_transaction(self._pool, event.tenant_id) as conn:
            if not await self._mark_processed(conn, event):
                log.info("olay başka bir teslimatta işlenmiş event=%s", event.event_id)
                return False
            row = await (
                await conn.execute(
                    "SELECT status FROM sources WHERE id = %s FOR UPDATE", (event.aggregate_id,)
                )
            ).fetchone()
            if row is None or row[0] == "deleting":
                return False

            # Yeniden indeksleme eski belgelerin yerini alır; parçalar zincirleme silinir.
            await conn.execute("DELETE FROM documents WHERE source_id = %s", (event.aggregate_id,))
            async with conn.cursor() as cur:
                await cur.executemany(
                    """INSERT INTO documents (id, tenant_id, collection_id, source_id, path, title, url,
                                              version, content_hash, chunk_count)
                       VALUES (%s, current_tenant_id(), %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        (
                            d.id,
                            source.collection_id,
                            event.aggregate_id,
                            d.raw.path,
                            d.title,
                            d.raw.url,
                            d.raw.version,
                            _sha256(d.raw.text),
                            len(d.chunks),
                        )
                        for d in documents
                    ],
                )
                rows = [(d, c) for d in documents for c in d.chunks]
                await cur.executemany(
                    """INSERT INTO chunks (id, tenant_id, collection_id, document_id, ordinal, section,
                                           content, embedding, content_hash)
                       VALUES (%s, current_tenant_id(), %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        (
                            uuid4(),
                            source.collection_id,
                            d.id,
                            c.ordinal,
                            c.section,
                            c.content,
                            v,
                            _sha256(c.content),
                        )
                        for (d, c), v in zip(rows, vectors, strict=True)
                    ],
                )
            await conn.execute(
                """UPDATE sources SET status = 'ready', document_count = %s, last_indexed_at = now(),
                                      last_error = NULL
                   WHERE id = %s""",
                (len(documents), event.aggregate_id),
            )
            return True

    async def _delete(self, event: Event) -> None:
        async with tenant_transaction(self._pool, event.tenant_id) as conn:
            if not await self._mark_processed(conn, event):
                return
            # Belgeler ve parçalar yabancı anahtarla zincirleme silinir: indeks, kaynağıyla aynı anda gider.
            await conn.execute(
                "DELETE FROM sources WHERE id = %s AND status = 'deleting'", (event.aggregate_id,)
            )

    @staticmethod
    async def _already_processed(conn: AsyncConnection, event: Event) -> bool:
        cursor = await conn.execute("SELECT 1 FROM processed_events WHERE event_id = %s", (event.event_id,))
        return await cursor.fetchone() is not None

    @staticmethod
    async def _mark_processed(conn: AsyncConnection, event: Event) -> bool:
        cursor = await conn.execute(
            """INSERT INTO processed_events (event_id, tenant_id) VALUES (%s, current_tenant_id())
               ON CONFLICT DO NOTHING RETURNING event_id""",
            (event.event_id,),
        )
        return await cursor.fetchone() is not None
