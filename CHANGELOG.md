# Changelog

Bu proje [Semantic Versioning](https://semver.org) kullanır.
Biçim: [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/).

## [Unreleased]

## [0.6.0] - 2026-11-11
İzleme, SLO alarmları ve yük testi. Bir soru web'den modele, kuyruktan da geçerek tek izde görünür; API
kullanılabilirliği için yanma hızı alarmları ve Grafana paneli kodla tanımlıdır. Yük testinde 500 eşzamanlı
sohbette tam cevap p95 7,4 sn, saniyede 68 cevap, 0 başarısız istek (sahte model, tek makine); bu,
gerçek modelin kapasitesini değil, modelin çevresindeki sistemin kapasitesini ölçer. Cevap kalitesi
değişmedi.

### Added
- Kök README: bileşenler, sistem diyagramı, yerel kurulum, servis adresleri ve `make` komutları. Modül haritası (`docs/architecture/modules.md`) koddaki 13 modüle göre güncellendi.
- Yük testi (ADR-0019, `make load`, `packages/load`): k6 ile 500 eşzamanlı sohbet ve 50 eşzamanlı indeksleme işi; sunucu ölçümleri Prometheus'tan. Son yapılandırmada tam cevap p95 7,4 sn, saniyede 68 cevap, 0 başarısız istek (sahte model, tek makine).
- AI servisi için üretim imajı (`apps/ai-service/Dockerfile`) ve süreç sayısı ayarı (`HTTP_WORKERS`, Linux).
- İzleme (ADR-0017): web, API ve AI servisi OTLP ile OpenTelemetry Collector'a yazar; bir soru tek izde görünür. İz kuyruktan da geçer (outbox `traceparent`, V8). Metrikler: HTTP RED, AI çağrısı, model süresi, ilk token, token, arama, indeksleme, cevap sonucu, ajan durumu. JSON loglar: her satırda iz ve kiracı kimliği. Gönderim `OTEL_EXPORT=true` ile açılır.
- SLO'lar ve alarmlar (ADR-0018): API kullanılabilirliği %99,5 için çok pencereli yanma hızı alarmları, indeksleme süresi, DLQ ve kuyruk birikmesi, model kesintisi, "bilmiyorum" oranı. Eşikler `promtool test rules` ile sınanır (`make obs-check`, CI). Her alarmın runbook'u `docs/runbooks/` altında.
- Grafana paneli kod olarak (`infra/compose/grafana`): SLO, API RED, model, arama, indeksleme, kuyruk, alarmlar ve hata logları; izden loga ve logdan ize geçiş. Compose'a Prometheus (`127.0.0.1:9090`), Loki (`127.0.0.1:3100`) ve Grafana (`127.0.0.1:3001`) eklendi.
- Compose'a OpenTelemetry Collector ve Tempo eklendi (`127.0.0.1:4318`, `127.0.0.1:3201`). Tam sistem testi izin üç servisten geçtiğini Tempo'dan doğrular.

### Changed
- API veritabanı havuzu 10 → 20 (`API_DB_POOL_SIZE`); yük testinde 10 bağlantı kuyruk oluşturdu.
- Belgedeki talimat taraması önbelleğe alındı; yük altında AI sürecinin işlemcisinin %30'unu harcıyordu. Davranış değişmedi.

## [0.5.0] - 2026-11-09
Yönetim paneli, araç çağıran ajan, MCP sunucusu, kod korumaları ve tam sistem testi. Ajan 12 sentetik
görevde %58 başarılı (`llama3.2:3b`; bilgi sorularında 6'da 2), istenmeyen ticket 0. Kırmızı takım setinde
başarılı saldırı korumasız 67 denemede 10, korumalı 2; kalan ikisi belgeyle yerleştirilen yanlış bilgi.
Sohbet kalitesi değişmedi: cevaplı sorularda %30 gereksiz "bilmiyorum", %61 doğru. Küçük yerel modelle
cevap kalitesi canlı kullanım için yeterli değildir.

### Added
- Tam sistem testi (`make e2e-full`, CI işi `full-stack`): gerçek Keycloak girişi, kaynak indeksleme, akışlı cevap, ajan onayı, denetim, API anahtarı ile MCP, kiracı izolasyonu ve çıkış tek senaryoda; model, embedding ve GitHub sabit parçayla değişir.
- Kırmızı takım seti: 40 senaryo (`packages/eval/golden/redteam-v1.jsonl`). CI'da tamamen kandırılmış modelle çalışır, canlı rapor `reports/redteam.*` eşikle denetlenir (ADR-0016).
- Kod korumaları (`guardrails.py`): zararlı ve istem çıkaran istekler modele gitmez, belgedeki talimat paragrafı istemden çıkar, cevapta yalnızca kayıtlı belge adresi kalır. Tehditler T3, T18, T26, T29, T30.
- PII maskeleme: e-posta, T.C. kimlik, IBAN, kart ve telefon indekse ve loglara girmez. Mevcut kaynaklar yeniden indekslenmelidir. Tehdit T9.
- Ajan: açık durum makinesi, `search_knowledge`, `fetch_document`, salt-okunur `query_sql`, onaylı `create_ticket`; adım, token ve süre bütçesi. Arayüz `/agent`: canlı adımlar, onay kartı. Ajan ölçümü `packages/eval/reports/agent-*` (ADR-0015).
- MCP sunucusu (`POST /mcp/`, AI servisi): `list_collections`, `search_knowledge`, `fetch_document`; yetki kararı çekirdek API'de. Tehdit T28.
- `POST .../search`, `GET .../documents`, `GET|POST .../agent-runs`, `GET .../agent-runs/{id}`, `POST .../agent-runs/{id}/approval`. Tehditler T26, T27.
- Yönetim paneli (`/admin`): kaynak ekleme, canlı indeksleme durumu, yeniden deneme ve silme; günlük kullanım grafiği ve kota göstergesi; sürümler arası değerlendirme tablosu; API anahtarı yönetimi; denetim kayıtları. Bölümler role göre gösterilir, giriş sonrası istenen panel sayfasına dönülür.
- `POST .../sources/{id}/retry`, `GET .../usage`, `GET|POST|DELETE .../api-keys`, `GET .../audit-log` (ADR-0014).
- Denetim kaydı (`audit_log`, append-only): değişiklikler ve reddedilen kararlar; soru metni yazılmaz. Rol denetimi tek yerde (`audit.Policy`). Tehdit T10 uygulandı.
- API anahtarları (`X-API-Key`): SHA-256 özetiyle saklanır, kapsam ve süre zorunlu, oluşturanın rolünü aşamaz; yönetim uçları anahtarla açılmaz. Tehdit T24.
- Token muhasebesi ve günlük kota: AI servisi Ollama sayaçlarını iletir, kesilen cevaplar tahmin olarak işaretlenir; kota dolunca model çağrılmadan 429. Tehdit T25.
- Web arayüzü (`apps/web`, Next.js): Keycloak ile giriş, çalışma alanı seçimi ve oluşturma, akışlı sohbet, durdurma, yeniden üretme, konuşma geçmişi, Türkçe/İngilizce, işletim sisteminden gelen açık/koyu tema.
- Atıf düğmeleri: üzerine gelince kaynak pasajını gösterir, tıklanınca kaynak kartını açar. Var olmayan kaynak numarası bağlantı olmaz; "bilmiyorum" ve üretilemeyen cevap için ayrı uyarılar.
- Web oturumu (ADR-0013): token'lar yalnızca sunucuda, şifreli `HttpOnly` çerezde; API aynı kökenli akış vekiliyle çağrılır; `Origin` denetimi ve nonce'lu CSP. Tehditler T22, T23.
- Web testleri CI'da: Vitest, axe (WCAG 2.2 AA, açık ve koyu tema), Playwright (üretim derlemesi, sahte OIDC ve API), ilk JS bütçesi (200 KB gzip; ölçülen 153 KB), üretilen API tiplerinin güncelliği.

### Changed
- ADR-0007: reranking'in cevaplara etkisi ölçüldü. `vector+bge-m3` doğru cevabı %61,0'den %64,0'e çıkarıyor (14 kazanç, 10 kayıp; p = 0,54) ve soru başına ~15 sn ekliyor; varsayılan kapalı kalır.

## [0.4.0] - 2026-11-06
Kaynaklı cevap, akışlı sohbet API'si ve eşikli değerlendirme kapısı. Altın set v2 (165 soru,
`llama3.2:3b`, CPU): cevapsız soruda %93 "bilmiyorum", cevaplı soruda %30 gereksiz "bilmiyorum",
cevaplı soruların %61'i doğru, model cevap verdiğinde %87 doğru (anahtar kelime ölçütü; yukarı
yanlı, bkz. ADR-0010), ortanca toplam süre 65 sn. Gereksiz "bilmiyorum" oranı ADR-0008'in %30
tetikleyicisini aştı.

