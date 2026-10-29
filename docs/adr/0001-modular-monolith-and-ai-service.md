# ADR-0001: Modüler monolit çekirdek ve ayrı AI servisi

- Durum: Kabul edildi
- Tarih: 2026-10-29

## Bağlam
Meridian'da iki farklı iş yükü var:

1. **Ürün çekirdeği:** kiracı, kimlik, yetki, kota, sohbet kaydı ve denetim kuralları.
   Güçlü tutarlılık ve tek veritabanı işlemi gerektirir; istekler kısa sürelidir.
2. **AI iş yükü:** ayrıştırma, parçalama, embedding, retrieval, reranking ve LLM çağrıları.
   Python ekosistemine bağlıdır; uzun süren, CPU/GPU yoğun ve farklı ölçeklenen işlerdir.

Ekip tek kişidir; operasyon yükü minimum olmalı, ama sınırlar ileride ayrıştırmaya izin vermelidir.

## Karar
Çekirdek, Spring Modulith ile **modüler monolit** (Java) olarak; AI iş yükü **ayrı bir
FastAPI servisi** olarak geliştirilir. Modül sınırları ArchUnit / Modulith testleriyle CI'da zorlanır.

Çekirdek modüller: `identity`, `tenancy`, `sources`, `ingestion`, `conversations`,
`agents`, `usage`, `audit`. Modüller birbirinin iç paketlerine erişemez; iletişim yayınlanmış
arayüzler ve uygulama olaylarıyla olur.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| Tek monolit (her şey Java) | En basit operasyon, tek dağıtım | Java'da AI ekosistemi zayıf; uzun indeksleme işleri API gecikmesini etkiler |
| Tam mikroservis (her modül ayrı) | Bağımsız dağıtım ve ölçekleme | Dağıtık işlem, ağ hataları, servisler arası tutarlılık; tek kişiyle yönetilemez |
| **Modüler monolit + AI servisi** | Tutarlılık tek yerde; AI bağımsız ölçeklenir ve dağıtılır | İki dil, iki CI hattı; servisler arası sözleşme ve sürümleme gerekir |

## Sonuçlar
- Yetki ve kiracı kararları tek süreçte, tek veritabanı işleminde verilir.
- AI servisi **kendi yetki kararı vermez**; yalnızca çekirdekten gelen doğrulanmış kimlik
  bağlamıyla (kiracı, kullanıcı, erişilebilir koleksiyonlar) çalışır.
- Servisler arası sözleşme OpenAPI ile tanımlanır ve sözleşme testleriyle korunur.
- Uzun işler (indeksleme) kuyruk üzerinden asenkron yürür; çekirdek API'nin gecikmesini etkilemez.
- Kabul edilen risk: iki dil ve iki araç zinciri bakım yükünü artırır.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Orta.** Modül sınırları kodda zorlandığı için bir modülün ayrı servise çıkarılması
mümkündür; asıl maliyet işlem sınırlarının olaylara dönüştürülmesidir.

Tetikleyici: bir modülün dağıtım sıklığı veya ölçekleme ihtiyacı diğerlerinden belirgin
şekilde ayrışırsa (ör. `ingestion` yükü API p95 gecikmesini SLO dışına iterse) ya da
ayrı bir ekip bir modülün sahipliğini alırsa.
