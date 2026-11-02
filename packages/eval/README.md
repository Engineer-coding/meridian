# Değerlendirme

Retrieval kalitesini sabit bir korpus ve elle doğrulanmış bir altın setle ölçer. Faz 3 kapısı:
recall@k ölçülür ve raporlanır ([reports/baseline.md](reports/baseline.md)).

| Dosya | İçerik |
|---|---|
| `corpus/manifest.json` | Korpus sürümleri: Kubernetes `concepts` (sabit commit) ve KVKK (resmî PDF'in sha256'sı) |
| `corpus/kvkk/6698.md` | KVKK metni; PDF'ten `scripts/kvkk_to_markdown.py` ile üretilir, her madde bir başlık |
| `golden/v1.jsonl` | 30 soru: 23 cevaplı (15 tek kaynaklı, 8 çok kaynaklı), 7 cevapsız; 12 Türkçe, 18 İngilizce. Kaynaklar `alternatives` ile aynı bilgiyi taşıyan başka bölümleri de kabul edebilir |
| `golden/v0.jsonl` | İlk sürüm (v0.3.0 baseline'ı bununla ölçüldü); değiştirilmez |
| `reports/baseline.{json,md}` | Kayıtlı ölçüm; altın set ya da manifest değişirse CI yeniden üretilmesini ister |

```bash
make eval-validate   # altın setin şeması ve dağılımı
make eval-smoke      # modelsiz duman testi (CI'da çalışır): hattı doğrular, kaliteyi ölçmez
make eval            # gerçek ölçüm (e5-large); ilk çalıştırma CPU'da ~1,5 saat
make eval NAME=baseline
```

## Nasıl ölçülür
1. Geçici bir PostgreSQL (pgvector) başlatılır; şema çekirdek API'nin migration'larından kurulur.
2. Korpus, üretimdeki indeksleme hattından (`Indexer`: ayrıştırma, parçalama, embedding, tek
   işlemde yazım) bir değerlendirme kiracısına indekslenir. Embedding'ler `~/.cache/meridian/eval`
   altında önbelleklenir.
3. Her altın kaynağın (belge + başlık) indekste en az bir parçayla eşleştiği doğrulanır; eşleşmeyen
   varsa ölçüm yapılmaz (altın set ya da ayrıştırıcı bozulmuştur).
4. Her soru üç yöntemle aranır (`Retriever`): **vector** (kosinüs, HNSW + iterative scan),
   **lexical** (`tsvector`, VEYA sorgusu, `ts_rank`), **hybrid** (ikisinin ilk 50'si, RRF k=60).

## Metrikler
Alaka birimi **altın kaynaktır**, parça değil. Bir bölüm birkaç parçaya bölünebilir; aynı
kaynağın ikinci parçası yeni bilgi getirmediği için her kaynak en fazla bir kez sayılır.

- **recall@k:** ilk k sonuçta bulunan altın kaynakların oranı. Çok kaynaklı soru, tüm kaynakları
  bulunduğunda 1 olur.
- **MRR:** ilk alakalı sonucun sırasının tersi (ilk 10'da yoksa 0).
- **nDCG@k:** ikili kazanç; bir sıra henüz bulunmamış bir kaynağı karşılıyorsa 1 kazandırır.
- Ortalamalar yalnızca cevaplı sorular üzerindendir. Cevapsız sorular için en iyi vektör skoru
  ayrıca raporlanır: Faz 4'te "bilmiyorum" eşiği için ilk veri.

## Sınırlar
- 23 cevaplı soru küçük bir örneklemdir: tek bir sorunun değişmesi recall@k'yi ~4 puan oynatır.
  Yöntemler arası küçük farklar anlamlı değildir.
- Altın set, korpusun yalnızca bir kısmını kapsar; her soru aynı kişi tarafından yazılmıştır.

## v0.3.0 bulguları
- **Vektör arama tek başına güçlü:** recall@5 0,87, recall@10 0,91; Türkçe KVKK sorularında
  ilk sıradaki sonuç her zaman doğru (MRR 1,00). Türkçe soru → İngilizce belge eşleşmesi de çalışıyor.
- **Hibrit (eşit ağırlıklı RRF)** ilk sırada daha isabetli (recall@1 0,70 → vektör 0,57) ama
  sözcüksel aramanın zayıf olduğu İngilizce sorularda recall@5'i düşürüyor (0,78). Ağırlıklı
  birleştirme ve reranking ADR-0007'de bu baseline'a karşı denenecek.
- **Cevapsız sorular skorla ayrılamıyor:** en iyi vektör skoru cevaplı sorularda 0,85–0,91,
  cevapsızlarda 0,79–0,87; aralıklar örtüşüyor. "Bilmiyorum" kararı tek bir benzerlik eşiğiyle
  verilemez, Faz 4'te cevap üretimi aşamasında ele alınmalı.
- **Altın set v1** (v0.3.0 sonrası): iki soruya alternatif kaynak eklendi, sorular ve asıl
  kaynaklar değişmedi.
  - `k8s-005`: 30 sn'lik varsayılan gerçekten "Pod phase" bölümünde (asıl etiket doğru); beklenen
    cevabın ikinci yarısı (süre dolunca KILL) "Termination of Pods" bölümünde → alternatif.
  - `k8s-002`: prob'ların ayrı sayfası (`workloads/pods/probes.md`) aynı bilgiyi taşıyor; beklenen
    cevaptaki EndpointSlice cümlesi orada birebir geçiyor → her iki kaynağa alternatif.
  - Etkisi küçük: vektör recall@3 0,826 → 0,848, MRR 0,821 → 0,824; hibrit recall@5 0,783 → 0,826.
    `k8s-002`'nin readiness kaynağı hiçbir yöntemde ilk 10'a girmiyor: bu bir etiket değil,
    gerçek bir retrieval hatası.

## Kaynaklı cevap (Adım 18)
`make eval-answers NAME=answers` → [reports/answers.md](reports/answers.md). Retrieval
ölçümüne ek olarak her soru için gerçek cevap üretilir (ADR-0008):

- **"Bilmiyorum" doğruluğu:** cevapsız sorularda çekimserlik (yüksek iyi), cevaplı sorularda
  gereksiz çekimserlik (düşük iyi).
- **Atıf:** cevap kaynak gösteriyor mu, gösterilen kaynak altın kaynak mı, var olmayan kaynak
  numarası var mı.
- **Süre:** ilk token ve toplam (ortanca).

Cevabın içeriğinin doğruluğu (hakem model) Adım 21'de eklenecek. İlk ölçüm (`llama3.2:3b`,
3 kaynak): cevapsız sorularda %86 "bilmiyorum", cevaplı sorularda %39 gereksiz "bilmiyorum",
cevapların %100'ü kaynak gösteriyor, %86'sı altın kaynağı gösteriyor, ortanca toplam süre 41 sn.
