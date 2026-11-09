# ADR-0011: Kuyruk tüketicisi: yeniden deneme, DLQ ve teslim garantisi

- Durum: Kabul edildi
- Tarih: 2026-11-02

## Bağlam
AI servisi `ai.indexing` kuyruğundan kaynak olaylarını (`source.created`, `source.deleted`) alır
(ADR-0004). İndeksleme dış sistemlere bağlıdır (GitHub, web siteleri, embedding sağlayıcısı) ve
bunlar geçici olarak hata verebilir. Bazı hatalar ise kalıcıdır (depo yok, mesaj bozuk) ve kaç
kez denenirse denensin düzelmez. İki uç da kötüdür:

- Hatalı mesajı hemen kuyruğa geri koymak, onu saniyede yüzlerce kez işlemeye çalışan bir döngü
  yaratır ve arkasındaki mesajları bekletir.
- Hatalı mesajı atmak, kaynağı sessizce `pending` durumda bırakır.

RabbitMQ'nun yerleşik gecikmeli teslimatı yoktur (eklenti gerekir).

## Karar
**Her mesajın tek bir son durumu vardır: onay, gecikmeli yeniden deneme ya da DLQ.**

| Durum | Ne olur |
|---|---|
| İşlendi | `ack` |
| Zarf okunamıyor; `message_id` veya `tenant_id` başlığı gövdeyle uyuşmuyor | `reject` → `meridian.dlx` → `ai.indexing.dlq`, işleyici hiç çağrılmaz |
| İşleyici `PermanentError` attı (bilinmeyen olay türü dahil) | `reject` → DLQ |
| Başka herhangi bir hata (geçici sayılır) | Kopya `ai.indexing.retry.N`'e yazılır, onaylanınca asıl mesaj `ack` |
| Deneme hakkı (`max_retries`, varsayılan 4) bitti | `reject` → DLQ |
| Tüketici onay vermeden çöktü | Broker yeniden teslim eder; 5. teslimattan sonra DLQ (`x-delivery-limit`) |

- **Bekleme kuyrukları:** `ai.indexing.retry.1..N`, tüketicisi olmayan quorum kuyruklardır.
  Mesaj, süresi (`expiration`) dolunca varsayılan exchange üzerinden `ai.indexing`'e döner.
  Deneme sayısı `x-retry-count` başlığında taşınır.
- **Süre:** N. deneme için üst sınır `base · factor^(N-1)` (varsayılan 1 s, 4 s, 16 s, 64 s);
  gerçek süre bunun yarısı ile tamamı arasında rastgeledir (*equal jitter*). Aynı anda düşen
  mesajlar aynı anda geri dönüp sağlayıcıyı yeniden boğmaz.
- **Neden her deneme ayrı kuyruk:** RabbitMQ süresi dolan mesajı yalnızca kuyruğun başından
  çıkarır. Tek kuyrukta 64 sn bekleyen mesaj, arkasındaki 1 sn'lik mesajı da bekletirdi. Bir
  katmandaki süreler en fazla jitter kadar farklıdır, gecikme sapması bununla sınırlıdır.
- Bekleme kuyrukları `x-dead-letter-strategy: at-least-once` kullanır: mesaj ana kuyruğa
  aktarımı onaylanana kadar bekleme kuyruğunda kalır.
- **Teslimat en az bir kezdir.** Kopya yazılıp broker onaylamadan asıl mesaj onaylanmaz; arada
  çökülürse mesaj iki kez işlenebilir ama kaybolmaz. İşleyiciler `eventId` ile idempotent
  olmalıdır; kalıcı tekrar ayıklaması indeksleme durumuyla birlikte veritabanında yapılır (Adım 16).
- Ana topoloji (exchange'ler, `ai.indexing`, DLQ) iki tarafta da aynı argümanlarla tanımlanır;
  hangi servis önce başlarsa başlasın sonuç aynıdır. Argümanlar farklılaşırsa RabbitMQ
  `PRECONDITION_FAILED` verir; servis bağlanmayı denemeye devam eder ve `/health/ready` 503 döner.
- `/health/live` broker kapalıyken de UP'tır (yeniden başlatmak broker'ı açmaz); `/health/ready`
  yalnızca tüketici kuyruğu dinlerken UP'tır.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| `nack(requeue=True)` | En basit | Bekleme yok: sıkı döngü, arkadaki mesajlar bekler |
| `rabbitmq_delayed_message_exchange` eklentisi | Tek exchange, istenen gecikme | Resmî destek dışı eklenti, gecikmedeki mesajlar çoğaltılmaz (düğüm kaybında kaybolur) |
| Tek bekleme kuyruğu, mesaj başına süre | Daha az kuyruk | Kuyruk başı engellemesi (yukarıda) |
| Tüketici içinde `sleep` ile yeniden deneme | Altyapı gerektirmez | Prefetch slotunu kilitler; süreç ölürse deneme sayısı kaybolur |
| Celery / Dramatiq | Hazır retry | Kendi mesaj biçimi ve topolojisi; ADR-0004'teki zarfla uyum ek iş |

## Sonuçlar
**Olumlu**
- Geçici bir sağlayıcı kesintisi mesaj kaybettirmez; kalıcı hata kuyruğu tıkamaz.
- DLQ'daki mesaj gövdesi ve başlıklarıyla (deneme sayısı, `x-death`) incelenip panelden yeniden
  yayımlanabilir.
- Kiracı kimliği başlıkla gövde arasında çapraz denetlenir (tehdit T15).

**Olumsuz / kabul edilen riskler**
- Ana kuyruğun ölü mektup stratejisi varsayılan (*at-most-once*); DLX'e aktarım sırasında broker
  çökerse mesaj kaybolabilir. Değiştirmek kuyruğun yeniden oluşturulmasını gerektirir; DLQ
  hacmi düşük olduğu için şimdilik kabul edildi.
- Bekleme süreleri katman sayısıyla sabitlenir; `max_retries` artırılırsa yeni kuyruklar
  otomatik tanımlanır, azaltılırsa eskiler elle silinir.
- DLQ'yu boşaltan otomatik bir süreç yoktur; DLQ'da 5 dakika bekleyen mesaj alarm üretir (`IndexingDeadLetters`,
  [ADR-0018](0018-slo-alerts-dashboards.md)), işlem adımları [runbook](../runbooks/queue-backlog.md)'tadır.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Düşük.** Karar mantığı tek bir sınıftadır (`IndexingConsumer`); işleyiciler yalnızca
`PermanentError` ile diğer hataları ayırır.

Tetikleyiciler:
- DLQ'ya düşen mesajların oranı günlük %1'i geçerse (sınıflandırma yanlış olabilir).
- Mesaj başına farklı gecikme gerekirse (ör. sağlayıcının `Retry-After` değeri).
