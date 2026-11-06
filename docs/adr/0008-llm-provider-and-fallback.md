# ADR-0008: LLM sağlayıcı soyutlaması, yedek zinciri ve doğrulanmış kanıtla cevap

- Durum: Kabul edildi
- Tarih: 2026-11-02

## Bağlam
Faz 4'te sistem, bulunan parçalardan kaynak gösteren cevap üretir. Kısıtlar:

- **Sağlayıcı kararı (kullanıcı):** yerel model (Ollama); veri dışarı çıkmaz, ücret yoktur.
- **Donanım:** geliştirme makinesi düşük güçlü bir dizüstü CPU'su (i7-1255U, GPU yok). Ölçüm:
  3B bir model istemi ~10 token/sn okur, ~6–7 token/sn üretir. ~1000 token'lık bağlamla ilk token
  60–80 sn sürer.
- **Plan:** "LLM sağlayıcısı çökerse sistem yalnızca 'kaynak ara' moduna düşer; ikinci sağlayıcıya
  otomatik geçilir."
- **Ölçülen davranış (`llama3.2:3b`, `qwen2.5:3b`):**
  - "Kaynaklar soruyu cevaplıyor mu? EVET/HAYIR" sorusuna iki model de her durumda HAYIR dedi.
  - Cevabı kaynakta olmayan tuzak soruda ("Kurula bildirim kaç saat?") ikisi de süre uydurdu
    ("15 gün", "30 gün").
  - Karmaşık (XML etiketli) istemde kaynak numarası yazmadılar.

## Karar

### 1. Sağlayıcı soyutlaması ve zincir
Cevap üretimi yalnızca `LLM` arayüzünü (`stream(messages, max_tokens)`) bilir. Sağlayıcılar
`LLM_CHAIN` ile sırayla tanımlanır, örneğin `ollama/llama3.2:3b, ollama/llama3.2:1b`.

- Zincir, **ilk token'dan önce** düşen sağlayıcının yerine sıradakini dener.
- Akış ortasında düşen sağlayıcı değiştirilmez. Kullanıcı yarım bir cevabın devamını başka bir
  modelden görmemelidir; hata çağırana iletilir.
- Hepsi düşerse cevaplayıcı **yalnızca kaynakları** döner (`degraded: true`). Arama LLM'e bağlı
  değildir, bu yüzden kullanıcı yine sonuç görür.
- Şimdilik yalnızca Ollama uygulanmıştır. Claude veya OpenAI eklemek, `LLM` arayüzünün yeni bir
  uygulaması ve zincire bir satırdır.

### 2. Önce kanıt alıntısı, sonra cevap
1. Model önce kaynaklardan cevabı veren cümleyi **aynen alıntılar** (ya da `YOK` yazar).
2. Kod, alıntının kaynak metinlerden birinde gerçekten geçip geçmediğini denetler: normalize
   edilmiş metinde birebir ya da ≥ %90 benzer bir pencere.
3. Geçmiyorsa sistem cevap üretmeden **"bilmiyorum"** der.
4. Geçiyorsa model aynı önekle, cümle sonlarına `[n]` yazarak kısa bir cevap üretir.
5. Cevaptaki var olmayan kaynak numaraları ayrıca işaretlenir (`invalid_citations`).

"Bilmiyorum" kararı böylece modelin beyanına değil, kodla doğrulanan bir olguya dayanır. İki
çağrı aynı önekle başladığı için Ollama öneki önbellekten okur; ikinci çağrının ek maliyeti
~12–18 sn'dir (ilk çağrı ~60–80 sn).

### 3. Kaynak metni güvenilmeyen veridir
- İstem, kaynak metnindeki talimatların uygulanmayacağını söyler.
- Kaynak metnindeki `[2] …` satırları `(2) …` yapılır, böylece belge yeni bir kaynak numarası
  taklit edemez.
