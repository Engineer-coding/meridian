# ADR-0007: Hibrit retrieval ve reranking seçimi (ablasyon verisiyle)

- Durum: Kabul edildi
- Tarih: 2026-11-03

## Bağlam
Cevap üretimi (ADR-0008) aramanın ilk **3** parçasını modele verir. CPU'da her ek parça cevaba
~30 sn ekler. Bu yüzden önemli olan ölçüt recall@3'tür: altın kaynak ilk üçte mi?

Elimizdeki seçenekler:
- **İlk aşama:** vektör (e5-large, HNSW), sözcüksel (`tsvector`) ya da ikisinin RRF birleşimi (hibrit).
- **İkinci aşama:** ilk aşamanın ilk 20 adayını çapraz kodlayıcıyla (reranker) yeniden sıralamak.
  Aday çok dilli modeller: `BAAI/bge-reranker-v2-m3` (int8 ONNX, 0,57 GB) ve
  `jinaai/jina-reranker-v2-base-multilingual` (1,1 GB). İkisi de CPU'da çift başına 0,4–0,5 sn.

## Ölçüm
Altın set v1, 23 cevaplı soru, 3093 parça
([packages/eval/reports/baseline.md](../../packages/eval/reports/baseline.md)):

| Yapılandırma | recall@1 | recall@3 | recall@5 | recall@10 | MRR | nDCG@10 | ek süre / soru |
|---|---|---|---|---|---|---|---|
| vector | 0,565 | **0,848** | 0,870 | 0,913 | 0,824 | 0,809 | — |
| lexical | 0,500 | 0,674 | 0,739 | 0,891 | 0,673 | 0,702 | — |
| hybrid (RRF) | **0,696** | 0,804 | 0,826 | 0,913 | **0,877** | **0,846** | — |
| vector + bge-m3 | 0,609 | **0,848** | **0,913** | 0,935 | 0,824 | 0,834 | 14 sn |
| hybrid + bge-m3 | 0,609 | **0,848** | 0,891 | **0,957** | 0,821 | 0,842 | 14 sn |
| vector + jina-v2 | 0,674 | 0,804 | 0,848 | 0,935 | 0,861 | 0,847 | 10 sn |
| hybrid + jina-v2 | 0,652 | 0,804 | 0,848 | 0,935 | 0,839 | 0,836 | 11 sn |

Okuma notları:
- 23 soruda bir sorunun farkı recall'da 0,043 eder. Tablodaki farkların çoğu bir, en fazla iki
  sorudur.
- **recall@3'ü hiçbir yapılandırma vektörün üstüne çıkaramadı.** Reranking'in kazancı 5. ve
  10. sıradadır.
- Hibrit en iyi ilk sonucu verir (recall@1, MRR), ama İngilizce sorularda sözcüksel arama
  zayıf olduğu için ilk üçe yanlış adaylar sokar.
- Cevap değerlendirmesinde (ADR-0008) altın kaynak soruların %96'sında zaten bağlamdaydı.
  Gereksiz "bilmiyorum" oranı (%39) aramadan değil, 3B modelin alıntı becerisinden kaynaklanıyor.
  Daha iyi sıralama bu sorunu çözmez.

## Yeniden ölçüm (altın set v2, 136 cevaplı soru, 2026-11-06)
"Altın set ≥ 150 soru" tetikleyicisi çalıştı. Daha büyük örneklem v1'in bir bulgusunu **çürüttü**:

| Yapılandırma | recall@1 | recall@3 | recall@5 | recall@10 | MRR | nDCG@10 | ek süre / soru |
|---|---|---|---|---|---|---|---|
| vector | 0,643 | 0,897 | 0,919 | 0,963 | 0,816 | 0,845 | — |
| lexical | 0,614 | 0,783 | 0,857 | 0,912 | 0,762 | 0,785 | — |
| hybrid (RRF) | 0,706 | 0,886 | 0,930 | 0,967 | 0,862 | 0,874 | — |
| vector + bge-m3 | 0,765 | 0,938 | 0,971 | 0,974 | **0,902** | 0,913 | 15 sn |
| hybrid + bge-m3 | 0,754 | **0,949** | **0,974** | **0,989** | 0,901 | **0,916** | 16 sn |
| vector + jina-v2 | 0,732 | 0,904 | 0,926 | 0,971 | 0,873 | 0,889 | 13 sn |
| hybrid + jina-v2 | 0,724 | 0,912 | 0,934 | 0,978 | 0,875 | 0,892 | 13 sn |

- **Reranking recall@3'ü artırıyor:** vektörde 0,897 → 0,938 (~5–6 soru), hibritte 0,949. v1'deki
  "hiçbir yapılandırma vektörün üstüne çıkamadı" sonucu küçük örneklemden kaynaklanıyordu.
- `bge-m3`, `jina-v2`'den açıkça iyi. En büyük kazanç çok kaynaklı sorularda (vektör recall@5
  0,76 → 0,88, hibrit + bge-m3 0,92).
- Sözcüksel arama tek başına en zayıf yöntem olmaya devam ediyor.

