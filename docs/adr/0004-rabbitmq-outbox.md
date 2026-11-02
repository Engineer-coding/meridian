# ADR-0004: RabbitMQ ve transactional outbox

- Durum: Kabul edildi
- Tarih: 2026-11-02

## Bağlam
Bir kaynak eklendiğinde çekirdek API iki şey yapmalıdır: kaynağı veritabanına yazmak ve AI
servisine "bunu indeksle" demek. Bu ikisi farklı sistemlerdir (PostgreSQL ve mesaj kuyruğu) ve
ortak bir işlem (transaction) yoktur. Saf "önce yaz, sonra yayımla" yaklaşımı iki hataya açıktır:

- Kayıt commit olur, yayın başarısız olur → kaynak sonsuza kadar `pending` kalır.
- Yayın yapılır, kayıt rollback olur → AI servisi var olmayan bir kaynağı indeksler.

İndeksleme dakikalar sürebilir, başarısız olabilir ve yeniden denenmelidir; bu yüzden asenkrondur.
Olay hacmi düşüktür (kaynak başına birkaç olay), ama hiçbiri kaybolmamalıdır.

## Karar
**Olaylar iş kaydıyla aynı PostgreSQL işleminde bir `outbox` tablosuna yazılır; ayrı bir
aktarıcı onları RabbitMQ'ya yayımlar ve broker onayından sonra siler.**

- `OutboxWriter` çağıranın işlemine katılır (`Propagation.MANDATORY`); işlem dışında çağrılamaz.
- Aktarıcı her 500 ms'de en fazla 100 olayı okur, yayımlar, **publisher confirm** bekler, sonra
  satırları kimlik listesiyle siler. Onay gelmezse işlem geri alınır ve olaylar yerinde kalır.
- Birden fazla API örneğinde aynı anda tek aktarıcı çalışır (`pg_try_advisory_xact_lock`):
  sıra korunur ve aynı olay iki örnekten eşzamanlı yayımlanmaz.
- Teslimat **en az bir kezdir**. Mesajın `message_id` alanı `event_id`'dir; tüketiciler tekrarı
  bununla ayıklar (idempotent tüketici, ADR-0001).
- Veritabanı rolleri (ADR-0002 ile uyumlu):
  - `meridian_app` outbox'a yalnızca **ekleyebilir**, yalnızca bağlamdaki kiracı adına (RLS).
    Okuyamaz, silemez: bir istek başka kiracıların olaylarını göremez.
  - `meridian_relay` tüm kiracıların olaylarını okuyup silebilir ama **başka hiçbir tabloya**
    erişemez ve olay ekleyemez. Bağlantı havuzu Spring bean'i değildir; başka kod enjekte edemez.

### Topoloji

| Ad | Tür | Not |
|---|---|---|
| `meridian.events` | topic exchange | Yönlendirme anahtarı = olay türü (`source.created`, `source.deleted`) |
| `ai.indexing` | quorum kuyruk | `source.*` ile bağlı; teslim sınırı 5; aşan mesaj DLX'e |
| `meridian.dlx` | direct exchange | Ölü mektup exchange'i |
| `ai.indexing.dlq` | quorum kuyruk | Panelden incelenip yeniden denenecek mesajlar |

Topolojiyi yayımlayan taraf (çekirdek API) tanımlar: kuyruk ilk olaydan önce var olmalıdır.
Gecikmeli yeniden deneme kuyrukları tüketicinin sorumluluğundadır (Adım 15).

### Mesaj zarfı

```json
{
  "eventId": "uuid", "type": "source.created", "tenantId": "uuid",
  "aggregateId": "uuid", "occurredAt": "RFC 3339",
  "data": { "sourceId": "uuid", "collectionId": "uuid", "type": "github", "config": { } }
}
```

Başlıklar: `message_id = eventId`, `type`, `tenant_id`, `content_type: application/json`,
kalıcı teslim (`delivery_mode = 2`). `config` varsayılanları doldurulmuş hâliyle gönderilir.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| Doğrudan yayın (işlem sonrası) | Basit | Commit ile yayın arasındaki çökmede olay kaybolur |
| Kafka | Yüksek hacim, yeniden oynatma | Bu hacim için ağır operasyon; DLQ/retry kendin kurulur |
| PostgreSQL'i kuyruk olarak kullanmak (`SKIP LOCKED`) | Tek sistem | Python tüketici havuzu, DLQ, görünürlük yeniden yazılır; DB yükü artar |
| Debezium (CDC) ile outbox | Yoklama yok, düşük gecikme | Kafka Connect + replikasyon slotu operasyonu; v0 için fazla |
| Spring Modulith Event Publication Registry | Hazır | Olay tablosunu JPA/kendi şemasıyla yönetir; RLS ve rol ayrımıyla uyumu ek iş |

## Sonuçlar
**Olumlu**
- "Kayıt var, olay yok" veya "olay var, kayıt yok" durumu oluşamaz (test: rollback'te olay kalmaz).
- Broker kapalıyken API çalışmaya devam eder; olaylar outbox'ta bekler ve broker dönünce iletilir
  (yerelde RabbitMQ durdurularak doğrulandı).
- Olay kimlik ve kiracı bilgisini taşır; tüketici kiracı bağlamını mesajdan kurar.

**Olumsuz / kabul edilen riskler**
- Yoklama gecikmesi (≤ 500 ms) ve boşken bile periyodik sorgu. Gerekirse `LISTEN/NOTIFY` eklenir.
- Tek aktarıcı yatay ölçeklenmez; saniyede yüzlerce olayın üzerine çıkılırsa yeniden ele alınır.
- Okuma anında commit edilmemiş, daha küçük kimlikli bir olay bir sonraki partiye kalabilir:
  küresel sıra "neredeyse"dir. Tüketiciler sıraya değil, olayın kendisine güvenir.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Düşük.** Yazma tarafı tek bir arayüzdür (`OutboxWriter.append`); aktarıcı CDC'ye (Debezium) veya
başka bir broker'a geçirilebilir, iş kodu değişmez.

Tetikleyiciler:
- Outbox gecikmesi (en eski bekleyen olayın yaşı) p95'te 5 saniyeyi geçerse.
- Olay hacmi sürekli 200 olay/sn'yi geçerse.
- Olayların yeniden oynatılması (replay) bir ürün gereksinimi olursa (→ Kafka değerlendirilir).
