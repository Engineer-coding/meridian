# ADR-0012: İndeksleme hattı ve embedding modeli (v0)

- Durum: Kabul edildi
- Tarih: 2026-11-02

## Bağlam
`source.created` olayı (ADR-0004) bir kaynağın aranabilir hâle gelmesi gerektiğini söyler. Hat
şunları yapmalıdır: kaynaktan belgeleri çekmek, okunabilir metne çevirmek, parçalamak, her
parçanın vektörünü hesaplamak ve sonucu `chunks` tablosuna (ADR-0003) yazmak.

Kısıtlar:
- Korpus çok dillidir (Kubernetes dokümanları İngilizce, KVKK Türkçe; altın set iki dili içerir).
- Mesaj en az bir kez gelir (ADR-0011); aynı olay iki kez işlenebilir.
- Yazma, okumayla aynı kiracı kuralına (RLS) tabidir; AI servisi kendi yetki kararını vermez (ADR-0001).
- Tek kişilik ekip: API anahtarı, faturalandırma ve veri işleme sözleşmesi gerektirmeyen bir v0.

## Karar

### Akış
1. **Başla (kısa işlem):** olay işlenmişse dur. Kaynak yoksa, başka kiracınınsa (RLS görmez) ya
   da siliniyorsa olayı işlenmiş say ve dur. Yoksa durumu `indexing` yap.
2. **Çek, ayrıştır, parçala, göm (işlem dışında):** dakikalar sürebilir; veritabanı bağlantısı tutulmaz.
3. **Yaz (tek işlem):** `processed_events`'e olay kimliğini ekle (`ON CONFLICT DO NOTHING`);
   eklenemezse başka bir teslimat zaten yazmıştır, dur. Kaynak satırını kilitle (`FOR UPDATE`);
   bu arada silinmeye başlandıysa dur. Kaynağın eski belgelerini sil, yenilerini ekle, durumu
   `ready` yap. Olayın etkisi ve "işlendi" kaydı birlikte commit olur ya da hiçbiri olmaz.
4. **Silme:** `source.deleted` kaynağı siler; belgeler ve parçalar yabancı anahtarla zincirleme gider.
5. **Başarısızlık:** DLQ'dan hemen önce kaynak `failed` olur. Kalıcı hatanın mesajı kiracıya
   gösterilir (ör. "dizin bulunamadı"); geçici hatanın ayrıntısı gösterilmez (iç adres sızmasın).

### Bileşenler
| Adım | v0 seçimi |
|---|---|
| Kaynak | GitHub: tek commit'e sabitlenmiş, `paths` ile daraltılabilen `.md/.mdx/.markdown/.txt` dosyaları (≤ 1 MB, kaynak başına ≤ 2000 dosya). `web` ve `upload` henüz desteklenmez → kalıcı hata. |
| Ayrıştırma | Markdown başlıklarına göre bölümler; Hugo front matter ve kısa kodları temizlenir; kod blokları içindeki `#` başlık sayılmaz. |
| Parçalama | Bölüm sınırını aşmayan, en fazla 1200 karakterlik parçalar; paragraf → cümle → kelime sırasıyla bölünür; ardışık parçalar ~150 karakter örtüşür. Her parça başlık yolunu taşır ("Pods > Pod lifecycle"). |
| Embedding | `intfloat/multilingual-e5-large` (1024 boyut), ONNX ile yerelde (fastembed). Belgeler `passage:`, sorgular `query:` ön ekiyle. Gömülen metin = başlık yolu + parça. |
| Tam metin | `to_tsvector('simple', section || ' ' || content)`: dil bağımsız, kök bulma yok. |

### Veritabanı rolü
`meridian_ai` (NOBYPASSRLS): `documents`, `chunks` üzerinde tam yetki; `processed_events`'e
okuma ve ekleme; `sources` üzerinde yalnızca kimlik/tür/yapılandırma/durum sütunlarını okuma,
durum sütunlarını güncelleme ve silme. Kimlik, üyelik, koleksiyon ve outbox tablolarını göremez.
Çekirdek API rolü (`meridian_app`) indeksi okuyabilir ama yazamaz.

