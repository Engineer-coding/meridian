# ADR-0015: Ajan ve MCP sunucusu

- Durum: Kabul edildi
- Tarih: 2026-11-07

## Bağlam
Plan, açık durum makinesi olan bir ajan (arama, belge okuma, salt-okunur SQL, sahte ticket) ve kiracının
koleksiyonlarını başka ajanlara açan bir MCP sunucusu ister. Belgeler güvenilmeyen veridir (T18); küçük
yerel model de güvenilir karar vermez. Üç soru belirleyicidir: model neyi yapabilir, ne yazılabilir, MCP
üzerinden yetkiye kim karar verir?

## Karar
**Model yalnızca eylem önerir. Eylemin geçerliliğine, sayısına ve etkisine kod karar verir.**

- **Durum makinesi:** `PLAN → ACT → OBSERVE`, `WAIT_APPROVAL`, `FINISH`, `STOPPED`. Geçişler veri olarak
  tanımlıdır. AI servisi durumsuzdur; geçmiş her çağrıda çekirdek API'den gelir.
- **Daraltma:** her adımda izinli eylemler JSON şemasıyla verilir ve çıktı kodla yeniden denetlenir. Ticket
  yalnızca görev isterse, belge yalnızca aramada görüldüyse seçilebilir; hiçbir iş yapılmadan bitirilemez.
- **Cevap:** model son cevabı JSON içinde yazmaz. Cevap, kaynaklı sohbetin ölçülen hattından geçer (kanıt
  alıntısı kodla doğrulanır, doğrulanamazsa "bilmiyorum"). Var olmayan atıf cevaptan çıkarılır.
- **Yazma:** ticket'ı yalnızca çekirdek API, insan onayından sonra yazar. Onay gövdesinde içerik alınmaz,
  kayıtlı öneri kullanılır. Durum değişikliği tek sorguda olduğu için çift onay ikinci ticket üretemez.
  AI servisinin `tickets` ve `agent_runs` tablolarına yetkisi yoktur.
- **Bütçe:** 6 adım, 12.000 token, parça başına 240 sn; onay öncesi harcanan token sonraki parçaya sayılır.
  Adım dolunca yeni araç çalışmaz, elde olanla cevap yazılır. Üst üste iki bozuk çıktı çalıştırmayı durdurur.
- **SQL:** RLS kiracıyı `app.tenant_id` ayarından okur; modelin yazdığı `set_config` bu ayarı değiştirebilir
  ve READ ONLY işlem bunu engellemez. Bu yüzden sorgu ayrıştırılır: tek SELECT, yalnızca iki
  `security_invoker` görünüm, izin listesindeki fonksiyonlar, CTE ve tür dönüşümü yok. Çalıştırılan metin
  ağaçtan yeniden üretilir; işlem salt-okunur, süre sınırlı, satır sınırlıdır.
- **MCP:** resmî SDK, durumsuz Streamable HTTP, `POST /mcp/` (AI servisi). Başlıklar `X-API-Key` ve
  `X-Tenant-Id`. Üç salt-okunur araç: `list_collections`, `search_knowledge`, `fetch_document`. Sunucu yetki
  kararı vermez, veritabanına bağlanmaz: her çağrı istemcinin anahtarıyla çekirdek API'ye gider ve
  `sources:read` kapsamı, RLS, oran sınırı orada uygulanır. Host başlığı denetlenir (DNS yeniden bağlama).
- **Gizlilik:** çalıştırma kişiye özeldir (RLS). Görev metni denetim kaydına yazılmaz.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Kendi durum makinesi** | Az kod, her geçiş test edilir, sağlayıcıdan bağımsız | Çoklu ajan, kalıcı grafik gibi özellikler yok |
| LangGraph | Hazır kontrol noktaları | Yeni bağımlılık; dört araçlık döngü için fazla |
| Sağlayıcının yerel araç çağırma özelliği | Standart | Küçük modellerde güvenilmez; eylem listesi şemayla daraltılamaz |
| SQL'de metin filtresi | Basit | Tırnaklı ad ve yorumlarla aşılır; `set_config` riski açık kalır |
| SQL için ayrı veritabanı rolü | Derinlemesine savunma | `set_config` yine çağrılabilir, tek başına çözmez; ileride eklenebilir |
| MCP'yi doğrudan veritabanına bağlamak | Bir ağ adımı az | Anahtar, kapsam ve oran sınırı ikinci kez yazılır |

## Sonuçlar
**Olumlu**
- Belgedeki bir talimat kendi başına yazma yapamaz: görev izni, kod denetimi ve insan onayı gerekir.
- MCP yetki kuralları REST API ile aynı koddan gelir; kiracı sızıntı paketi yeni uçları kapsar.

**Olumsuz / kabul edilen riskler**
- Ayrıştırıcı farkı riski: `sqlglot` ile PostgreSQL bir ifadeyi farklı okuyabilir. Yeniden üretilen metnin
  çalıştırılması ve fonksiyon izin listesi bunu azaltır, sıfırlamaz.
- Görev "ticket" kelimesi içeriyorsa belge etkisiyle yanlış içerikli öneri çıkabilir; son kapı insandır.
- Ticket çalıştırmayı bitirir: önce arama, sonra ticket isteyen görevde arama sonucu cevaba yazılmaz.
- Kullanıcı başına tek etkin çalıştırma; API çökerse kayıt 10 dakika sonra serbest kalır.
- Canlı istem enjeksiyonu kırmızı takım setiyle henüz ölçülmedi (sıradaki adım).
- OAuth yok; MCP yalnızca API anahtarıyla çalışır.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Orta.** Ajan tek modülde, MCP ince bir vekildir.

Tetikleyiciler:
- Birden çok yazma aracı ya da uzun süren iş gerekirse: kalıcı iş akışı motoru.
- Ajan ölçümü güçlü bir modelle yeterli çıkarsa: yerel araç çağırma yeniden denenebilir.
- MCP dış ağa açılırsa: OAuth ve ayrı oran sınırı.
