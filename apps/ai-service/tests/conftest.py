"""Paylaşılan test altyapısı: gerçek RabbitMQ ve gerçek PostgreSQL (pgvector) konteynerleri.

Veritabanı Compose ile aynı başlangıç scriptleriyle kurulur ve şema çekirdek API'nin Flyway
migration'larından uygulanır: AI servisi kendi şema kopyasını tutmaz, testler gerçek şemaya
(RLS politikaları ve rol yetkileri dahil) karşı çalışır.
"""

import asyncio
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.rabbitmq import RabbitMqContainer

from meridian_ai.settings import Settings

# psycopg'nin asenkron sürücüsü Windows'un varsayılan ProactorEventLoop'unu desteklemez.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = Path(__file__).resolve().parents[3]
INIT_SCRIPTS = ROOT / "infra" / "compose" / "postgres" / "init"
MIGRATIONS = ROOT / "apps" / "api" / "src" / "main" / "resources" / "db" / "migration"

SUPERUSER_PASSWORD = "super_test"
OWNER_PASSWORD = "owner_test"
AI_PASSWORD = "ai_test"


@pytest.fixture(scope="session")
def broker() -> Iterator[RabbitMqContainer]:
    with RabbitMqContainer("rabbitmq:4.1") as container:
        yield container


@pytest.fixture(scope="session")
def database() -> Iterator[PostgresContainer]:
    container = (
        PostgresContainer(
            "pgvector/pgvector:pg17",
            username="meridian",
            password=SUPERUSER_PASSWORD,
            dbname="meridian",
            driver=None,
        )
        .with_env("DB_OWNER_PASSWORD", OWNER_PASSWORD)
        .with_env("DB_APP_PASSWORD", "app_test")
        .with_env("DB_RELAY_PASSWORD", "relay_test")
        .with_env("DB_AI_PASSWORD", AI_PASSWORD)
        .with_volume_mapping(str(INIT_SCRIPTS), "/docker-entrypoint-initdb.d", "ro")
    )
    with container:
        _migrate(container)
        yield container


def _migrate(container: PostgresContainer) -> None:
    def version(path: Path) -> int:
        return int(re.match(r"V(\d+)__", path.name).group(1))

    with psycopg.connect(conninfo(container, "meridian_owner", OWNER_PASSWORD), autocommit=True) as conn:
        # Flyway'in geçmiş tablosu; V1 uygulama rolünün yetkisini bu tablodan geri alır.
        conn.execute("CREATE TABLE core.flyway_schema_history (installed_rank integer PRIMARY KEY)")
        for migration in sorted(MIGRATIONS.glob("V*__*.sql"), key=version):
            conn.execute(migration.read_text(encoding="utf-8"))


def conninfo(container: PostgresContainer, user: str, password: str) -> str:
    host, port = container.get_container_host_ip(), container.get_exposed_port(5432)
    return f"postgresql://{user}:{password}@{host}:{port}/meridian"


@pytest.fixture(scope="session")
def settings(broker: RabbitMqContainer, database: PostgresContainer) -> Settings:
    return Settings(
        rabbitmq_host=broker.get_container_host_ip(),
        rabbitmq_port=int(broker.get_exposed_port(5672)),
        rabbitmq_user=broker.username,
        rabbitmq_password=broker.password,
        retry_base_ms=100,
        retry_factor=2,
        max_retries=2,
        postgres_host=database.get_container_host_ip(),
        postgres_port=int(database.get_exposed_port(5432)),
        db_ai_password=AI_PASSWORD,
        _env_file=None,
    )
