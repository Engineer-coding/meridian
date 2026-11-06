# ADR-0010: Değerlendirme kapısının CI'daki yeri

- Durum: Kabul edildi
- Tarih: 2026-11-06

## Bağlam
Plan, kalite düşünce CI'ın kırılmasını istiyor. Gerçek ölçüm ise CPU'da saatler sürüyor: 165 soruda
yalnızca model çağrıları ~3 saat, korpusun gömülmesi önbelleksiz ~1,5 saat. Ayrıca embedding
modeli, reranker ve Ollama gerekiyor. Bunları her push'ta barındırılan CI'da çalıştırmak mümkün değil.

Ölçümü yalnızca geliştiricinin makinesinde bırakmanın riski, kayıtlı raporun zamanla koddan
kopmasıdır: arama kodu değişir, rapordaki sayılar artık o kodu anlatmaz ama kimse fark etmez.

## Karar
**CI ölçmez, kayıtlı ölçümün geçerliliğini denetler.**

1. Rapor bir parmak izi taşır: skoru etkileyen kodun (arama hattı, cevap üretimi, puanlama), altın
   setin ve korpus manifestinin sha256'sı (`evaluation/gate.py`). Satır sonları normalize edilir.
2. Normal test paketindeki iki test (`test_committed_*_report_is_current_and_meets_thresholds`)
   parmak izini yeniden hesaplar. Eşleşmezse CI kırılır ve hangi komutla yeniden ölçüleceğini söyler.
3. Aynı testler rapordaki skorları `packages/eval/thresholds.json` ile karşılaştırır. Eksik metrik
   de ihlaldir.
4. Modelsiz duman testi (`make eval-smoke`) hattın çalıştığını CI'da doğrulamaya devam eder.

Eşikler ölçümün yaklaşık 3–4 puan altındadır (~4–5 soru). Bir **gerileme korumasıdır, kalite
hedefi değildir**: "%57 doğru" kabul edilebilir bir ürün kalitesi anlamına gelmez.

| Ölçüt | Ölçülen | Eşik |
|---|---|---|
| vektör recall@3 / recall@5 / MRR | 0,897 / 0,919 / 0,816 | ≥ 0,87 / 0,89 / 0,79 |
| Cevapsız soruda "bilmiyorum" | %93,1 | ≥ %85 |
| Cevaplı soruda gereksiz "bilmiyorum" | %30,1 | ≤ %35 |
| Altın kaynak bağlamda | %93,4 | ≥ %90 |
| Gösterilen kaynak altın kaynak | %80,0 | ≥ %75 |
| Cevap doğru (tüm cevaplı sorular) | %61,0 | ≥ %57 |
| Cevap doğru (model cevap verdiğinde) | %87,4 | ≥ %82 |
| Var olmayan kaynak numarası | %0,6 | ≤ %2 |

## Cevap doğruluğu neden anahtar kelimeyle ölçülüyor
Hakem model bu donanımda yavaştır ve deterministik değildir; 3B bir modelin hakemliği de güvenilir
olmaz. Anahtar kelime deterministiktir, model istemez, CI'da aynı sonucu verir. Bedeli, anlamı
görmemesidir.

İlk ölçümden sonra cevaplar okunarak puanlama denetlendi:
- **İki kod hatası düzeltildi.** Noktadan sonra gelen kelime eşleşmiyordu (`.status.recommendation`),
  `[1]` atıf numarası "1" anahtar kelimesini karşılayabiliyordu.
- **Üç sorunun anahtar kelimesi düzeltildi.** `k8s-163` puanı düşürür ("bir" her cümlede geçiyordu);
  `k8s-126` ve `kvkk-103` yükseltir. Bu düzeltmeler cevaplar görüldükten sonra yapıldığı için
  `v2-decisions.json` içinde `post_measurement_edits` olarak işaretlidir; insan onayı değildir.
- **Çözülmeyen yanlış pozitifler var.** `kvkk-158`, `k8s-177` ve `k8s-004` anahtar kelimeyi geçiyor
  ama cevabın bir kısmı yanlış. Bu okumaya göre "model cevap verdiğinde doğru" oranı %87 değil
  yaklaşık %84'tür. Okuma Claude tarafından yapıldı, cevapların çoğunda ilk 300 karaktere bakıldı;
  kesin bir sayı değil, ölçütün yukarı yanlı olduğunun işaretidir.

## Altın setin doğrulama düzeyi
Set sentetiktir. Her adayın kanıtının kaynakta geçtiği kodla denetlendi (`evaluation/candidates.py`).
Son onay tek kişi tarafından, 166 kart için ~3 dakikada verildi (kart başına ~1,1 sn; süre
`v2-decisions.json` içindedir). Bu yüzden set "ayrıntılı insan doğrulamasından geçmiş" olarak
tanımlanmaz. `verified: true` alanı "onaylandı" demektir, "tek tek okundu" değil.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Parmak izi + kayıtlı rapor + eşik** | Her push'ta saniyeler; koddan kopmayı yakalar | Rapor elle değiştirilebilir; ölçümün dürüstlüğü geliştiriciye bağlı |
| Her push'ta tam ölçüm | En güvenilir | CPU'da saatler; barındırılan CI'da Ollama ve modeller yok |
| Önbellekli CI ölçümü | Dakikalar | Büyük önbellekleri CI'a taşımak gerekir; LLM önbelleği deposunda tutulmaz |
| Küçük alt küme ölçümü | Gerçek model çalışır | CI'da yine LLM gerekir; küçük örneklem gürültülü |
| Yalnızca duman testi | Basit | Kalite gerilemesini hiç görmez |

## Sonuçlar
**Olumlu**
- Arama, cevap ya da puanlama kodu, altın set veya korpus değişirse ölçüm yenilenmeden birleştirilemez.
- Yeniden ölçüm önbellek sayesinde değişmeyen kısımlar için dakikalar sürer.

**Olumsuz / kabul edilen riskler**
- CI ölçümün kendisini tekrar etmez. Elle değiştirilmiş bir rapor parmak izi tutuyorsa geçer.
- Prompt dışındaki model değişikliği (Ollama'da aynı etiketin yeni sürümü) parmak izine girmez.
- Yorum satırı değişikliği de parmak izini bozar ve yeniden ölçüm ister. Önbellek bunu ucuzlatır.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Düşük.** İki test ve bir JSON dosyasıdır.

Tetikleyiciler:
- GPU'lu bir CI koşucusu ya da onaylı bir bulut LLM'i olursa: gece çalışan gerçek ölçüm eklenir.
- Anahtar kelime ölçütü ile elle okuma arasındaki fark büyürse ya da hakem için güvenilir bir model
  olursa: hakem modelli doğruluk ölçütü eklenir.
- Ölçüm iyileşirse eşikler yukarı çekilir; eşik düşürmek bir ADR güncellemesi gerektirir.
