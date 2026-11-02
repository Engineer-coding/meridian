"""Gerçek bir RabbitMQ'ya karşı tüketici davranışı: onay, yeniden deneme, DLQ."""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import uuid4

import aio_pika
import pytest
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractRobustConnection

from meridian_ai import topology
from meridian_ai.consumer import IndexingConsumer
from meridian_ai.events import Event
from meridian_ai.handlers import PermanentError
from meridian_ai.settings import Settings

MAX_RETRIES = 2  # conftest.settings ile aynı


@pytest.fixture(scope="session")
async def connection(settings: Settings) -> AsyncIterator[AbstractRobustConnection]:
    connection = await aio_pika.connect_robust(settings.amqp_url)
    # Çekirdek API'nin (OutboxConfiguration.messagingTopology) tanımladığı topoloji, aynı
    # argümanlarla. Tüketici bunun üstüne kendi tanımını yapabilmeli (PRECONDITION_FAILED yok).
    async with connection.channel() as channel:
        events = await channel.declare_exchange(topology.EVENTS, ExchangeType.TOPIC, durable=True)
        dlx = await channel.declare_exchange(topology.DEAD_LETTERS, ExchangeType.DIRECT, durable=True)
        indexing = await channel.declare_queue(
            "ai.indexing",
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-dead-letter-exchange": "meridian.dlx",
                "x-dead-letter-routing-key": "ai.indexing",
                "x-delivery-limit": 5,
            },
        )
        await indexing.bind(events, "source.*")
        dlq = await channel.declare_queue(
            "ai.indexing.dlq", durable=True, arguments={"x-queue-type": "quorum"}
        )
        await dlq.bind(dlx, "ai.indexing")
    yield connection
    await connection.close()


@pytest.fixture
async def channel(connection: AbstractRobustConnection) -> AsyncIterator[AbstractChannel]:
    async with connection.channel() as channel:
        for name in (topology.INDEXING_QUEUE, topology.INDEXING_DLQ):
            await (await channel.get_queue(name)).purge()
        yield channel


class Recorder:
    """Test işleyicisi: çağrıları kaydeder, sırayla verilen davranışları uygular."""

    def __init__(self, *failures: Exception) -> None:
        self.calls: list[Event] = []
        self.failures: list[tuple[Event, Exception]] = []
        self._failures = list(failures)
        self.always: Exception | None = None

    async def failed(self, event: Event, error: Exception) -> None:
        self.failures.append((event, error))

    async def handle(self, event: Event) -> None:
        self.calls.append(event)
        if self.always is not None:
            raise self.always
        if self._failures:
            raise self._failures.pop(0)


@pytest.fixture
async def run_consumer(
    settings: Settings, channel: AbstractChannel
) -> AsyncIterator[Callable[[Recorder], Any]]:
    consumers: list[IndexingConsumer] = []

    async def start(handler: Recorder) -> IndexingConsumer:
        consumer = IndexingConsumer(settings, handler)
        consumer.start()
        consumers.append(consumer)
        await eventually(lambda: consumer.ready)
        return consumer

    yield start
    for consumer in consumers:
        await consumer.stop()


def envelope(event_type: str = "source.created") -> dict[str, Any]:
    return {
        "eventId": str(uuid4()),
        "type": event_type,
        "tenantId": str(uuid4()),
        "aggregateId": str(uuid4()),
        "occurredAt": "2026-11-02T10:00:00Z",
        "data": {"type": "github", "config": {"repository": "kubernetes/website", "branch": "main"}},
    }


async def publish(channel: AbstractChannel, body: dict[str, Any], **header_overrides: Any) -> None:
    """Aktarıcının (OutboxRelay) yayımladığı biçimde bir mesaj."""
    exchange = await channel.get_exchange(topology.EVENTS)
    headers = {"tenant_id": body.get("tenantId")} | header_overrides
    await exchange.publish(
        Message(
            json.dumps(body).encode(),
            message_id=body.get("eventId"),
            type=body.get("type"),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            headers=headers,
        ),
        routing_key=str(body.get("type")),
    )