**Varsayılan şimdilik değişmedi, ama gerekçesi zayıfladı.** Gerçek cevap süresi ~65 sn olduğu için
+15 sn v1'de sanıldığı kadar büyük değil (ADR-0008'deki süre düzeltmesi). Öte yandan altın kaynak
zaten %93 oranında bağlamda ve gereksiz "bilmiyorum" cevaplarının çoğu (41'in 35'i) altın kaynak
bağlamdayken oluyor.

### Cevaplara etkisi (`vector` ve `vector+bge-m3`, 165 soru, aynı model)
| Ölçüt | Reranking yok | `bge-m3` |
|---|---|---|
| Altın kaynak bağlamda | %93,4 | %96,3 |
| Gösterilen kaynak altın kaynak | %80,0 | %87,8 |
| Cevap doğru, tüm cevaplı sorular | %61,0 (83/136) | %64,0 (87/136) |
| Cevap doğru, model cevap verdiğinde | %87,4 | %88,8 |
| Cevaplı soruda gereksiz "bilmiyorum" | %30,1 (41) | %27,9 (38) |
| Cevapsız soruda "bilmiyorum" | %93,1 (27/29) | %89,7 (26/29) |
| Ortanca toplam süre | ~65 sn | ~80 sn (64,8 sn cevap + 15 sn sıralama) |

- **Net +4 doğru cevap gürültüden ayrılamıyor.** Reranking 14 soruyu doğruya çevirdi, 10 soruyu
  yanlışa; işaret testi p = 0,54. Bağlamdaki küçük değişiklikler bu modelin cevabını iki yönde de
  oynatıyor.
- **Bir uydurma eklendi:** `k8s-201` cevapsız sorusuna "15 dakika" cevabı verildi. Set küçük olduğu
  için tek soru kanıt sayılmaz ama beklenen iyileşme burada da yok.
- Atıf isabetindeki artış (17 kazanç, 7 kayıp; p = 0,06) güçlü bir aday ama kesin değil; cevabın doğruluğunu
  belirgin biçimde değiştirmedi.

**Sonuç: varsayılan kapalı kalır.** Her soruya ~15 sn eklemek bu kazancı karşılamıyor. Gereksiz
"bilmiyorum" sorunu aramada değil modelde; önce model ya da istem değişmeli (ADR-0008). Rapor:
[answers-bge-m3.md](../../packages/eval/reports/answers-bge-m3.md).

## Karar
- **Varsayılan: vektör arama, reranking kapalı, 3 kaynak.** Bu donanımda en yüksek recall@3'ü
  ek süre olmadan veren yapılandırma budur.
- Reranker bir ayardır: `RERANKER=bge-m3`, `RERANK_CANDIDATES=20`. Ablasyonda en iyi
  recall@5/@10'u `bge-m3` verdi; bağlam 5 kaynağa çıkarılırsa ya da güçlü bir donanım/sağlayıcı
  kullanılırsa açılır.
- Hibrit, "en iyi tek sonuç" gereken yerler için (arama sonuç listesi, Faz 5 arayüzü) seçenek
  olarak kalır.
- Ağırlıklı RRF ve parça boyutu ablasyonu yapılmadı. Parça boyutu değişince tüm korpusun yeniden
  gömülmesi gerekir (CPU'da ~1,5 saat); altın set büyüdükten sonra (Adım 21) yapılacak.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Vektör, reranking yok** | En yüksek recall@3, ek süre yok | recall@5/@10'da reranker'ın gerisinde |
| Vektör + bge-m3 | recall@5 +0,043, recall@10 +0,022 | Soru başına +14 sn; recall@3 değişmiyor |
| Hibrit | En iyi recall@1 ve MRR | recall@3 0,804; sözcüksel arama İngilizcede zayıf |
| jina-v2 | Daha hızlı (10 sn) | bge-m3'ün gerisinde; recall@3 düşüyor |

## Sonuçlar
**Olumlu**
- Karar, kayıtlı ve yeniden üretilebilir bir tabloya dayanıyor. Reranker skorları önbellekli
  olduğu için tablo dakikalar içinde yeniden üretilir.
- Reranker eklemek kod değil, ayar değişikliği.

**Olumsuz / kabul edilen riskler**
- v2 sentetik ve hızlı onaylanmış bir settir (ADR-0010); küçük farklara fazla anlam yüklenmemeli.
- `k8s-002` (readiness) ve `k8s-012`, `k8s-014` gibi çok kaynaklı soruların ikinci kaynağı
  çoğu yapılandırmada ilk 10'a girmiyor. Soru ayrıştırma (çok adımlı arama) ileride değerlendirilir.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Düşük.** Yapılandırma iki ayardan ibaret; ölçüm `make eval` ile tekrarlanır.

Tetikleyiciler:
- Model ya da istem değişince `vector` ve `vector+bge-m3` cevap değerlendirmesi birlikte tekrarlanır:
  daha güçlü bir model iyi bağlamdan daha çok yararlanabilir.
- Bağlam 3 kaynaktan fazlasına çıkarsa: reranker açılır (recall@5'te önde).
- GPU'lu bir ortam olursa: reranking'in ek süresi 1 sn'nin altına iner ve varsayılan olarak açılır.
