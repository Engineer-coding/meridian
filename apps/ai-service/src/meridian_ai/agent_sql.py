"""Ajanın salt-okunur SQL aracı: model metni, çalıştırılmadan önce izin listesiyle denetlenir (ADR-0015).

RLS kiracıyı ``app.tenant_id`` ayarından okur. Modelin yazdığı ``SELECT set_config(...)`` bu ayarı
değiştirip başka kiracının verisini açabilirdi; READ ONLY işlem bunu engellemez. Bu yüzden denetim metin
filtresi değil, ayrıştırılmış ağaç üzerinde reddetme varsayılanıdır: yalnızca tek SELECT, yalnızca iki
görünüm, yalnızca listelenen fonksiyonlar. Çalıştırılan metin modelinki değil, ağaçtan yeniden üretilendir;
böylece ayrıştırıcının anlamadığı bir hile (yorum, kaçış) veritabanına ulaşmaz.
"""

import json
from typing import Any
from uuid import UUID

import sqlglot
from psycopg import Error as PsycopgError
from psycopg_pool import AsyncConnectionPool
from sqlglot import exp
from sqlglot.errors import SqlglotError

from meridian_ai.db import tenant_transaction

# security_invoker görünümleri: RLS çağıran rolle uygulanır; config gibi sütunlar görünmez.
ALLOWED_TABLES = frozenset({"agent_sources", "agent_documents"})
ALLOWED_FUNCTIONS: tuple[type[exp.Expression], ...] = (
    exp.Count,
    exp.Sum,
    exp.Avg,
    exp.Min,
    exp.Max,
    exp.Lower,
    exp.Upper,
    exp.Length,
    exp.Coalesce,
    exp.And,
    exp.Or,
)
FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.With,
    exp.Into,
    exp.Lock,
    exp.Lateral,
    exp.Unnest,
    exp.Cast,
    exp.Placeholder,
    exp.Parameter,
    exp.Command,
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
)

MAX_SQL_CHARS = 1000
MAX_ROWS = 20
MAX_RESULT_CHARS = 1500
TIMEOUT_MS = 2000

SCHEMA_HELP = (
    "agent_sources(name, type, status, document_count, last_indexed_at, created_at); "
    "agent_documents(path, title, chunk_count, indexed_at)"
)


class SqlRejected(Exception):
    """Sorgu izin listesine uymuyor; mesajı modele gözlem olarak döner."""


def validate_sql(sql: str) -> str:
    """Geçerliyse çalıştırılacak, ağaçtan yeniden üretilmiş sorguyu döndürür."""
    if len(sql) > MAX_SQL_CHARS:
        raise SqlRejected(f"sorgu en fazla {MAX_SQL_CHARS} karakter olabilir")
    try:
        statements = sqlglot.parse(sql, dialect="postgres")
    except SqlglotError as e:
        raise SqlRejected("sorgu ayrıştırılamadı") from e
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise SqlRejected("yalnızca tek bir SELECT çalıştırılabilir")
    tree = statements[0]

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlRejected(f"izin verilmeyen ifade: {type(node).__name__}")
        if isinstance(node, exp.Table):
            # Şema önekli ad ya da fonksiyon gibi kullanılan tablo da reddedilir.
            if node.db or node.catalog or not isinstance(node.this, exp.Identifier):
                raise SqlRejected(f"yalnızca şu görünümler sorgulanabilir: {SCHEMA_HELP}")
            if node.name not in ALLOWED_TABLES:
                raise SqlRejected(f"yalnızca şu görünümler sorgulanabilir: {SCHEMA_HELP}")
        if isinstance(node, exp.Func) and not isinstance(node, ALLOWED_FUNCTIONS):
            raise SqlRejected(f"izin verilmeyen fonksiyon: {node.sql(dialect='postgres')[:40]}")
    if not tree.args.get("from_") and not tree.args.get("from"):
        raise SqlRejected("FROM ile bir görünüm sorgulanmalı")
    return tree.sql(dialect="postgres", comments=False)


async def run_readonly(pool: AsyncConnectionPool, tenant_id: UUID, sql: str) -> str:
    """Denetlenen sorguyu kiracı bağlamında, salt-okunur ve süre sınırlı çalıştırır."""
    query = validate_sql(sql)
    try:
        async with tenant_transaction(pool, tenant_id) as conn:
            await conn.execute("SET LOCAL transaction_read_only = on")
            await conn.execute(f"SET LOCAL statement_timeout = {TIMEOUT_MS}")
            cursor = await conn.execute(f"SELECT * FROM ({query}) AS result LIMIT {MAX_ROWS}")  # noqa: S608 - ağaç denetiminden geçti
            names = [column.name for column in cursor.description or []]
            rows: list[dict[str, Any]] = [
                dict(zip(names, row, strict=True)) for row in await cursor.fetchall()
            ]
    except PsycopgError as e:
        # Ayrıntı modele gitmez: veritabanı iletisi şema bilgisi taşıyabilir.
        raise SqlRejected("sorgu çalıştırılamadı; sütun adlarını kontrol edin: " + SCHEMA_HELP) from e
    return json.dumps(rows, ensure_ascii=False, default=str)[:MAX_RESULT_CHARS]