async def eventually(predicate: Callable[[], bool], timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("koşul zamanında sağlanmadı")
        await asyncio.sleep(0.05)


async def dead_letters(
    channel: AbstractChannel, expected: int, timeout: float = 15
) -> list[AbstractIncomingMessage]:
    queue = await channel.get_queue(topology.INDEXING_DLQ)
    received: list[AbstractIncomingMessage] = []
    deadline = time.monotonic() + timeout
    while len(received) < expected and time.monotonic() < deadline:
        message = await queue.get(no_ack=True, fail=False)
        if message is None:
            await asyncio.sleep(0.05)
        else:
            received.append(message)
    return received


async def queue_is_empty(channel: AbstractChannel, name: str) -> bool:
    declared = await channel.declare_queue(name, passive=True)
    return declared.declaration_result.message_count == 0


async def test_processed_message_is_acknowledged_once(run_consumer, channel: AbstractChannel) -> None:
    handler = Recorder()
    await run_consumer(handler)
    body = envelope()

    await publish(channel, body)
    await eventually(lambda: len(handler.calls) == 1)
    await asyncio.sleep(0.5)

    assert str(handler.calls[0].event_id) == body["eventId"]
    assert len(handler.calls) == 1
    assert await queue_is_empty(channel, topology.INDEXING_QUEUE)
    assert await dead_letters(channel, expected=1, timeout=0.5) == []


async def test_transient_failure_is_retried_with_backoff_then_succeeds(
    run_consumer, channel: AbstractChannel
) -> None:
    handler = Recorder(ConnectionError("embedding sağlayıcısı yanıt vermiyor"), TimeoutError())
    await run_consumer(handler)
    started = time.monotonic()

    await publish(channel, envelope())
    await eventually(lambda: len(handler.calls) == 3)

    # İki bekleme: en az 50 ms (100 ms'nin yarısı) + 100 ms (200 ms'nin yarısı).
    assert time.monotonic() - started >= 0.15
    assert len({call.event_id for call in handler.calls}) == 1
    assert await dead_letters(channel, expected=1, timeout=0.5) == []
    for attempt in range(1, MAX_RETRIES + 1):
        assert await queue_is_empty(channel, topology.retry_queue(attempt))


async def test_exhausted_retries_end_in_the_dead_letter_queue(run_consumer, channel: AbstractChannel) -> None:
    handler = Recorder()
    handler.always = ConnectionError("hep kapalı")
    await run_consumer(handler)
    body = envelope()

    await publish(channel, body)
    [dead] = await dead_letters(channel, expected=1)

    assert len(handler.calls) == MAX_RETRIES + 1
    assert [type(error) for _, error in handler.failures] == [ConnectionError]
    assert dead.message_id == body["eventId"]
    assert dead.headers[topology.RETRY_HEADER] == MAX_RETRIES
    assert dead.headers["tenant_id"] == body["tenantId"]
    assert json.loads(dead.body) == body


async def test_permanent_failure_skips_retries(run_consumer, channel: AbstractChannel) -> None:
    handler = Recorder(PermanentError("depo bulunamadı"))
    await run_consumer(handler)

    await publish(channel, envelope())
    [dead] = await dead_letters(channel, expected=1)

    assert len(handler.calls) == 1
    assert [str(error) for _, error in handler.failures] == ["depo bulunamadı"]
    assert topology.RETRY_HEADER not in (dead.headers or {})


@pytest.mark.parametrize(
    ("body", "headers"),
    [
        pytest.param({"eventId": "bozuk"}, {}, id="gecersiz-zarf"),
        pytest.param(envelope(), {"tenant_id": str(uuid4())}, id="baska-kiraci-basligi"),
    ],
)
async def test_untrustworthy_message_is_never_handled(
    run_consumer, channel: AbstractChannel, body: dict[str, Any], headers: dict[str, Any]
) -> None:
    handler = Recorder()
    await run_consumer(handler)

    body = body | {"type": "source.created"}
    await publish(channel, body, **headers)
    assert len(await dead_letters(channel, expected=1)) == 1
    assert handler.calls == []
    assert handler.failures == []
