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
| T1 | Kiracılar arası veri sızıntısı | I | 1, 2 | RLS + `FORCE`, ayrı uygulama rolü, `SET LOCAL` bağlam, sorgu seviyesinde ACL ([ADR-0002](../adr/0002-tenant-isolation-rls.md)) | Uç nokta başına üretilen sızıntı testleri; RLS'i kapalı tablo için şema testi | **Uygulandı** (Faz 2: `TenantScopedEndpointsTest`, `RlsSchemaTest`; adresteki kiracı ancak üyelik doğrulandıktan sonra bağlama yazılır) |
| T2 | Yetkisiz parçanın LLM'e ulaşması | I | 2, 3 | Yetki filtresi retrieval sorgusunda (sonradan süzme yok) ([ADR-0003](../adr/0003-pgvector.md)) | Kısıtlı koleksiyonla retrieval testi | Planlandı |
| T3 | Dolaylı prompt injection (doküman içinden) | T, E | 5, 6 | Ayrıntı T18 ve T26; ölçüm [ADR-0016](../adr/0016-guardrails-and-red-team.md) | `test_redteam.py`, kayıtlı `redteam` raporu | **Kısmen** |
| T4 | Web tarayıcıda SSRF | S, I | 4 | Hedef allowlist'i, özel/link-local IP aralıklarının engellenmesi (DNS çözümünden sonra), yönlendirme takibinde tekrar kontrol, çıkış proxy'si | Birim + entegrasyon testleri (`169.254.169.254`, `localhost`, DNS rebinding) | Planlandı |
| T5 | Sır ve anahtar sızıntısı | I | 7 | `.env` git dışı; gitleaks; API anahtarları yalnızca hash olarak saklanır; düzenli rotasyon | CI'da gitleaks (tüm geçmiş) | **Kısmen uygulandı** (gitleaks CI) |
| T6 | Bağımlılık zinciri saldırısı | T | 7 | Sabit sürümlü imaj ve action'lar, Dependabot, SBOM (CycloneDX), Trivy, cosign ile imzalı imajlar | CI kapıları | **Kısmen uygulandı** (sabit imaj sürümleri) |
| T7 | API kötüye kullanımı / maliyet saldırısı | D | 1 | Kiracı ve anahtar bazında oran sınırı (Redis token bucket), kapsamlı anahtarlar, günlük token kotası, global bütçe tavanı | Yük ve kötüye kullanım testleri | Planlandı |
| T8 | Aşırı yetkili ajan | E | 6 | Salt-okunur varsayılan; yazma etkili araçlarda insan onayı; adım, süre ve maliyet tavanı | Ajan senaryo testleri | Planlandı |
| T9 | Hassas veri (PII) sızıntısı | I | 3 | E-posta, T.C. kimlik, IBAN, kart ve telefon indekslemeden önce maskelenir; log satırları ve istisnalar filtreden geçer, belge alıntısı loglanmaz ([ADR-0016](../adr/0016-guardrails-and-red-team.md)). İsim ve adres yakalanmaz; at-rest şifreleme ve TLS Faz 6 | `test_redteam.py` | **Kısmen** |
| T10 | Denetim kaydının değiştirilmesi / inkâr | R, T | 2 | `audit_log` append-only (uygulama rolüne `UPDATE`/`DELETE` yetkisi yok); değişiklikler ve reddedilen kararlar yazılır ([ADR-0014](../adr/0014-audit-usage-api-keys.md)) | `AdminApiTest` | **Uygulandı** |
| T11 | Yerel geliştirme servislerinin ağa açılması | I | 1 | Compose portları yalnızca `127.0.0.1`'e bağlı | Compose dosyası incelemesi | **Uygulandı** |
| T13 | Yabancı anahtar üzerinden kiracılar arası referans: FK denetimi RLS'e tabi değildir; başka kiracının koleksiyon kimliğini bilen biri ona kaynak bağlayabilir | T, I | 1, 2 | Kiracıya ait tablolar arasında bileşik FK (`tenant_id`, `id`); uygulama katmanında da RLS altında varlık kontrolü | Uygulama rolüyle doğrudan SQL denemesi (`KnowledgeSchemaTest`) | **Uygulandı** |
| T14 | Olay kanalından sızıntı veya olay uydurma | I, T | 1, 2 | Uygulama rolü outbox'a yalnızca kendi kiracısı adına ekleyebilir, okuyamaz; aktarıcı rolü yalnızca outbox'ı görür, olay ekleyemez ([ADR-0004](../adr/0004-rabbitmq-outbox.md)) | Rol yetki testleri (`OutboxRelayTest`) | **Uygulandı** |
| T15 | Zehirli veya sahte mesajla AI servisini kilitlemek ya da başka kiracı adına iş yaptırmak | T, D | 2 | Zarf doğrulanır; `message_id`/`tenant_id` başlıkları gövdeyle uyuşmazsa mesaj işlenmeden DLQ'ya gider. Geçici hatalar sınırlı ve beklemeli denenir, çöken tüketicide teslim sınırı 5 ([ADR-0011](../adr/0011-consumer-retry-dlq.md)) | `test_consumer.py` | **Uygulandı** |
| T16 | AI servisi üzerinden başka kiracının indeksine yazma veya okuma | I, T, E | 2 | `meridian_ai` rolü NOBYPASSRLS; her işlem olaydaki kiracıyla açılır; başka kiracının kaynağı görünmez; bileşik FK parçayı yalnızca kendi belgesine/koleksiyonuna bağlar; rol kimlik, üyelik ve outbox tablolarını göremez ([ADR-0012](../adr/0012-indexing-pipeline.md)) | `test_indexer.py` | **Uygulandı** |
| T17 | Kiracının verdiği adresle sunucu tarafı istek (SSRF) | I, E | 2 | GitHub çekici yalnızca sabit GitHub adreslerine gider, kiracı değerleri URL yolunda kodlanır; `web` kaynakları ayrı SSRF tasarımına kadar devre dışı | `test_fetchers.py` | **Kısmen (web ertelendi)** |
| T18 | Belge içeriğiyle istem enjeksiyonu (dolaylı prompt injection) | T, I, E | 2 | Talimat gibi görünen paragraf istemden çıkar; `[n]` taklit edilemez; cevap kodla doğrulanmış alıntıya bağlı; yabancı bağlantı cevaptan silinir ([ADR-0016](../adr/0016-guardrails-and-red-team.md)). Canlı ölçümde 67 denemede 2 başarılı saldırı, ikisi de yanlış bilgi. Kalıpları aşan talimat modele kalır | `test_redteam.py`, `test_answering.py` | **Kısmen** |
| T19 | AI servisi iç ucunu doğrudan çağırıp başka kiracı adına sorgulamak | S, I, E | 2 | Paylaşılan gizli anahtar (sabit zamanlı karşılaştırma, boşsa kapalı), varsayılan yalnızca 127.0.0.1; kiracı kararı çekirdek API'de üyelik doğrulandıktan sonra verilir. Kubernetes'te NetworkPolicy: AI servisine yalnızca API pod'ları ve ingress erişir; ingress yalnızca `/mcp` yolunu yönlendirir, `/internal` dışarıya açık değil ([ADR-0009](../adr/0009-gitops-deployment.md)) | `test_internal_api.py`, `infra/helm/meridian/tests/networkpolicy_test.yaml`, `infra/k8s/smoke.sh` (web → ai engellenir) | **Uygulandı** |
| T20 | Aynı kiracının başka üyesinin konuşmaları okuması | I | 1 | RLS kiracıyla birlikte kullanıcıyı denetler; bileşik FK başkasının konuşmasına mesaj bağlanmasını önler; mesajlar değiştirilemez | `ChatApiTest` | **Uygulandı** |
| T21 | Çok sayıda soruyla pahalı modeli meşgul etmek | D | 1, 2 | Kullanıcı başına token-bucket, model çağrılmadan önce 429 | `ChatApiTest` | **Uygulandı** |
| T22 | Model çıktısı ya da belge içeriğiyle arayüzde XSS, görselle veri sızdırma | T, I, E | 2 | Ham HTML işlenmez, bağlantı yalnızca http(s), görsel gösterilmez; nonce'lu CSP dış isteği engeller; token tarayıcı koduna verilmez ([ADR-0013](../adr/0013-web-session-bff.md)) | `Answer.test.tsx`, `e2e/chat.spec.ts` | **Uygulandı** |
| T23 | Çerezli API vekiline başka siteden istek (CSRF), vekille `/v1` dışına çıkma | S, T, E | 2 | `SameSite=Lax` + `Origin` denetimi; yol segmentleri doğrulanır; çerez API'ye geçmez | `proxy.test.ts`, `e2e/chat.spec.ts` | **Uygulandı** |
| T24 | API anahtarının çalınması ya da yetkisinin aşılması | S, I, E | 2 | Gizli değer yalnızca SHA-256 özetiyle saklanır, bir kez gösterilir; kapsam ve süre zorunlu; listede olmayan uç reddedilir; anahtar oluşturanın rolünü aşamaz, üyelik kalkınca çalışmaz; arama RLS altında, kiracı adresinden | `AdminApiTest` | **Uygulandı** |
| T25 | Sınırsız kullanımla model kaynağını ya da bütçeyi tüketmek | D | 1, 2 | Kiracı başına günlük token kotası, model çağrılmadan önce 429 (kota yumuşak: eşzamanlı sorular bir cevap kadar aşabilir) | `AdminApiTest` | **Uygulandı** |
| T26 | Aşırı yetkili ajan: belgedeki talimatla yazma ya da veri sızdırma | T, I, E | 2 | Yazma yalnızca çekirdek API'de ve insan onayıyla; ticket ancak görev isterse önerilir; izinli eylemler kodla denetlenir; adım, token ve süre bütçesi ([ADR-0015](../adr/0015-agent-and-mcp.md)). Kandırılmış modelle ve canlı modelle ölçüldü: istenmeyen ticket 0, yasak SQL 0 ([ADR-0016](../adr/0016-guardrails-and-red-team.md)). Görev ticket isterse içerik belgeden etkilenebilir; son kapı onay kartı | `test_redteam.py`, `test_agent.py`, `AgentApiTest` | **Uygulandı** |
| T27 | Ajanın SQL aracıyla kiracı bağlamını değiştirmek (`set_config`) ya da başka tablo okumak | I, E | 2 | Ayrıştırılmış ağaçta izin listesi: tek SELECT, iki `security_invoker` görünüm, listelenen fonksiyonlar; ağaçtan yeniden üretilen metin, salt-okunur işlem, süre ve satır sınırı | `test_agent.py` | **Uygulandı** |
| T28 | MCP üzerinden yetkisiz erişim, anahtar sızması, tarayıcıdan yerel sunucuya istek | S, I | 2 | Yetki kararı çekirdek API'de (kapsam, RLS, oran sınırı); anahtar kaydedilmez ve yalnızca sabit API adresine gider; Host başlığı denetlenir | `test_mcp.py`, `AgentApiTest` | **Uygulandı** |
| T29 | Zararlı istek ya da sistem istemini çıkarma | I, E | 2 | Açık kalıplar modele gitmez, yalnızca tür loglanır; kanıt doğrulaması genel bilgiden cevabı engeller ([ADR-0016](../adr/0016-guardrails-and-red-team.md)). Başka sözcüklerle yazılan istek kalıptan geçer | `test_redteam.py` | **Kısmen** |
| T30 | Belgeyle yanlış bilgi yerleştirme | T | 2 | Kod koruması yok: cevap belgeyi kaynak gösterir, kaynak ekleme yetkili rolle sınırlıdır. Canlı ölçümde 2/2 başarılı ([ADR-0016](../adr/0016-guardrails-and-red-team.md)) | kayıtlı `redteam` raporu | **Kabul edilen risk** |
| T12 | Slug numaralandırma: 409 cevabı başka kiracının slug'ını kullandığını açığa çıkarır | I | 1 | Slug'lar adreste görünen, gizli olmayan tanımlayıcılardır; kiracı verisi sızmaz | — | **Kabul edilen risk** |

