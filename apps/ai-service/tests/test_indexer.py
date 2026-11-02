"""İndeksleme hattı gerçek şemaya karşı: yazım, idempotency, kiracı izolasyonu ve rol sınırları."""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import aio_pika
import psycopg
import pytest
from aio_pika import DeliveryMode, Message
from fastapi.testclient import TestClient
from psycopg_pool import AsyncConnectionPool

from meridian_ai import topology
from meridian_ai.app import create_app
from meridian_ai.consumer import IndexingConsumer
from meridian_ai.db import create_pool, tenant_transaction
from meridian_ai.embedding import HashEmbedder
from meridian_ai.evaluation.database import Database
from meridian_ai.events import Event
from meridian_ai.fetchers import RawDocument
from meridian_ai.handlers import PermanentError
from meridian_ai.indexer import TRANSIENT_FAILURE, Indexer
from meridian_ai.settings import Settings

POD_DOC = """---
title: Pods
---
Pods are the smallest deployable units of computing that you can create and manage in Kubernetes.

## Pod lifecycle

A Pod moves through phases: Pending, Running, Succeeded, Failed.
"""

KVKK_DOC = """# Kişisel Verilerin Korunması Kanunu

## Madde 13

Veri sorumlusu başvuruyu en geç otuz gün içinde ücretsiz olarak sonuçlandırır.
"""


class FakeFetcher:
    def __init__(self, *documents: tuple[str, str], delay: float = 0.0) -> None:
        self.documents = list(documents)
        self.delay = delay
        self.calls = 0

    async def fetch(self, config: Mapping[str, Any]) -> list[RawDocument]:
        self.calls += 1
        await asyncio.sleep(self.delay)
        return [
            RawDocument(path, f"https://example.test/{path}", "v1", text) for path, text in self.documents
        ]


class Seed:
    """Testin ihtiyaç duyduğu kiracı, koleksiyon ve kaynakları süper kullanıcıyla (RLS dışında) kurar."""

    def __init__(self, database: Database) -> None:
        self._conninfo = database.conninfo("meridian")

    def query(self, sql: str, *params: Any) -> list[tuple]:
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall() if cursor.description else []

    def tenant(self) -> UUID:
        tenant = uuid4()
        self.query("INSERT INTO core.tenants (id, slug, name) VALUES (%s, %s, 'Test')", tenant, f"t-{tenant}")
        return tenant

    def source(self, tenant: UUID, type_: str = "github", status: str = "pending") -> UUID:
        collection, source = uuid4(), uuid4()
        self.query(
            "INSERT INTO core.collections (id, tenant_id, name) VALUES (%s, %s, %s)",
            collection,
            tenant,
            f"c-{collection}",
        )
        self.query(
            """INSERT INTO core.sources (id, tenant_id, collection_id, name, type, config, status)
               VALUES (%s, %s, %s, 'kaynak', %s, %s, %s)""",
            source,
            tenant,
            collection,
            type_,
            json.dumps({"type": type_, "repository": "org/repo", "branch": "main", "paths": []}),
            status,
        )
        return source

    def status(self, source: UUID) -> tuple | None:
        rows = self.query("SELECT status, document_count, last_error FROM core.sources WHERE id = %s", source)
        return rows[0] if rows else None

    def count(self, table: str, source: UUID) -> int:
        sql = {
            "documents": "SELECT count(*) FROM core.documents WHERE source_id = %s",
            "chunks": "SELECT count(*) FROM core.chunks c JOIN core.documents d ON d.id = c.document_id"
            " WHERE d.source_id = %s",
        }[table]
        return self.query(sql, source)[0][0]


def event(tenant: UUID, source: UUID, type_: str = "source.created") -> Event:
    return Event(
        event_id=uuid4(),
        type=type_,
        tenant_id=tenant,
        aggregate_id=source,
        occurred_at=datetime.now(UTC),
        data={},
    )


@pytest.fixture(scope="session")
def seed(database: Database) -> Seed:
    return Seed(database)


@pytest.fixture(scope="session")
async def pool(settings: Settings) -> AsyncIterator[AsyncConnectionPool]:
    pool = create_pool(settings.database_conninfo)
    await pool.open(wait=True)
    yield pool
    await pool.close()


@pytest.fixture
def fetcher() -> FakeFetcher:
    return FakeFetcher(("docs/pods.md", POD_DOC), ("kvkk/6698.md", KVKK_DOC))


@pytest.fixture
def indexer(pool: AsyncConnectionPool, fetcher: FakeFetcher) -> Indexer:
    return Indexer(pool, HashEmbedder(), {"github": fetcher})


