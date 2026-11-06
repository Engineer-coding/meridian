# ADR-0014: Denetim kaydı, token kotası ve API anahtarları

- Durum: Kabul edildi
- Tarih: 2026-11-07

## Bağlam
Yönetim paneli üç veriye dayanır: kimin ne yaptığı, ne kadar kaynak harcandığı ve sisteme tarayıcı
dışından nasıl erişildiği. Sözleşmede `X-API-Key` şeması ve kota hatası tanımlıydı, kodu yoktu. Rol
denetimi yalnızca bilgi modülündeydi; yeni uçlar bunu ya kopyalayacak ya da modül sınırını delecekti.

## Karar
**Rol denetimi ve denetim kaydı tek modülde (`audit`); kullanım ayrı modülde (`usage`); anahtarlar ayrı
modülde (`apikeys`).** Üç tablo da RLS altındadır.

- **Denetim kaydı:** başarılı değişiklikler iş işlemiyle birlikte yazılır, iş geri alınırsa kayıt da
  kalmaz. Reddedilen karar, işlem geri alındıktan sonra ayrı işlemde yazılır. Uygulama rolü kaydı
  güncelleyemez, silemez. Okumalar kaydedilmez. **Soru metni yazılmaz:** konuşmalar kişiye özeldir (T20),
  kaydı yöneticiler okur.
- **Token sayımı:** AI servisi sağlayıcının sayaçlarını istek başına bir sayaçta toplar ve "done" olayıyla
  API'ye iletir; değer istemciye gitmez. Akış kesilirse sayaç gelmez: metin uzunluğundan tahmin edilir ve
  `estimated` işaretlenir. Hiç metin yoksa model çalışmamış sayılır, kayıt yazılmaz.
- **Kota:** plan başına günlük token, gün sınırı UTC. Denetim model çağrılmadan önce yapılır, 429 ve
  `quota-exceeded` problem türü döner. Maliyet yapılandırılan fiyattan hesaplanır; yerel modelde 0.
- **API anahtarı:** 256 bit rastgele değer, yalnızca SHA-256 özeti saklanır, bir kez gösterilir. Kapsam ve
  süre zorunludur. Anahtar oluşturan kullanıcı adına çalışır: rolü düşerse anahtar da düşer, üyeliği kalkarsa
  çalışmaz. Kapsam listesinde olmayan uç reddedilir, bu yüzden anahtar yönetimi, kullanım ve denetim uçları
  yalnızca oturumla açılır. Arama, adresteki kiracının bağlamında yapılır: RLS'i atlayan rol gerekmez.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Veritabanında sayım + yumuşak kota** | Tek kaynak, RLS altında, kaybolmaz | Eşzamanlı sorular sınırı bir cevap kadar aşabilir |
| Redis'te atomik sayaç | Sınır kesin | Redis kapalıyken ya sınırsız ya kapalı; muhasebe yine veritabanı ister |
| Anahtarı bcrypt/argon2 ile saklamak | Zayıf parolaya karşı dayanıklı | Değer zaten rastgele; her istekte pahalı, gereksiz |
| Anahtarı kullanıcıdan bağımsız servis hesabı yapmak | Kişi ayrılınca anahtar sürer | Rol modeli genişler; şimdilik gereksiz |
| Denetim kaydını ayrı işlemde yazmak (`REQUIRES_NEW`) | İş düşse de deneme görünür | Bağlantı havuzunda kilitlenme riski; olmayan bir değişiklik "yapıldı" görünebilir |

## Sonuçlar
**Olumlu**
- Yeni uçların yetki kararı ve kaydı tek arayüzden geçer.
- Kiracı sızıntı paketi yeni uçları sözleşmeden kendiliğinden kapsar.

**Olumsuz / kabul edilen riskler**
- Kota yumuşaktır; kesin bütçe sınırı değildir.
- Anahtar kişiye bağlıdır: oluşturan ayrılınca anahtar durur.
- Kullanıcı silinince denetim kaydındaki e-posta görünmez, kimliği kalır.
- Yerel Ollama dışında sağlayıcı sayacı henüz yok; eklenince aynı sayacı doldurması gerekir.
- Eşzamanlı indeksleme ve API çağrısı kotası yok (planda var): henüz yalnızca günlük token.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Düşük-orta.** Tablolar yalnızca eklenen kayıtlar tutar; uçlar sözleşmeden üretilir.

Tetikleyiciler:
- Ücretli sağlayıcı ya da kesin bütçe gerekirse: Redis'te rezervasyonlu kota.
- Kayıt hacmi büyürse: `audit_log` ve `usage_events` için zamana göre bölümleme ve saklama süresi.
