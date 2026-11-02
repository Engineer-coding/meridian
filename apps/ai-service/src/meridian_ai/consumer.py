"""``ai.indexing`` kuyruğunun tüketicisi: onay, yeniden deneme ve DLQ kararları (ADR-0011)."""

import asyncio
import logging
from typing import Any

import aio_pika
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractRobustConnection
from aio_pika.connection import make_url

from meridian_ai import topology
from meridian_ai.events import Event, InvalidMessage, parse_event
from meridian_ai.handlers import Handler, PermanentError
from meridian_ai.retry import backoff
from meridian_ai.settings import Settings

log = logging.getLogger(__name__)


class IndexingConsumer:
    """Her mesaj için tek bir son durum vardır:

    - işlendi → ``ack``
    - okunamıyor ya da kalıcı hata → ``reject`` → DLX → ``ai.indexing.dlq``
    - geçici hata → ``ai.indexing.retry.N`` kuyruğuna kopyası yazılır, sonra ``ack``;
      deneme hakkı bittiyse ``reject`` → DLQ

    Kopya yazılıp onaylanmadan asıl mesaj onaylanmaz: arada çökülürse mesaj ikinci kez
    işlenebilir ama kaybolmaz. Teslimat en az bir kezdir; işleyiciler idempotent olmalıdır.
    """

    def __init__(self, settings: Settings, handler: Handler) -> None:
        self._settings = settings
        self._handler = handler
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._consuming = False
        self._task: asyncio.Task[None] | None = None

    @property
    def ready(self) -> bool:
        return self._consuming and self._connection is not None and self._connection.connected.is_set()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="indexing-consumer")

    async def stop(self) -> None:
        self._consuming = False
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._connection is not None:
            # Onaylanmamış mesajlar broker'a geri döner ve sonra yeniden teslim edilir.
            await self._connection.close()

    async def _run(self) -> None:
        # İlk bağlantı başarısız olursa (broker henüz açılmadı, topoloji uyuşmuyor) servis
        # ayakta kalır ama hazır değildir; sonraki kopmaları connect_robust kendisi onarır.
        attempt = 0
        while True:
            try:
                await self._connect()
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                attempt += 1
                delay = backoff(min(attempt, 6), base_ms=500, factor=2)
                log.exception(
                    "RabbitMQ'ya bağlanılamadı; %.1f sn sonra tekrar denenecek", delay.total_seconds()
                )
                if self._connection is not None:
                    await self._connection.close()
                    self._connection = None
                await asyncio.sleep(delay.total_seconds())

    async def _connect(self) -> None:
        # connect_robust yerine nesneyi önce kurup saklıyoruz: ilk bağlantı başarısız olsa da
        # arka plandaki yeniden bağlanma görevi çalışmaya devam eder ve ancak close() ile durur.
        self._connection = aio_pika.RobustConnection(make_url(self._settings.amqp_url))
        await self._connection.connect()
        self._channel = await self._connection.channel(publisher_confirms=True)
        await self._channel.set_qos(prefetch_count=self._settings.prefetch)
        queue = await topology.declare(self._channel, self._settings.max_retries)
        await queue.consume(self._on_message)
        self._consuming = True
        log.info("ai.indexing tüketiliyor (prefetch=%d)", self._settings.prefetch)

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        headers = dict(message.headers or {})
        try:
            event = parse_event(message.body, message.message_id, headers)
        except InvalidMessage as e:
            log.warning("okunamayan mesaj, DLQ'ya gönderiliyor message_id=%s: %s", message.message_id, e)
            await message.reject(requeue=False)
            return
        try:
            await self._handler.handle(event)
        except PermanentError as e:
            log.warning("kalıcı hata, DLQ'ya gönderiliyor message_id=%s: %s", message.message_id, e)
            await self._dead_letter(message, event, e)
        except Exception as e:
            await self._retry_later(message, event, headers, e)
        else:
            await message.ack()

    async def _dead_letter(self, message: AbstractIncomingMessage, event: Event, error: Exception) -> None:
        try:
            await self._handler.failed(event, error)
        except Exception:
            # Sonuç kaydedilemedi (ör. veritabanı kapalı); mesaj yine de DLQ'da incelenebilir.
            log.exception("başarısızlık kaydedilemedi message_id=%s", message.message_id)
        await message.reject(requeue=False)

    async def _retry_later(
        self, message: AbstractIncomingMessage, event: Event, headers: dict[str, Any], error: Exception
    ) -> None:
        attempt = int(headers.get(topology.RETRY_HEADER, 0)) + 1
        if attempt > self._settings.max_retries:
            log.error(
                "deneme hakkı bitti (%d), DLQ'ya gönderiliyor message_id=%s: %r",
                self._settings.max_retries,
                message.message_id,
                error,
            )
            await self._dead_letter(message, event, error)
            return

        delay = backoff(attempt, self._settings.retry_base_ms, self._settings.retry_factor)
        retry = Message(
            message.body,
            headers={**headers, topology.RETRY_HEADER: attempt},
            message_id=message.message_id,
            type=message.type,
            content_type=message.content_type,
            delivery_mode=DeliveryMode.PERSISTENT,
            expiration=delay,
        )
        assert self._channel is not None  # noqa: S101 - mesaj ancak kanal açıkken gelir
        try:
            await self._channel.default_exchange.publish(retry, routing_key=topology.retry_queue(attempt))
        except Exception:
            # Kopya yazılamadı: asıl mesaj kuyruğa döner. Sonsuz döngüyü teslim sınırı keser.
            log.exception("yeniden deneme kuyruğuna yazılamadı message_id=%s", message.message_id)
            await message.nack(requeue=True)
            return
        log.warning(
            "geçici hata, %d. deneme %.1f sn sonra message_id=%s: %r",
            attempt,
            delay.total_seconds(),
            message.message_id,
            error,
        )
        await message.ack()
