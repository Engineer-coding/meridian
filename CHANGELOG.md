# Changelog

Bu proje [Semantic Versioning](https://semver.org) kullanır.
Biçim: [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/).

## [Unreleased]
### Added
- Sohbet API'si: `/v1/tenants/{tenantId}/conversations` ve `.../messages`. Cevap SSE ile akar (`sources` → `token` → `done`); mesajlar kaynak ve atıflarıyla kaydedilir. Konuşmalar kiracı içinde de kişiye özeldir (RLS). AI servisine ulaşılamazsa akış `degraded: true` ile biter; istemci yarıda ayrılırsa mesaj `interrupted` kaydedilir.
- Redis'te kullanıcı başına token-bucket oran sınırı (429 + `Retry-After`); Redis kapalıysa istek geçer.
- AI servisi iç ucu `POST /internal/v1/answer` (NDJSON), `AI_INTERNAL_TOKEN` ile korunur; anahtar yoksa her isteği reddeder (tehdit T19).
- Kaynaklı cevap (ADR-0008): model önce cevabı veren cümleyi kaynaklardan alıntılar, kod alıntının kaynakta gerçekten geçtiğini doğrular; doğrulanamazsa "bilmiyorum", doğrulanırsa `[n]` atıflı kısa cevap akışla üretilir. Var olmayan kaynak numaraları işaretlenir.
- LLM sağlayıcı zinciri (`LLM_CHAIN`, varsayılan `ollama/llama3.2:3b`): ilk token'dan önce düşen sağlayıcının yerine sıradaki denenir; hepsi düşerse yalnızca kaynaklar dönülür.
- Cevap değerlendirmesi (`make eval-answers`): "bilmiyorum" doğruluğu, atıf isabeti, var olmayan atıf oranı ve süreler; LLM cevapları diskte önbelleklenir.
- İkinci aşama sıralama (ADR-0007): çok dilli çapraz kodlayıcılar (`bge-reranker-v2-m3` int8, `jina-reranker-v2`); `RERANKER` ayarıyla açılır, varsayılan kapalı.
- Ablasyon tablosu: vektör / sözcüksel / hibrit ilk aşama ve iki reranker için recall@k, MRR, nDCG ve soru başına ek süre; reranker skorları önbellekli. Bulgu: 3 kaynaklı bağlamda reranking recall@3'ü artırmıyor (0,848), recall@5'i 0,870 → 0,913 yapıyor (+14 sn).
- Tehdit T18 (belge içeriğiyle istem enjeksiyonu): ilk önlemler.

### Changed
- Altın set v1: `k8s-002` ve `k8s-005` kaynaklarına aynı bilgiyi taşıyan alternatif bölümler eklendi (`alternatives`); değerlendirme ve doğrulayıcı v1'i kullanır, baseline yeniden üretildi. v0 değiştirilmeden saklanır.

## [0.3.0] - 2026-11-02
Faz 3 (AI servisi ve indeksleme) kapısı geçildi: recall@k altın set v0 üzerinde ölçülüyor ve
raporlanıyor ([packages/eval/reports/baseline.md](packages/eval/reports/baseline.md)). Vektör
arama (multilingual-e5-large): recall@5 0,87, recall@10 0,91, MRR 0,82 (23 cevaplı soru).

### Added
- Retrieval değerlendirmesi (`make eval`, `make eval-smoke`): korpus üretimdeki indeksleme hattıyla geçici bir veritabanına indekslenir; vektör, sözcüksel ve hibrit (RRF) arama için recall@k, MRR ve nDCG@k raporlanır. Altın kaynakların indekste karşılığı yoksa ölçüm yapılmaz.
- Kayıtlı baseline raporu ve CI kapısı: altın set ya da korpus manifesti değişip rapor yenilenmezse test kırılır; `eval-smoke` CI işi tüm hattı modelsiz olarak gerçek korpusla çalıştırır.
- `Retriever`: kiracı (RLS) ve isteğe bağlı koleksiyon kapsamlı vektör / sözcüksel / hibrit arama.
- KVKK korpusu: resmî PDF'ten (sha256 doğrulamalı) madde başlıklı Markdown'a dönüştürücü.
- Koleksiyon ve kaynak uçları (`/v1/tenants/{tenantId}/collections`, `/sources`): idempotent oluşturma, rol denetimi (viewer → 403), cursor sayfalaması, asenkron silme.
- Transactional outbox ve RabbitMQ aktarıcısı (ADR-0004): olay kayıtla aynı işlemde yazılır, broker onayından sonra silinir; ayrı `meridian_relay` veritabanı rolü.
- RabbitMQ topolojisi: `meridian.events` → `ai.indexing` (quorum, teslim sınırı 5) → `ai.indexing.dlq`.
- Bileşik yabancı anahtarlar: kaynak başka kiracının koleksiyonuna bağlanamaz (tehdit T13).
- Python AI servisi iskeleti (`apps/ai-service`, FastAPI + uv): `/health/live`, `/health/ready`, `make ai-test`, `make ai-run`, CI işi.
- İndeksleme hattı (ADR-0012): GitHub kaynakları tek commit'e sabitlenerek çekilir, Markdown başlıklarına göre bölünür, `multilingual-e5-large` ile yerelde gömülür ve `documents`/`chunks` (pgvector + `tsvector`) tablolarına tek işlemde yazılır; `source.deleted` kaynağı indeksiyle birlikte siler.
- `meridian_ai` veritabanı rolü ve `processed_events` ile idempotent tüketici: aynı olay kaç kez gelirse gelsin indeks bir kez yazılır (tehdit T16).
- GitHub kaynaklarında `paths` alanı: büyük depolarda yalnızca seçilen dizinler indekslenir.
- `ai.indexing` tüketicisi (ADR-0011): geçici hatada üstel bekleme + jitter ile `ai.indexing.retry.N` kuyrukları, kalıcı hata ve tükenen denemelerde DLQ; başlık/gövde uyuşmayan mesajlar işlenmez (tehdit T15).

### Changed
- Yeni ortam değişkenleri `DB_RELAY_PASSWORD` ve `DB_AI_PASSWORD`. Mevcut yerel veritabanında roller yoksa `make reset && make up`.
- `web` ve `upload` kaynakları henüz indekslenmez; `failed` durumuna geçer ve nedeni `lastError`'da yazar.
- API sözleşmesi 0.3.0: GitHub kaynaklarına isteğe bağlı `paths` alanı.

## [0.2.0] - 2026-11-02
Faz 2 (çekirdek backend) kapısı geçildi: sözleşmedeki her kiracıya bağlı uç nokta için
"A kiracısı B'nin verisine erişemez" testi CI'da yeşil.

### Added
- Spring Boot 4.1 çekirdek API: Flyway şeması, sahip/uygulama rolleri, zorunlu RLS ve kiracı bağlamının her işleme aktarılması.
- Keycloak 26.8 ile OIDC kimlik doğrulama; adresteki kiracı yalnızca üyelik doğrulandıktan sonra kabul edilir.
- OpenAPI sözleşmesinden üretilen sunucu arayüzleri; sözleşmeye uymayan kod derlenmez.
- `POST /v1/tenants`: `Idempotency-Key` ile tekrarlanabilir kiracı oluşturma (aynı anahtar + farklı gövde → 422).
- Kiracı sızıntı paketi: sözleşmedeki her `{tenantId}` uç noktası için otomatik üretilen erişim testi.
- Spring Modulith modül sınırları ve ArchUnit mimari kuralları (`docs/architecture/modules.md`).

### Fixed
- Sözleşmede kaynak türü alanlarına `type: string` eklendi; kod üretici discriminator'ı doğru kuruyor.

## [0.1.0] - 2026-10-29
### Added
- Monorepo iskeleti ve `make up` ile yerel altyapı: PostgreSQL 17 + pgvector 0.8.7, Redis, RabbitMQ, RustFS (S3).
- CI: gitleaks (tüm geçmiş), altyapı smoke testi, OpenAPI lint, altın set doğrulaması.
- Tehdit modeli v0 ve ADR-0001..0003 (modüler monolit, RLS, pgvector).
- OpenAPI v0 sözleşmesi: kimlik, kiracı, kaynak uçları.
- Değerlendirme: korpus manifesti (Kubernetes docs @ef4f9c6, KVKK 6698) ve 30 soruluk altın set v0.

### Changed
- MinIO yerine RustFS: MinIO topluluk Docker imajları yayından kalktı.
- gitleaks-action yerine sürümü sabitlenmiş gitleaks imajı: action ilk commit'te aralığı çözemiyordu.

[Unreleased]: https://github.com/Engineer-coding/meridian/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Engineer-coding/meridian/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Engineer-coding/meridian/releases/tag/v0.1.0