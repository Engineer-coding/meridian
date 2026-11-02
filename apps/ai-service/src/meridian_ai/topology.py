"""RabbitMQ topolojisi (ADR-0004, ADR-0011).

Ana exchange ve kuyruklar çekirdek API'de de tanımlıdır (``OutboxConfiguration``). RabbitMQ
var olan bir kuyruğu farklı argümanlarla yeniden tanımlamayı reddeder (PRECONDITION_FAILED);
bu yüzden buradaki argümanlar Java tarafıyla birebir aynı olmalıdır. Hangi servis önce
başlarsa başlasın topoloji aynı olur.
"""

from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractQueue

EVENTS = "meridian.events"
DEAD_LETTERS = "meridian.dlx"
INDEXING_QUEUE = "ai.indexing"
INDEXING_DLQ = "ai.indexing.dlq"

# Kaç kez yeniden denendiği; ilk teslimatta yoktur.
RETRY_HEADER = "x-retry-count"

INDEXING_ARGUMENTS = {
    "x-queue-type": "quorum",
    "x-dead-letter-exchange": DEAD_LETTERS,
    "x-dead-letter-routing-key": INDEXING_QUEUE,
    # Tüketici mesajı onaylamadan çöküp duruyorsa (ör. bellek taşması) beşinci teslimattan sonra DLQ.
    "x-delivery-limit": 5,
}


def retry_queue(attempt: int) -> str:
    return f"{INDEXING_QUEUE}.retry.{attempt}"


async def declare(channel: AbstractChannel, max_retries: int) -> AbstractQueue:
    """Topolojiyi tanımlar ve tüketilecek ana kuyruğu döndürür."""
    events = await channel.declare_exchange(EVENTS, ExchangeType.TOPIC, durable=True)
    dead_letters = await channel.declare_exchange(DEAD_LETTERS, ExchangeType.DIRECT, durable=True)

    indexing = await channel.declare_queue(INDEXING_QUEUE, durable=True, arguments=INDEXING_ARGUMENTS)
    await indexing.bind(events, "source.*")
    dlq = await channel.declare_queue(INDEXING_DLQ, durable=True, arguments={"x-queue-type": "quorum"})
    await dlq.bind(dead_letters, INDEXING_QUEUE)

    # Bekleme kuyrukları: tüketicisi yoktur. Mesaj süresi (expiration) dolunca varsayılan
    # exchange üzerinden ana kuyruğa geri döner. Her deneme kendi kuyruğundadır, çünkü RabbitMQ
    # süresi dolan mesajı yalnızca kuyruğun başından çıkarır: tek kuyrukta 64 sn bekleyen bir
    # mesaj arkasındaki 1 sn'lik mesajı da bekletirdi. Aynı katmandaki süreler en fazla jitter
    # kadar farklıdır. "at-least-once" geri dönüşü, ana kuyruğa aktarım onaylanana kadar
    # mesajı bekleme kuyruğunda tutar.
    for attempt in range(1, max_retries + 1):
        await channel.declare_queue(
            retry_queue(attempt),
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": INDEXING_QUEUE,
                "x-dead-letter-strategy": "at-least-once",
                "x-overflow": "reject-publish",
            },
        )
    return indexing
