# ADR-0017: İzleme: OpenTelemetry, tek iz ve JSON loglar

- Durum: Kabul edildi
- Tarih: 2026-11-09

## Bağlam
Plan, bir sorunun tarayıcıdan modele kadar tek iz olarak görünmesini, RED ve modele özgü metrikleri, her satırında
iz ve kiracı kimliği olan JSON logları ister. Üç servis üç dilde yazılı (Java, Python, TypeScript) ve indeksleme
kuyruktan geçiyor; iz, istek ile kuyruk arasında kopmamalı. Kayıtlı kalite ve kırmızı takım raporları, ölçülen
koddaki her değişiklikte yeniden üretilmeyi ister (ADR-0010, ADR-0016); izleme bunları geçersiz kılmamalı.

## Karar
**Her servis OTLP ile tek bir toplayıcıya yazar; iz bağlamı W3C `traceparent` ile HTTP'den ve kuyruktan geçer.**

- **Toplayıcı:** OpenTelemetry Collector. Servisler arka ucu bilmez; arka uç değişirse servisler değişmez.
  İzler Tempo'ya, metrikler Prometheus'a, loglar Loki'ye gider ([ADR-0018](0018-slo-alerts-dashboards.md)).
- **API:** `spring-boot-starter-opentelemetry` (Micrometer köprüsü). HTTP istekleri ve AI servisi çağrıları
  span ve süre histogramıdır (`http.server.requests`, `meridian.ai.request`). AI çağrısına `traceparent` eklenir.
- **Kuyruk:** olayı yazan isteğin `traceparent` değeri outbox'ta saklanır (V8), aktarıcı mesaj başlığına koyar,
  AI servisindeki işleme span'ı aynı izin devamıdır. Böylece "kaynak ekle" isteği ile indeksleme tek izdedir.
- **AI servisi:** FastAPI ve httpx otomatik; model, arama ve embedding dışarıdan sarılır (`observability.py`).
  Ölçülen dosyalar değişmez, değerlendirme raporlarının parmak izi geçerli kalır. Metrikler: model süresi,
  ilk token, token sayısı, arama süresi, indeksleme süresi, cevap sonucu (`answered`, `abstained`, `degraded`),
  ajan durumu.
- **Web:** `@vercel/otel` yalnızca sunucuda; API'ye giden çağrıya `traceparent` ekler, başka adrese eklemez.
  Tarayıcıdan gelen `traceparent` vekilde API'ye iletilmez.
- **Loglar:** JSON (API'de ECS). Her satırda `traceId`, `spanId` ve istek kiracıya aitse `tenant.id`.
  Kullanıcı kimliği, soru ve belge metni yazılmaz; PII maskesi (ADR-0016) log yolunda kalır.
- **Gönderim anahtarı:** `OTEL_EXPORT=true` ve `OTEL_ENDPOINT`. Kapalıyken span ve iz kimliği yine üretilir ve
  taşınır, yalnızca dışarı yazılmaz. Örnekleme `OTEL_SAMPLING` (varsayılan 1,0).

## Doğrulama
- API: AI servisine giden çağrıda `traceparent` var (`ChatApiTest`); outbox başlığı olayı yazan span'ın izini
  taşır, izsiz olayda başlık yok (`OutboxRelayTest`); kiracı log bağlamında yalnızca istek boyunca durur.
- AI servisi: API'den gelen iz kimliği arama ve model span'larında sürer, soru ve belge metni hiçbir span'da yok;
  kuyruk mesajındaki iz işleme span'ında sürer; cevap sonucu sayılır; log satırı JSON (`test_internal_api.py`,
  `test_consumer.py`).
- Tam sistem: tek bir sohbet sorusunun izi Tempo'da tam olarak `meridian-web`, `meridian-api`, `meridian-ai`
  servislerini içerir; kaynak ekleme izi kuyruktan geçip AI servisinde sürer (`e2e-full`).

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **OTLP + Collector** | Satıcıdan bağımsız, tek protokol, arka uç değişimi servis değişikliği istemez | Bir süreç daha |
| Doğrudan Prometheus kazıma + ayrı log toplayıcı | Yaygın | Üç ayrı yol; iz ve metrik ayrı kimlikle |
| OpenTelemetry Java ajanı | Kodsuz | Spring'in gözlem API'siyle çift span; sürüm uyumu kırılgan |
| Ölçülen kodun içine span eklemek | Daha ince ayrıntı | Her değişiklik saatler süren yeniden ölçüm ister (ADR-0016) |
| Kuyrukta yeni iz başlatıp bağ (link) kurmak | Uzun işler ayrı görünür | İstek ile indeksleme tek bakışta görülmez |

## Sonuçlar
**Olumlu**
- Yavaş bir cevabın nerede beklediği (arama, kanıt, cevap) tek izde görülür.
- İzleme kapalıyken de iz kimliği loglarda durur; bir hata satırı ilgili isteğe bağlanabilir.

**Olumsuz / kabul edilen riskler**
- Tarayıcı span'ı yok: iz web sunucusunda başlar. Tarayıcı SDK'sı ilk JS bütçesini zorlar; ölçülmeden eklenmez.
- Spring Boot 4.1'de iz bağlamının taşınması genel dışa aktarım anahtarına bağlıdır; bu yüzden yalnızca OTLP
  gönderimi kapatılır. Testler `@AutoConfigureTracing` ile üretimdeki gibi çalışır.
- Örnekleme 1,0: yerelde ve testte doğru, üretimde yük testine göre düşürülmeli.
- Ajan adımları ayrı span değil; model çağrıları ve arama span olarak görünür.
- Tempo tek süreç ve yerel diskte: yalnızca geliştirme ve test içindir.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
Gönderim ortam değişkeniyle kapanır; kaldırmak bağımlılıkları ve sarmalayıcıları silmektir. Outbox sütunu boş
kalabilir. İzleme yükü yük testinde p95'i belirgin artırırsa örnekleme düşürülür ya da toplu gönderim ayarlanır.