STRIDE: **S**poofing, **T**ampering, **R**epudiation, **I**nformation disclosure, **D**enial of service, **E**levation of privilege.

## Kapsam dışı (v0)
- Altyapı sağlayıcısının (bulut) kendisinin ele geçirilmesi.
- Kurumsal SSO'nun tüm varyantları (yalnızca OIDC desteklenir).
- Fiziksel saldırılar ve son kullanıcı cihaz güvenliği.

## Barındırılan LLM'e giden veri

`LLM_CHAIN` içinde `anthropic/<model>` varsa (demo: `claude-haiku-5-5`) aşağıdakiler makineden çıkar.
Yalnızca `ollama/...` kullanılırsa hiçbir şey dışarı gitmez.

| Alan | Gider mi | Not |
|---|---|---|
| Soru metni | Evet | Kullanıcının yazdığı haliyle; zararlı ve istem çıkaran istekler modele gitmeden durdurulur (T29) |
| Seçilen kaynak parçaları (ilk 3) | Evet | İndekslemede PII maskelenmiştir (T9); talimat paragrafları çıkarılır (T18) |
| Ajan araç sonuçları | Evet | Yalnızca ajan sayfasında; salt-okunur SQL sonuçları dahil |
| Kullanıcı, kiracı, konuşma kimliği | Hayır | İstekte kimlik alanı yok |
| Önceki konuşma mesajları | Hayır | Her cevap tek soruyla üretilir |
| İz bağlamı (`traceparent`) | Evet | SDK'nın varsayılanı; içerik değil, yalnızca iz kimliği |

## Açık sorular
- API anahtarı hash algoritması ve rotasyon süresi Faz 2'de (ADR-0005) belirlenecek.
