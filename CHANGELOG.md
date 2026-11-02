# Changelog

Bu proje [Semantic Versioning](https://semver.org) kullanır.
Biçim: [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/).

## [Unreleased]
### Added
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