Belge → kaynak → koleksiyon tutarlılığı bileşik yabancı anahtarlarla şemada zorlanır: bir parça
başka bir koleksiyonun ya da kiracının belgesine bağlanamaz.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Yerel multilingual-e5-large** | Ücretsiz, veri dışarı çıkmaz, Türkçe dahil 100 dil, deterministik | CPU'da yavaş (büyük kaynaklar dakikalar sürer); ilk çalıştırmada 2,2 GB indirme; ~2 GB RAM |
| BGE-M3 | Daha uzun bağlam (8192), seyrek+yoğun | fastembed'de yoğun vektör için hazır ONNX yok; torch bağımlılığı ağır |
| multilingual-e5-small / MiniLM | 5–10 kat hızlı, küçük | Retrieval kalitesi belirgin düşük; şema boyutu (1024) değişir |
| OpenAI / Voyage / Cohere API | Hızlı, güçlü | Anahtar ve maliyet; kiracı verisi üçüncü tarafa gider (KVKK yurt dışı aktarım değerlendirmesi) |
| Tek işlemde çek+göm+yaz | Basit | Dakikalarca açık işlem ve bağlantı; kilitler ve vacuum sorunları |
| İdempotency'yi yalnızca "sil ve yeniden yaz" ile sağlamak | Ek tablo yok | Silinmiş bir kaynak için gecikmiş olay onu "diriltmeye" çalışır; tekrarları ölçemeyiz |

## Sonuçlar
**Olumlu**
- Aynı olay kaç kez gelirse gelsin indeks bir kez yazılır (test: ardışık ve eşzamanlı tekrar).
- Başka kiracı adına gelen bir olay hiçbir şey yazamaz: kaynağı RLS yüzünden göremez ve
  `meridian_ai` rolü başka kiracıya ait parça ekleyemez (test edildi).
- Model, sağlayıcı ve parçalama değiştirilebilir; Adım 17'nin değerlendirme hattı bu seçimleri
  recall@k / MRR / nDCG ile ölçecek ve ADR-0007'ye veri sağlayacak.

**Ölçüm (yerel, 2026-11-02):** `kubernetes/website` → `content/en/docs/concepts/workloads/pods`:
15 belge, 278 parça, dizüstü CPU'sunda **~2,1 sn/parça** (ilk çalıştırmadaki 2,2 GB model indirmesi
hariç ~10 dakika). Türkçe bir soru ("Bir pod içindeki konteyner çökerse ne olur?") İngilizce
dokümandaki doğru bölümü ilk sırada buldu; aynı kullanıcının diğer kiracısında sonuç dönmedi.
Bu hızla `concepts` bölümünün tamamı (~3000 parça) saatler sürer: aşağıdaki ikinci tetikleyici
**şimdiden oluşmuştur** ve Adım 17'de değerlendirme korpusu için ele alınacaktır (GPU, daha küçük
model ya da API; kalite farkı ölçülerek).

**Olumsuz / kabul edilen riskler**
- Yeniden indeksleme her seferinde tüm belgeleri yeniden gömer; değişmeyen belgeler için
  `content_hash` ile atlama ileride eklenecek.
- Embedding süreci CPU'yu doldurur; büyük bir kaynak indekslenirken aynı süreçteki diğer mesajlar
  yavaşlar (prefetch 2). Ölçeklemede embedding ayrı bir işçiye ayrılır.
- Model değişikliği vektör boyutunu değiştirebilir: yeni sütun, yeniden indeksleme ve migration gerekir.
- `web` kaynakları sunucunun kiracı adına rastgele adreslere istek atması demektir (SSRF);
  ayrı bir güvenlik tasarımı gerektirdiği için ertelendi.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Orta.** Model `Embedder` arayüzünün arkasındadır; değiştirmek tüm kaynakların yeniden
indekslenmesini gerektirir.

Tetikleyiciler:
- Adım 17 değerlendirmesinde recall@10 hedefin altında kalırsa (önce parçalama, sonra model).
- 1000 parçalık bir kaynağın indekslenmesi 10 dakikayı geçerse.
- Bir kiracı, verisinin üçüncü taraf bir sağlayıcıya gitmesini kabul ederse ve kalite farkı ölçülürse.