async def test_source_is_indexed_into_documents_and_chunks(indexer: Indexer, seed: Seed, pool) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant)

    await indexer.handle(event(tenant, source))

    assert seed.status(source) == ("ready", 2, None)
    rows = seed.query(
        """SELECT d.path, d.title, c.section, c.tenant_id = d.tenant_id, c.collection_id = d.collection_id
           FROM core.chunks c JOIN core.documents d ON d.id = c.document_id
           WHERE d.source_id = %s ORDER BY d.path, c.ordinal""",
        source,
    )
    assert [r[:3] for r in rows] == [
        ("docs/pods.md", "Pods", "Pods"),
        ("docs/pods.md", "Pods", "Pods > Pod lifecycle"),
        (
            "kvkk/6698.md",
            "Kişisel Verilerin Korunması Kanunu",
            "Kişisel Verilerin Korunması Kanunu > Madde 13",
        ),
    ]
    assert all(r[3] and r[4] for r in rows)


async def test_index_is_searchable_by_vector_and_full_text(indexer: Indexer, seed: Seed, pool) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant)
    await indexer.handle(event(tenant, source))
    query = await HashEmbedder().embed_query("başvuru otuz gün içinde sonuçlandırır")

    async with tenant_transaction(pool, tenant) as conn:
        nearest = await (
            await conn.execute(
                "SELECT section FROM chunks ORDER BY embedding <=> %s::vector LIMIT 1", (query,)
            )
        ).fetchone()
        lexical = await (
            await conn.execute(
                "SELECT section FROM chunks WHERE content_tsv @@ plainto_tsquery('simple', %s)", ("phases",)
            )
        ).fetchall()

    assert nearest[0].endswith("Madde 13")
    assert lexical == [("Pods > Pod lifecycle",)]


async def test_redelivered_event_has_a_single_effect(
    indexer: Indexer, fetcher: FakeFetcher, seed: Seed
) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant)
    created = event(tenant, source)

    await indexer.handle(created)
    await indexer.handle(created)

    assert fetcher.calls == 1
    assert seed.count("documents", source) == 2


async def test_concurrent_duplicates_are_resolved_at_write_time(pool, seed: Seed) -> None:
    slow = FakeFetcher(("docs/pods.md", POD_DOC), delay=0.3)
    indexer = Indexer(pool, HashEmbedder(), {"github": slow})
    tenant = seed.tenant()
    source = seed.source(tenant)
    created = event(tenant, source)

    await asyncio.gather(indexer.handle(created), indexer.handle(created))

    assert slow.calls == 2
    assert seed.count("documents", source) == 1
    assert seed.count("chunks", source) == 2


async def test_reindex_replaces_previous_documents(
    indexer: Indexer, fetcher: FakeFetcher, seed: Seed
) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant)
    await indexer.handle(event(tenant, source))

    fetcher.documents = [("docs/pods.md", POD_DOC)]
    await indexer.handle(event(tenant, source))

    assert seed.status(source) == ("ready", 1, None)
    assert seed.count("chunks", source) == 2


async def test_event_naming_another_tenants_source_changes_nothing(indexer: Indexer, seed: Seed) -> None:
    owner, intruder = seed.tenant(), seed.tenant()
    source = seed.source(owner)

    await indexer.handle(event(intruder, source))

    assert seed.status(source) == ("pending", 0, None)
    assert seed.count("documents", source) == 0


async def test_deleted_source_takes_its_index_with_it(indexer: Indexer, seed: Seed) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant)
    await indexer.handle(event(tenant, source))
    seed.query("UPDATE core.sources SET status = 'deleting' WHERE id = %s", source)

    await indexer.handle(event(tenant, source, "source.deleted"))

    assert seed.status(source) is None
    assert seed.query("SELECT count(*) FROM core.documents WHERE source_id = %s", source) == [(0,)]


async def test_creation_event_for_a_deleting_source_is_skipped(
    indexer: Indexer, fetcher: FakeFetcher, seed: Seed
) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant, status="deleting")

    await indexer.handle(event(tenant, source))

    assert fetcher.calls == 0
    assert seed.status(source) == ("deleting", 0, None)


async def test_unsupported_source_type_fails_permanently_with_a_visible_reason(
    indexer: Indexer, seed: Seed
) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant, type_="web")
    created = event(tenant, source)

    with pytest.raises(PermanentError) as raised:
        await indexer.handle(created)
    await indexer.failed(created, raised.value)

    assert seed.status(source) == ("failed", 0, "'web' kaynak türü henüz desteklenmiyor")


