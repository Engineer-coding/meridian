# Mimari Karar Kayıtları (ADR)

Her önemli mimari karar burada kayıt altına alınır. Yeni bir ADR için
[0000-template.md](0000-template.md) dosyasını kopyalayın ve sıradaki numarayı verin.
Kabul edilmiş bir ADR değiştirilmez; yerine yeni bir ADR yazılır ve eskisinin durumu
"Yerini aldı: ADR-XXXX" olarak güncellenir.

| # | Başlık | Durum |
|---|---|---|
| [0001](0001-modular-monolith-and-ai-service.md) | Modüler monolit çekirdek ve ayrı AI servisi | Kabul edildi |
| [0002](0002-tenant-isolation-rls.md) | Kiracı izolasyonu: paylaşımlı şema + RLS | Kabul edildi |
| [0003](0003-pgvector.md) | Vektör araması için PostgreSQL + pgvector | Kabul edildi |
| [0004](0004-rabbitmq-outbox.md) | RabbitMQ ve transactional outbox | Kabul edildi |
| 0005 | Kimlik: OIDC ve API anahtarları | Planlandı |
| 0006 | Streaming: SSE ve WebSocket | Planlandı |
| [0007](0007-hybrid-retrieval-and-reranking.md) | Hibrit retrieval ve reranking seçimi (ablasyon verisiyle) | Kabul edildi |
| [0008](0008-llm-provider-and-fallback.md) | LLM sağlayıcı soyutlaması, yedek zinciri ve doğrulanmış kanıtla cevap | Kabul edildi |
| 0009 | GitOps ile dağıtım | Planlandı |
| [0010](0010-eval-gate-in-ci.md) | Değerlendirme kapısının CI'daki yeri | Kabul edildi |
| [0011](0011-consumer-retry-dlq.md) | Kuyruk tüketicisi: yeniden deneme, DLQ ve teslim garantisi | Kabul edildi |
| [0012](0012-indexing-pipeline.md) | İndeksleme hattı ve embedding modeli (v0) | Kabul edildi |
| [0013](0013-web-session-bff.md) | Web oturumu: token'lar tarayıcıya verilmez (BFF) | Kabul edildi |
