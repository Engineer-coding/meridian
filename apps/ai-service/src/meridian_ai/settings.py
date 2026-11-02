from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ortam değişkenlerinden okunur; yerelde kökteki .env dosyası da kullanılır."""

    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str
    rabbitmq_password: str

    # Aynı anda işlenen en fazla mesaj; indeksleme ağır olduğu için düşük tutulur.
    prefetch: int = Field(default=8, ge=1)

    # Geçici hatada bekleme: base, base*factor, base*factor², ... (her biri ayrı bir kuyruk katmanı).
    retry_base_ms: int = Field(default=1_000, ge=1)
    retry_factor: int = Field(default=4, ge=1)
    max_retries: int = Field(default=4, ge=0, le=10)

    @property
    def amqp_url(self) -> str:
        user = quote(self.rabbitmq_user, safe="")
        password = quote(self.rabbitmq_password, safe="")
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"
