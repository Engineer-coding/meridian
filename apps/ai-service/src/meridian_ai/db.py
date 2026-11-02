"""Veritabanı erişimi: her işlem kiracı bağlamıyla açılır, RLS geri kalanını yapar (ADR-0002)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool


async def _configure(connection: AsyncConnection) -> None:
    await register_vector_async(connection)
    # register_vector_async bir sorgu çalıştırır; havuza boşta ("idle") dönmesi gerekir.
    await connection.commit()


def create_pool(conninfo: str) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        conninfo,
        min_size=1,
        max_size=4,
        open=False,
        configure=_configure,
        name="meridian-ai",
    )


@asynccontextmanager
async def tenant_transaction(pool: AsyncConnectionPool, tenant_id: UUID) -> AsyncIterator[AsyncConnection]:
    """Kiracı bağlamı ``set_config(..., true)`` ile yalnızca bu işleme atanır; bağlantı havuza
    döndüğünde bağlam da biter. Bağlam olmadan açılan bir sorgu hiçbir satır görmez."""
    async with pool.connection() as connection, connection.transaction():
        await connection.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
        yield connection
