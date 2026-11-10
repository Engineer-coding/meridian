# ADR-0019: Yük testi: k6, sahte model ve ölçülerek bulunan darboğazlar

- Durum: Kabul edildi
- Tarih: 2026-11-10

## Bağlam
Plan, 500 eşzamanlı sohbet ve 50 eşzamanlı indeksleme işiyle bir yük testi ve darboğaz raporu ister; hedefler
tam cevap p95 < 8 sn, başarı > %99,5, 10 sayfalık belge p95 < 60 sn. Bu makinede yerel model bir cevabı
dakikalar içinde üretir: gerçek modelle 500 eşzamanlı sohbet ölçülemez, ölçülse de modelin değil donanımın
sınırı görülür. Sorular: neyi ölçeceğiz, model nasıl temsil edilecek, ortam üretime ne kadar benzeyecek?

## Karar
**Sistemi ölçmek için modeli sahte ama gecikmeli tutarız; darboğazı tahminle değil izle ve profille buluruz.**

- **Araç:** k6, Docker'da (`packages/load`, `make load`). Kurulum gerektirmez, betik depodadır.
- **Model:** sahte, gecikmesi ayarlanabilir (`MODEL_DELAY`, varsayılan kanıt 1 sn + cevap 3 sn: barındırılan bir
  modele yakın). Embedding sahte (`HashEmbedder`); gerçek embedding'in maliyeti ayrıca ölçülür.
- **Ortam:** atılabilir altyapı (`compose.e2e.yaml`); API JVM'de, AI servisi üretim imajında, Linux
  kapsayıcısında (`apps/ai-service/Dockerfile`). Windows'ta psycopg'nin `select()` döngüsü ~512 soketle
  sınırlıdır ve 500 akışta istek kaybettirir; bu geliştirme makinesinin sınırıdır, üretimin değil.
- **Ölçüm:** k6 istemcinin gördüğünü, Prometheus aynı penceredeki sunucu tarafını (ilk token, arama, havuz
  bekleyişi, işlemci) verir. Yavaş istekler Tempo'da açılır, işlemci `py-spy` ile profillenir.
- **Varsayılanlar ölçümle değişti:** API veritabanı havuzu 10 → 20 (`API_DB_POOL_SIZE`); AI servisine süreç
  sayısı ayarı (`HTTP_WORKERS`, Linux'ta); belgedeki talimat taraması önbelleğe alındı. AI havuzu 4'te kaldı:
  20'ye çıkarmak sonucu değiştirmedi.

## Ölçüm
500 eşzamanlı sohbet, son yapılandırma: tam cevap p50 / p95 / p99 = 4,3 / 7,4 / 8,1 sn, ilk olay p95 1,4 sn,
saniyede 68 cevap, %99,97 tamamlanan, 42.326 istekte 0 başarısız. Başlangıçta (AI servisi Linux'ta, eski
varsayılanlar) p95 13,4 sn ve saniyede 42 cevaptı. Adım adım tablo ve darboğazlar `packages/load/README.md`'de.

50 eşzamanlı indeksleme: 50/50 hazır, p95 5,3 sn (sahte embedding). Gerçek e5-large ile tek bir 10 sayfalık
belge bu makinede ~42 sn: tek belge hedefi tutar, 50 belge aynı anda gelirse kuyruk kabaca yarım saatte boşalır
(tahmin).

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Sahte, gecikmeli model** | Sistemin kapasitesi ayrı görülür, tekrarlanabilir | Modelin gerçek davranışı (değişken süre, token sayısı) yok |
| Gerçek yerel model | Gerçekçi | CPU'da dakikalar; donanım ölçülür, sistem değil |
| Barındırılan model API'si | Gerçekçi gecikme | Maliyet, oran sınırı, veri dışarı çıkar |
| AI servisini Windows'ta ölçmek | Kurulum yok | `select()` sınırı yüzünden geliştirme makinesi ölçülür |
| Gatling / Locust | Olgun | k6 betiği küçük, Docker'da tek komut |

## Sonuçlar
**Olumlu**
- Darboğazlar sırayla ve kanıtla bulundu: platform sınırı, tek çekirdek, pahalı bir koruma, API havuzu.
- AI servisi için üretim imajı hazır; Kubernetes adımı onu kullanır.

**Olumsuz / kabul edilen riskler**
- Tek makine: yük üreten ve ölçülen aynı işlemcileri paylaşır; sayılar bu makineye özgüdür.
- Web sunucusundaki oturum vekili testte yok; API doğrudan çağrıldı.
- Gerçek embedding ile eşzamanlı indeksleme ölçülmedi; sınır tahmindir.
- API havuzunda hâlâ en çok 126 istek bekledi: bir sonraki ölçek adımında ilk bakılacak yer.
- "İlk token p95 < 1,5 sn" hedefi bu donanımda ölçülemez.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
Ayarlar ortam değişkenleridir. Gerçek dağıtım ortamı (Kubernetes) kurulunca test oraya karşı tekrarlanır;
barındırılan ya da GPU'lu model gelince model gecikmesi ölçülen değerle değiştirilir.
