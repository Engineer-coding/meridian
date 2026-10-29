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
| 0004 | RabbitMQ ve transactional outbox | Planlandı |
| 0005 | Kimlik: OIDC ve API anahtarları | Planlandı |
| 0006 | Streaming: SSE ve WebSocket | Planlandı |
| 0007 | Hibrit retrieval ve reranking seçimi (ablasyon verisiyle) | Planlandı |
| 0008 | LLM sağlayıcı soyutlaması ve fallback | Planlandı |
| 0009 | GitOps ile dağıtım | Planlandı |
| 0010 | Değerlendirme kapısının CI'daki yeri | Planlandı |
