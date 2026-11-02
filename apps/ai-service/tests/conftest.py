"""Paylaşılan test altyapısı: gerçek RabbitMQ ve gerçek PostgreSQL (pgvector) konteynerleri.

Veritabanı Compose ile aynı başlangıç scriptleriyle kurulur ve şema çekirdek API'nin Flyway
migration'larından uygulanır (``meridian_ai.evaluation.database``).
"""

import asyncio
import sys
from collections.abc import Iterator

import pytest
from testcontainers.community.rabbitmq import RabbitMqContainer

from meridian_ai.evaluation import database as db
from meridian_ai.settings import Settings

# psycopg'nin asenkron sürücüsü Windows'un varsayılan ProactorEventLoop'unu desteklemez.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def broker() -> Iterator[RabbitMqContainer]:
    with RabbitMqContainer("rabbitmq:4.1") as container:
        yield container


@pytest.fixture(scope="session")
def database() -> Iterator[db.Database]:
    with db.ephemeral() as database:
        yield database


@pytest.fixture(scope="session")
def settings(broker: RabbitMqContainer, database: db.Database) -> Settings:
    return Settings(
        rabbitmq_host=broker.get_container_host_ip(),
        rabbitmq_port=int(broker.get_exposed_port(5672)),
        rabbitmq_user=broker.username,
        rabbitmq_password=broker.password,
        retry_base_ms=100,
        retry_factor=2,
        max_retries=2,
        postgres_host=database.host,
        postgres_port=database.port,
        db_ai_password=db.PASSWORDS["meridian_ai"],
        _env_file=None,
    )
