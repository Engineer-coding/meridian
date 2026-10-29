# ADR-0003: Vektör araması için PostgreSQL + pgvector (ayrı vektör DB yerine)

- Durum: Kabul edildi
- Tarih: 2026-10-29

## Bağlam
Retrieval hattı her parça için üç tür veriye ihtiyaç duyar: embedding vektörü, tam metin
indeksi (BM25 benzeri arama için `tsvector`) ve ilişkisel meta veri (kiracı, koleksiyon, ACL,
belge sürümü). Hibrit arama bu ikisini Reciprocal Rank Fusion ile birleştirir.

Kısıtlar:
- Yetkisiz bir parça LLM'e hiç ulaşmamalıdır; yetki filtresi arama **sırasında** uygulanmalıdır
  (ADR-0002'deki RLS kuralı vektörler için de geçerli olmalı).
- Belge silindiğinde veya güncellendiğinde vektörler ve meta veri **aynı işlemde** tutarlı kalmalı.
- Tek kişilik ekip: işletilecek her ek veri deposu yedekleme, izleme, güvenlik ve maliyet getirir.
- Başlangıç ölçeği: demo korpusu ve kiracı başına onbinler–yüzbinler düzeyinde parça.

## Karar
Vektörler, tam metin indeksiyle birlikte PostgreSQL'de, **pgvector** eklentisi ve **HNSW**
indeksiyle `chunks` tablosunda tutulur. Ayrı bir vektör veritabanı şimdilik kullanılmaz;
geçiş kararı ölçüme bağlanır (aşağıdaki tetikleyiciler).

```sql
CREATE TABLE chunks (
  id            uuid PRIMARY KEY,
  tenant_id     uuid NOT NULL,
  collection_id uuid NOT NULL,
  document_id   uuid NOT NULL,
  content       text NOT NULL,
  content_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
  embedding     vector(1024) NOT NULL,   -- boyut, seçilen embedding modeline göre (ADR-0007)
  content_hash  text NOT NULL
);

CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_gin        ON chunks USING gin (content_tsv);
CREATE INDEX chunks_tenant_coll    ON chunks (tenant_id, collection_id);
```

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **PostgreSQL + pgvector** | Tek depo; RLS, işlem ve yedekleme ortak; SQL ile hibrit sorgu; ek operasyon yok | Çok büyük ölçekte (on milyonlarca vektör) bellek ve indeks oluşturma maliyeti; filtreli HNSW'de eksik sonuç riski |
| Qdrant | Vektör aramaya özel; payload filtreleri indeksle birlikte çalışır; yüksek ölçek | Ayrı depo: iki sistem arasında tutarlılık (outbox/çift yazım), ayrı yetki modeli, ayrı yedekleme |
| Weaviate | Yerleşik hibrit arama ve modüller | Ağır bağımlılık; framework'e bağlanma; ayrı operasyon |
| Elasticsearch / OpenSearch | Olgun BM25 + vektör; güçlü tam metin | Yüksek kaynak tüketimi; ayrı küme; kiracı izolasyonu ayrıca kurulmalı |

## Sonuçlar
**Olumlu**
- Vektörler ADR-0002'deki **aynı RLS politikasıyla** korunur; yetki ayrı bir sistemde tekrar
  edilmez.
- Belge silme/güncelleme, meta veri ve vektörde tek işlemde yapılır; senkronizasyon hattı gerekmez.
- Hibrit arama tek SQL sorgusunda (iki CTE + RRF) yazılabilir ve tek trace'te ölçülür.

**Bilinen tuzak: filtreli HNSW araması eksik sonuç döndürebilir**
HNSW indeksi önce en yakın `hnsw.ef_search` (varsayılan 40) adayı bulur; kiracı/ACL filtresi
bu adaylara **sonradan** uygulanır. Filtre seçici ise (ör. küçük bir kiracı, kısıtlı bir koleksiyon)
`LIMIT 50` isteyen bir sorgu 50'den çok daha az sonuç döndürebilir — recall sessizce düşer.

Önlemler:
- pgvector 0.8+ ile gelen **iterative index scan**: `SET LOCAL hnsw.iterative_scan = relaxed_order;`
  indeks, yeterli sonuç bulunana kadar taramaya devam eder (`hnsw.max_scan_tuples` ile sınırlı).
  Varsayılanı `off` olduğu için retrieval sorgusunda açıkça açılmalıdır
  (yerel ortamda doğrulandı: pgvector 0.8.7, `ef_search=40`, `max_scan_tuples=20000`).
- Sorgu başına `hnsw.ef_search` değeri, istenen aday sayısına göre ayarlanır.
- Bu davranış **testle ölçülür**: küçük ve büyük kiracı için filtreli sorgularda dönen sonuç
  sayısı ve recall@k raporlanır.

**Kabul edilen riskler**
- Vektör yükü (indeks oluşturma, bellek) işlemsel veritabanıyla aynı kaynakları paylaşır.
- HNSW indeksi bellekte en iyi çalışır; parça sayısı büyüdükçe `shared_buffers` / RAM ihtiyacı artar.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Orta.** Retrieval, AI servisindeki tek bir `Retriever` arayüzünün arkasındadır; başka bir vektör
deposuna geçiş bu arayüzün yeni bir uygulamasıdır. Asıl maliyet, iki depo arasındaki tutarlılık
(outbox ile çift yazım) ve yetki filtresinin yeni depoda yeniden kurulmasıdır.

Tetikleyiciler (sayılar yük testi sonrası doldurulacak):
- Retrieval adımının p95 gecikmesi, ilk token SLO'sunu (p95 < 1,5 sn) tehdit ederse.
- Toplam parça sayısı **X**'i geçerse veya HNSW indeksi mevcut RAM'e sığmazsa.
- Filtreli sorgularda recall@k, iterative scan ile bile hedefin altında kalırsa.

Tetikleyici oluştuğunda: aynı altın set ve yük profiliyle **pgvector vs Qdrant** karşılaştırmalı
benchmark yapılır; sonuç yeni bir ADR olarak bu kaydın yerine geçer.
