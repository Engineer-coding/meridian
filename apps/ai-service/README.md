# Meridian AI servisi

Kaynak olaylarını `ai.indexing` kuyruğundan alıp indeksleyen Python servisi (ADR-0001, ADR-0004,
ADR-0011, ADR-0012). Python 3.13 ve [uv](https://docs.astral.sh/uv/) kullanır; uv gerekli Python
sürümünü kendisi indirir.

```bash
make ai-test   # ruff + pytest (entegrasyon testleri Docker ile gerçek RabbitMQ ve PostgreSQL başlatır)
make ai-run    # http://localhost:8090; RabbitMQ ve veritabanı bilgileri kökteki .env dosyasından
```

Akış: `source.created` → GitHub'dan dosyalar → Markdown bölümleri → ~1200 karakterlik parçalar →
`multilingual-e5-large` vektörleri → `documents` / `chunks` tabloları (tek işlem, kiracı RLS'i altında).

Cevap (ADR-0008): soru → 3 kaynak → model cevabı veren cümleyi alıntılar → kod alıntıyı kaynakta
doğrular → doğrulanırsa `[n]` atıflı cevap, doğrulanamazsa "bilmiyorum". Ollama'nın çalışıyor ve
modelin indirilmiş olması gerekir (`ollama pull llama3.2:3b`).

İlk indekslemede embedding modeli (~2,2 GB) `~/.cache/meridian/fastembed` altına indirilir. Model
CPU'da çalışır ve yavaştır: dizüstü bir makinede parça başına ~2 saniye.

| Uç | Anlamı |
|---|---|
| `GET /health/live` | Süreç ayakta |
| `GET /health/ready` | Kuyruk dinleniyor ve veritabanına ulaşılıyor; değilse 503 |

| Ortam değişkeni | Varsayılan |
|---|---|
| `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | `127.0.0.1`, `5672` |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `DB_AI_USER`, `DB_AI_PASSWORD` | `127.0.0.1`, `5432`, `meridian`, `meridian_ai` |
| `EMBEDDING_MODEL`, `EMBEDDING_CACHE_DIR`, `EMBEDDING_BATCH_SIZE` | `intfloat/multilingual-e5-large`, …, `16` |
| `LLM_CHAIN`, `OLLAMA_URL` | `ollama/llama3.2:3b`, `http://127.0.0.1:11434` |
| `ANSWER_SOURCES`, `ANSWER_MAX_TOKENS` | `3`, `300` |
| `GITHUB_TOKEN` | yok (saatte 60 API isteği) |
| `MAX_FILES_PER_SOURCE`, `PREFETCH`, `RETRY_BASE_MS`, `RETRY_FACTOR`, `MAX_RETRIES` | `2000`, `2`, `1000`, `4`, `4` |
| `HTTP_HOST`, `HTTP_PORT` | `127.0.0.1`, `8090` |
