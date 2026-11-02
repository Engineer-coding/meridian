# Meridian AI servisi

Kaynak olaylarını `ai.indexing` kuyruğundan alıp indeksleyen Python servisi (ADR-0001, ADR-0004,
ADR-0011). Python 3.13 ve [uv](https://docs.astral.sh/uv/) kullanır; uv gerekli Python sürümünü
kendisi indirir.

```bash
make ai-test   # ruff + pytest (entegrasyon testleri Docker ile gerçek RabbitMQ başlatır)
make ai-run    # http://localhost:8090, RabbitMQ bilgileri kökteki .env dosyasından
```

| Uç | Anlamı |
|---|---|
| `GET /health/live` | Süreç ayakta |
| `GET /health/ready` | Kuyruk dinleniyor; değilse 503 |

Ayarlar ortam değişkenleridir: `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`,
`RABBITMQ_PASSWORD`, `PREFETCH`, `RETRY_BASE_MS`, `RETRY_FACTOR`, `MAX_RETRIES`.