- Kırmızı takım seti ve guardrail'ler Faz 5'te (planın Faz 4'ü) eklenecek.

### 4. Bağlam küçük tutulur
Varsayılan 3 kaynak kullanılır (`ANSWER_SOURCES`). Retrieval baseline'ında vektör recall@3 0,85,
recall@5 0,87; 2 kaynak daha eklemek CPU'da ~40 sn daha demektir.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Kanıt alıntısı + kod doğrulaması** | Uydurmayı modelden bağımsız yakalar; dayanak cümle arayüzde gösterilebilir | İkinci çağrı; alıntıyı yanlış seçen model gereksiz "bilmiyorum" der |
| Modelden EVET/HAYIR kontrolü | Basit | Ölçüldü: 3B modeller her soruya HAYIR dedi |
| Benzerlik skoru eşiği | Model çağrısı yok | Baseline: cevaplı ve cevapsız soruların skorları örtüşüyor (0,85–0,91 / 0,79–0,87) |
| Tek çağrı, "BİLMİYORUM yaz" talimatı | En hızlı | Ölçüldü: model tuzak soruda uydurdu |
| Claude API | Hızlı, güçlü, talimata uyar | Kullanıcı kararı: yerel model; ileride zincire eklenebilir |

## Ölçüm (altın set v1, 30 soru, `llama3.2:3b`, [rapor](../../packages/eval/reports/answers.md))
| | Tek çağrı + Türkçe talimat | Kanıt + Türkçe talimat | **Kanıt + dile göre talimat (seçilen)** |
|---|---|---|---|
| Cevapsız soruda "bilmiyorum" | 0/2 (deneme) | %100 | **%86** |
| Cevaplı soruda gereksiz "bilmiyorum" | — | %56 | **%39** |
| Cevap kaynak gösteriyor | %0 (deneme) | %90 | **%100** |
| Gösterilen kaynak altın kaynak | — | %80 | **%86** |
| Var olmayan kaynak numarası | — | %3 | **%0** |

- Türkçe talimat İngilizce kaynakta modeli alıntıyı **çevirmeye** itiyordu; doğrulama da
  başarısız oluyordu. Alıntı talimatı artık kaynakların dilinde, cevap talimatı sorunun dilinde.
- Kaynakta birebir geçen kısa alıntılar (`ClusterIP`, `25%`) kabul edilince İngilizce sorular
  kurtuldu. Bedeli: `kvkk-003` tuzağında model gerçek ama ilgisiz "Otuz gün." parçasını
  alıntıladı ve cevap uydurdu. Bu, aşağıda kabul edilen "gerçek ama ilgisiz alıntı" riskinin ta kendisi.
- Cevaplı sorularda gereksiz "bilmiyorum" (%39) aşağıdaki %30 tetikleyicisinin **üstünde**.
  Sıradaki iyileştirmeler: reranking (Adım 19), alıntı-soru ilgisi denetimi ve güçlü bir sağlayıcı.

## Sonuçlar
**Olumlu**
- Sağlayıcı bir yapılandırma satırıyla değişir; değerlendirme hattı aynı ölçütlerle karşılaştırır.
- LLM düşse de arama çalışır; kullanıcı en azından ilgili kaynakları görür.
- Cevap değerlendirmesi önbelleklidir (`~/.cache/meridian/eval/completions.sqlite`): istem veya
  model değişmedikçe yeniden çalıştırmak saniyeler sürer.

**Olumsuz / kabul edilen riskler**
- Bu donanımda bir cevabın ilk kelimesi ~1,5 dakika sonra gelir. Etkileşimli demo için yavaştır.
  GPU'lu bir makine ya da bulut sağlayıcısı, zincire tek satırla eklenebilir.
- 3B model doğru alıntıyı bulamazsa cevabı olan soruda da "bilmiyorum" der. Bu oran
  değerlendirme raporunda ölçülür (`abstain_when_answerable`).
- Alıntı doğrulaması alıntının *ilgili* olduğunu kanıtlamaz, yalnızca *gerçek* olduğunu kanıtlar.
  Model soruyla ilgisiz ama gerçek bir cümle alıntılarsa cevap aşamasına geçilir.

## Yeniden ölçüm (altın set v2, 165 soru, 2026-11-06)
| Ölçüt | Değer |
|---|---|
| Cevapsız soruda "bilmiyorum" | %93,1 (29 sorunun 27'si) |
| Cevaplı soruda gereksiz "bilmiyorum" | **%30,1** (136 sorunun 41'i) |
| Cevap doğru, tüm cevaplı sorular / model cevap verdiğinde | %61,0 / %87,4 (bkz. ADR-0010) |
| Ortanca ilk token / toplam süre | 57,1 sn / 64,9 sn |

- **Aşağıdaki %30 tetikleyicisi aşıldı.** Sistem cevap verdiğinde çoğunlukla doğru ama cevaplanabilir
  soruların üçte birine yakınında susuyor; 41'in 35'inde altın kaynak bağlamdaydı. Sorun aramada
  değil, 3B modelin alıntı becerisinde. Model ya da istem değişikliği sıradaki iştir.
- **Zayıf noktalar:** çok kaynaklı soruların yalnızca 11/33'ü doğru; Türkçe sorular 33/64, İngilizce
  50/72. Türkçe cevaplarda dil karışması görülüyor ("Bu information…") ve bu ölçülmüyor.
- **Uydurma tamamen bitmedi.** `kvkk-003` ve `kvkk-177` gerçek bir alıntıya dayanıp soruyla ilgisiz
  cevap verdi. Bu, aşağıda kabul edilen "alıntı gerçek ama ilgisiz" riskidir.
- **Süre düzeltmesi.** Önceki raporlar yalnızca son model çağrısını sayıyordu; kanıt çağrısı
  (~50 sn) eksikti. Eski "41 sn" gerçek süreyi olduğundan az gösteriyordu. İki çağrı artık toplanıyor.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Düşük.** İki aşamalı akış tek bir sınıftadır (`Answerer`). Güçlü bir sağlayıcıyla tek aşamaya
dönmek bir ayardır.

Tetikleyiciler:
- Cevaplı sorularda gereksiz "bilmiyorum" oranı %30'u geçerse: model ya da istem değişir.
- GPU'lu çalışma ortamı ya da onaylı bir bulut sağlayıcısı mevcut olursa: zincirin başına eklenir
  ve aynı değerlendirmeyle karşılaştırılır.
