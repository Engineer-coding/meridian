# Tehdit Modeli v0

- Sürüm: v0 (Faz 1)
- Tarih: 2026-10-29
- Yöntem: varlıklar → güven sınırları → tehditler (STRIDE kategorileriyle) → önlem → otomatik doğrulama
- Güncelleme kuralı: her faz sonunda `Durum` sütunu güncellenir; yeni bir bileşen veya dış
  bağlantı eklendiğinde ilgili güven sınırı ve tehditler eklenir.

## Korunan varlıklar
| Varlık | Neden kritik |
|---|---|
| Kiracı dokümanları ve parçaları (embedding dahil) | Müşterinin gizli iç bilgisi; sızıntı ürünü bitirir |
| Kullanıcı soruları, cevaplar, geri bildirimler | Kişisel veri ve iş sırrı içerebilir (KVKK/GDPR) |
| API anahtarları, OIDC belirteçleri | Kiracı adına tam erişim sağlar |
| LLM sağlayıcı ve altyapı sırları | Maliyet kötüye kullanımı, altyapı erişimi |
| Denetim kaydı (`audit_log`) | Olay sonrası inceleme ve uyumluluk kanıtı; değiştirilemez olmalı |
| Kota ve kullanım kayıtları | Maliyet atfı; manipülasyonu mali zarar doğurur |

## Güven sınırları
1. **Tarayıcı / API istemcisi ↔ Ingress** — internet; kimliği doğrulanmamış trafik.
2. **Çekirdek API ↔ AI servisi** — AI servisi kendi yetki kararı vermez, çekirdeğin kimlik bağlamına güvenir.
3. **AI servisi ↔ LLM sağlayıcı** — veri şirket dışına çıkar.
4. **Web tarayıcı bağlayıcısı ↔ dış internet** — sunucu, kullanıcının verdiği URL'ye istek atar (SSRF).
5. **Doküman içeriği ↔ LLM prompt'u** — güvenilmeyen veri modelin bağlamına girer (dolaylı prompt injection).
6. **Ajan ↔ araçlar** — model çıktısı gerçek eylemlere (SQL, bilet oluşturma) dönüşür.
7. **CI/CD ↔ bağımlılıklar ve imaj kayıtları** — üçüncü taraf kod yapı çıktısına girer.

## Tehditler
| # | Tehdit | STRIDE | Sınır | Önlem | Doğrulama | Durum |
|---|---|---|---|---|---|---|
| T1 | Kiracılar arası veri sızıntısı | I | 1, 2 | RLS + `FORCE`, ayrı uygulama rolü, `SET LOCAL` bağlam, sorgu seviyesinde ACL ([ADR-0002](../adr/0002-tenant-isolation-rls.md)) | Uç nokta başına üretilen sızıntı testleri; RLS'i kapalı tablo için şema testi | Planlandı |
| T2 | Yetkisiz parçanın LLM'e ulaşması | I | 2, 3 | Yetki filtresi retrieval sorgusunda (sonradan süzme yok) ([ADR-0003](../adr/0003-pgvector.md)) | Kısıtlı koleksiyonla retrieval testi | Planlandı |
| T3 | Dolaylı prompt injection (doküman içinden) | T, E | 5, 6 | Doküman içeriği "veri" olarak işaretlenir; araçlar en az yetkiyle; şemalı çıktı doğrulaması | CI'da kırmızı-takım seti | Planlandı |
| T4 | Web tarayıcıda SSRF | S, I | 4 | Hedef allowlist'i, özel/link-local IP aralıklarının engellenmesi (DNS çözümünden sonra), yönlendirme takibinde tekrar kontrol, çıkış proxy'si | Birim + entegrasyon testleri (`169.254.169.254`, `localhost`, DNS rebinding) | Planlandı |
| T5 | Sır ve anahtar sızıntısı | I | 7 | `.env` git dışı; gitleaks; API anahtarları yalnızca hash olarak saklanır; düzenli rotasyon | CI'da gitleaks (tüm geçmiş) | **Kısmen uygulandı** (gitleaks CI) |
| T6 | Bağımlılık zinciri saldırısı | T | 7 | Sabit sürümlü imaj ve action'lar, Dependabot, SBOM (CycloneDX), Trivy, cosign ile imzalı imajlar | CI kapıları | **Kısmen uygulandı** (sabit imaj sürümleri) |
| T7 | API kötüye kullanımı / maliyet saldırısı | D | 1 | Kiracı ve anahtar bazında oran sınırı (Redis token bucket), kapsamlı anahtarlar, günlük token kotası, global bütçe tavanı | Yük ve kötüye kullanım testleri | Planlandı |
| T8 | Aşırı yetkili ajan | E | 6 | Salt-okunur varsayılan; yazma etkili araçlarda insan onayı; adım, süre ve maliyet tavanı | Ajan senaryo testleri | Planlandı |
| T9 | Hassas veri (PII) sızıntısı | I | 3 | İndekslemede ve loglarda maskeleme; hassas kiracı için kendi sunucuda model; at-rest şifreleme; her yerde TLS | Log taraması, şifreleme kontrol testleri | Planlandı |
| T10 | Denetim kaydının değiştirilmesi / inkâr | R, T | 2 | `audit_log` append-only (uygulama rolüne `UPDATE`/`DELETE` yetkisi yok) | Yetki testi | Planlandı |
| T11 | Yerel geliştirme servislerinin ağa açılması | I | 1 | Compose portları yalnızca `127.0.0.1`'e bağlı | Compose dosyası incelemesi | **Uygulandı** |

STRIDE: **S**poofing, **T**ampering, **R**epudiation, **I**nformation disclosure, **D**enial of service, **E**levation of privilege.

## Kapsam dışı (v0)
- Altyapı sağlayıcısının (bulut) kendisinin ele geçirilmesi.
- Kurumsal SSO'nun tüm varyantları (yalnızca OIDC desteklenir).
- Fiziksel saldırılar ve son kullanıcı cihaz güvenliği.

## Açık sorular
- LLM sağlayıcıya hangi alanlar gidiyor? Veri akış tablosu Faz 4'te eklenecek.
- API anahtarı hash algoritması ve rotasyon süresi Faz 2'de (ADR-0005) belirlenecek.
