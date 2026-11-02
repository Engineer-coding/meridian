"""Geçici PostgreSQL (pgvector): Compose ile aynı başlangıç scriptleri, çekirdek API'nin migration'ları.

Değerlendirme ve testler AI servisinin şema kopyasını değil, gerçek şemayı (RLS ve rol yetkileri
dahil) kullanır. Yalnızca geliştirme bağımlılıklarıyla (testcontainers) çalışır.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg

from meridian_ai.evaluation.corpus import REPO_ROOT

INIT_SCRIPTS = REPO_ROOT / "infra" / "compose" / "postgres" / "init"
MIGRATIONS = REPO_ROOT / "apps" / "api" / "src" / "main" / "resources" / "db" / "migration"

SUPERUSER = "meridian"
PASSWORDS = {
    SUPERUSER: "super_test",
    "meridian_owner": "owner_test",
    "meridian_app": "app_test",
    "meridian_relay": "relay_test",
    "meridian_ai": "ai_test",
}


@dataclass(frozen=True)
class Database:
    host: str
    port: int

    def conninfo(self, role: str) -> str:
        return f"postgresql://{role}:{PASSWORDS[role]}@{self.host}:{self.port}/meridian"


@contextmanager
def ephemeral() -> Iterator[Database]:
    from testcontainers.community.postgres import PostgresContainer

    container = (
        PostgresContainer(
            "pgvector/pgvector:pg17",
            username=SUPERUSER,
            password=PASSWORDS[SUPERUSER],
            dbname="meridian",
            driver=None,
        )
        .with_env("DB_OWNER_PASSWORD", PASSWORDS["meridian_owner"])
        .with_env("DB_APP_PASSWORD", PASSWORDS["meridian_app"])
        .with_env("DB_RELAY_PASSWORD", PASSWORDS["meridian_relay"])
        .with_env("DB_AI_PASSWORD", PASSWORDS["meridian_ai"])
        .with_volume_mapping(str(INIT_SCRIPTS), "/docker-entrypoint-initdb.d", "ro")
    )
    with container:
        database = Database(container.get_container_host_ip(), int(container.get_exposed_port(5432)))
        migrate(database)
        yield database


def migrate(database: Database) -> None:
    def version(path: Path) -> int:
        return int(re.match(r"V(\d+)__", path.name).group(1))

    with psycopg.connect(database.conninfo("meridian_owner"), autocommit=True) as conn:
        # Flyway'in geçmiş tablosu; V1 uygulama rolünün yetkisini bu tablodan geri alır.
        conn.execute("CREATE TABLE core.flyway_schema_history (installed_rank integer PRIMARY KEY)")
        for migration in sorted(MIGRATIONS.glob("V*__*.sql"), key=version):
            conn.execute(migration.read_text(encoding="utf-8"))
