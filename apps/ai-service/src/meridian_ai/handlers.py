"""Olay işleyicisi sözleşmesi ve hata sınıflandırması."""

from typing import Protocol

from meridian_ai.events import Event


class PermanentError(Exception):
    """Yeniden denemek sonucu değiştirmez (ör. erişilemeyen depo, desteklenmeyen tür): doğrudan DLQ.

    Mesajı kiracıya (kaynağın ``last_error`` alanı) gösterilir; iç ayrıntı içermemelidir.
    Bunun dışındaki her hata geçici sayılır ve beklemeli olarak yeniden denenir.
    """


class Handler(Protocol):
    async def handle(self, event: Event) -> None:
        """Olayı işler. Aynı olay birden çok kez gelebilir; etkisi bir kez oluşmalıdır."""

    async def failed(self, event: Event, error: Exception) -> None:
        """Olay DLQ'ya gönderilmeden hemen önce çağrılır: sonucu kalıcı olarak kaydetmek için."""