async def test_transient_failure_details_are_not_shown_to_the_tenant(indexer: Indexer, seed: Seed) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant)

    await indexer.failed(event(tenant, source), ConnectionError("10.0.3.7:5432 bağlantı reddedildi"))

    assert seed.status(source) == ("failed", 0, TRANSIENT_FAILURE)


async def test_unknown_event_type_is_permanent(indexer: Indexer, seed: Seed) -> None:
    with pytest.raises(PermanentError, match="bilinmeyen olay türü"):
        await indexer.handle(event(seed.tenant(), uuid4(), "source.renamed"))


def as_ai(database: Database, *statements: str) -> list[tuple]:
    with psycopg.connect(database.conninfo("meridian_ai")) as conn:
        cursor = None
        for statement in statements:
            cursor = conn.execute(statement)
        return cursor.fetchall() if cursor and cursor.description else []


@pytest.mark.parametrize(
    "table", ["tenants", "users", "memberships", "collections", "outbox", "idempotency_keys"]
)
def test_ai_role_cannot_read_identity_or_core_tables(database: Database, table: str) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_ai(database, f"SELECT count(*) FROM core.{table}")


def test_ai_role_cannot_change_what_a_source_is(database: Database, seed: Seed) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_ai(
            database,
            f"SELECT set_config('app.tenant_id', '{tenant}', false)",
            f"UPDATE core.sources SET config = '{{}}' WHERE id = '{source}'",
        )


async def test_ai_role_cannot_write_or_see_another_tenants_index(
    indexer: Indexer, database: Database, seed: Seed
) -> None:
    owner, other = seed.tenant(), seed.tenant()
    source = seed.source(owner)
    await indexer.handle(event(owner, source))
    [(document, collection)] = seed.query(
        "SELECT id, collection_id FROM core.documents WHERE source_id = %s LIMIT 1", source
    )

    assert as_ai(database, "SELECT count(*) FROM core.chunks") == [(0,)], "bağlamsız sorgu satır görmez"
    assert as_ai(
        database,
        f"SELECT set_config('app.tenant_id', '{other}', false)",
        f"SELECT count(*) FROM core.chunks WHERE document_id = '{document}'",
    ) == [(0,)]
    zero = "[" + ",".join(["0.1"] * 1024) + "]"
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_ai(
            database,
            f"SELECT set_config('app.tenant_id', '{other}', false)",
            f"""INSERT INTO core.chunks (id, tenant_id, collection_id, document_id, ordinal, section, content,
                                         embedding, content_hash)
                VALUES ('{uuid4()}', '{owner}', '{collection}', '{document}',
                        99, 's', 'sahte', '{zero}', 'h')""",
        )


async def test_event_from_the_queue_ends_with_a_ready_source(settings: Settings, pool, seed: Seed) -> None:
    tenant = seed.tenant()
    source = seed.source(tenant)
    consumer = IndexingConsumer(
        settings, Indexer(pool, HashEmbedder(), {"github": FakeFetcher(("a.md", POD_DOC))})
    )
    consumer.start()
    try:
        deadline = time.monotonic() + 15
        while not consumer.ready:
            assert time.monotonic() < deadline
            await asyncio.sleep(0.05)
        body = {
            "eventId": str(uuid4()),
            "type": "source.created",
            "tenantId": str(tenant),
            "aggregateId": str(source),
            "occurredAt": datetime.now(UTC).isoformat(),
            "data": {},
        }
        connection = await aio_pika.connect(settings.amqp_url)
        async with connection, connection.channel() as channel:
            exchange = await channel.get_exchange(topology.EVENTS)
            await exchange.publish(
                Message(
                    json.dumps(body).encode(),
                    message_id=body["eventId"],
                    type="source.created",
                    content_type="application/json",
                    delivery_mode=DeliveryMode.PERSISTENT,
                    headers={"tenant_id": str(tenant)},
                ),
                routing_key="source.created",
            )
        while (seed.status(source) or ("?",))[0] != "ready":
            assert time.monotonic() < deadline + 15, seed.status(source)
            await asyncio.sleep(0.1)
    finally:
        await consumer.stop()


def test_ready_when_broker_and_database_are_reachable(settings: Settings) -> None:
    with TestClient(create_app(settings, embedder=HashEmbedder())) as client:
        deadline = time.monotonic() + 15
        while client.get("/health/ready").status_code != 200:
            assert time.monotonic() < deadline, "servis hazır olmadı"
            time.sleep(0.1)
