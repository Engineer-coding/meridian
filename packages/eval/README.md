# Değerlendirme

Retrieval ve cevap kalitesini sabit bir korpus ve altın setle ölçer. Raporlar
([baseline](reports/baseline.md), [cevaplar](reports/answers.md)) depoda tutulur; CI raporların
güncelliğini ve eşikleri denetler ([ADR-0010](../../docs/adr/0010-eval-gate-in-ci.md)).

| Dosya | İçerik |
|---|---|
| `corpus/manifest.json` | Korpus sürümleri: Kubernetes `concepts` (sabit commit) ve KVKK (resmî PDF'in sha256'sı) |
| `corpus/kvkk/6698.md` | KVKK metni; PDF'ten `scripts/kvkk_to_markdown.py` ile üretilir, her madde bir başlık |
| `golden/v2.jsonl` | **Geçerli set.** 165 soru: 136 cevaplı (103 tek kaynaklı, 33 çok kaynaklı), 29 cevapsız; 79 Türkçe, 86 İngilizce. Sentetik; kanıtı kodla denetlendi, hızlı onaylandı (aşağıya bakın) |
| `candidates/` | v2 adayları, onay sayfası ve kararlar (`v2-decisions.json`). `scripts/build_golden_v2.py` seti bunlardan üretir |
| `thresholds.json` | CI eşikleri: gerileme koruması, kalite hedefi değil |
| `golden/v1.jsonl` | 30 soru: 23 cevaplı (15 tek kaynaklı, 8 çok kaynaklı), 7 cevapsız; 12 Türkçe, 18 İngilizce. Kaynaklar `alternatives` ile aynı bilgiyi taşıyan başka bölümleri de kabul edebilir |
| `golden/v0.jsonl` | İlk sürüm (v0.3.0 baseline'ı bununla ölçüldü); değiştirilmez |
| `reports/{baseline,answers}.{json,md}` | Kayıtlı ölçümler; skoru etkileyen kod, altın set ya da manifest değişirse CI yeniden üretilmesini ister |

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
- 136 cevaplı soruda tek sorunun etkisi ~0,7 puandır. 1–2 puanlık farklar anlamlı değildir.
- **Set sentetiktir.** Adaylar model yardımıyla yazıldı, kanıtın kaynakta geçtiği kodla denetlendi.
  166 kart tek kişi tarafından ~3 dakikada onaylandı, bu yüzden "ayrıntılı insan doğrulaması" sayılmaz.
- **Doğruluk ölçütü anahtar kelimeye dayanır,** anlamı görmez ve yukarı yanlıdır: cevapları okuyunca
  "cevap verdiğinde doğru" oranı %87 değil yaklaşık %84 çıktı (ADR-0010).
- Korpusun yalnızca bir kısmı kapsanır; sorular aynı kaynaktan üretilmiştir.

## v0.4.0 bulguları (altın set v2)
- **Arama iyi:** vektör recall@3 0,897, recall@5 0,919. `bge-m3` reranker recall@3'ü 0,938'e çıkarıyor;
  v1'deki "reranking recall@3'ü artırmıyor" sonucu küçük örneklem kaynaklıydı (ADR-0007).
- **Asıl darboğaz model:** altın kaynak %93 oranında bağlamda ama cevaplı soruların %30'unda
  gereksiz "bilmiyorum" var; bunların 41'inin 35'inde kaynak bağlamdaydı (ADR-0008).
- **Model cevap verdiğinde çoğunlukla doğru:** %87 (okuyarak ~%84). Tüm cevaplı sorularda ise %61.
- **Zayıf yerler:** çok kaynaklı sorular 11/33; Türkçe 33/64, İngilizce 50/72.
- **Cevapsız sorular:** %93 "bilmiyorum"; 29 sorunun 2'si gerçek ama ilgisiz alıntıyla cevaplandı.
- **Reranking cevabı belirgin değiştirmiyor:** `vector+bge-m3` doğru cevapta %61,0 → %64,0 (14 kazanç,
  10 kayıp; p = 0,54), +15 sn ([rapor](reports/answers-bge-m3.md)). Varsayılan kapalı kalır.
- **Gerçek süre:** ortanca ilk token 57 sn, toplam 65 sn (CPU). Önceki raporlar kanıt çağrısını saymıyordu.

Aşağıdaki bölümler, ölçüldükleri dönemin küçük setleriyle (v0, v1) yazılmıştır.

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

Cevap doğruluğu Adım 21'de anahtar kelimeyle eklendi (ADR-0010). İlk ölçüm (`llama3.2:3b`,
3 kaynak): cevapsız sorularda %86 "bilmiyorum", cevaplı sorularda %39 gereksiz "bilmiyorum",
cevapların %100'ü kaynak gösteriyor, %86'sı altın kaynağı gösteriyor, ortanca toplam süre 41 sn.

## Ablasyon (Adım 19, ADR-0007)
`make eval NAME=baseline` artık 7 yapılandırmayı ölçer: vektör, sözcüksel, hibrit ve
iki reranker'ın (`bge-m3`, `jina-v2`) vektör ve hibrit üstünde yeniden sıralaması (ilk 20 aday).

- 3 kaynaklı bağlam için ölçüt recall@3. Bunu hiçbir yapılandırma vektörün (0,848) üstüne
  çıkaramadı; `bge-m3` recall@5'i 0,870 → 0,913, recall@10'u 0,913 → 0,935 yaptı (soru başına +14 sn).
- Hibrit en iyi ilk sonucu veriyor (recall@1 0,696, MRR 0,877).
- Gereksiz "bilmiyorum" oranının kaynağı arama değil; altın kaynak soruların %96'sında zaten bağlamda.