### Added
- Altın set v2: 165 soru (103 tek kaynaklı, 33 çok kaynaklı, 29 cevapsız; 79 Türkçe, 86 İngilizce). Sentetik; kanıtı kodla denetlendi, tek kişi tarafından hızlı onaylandı.
- Anahtar kelimeye dayalı cevap doğruluğu ölçütü (`correct`, `correct_when_answered`).
- Değerlendirme kapısı (ADR-0010): raporlar kodun, altın setin ve manifestin parmak izini taşır; CI güncelliği ve `packages/eval/thresholds.json` eşiklerini denetler.
- Sohbet API'si: `/v1/tenants/{tenantId}/conversations` ve `.../messages`. Cevap SSE ile akar (`sources` → `token` → `done`); mesajlar kaynak ve atıflarıyla kaydedilir. Konuşmalar kiracı içinde de kişiye özeldir (RLS). AI servisine ulaşılamazsa akış `degraded: true` ile biter; istemci yarıda ayrılırsa mesaj `interrupted` kaydedilir.
- Redis'te kullanıcı başına token-bucket oran sınırı (429 + `Retry-After`); Redis kapalıysa istek geçer.
- AI servisi iç ucu `POST /internal/v1/answer` (NDJSON), `AI_INTERNAL_TOKEN` ile korunur; anahtar yoksa her isteği reddeder (tehdit T19).
- Kaynaklı cevap (ADR-0008): model önce cevabı veren cümleyi kaynaklardan alıntılar, kod alıntının kaynakta gerçekten geçtiğini doğrular; doğrulanamazsa "bilmiyorum", doğrulanırsa `[n]` atıflı kısa cevap akışla üretilir. Var olmayan kaynak numaraları işaretlenir.
- LLM sağlayıcı zinciri (`LLM_CHAIN`, varsayılan `ollama/llama3.2:3b`): ilk token'dan önce düşen sağlayıcının yerine sıradaki denenir; hepsi düşerse yalnızca kaynaklar dönülür.
- Cevap değerlendirmesi (`make eval-answers`): "bilmiyorum" doğruluğu, atıf isabeti, var olmayan atıf oranı ve süreler; LLM cevapları diskte önbelleklenir.
- İkinci aşama sıralama (ADR-0007): çok dilli çapraz kodlayıcılar (`bge-reranker-v2-m3` int8, `jina-reranker-v2`); `RERANKER` ayarıyla açılır, varsayılan kapalı.
- Ablasyon tablosu: vektör / sözcüksel / hibrit ilk aşama ve iki reranker için recall@k, MRR, nDCG ve soru başına ek süre; reranker skorları önbellekli. Bulgu: 3 kaynaklı bağlamda reranking recall@3'ü artırmıyor (0,848), recall@5'i 0,870 → 0,913 yapıyor (+14 sn).
- Tehdit T18 (belge içeriğiyle istem enjeksiyonu): ilk önlemler.

### Fixed
- Cevap süresi raporu yalnızca son model çağrısını sayıyordu; kanıt çağrısı eklendi (ortanca toplam 18,6 sn yerine 64,9 sn).

### Changed
- ADR-0007 yeniden ölçüldü: 136 cevaplı soruda `bge-m3` vektör recall@3'ü 0,897'den 0,938'e çıkarıyor. v1'in aksine reranking recall@3'ü artırıyor; varsayılan, cevap doğruluğuna etkisi ölçülene kadar kapalı kalır.
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

[Unreleased]: https://github.com/Engineer-coding/meridian/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/Engineer-coding/meridian/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Engineer-coding/meridian/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Engineer-coding/meridian/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Engineer-coding/meridian/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Engineer-coding/meridian/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Engineer-coding/meridian/releases/tag/v0.1.0