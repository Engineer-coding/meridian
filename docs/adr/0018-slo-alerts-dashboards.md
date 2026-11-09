# ADR-0018: SLO'lar, yanma hızı alarmları ve kod olarak paneller

- Durum: Kabul edildi
- Tarih: 2026-11-09

## Bağlam
ADR-0017 izleri, metrikleri ve logları toplayıcıya taşıdı. Plan ayrıca Grafana panelleri, SLO tabanlı (yanma hızı)
alarmlar ve şu hedefleri ister: API kullanılabilirliği %99,5; ilk token p95 < 1,5 sn; 10 sayfalık belge p95 < 60 sn
indekslenir. ADR-0011 DLQ derinliği için alarm sözü verdi. Sorular: hangi arka uçlar, hangi hedef alarm üretir,
alarm eşikleri nasıl sınanır?

## Karar
**Metrik Prometheus'ta, log Loki'de, iz Tempo'da; kurallar, testleri ve paneller depoda kod.**

- **Akış:** servisler → Collector → Prometheus (kazıma), Loki (OTLP), Tempo. Kuyruk derinliği RabbitMQ'nun kendi
  Prometheus ucundan. Grafana veri kaynaklarını ve paneli dosyadan yükler; arayüzde yapılan değişiklik kalıcı
  değildir. İzden loga, logdaki `trace_id`'den ize geçilir.
- **Kullanılabilirlik SLO'su:** 30 günde 5xx olmayan isteklerin oranı ≥ %99,5; sağlık uçları sayılmaz, 4xx
  bütçeden düşmez. Çok pencereli yanma hızı: 14,4 kat (1 sa ve 5 dk) acil, 6 kat (6 sa ve 30 dk) kayıt.
- **İndeksleme:** 60 saniyede biten olay oranı < %95 ise 30 dakika sonra kayıt (`IndexingSlow`).
- **Kuyruk:** DLQ'da 5 dakika mesaj (`IndexingDeadLetters`), kuyrukta 10 dakika 100'den fazla mesaj.
- **Model:** cevapların %10'undan fazlası 10 dakikada modelsiz dönerse acil (`AnswersDegraded`); en az 5 cevap
  şartıyla tek hata alarm üretmez. "Bilmiyorum" oranı %50'yi bir saat aşarsa kayıt (kalite sinyali).
- **İlk token:** kayıt kuralı ve panel var, **alarm yok**. Bu donanımda yerel modelle ilk token dakikalar sürer;
  her zaman ateşlenen alarm gürültüdür. Barındırılan ya da GPU'lu model gelince alarm eklenir.
- **Sınama:** `make obs-check` kural sözdizimini, yapılandırmayı ve `promtool test rules` ile alarm eşiklerini
  sentetik seriyle sınar (CI, `infra-smoke`). Tam sistem testi Prometheus'ta gerçek metriklerin, sağlıklı
  kuralların, Loki'de iz kimlikli logların ve Grafana'da panel ile üç veri kaynağının olduğunu denetler.
- Her alarm bir runbook'a bağlanır: `docs/runbooks/api-errors.md`, `queue-backlog.md`, `llm-outage.md`.

## Doğrulama
- Alarm testleri: %10 hata hızlı yanmayı ateşler; %0,2 hata ve sağlık ucundaki 500'ler ateşlemez; DLQ'daki mesaj
  5. dakikadan önce değil sonra ateşler; az trafikte tek bozuk cevap alarm üretmez. Sağlık ucu filtresi kurala
  bilerek bozulunca test kırıldı.
- Panelde 5xx hiç yokken kullanılabilirlik "veri yok" görünüyordu (boş seriye bölme); hata tarafı yoksa sıfır
  sayılacak şekilde düzeltildi.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Prometheus + Loki + Tempo + Grafana** | Açık kaynak, yerelde çalışır, veri kaynakları birbirine bağlanır | Dört süreç |
| Tek eşikli alarm (hata > %1, 5 dk) | Basit | Kısa sıçramada gürültü, yavaş sızıntıyı kaçırır |
| Grafana alarmları | Tek arayüz | Kurallar ve testleri `promtool` ile sınanamaz |
| Panelleri arayüzde çizip dışa aktarmak | Hızlı | Gözden geçirilemez, sürümler arası kayar |
| Barındırılan izleme hizmeti | Bakım yok | Maliyet, veri dışarı çıkar |

## Sonuçlar
**Olumlu**
- Alarm eşiği değişikliği kod incelemesinden ve testten geçer.
- Bir hata bildiriminden ize, oradan log satırına iki tıkla gidilir.

**Olumsuz / kabul edilen riskler**
- Alertmanager yok: alarmlar Prometheus'ta ve paneldeki listede görünür, kimseye bildirilmez. Bildirim kanalı
  dağıtım ortamıyla birlikte (Kubernetes adımı) eklenir.
- Test trafiği az ve kısa: model ve indeksleme panelleri yük testinde dolu görülecek; eşikler o zaman gözden geçirilir.
- 30 günlük pencere yerelde anlamsız kısalır; kullanılabilirlik değeri yerelde birkaç saatin değeridir.
- Tek süreçli Loki, Tempo ve Prometheus yalnızca geliştirme ve test içindir; saklama 3-7 gün.
- Kiracı etiketi metriklerde yok (yüksek kardinalite); kiracı başına maliyet yönetim panelindedir.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
Arka uçlar toplayıcının arkasındadır; birini değiştirmek yalnızca toplayıcı ve Grafana yapılandırmasını değiştirir.
Yük testinde alarmlar gereksiz ateşlenirse ya da gerçek bir sorunu kaçırırsa eşikler yeniden ayarlanır.
