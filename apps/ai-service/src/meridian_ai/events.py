"""Çekirdek API'nin outbox üzerinden yayımladığı olay zarfı (ADR-0004)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

TENANT_HEADER = "tenant_id"


class InvalidMessage(Exception):
    """Mesaj okunamıyor ya da tutarsız: kaç kez denenirse denensin sonuç değişmez."""


class Event(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    event_id: UUID = Field(alias="eventId")
    type: str
    tenant_id: UUID = Field(alias="tenantId")
    aggregate_id: UUID = Field(alias="aggregateId")
    occurred_at: datetime = Field(alias="occurredAt")
    data: dict[str, Any]


def parse_event(body: bytes, message_id: str | None, headers: dict[str, Any]) -> Event:
    """Zarfı doğrular ve başlıklarla karşılaştırır.

    Başlıklar ile gövde aynı kaynaktan (aktarıcı) gelir; uyuşmazlık bozulma ya da sahte bir
    mesaj demektir. Kiracı kimliği yanlış bir mesajla başka kiracı adına iş yapılmasın diye
    böyle bir mesaj işlenmez.
    """
    try:
        event = Event.model_validate_json(body)
    except ValidationError as e:
        raise InvalidMessage(f"zarf geçersiz: {e.error_count()} hata") from e
    if message_id != str(event.event_id):
        raise InvalidMessage("message_id başlığı eventId ile uyuşmuyor")
    if headers.get(TENANT_HEADER) != str(event.tenant_id):
        raise InvalidMessage("tenant_id başlığı tenantId ile uyuşmuyor")
    return event
