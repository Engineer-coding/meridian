from pathlib import Path
from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ortam değişkenlerinden okunur; yerelde kökteki .env dosyası da kullanılır."""

    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    # Compose portları yalnızca 127.0.0.1'e açar; "localhost" Windows'ta önce ::1'i dener ve
    # her bağlantı saniyelerce gecikir.
    rabbitmq_host: str = "127.0.0.1"
    rabbitmq_port: int = 5672
    rabbitmq_user: str
    rabbitmq_password: str

    # Aynı anda işlenen en fazla mesaj; indeksleme ağır olduğu için düşük tutulur.
    prefetch: int = Field(default=2, ge=1)

    # Geçici hatada bekleme: base, base*factor, base*factor², ... (her biri ayrı bir kuyruk katmanı).
    retry_base_ms: int = Field(default=1_000, ge=1)
    retry_factor: int = Field(default=4, ge=1)
    max_retries: int = Field(default=4, ge=0, le=10)

    # Veritabanı: AI servisi kendi rolüyle (meridian_ai) bağlanır; RLS her sorguda geçerlidir.
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "meridian"
    db_ai_user: str = "meridian_ai"
    db_ai_password: str = ""

    # Embedding (ADR-0012). Model ilk kullanımda indirilir ve önbellekte tutulur.
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_cache_dir: Path = Path.home() / ".cache" / "meridian" / "fastembed"
    embedding_batch_size: int = Field(default=16, ge=1)

    # GitHub: token olmadan saatte 60 API isteği; dosya içerikleri bu sınıra dahil değildir.
    github_token: SecretStr | None = None
    max_files_per_source: int = Field(default=2_000, ge=1)

    @property
    def amqp_url(self) -> str:
        user = quote(self.rabbitmq_user, safe="")
        password = quote(self.rabbitmq_password, safe="")
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"

    @property
    def database_conninfo(self) -> str:
        user = quote(self.db_ai_user, safe="")
        password = quote(self.db_ai_password, safe="")
        return f"postgresql://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
