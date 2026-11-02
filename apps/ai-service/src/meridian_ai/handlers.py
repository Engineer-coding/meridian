"""Olay işleyicileri. Asıl indeksleme (ayrıştırma, parçalama, embedding) Adım 16'da gelir."""

import logging
from collections.abc import Awaitable, Callable

from meridian_ai.events import Event

log = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]


class PermanentError(Exception):
    """Yeniden denemek sonucu değiştirmez (ör. erişilemeyen depo, desteklenmeyen tür): doğrudan DLQ.

    Bunun dışındaki her hata geçici sayılır ve beklemeli olarak yeniden denenir.
    """


async def handle_event(event: Event) -> None:
    match event.type:
        case "source.created" | "source.deleted":
            log.info(
                "olay alındı type=%s tenant=%s source=%s event=%s",
                event.type,
                event.tenant_id,
                event.aggregate_id,
                event.event_id,
            )
        case _:
            raise PermanentError(f"bilinmeyen olay türü: {event.type}")
