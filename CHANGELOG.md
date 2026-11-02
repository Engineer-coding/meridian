# Changelog

Bu proje [Semantic Versioning](https://semver.org) kullanır.
Biçim: [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/).

## [Unreleased]
### Added
- Spring Boot 4.1 çekirdek API: Flyway şeması, sahip/uygulama rolleri, zorunlu RLS ve kiracı bağlamının her işleme aktarılması.
- Keycloak 26.8 ile OIDC kimlik doğrulama; adresteki kiracı yalnızca üyelik doğrulandıktan sonra kabul edilir.
- OpenAPI sözleşmesinden üretilen sunucu arayüzleri; sözleşmeye uymayan kod derlenmez.
- `POST /v1/tenants`: `Idempotency-Key` ile tekrarlanabilir kiracı oluşturma (aynı anahtar + farklı gövde → 422).
- Kiracı sızıntı paketi: sözleşmedeki her `{tenantId}` uç noktası için otomatik üretilen erişim testi.

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

[Unreleased]: https://github.com/Engineer-coding/meridian/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Engineer-coding/meridian/releases/tag/v0.1.0