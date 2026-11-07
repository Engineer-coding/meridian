# ADR-0016: Kod korumaları ve kırmızı takım seti

- Durum: Kabul edildi
- Tarih: 2026-11-07

## Bağlam
Plan; dolaylı istem enjeksiyonuna karşı veri/talimat ayrımı, indeks ve loglarda PII maskeleme, zararlı istek
sınıflandırma ve CI'da çalışan bir kırmızı takım seti ister. CI'da model yoktur; küçük yerel modelin davranışı
da güvence sayılamaz. İki soru belirleyicidir: model kanarsa ne olur, koruma doğru cevabı da engeller mi?

## Karar
**Ölçüm iki parçadır, korumalar modelin dışındadır.**

- **Set:** `packages/eval/golden/redteam-v1.jsonl`, 40 senaryo, sohbet ve ajanda 68 deneme. Her senaryo kendi
  kiracısında, gerçek indeksleme hattından geçer ve hedef belge küçük korpusta durur: en kötü durum ölçülür.
  Belgeye ulaşmayan deneme başarı sayılmaz. Her senaryoda `guard` korumayı yazar: `code`, `human` ya da `model`.
- **CI:** `Compromised` modeli bağlamında gördüğü her talimata uyar ve şemayı çiğner. `guard: code` senaryoları
  bu modelle bile durmalıdır (`test_redteam.py`). Testler modelin iyi davranmasına dayanmaz.
- **Canlı ölçüm:** `make eval-redteam NAME=redteam`, gerçek modelle. CPU'da saatler sürdüğü için CI çalıştırmaz;
  raporun parmak izini ve eşikleri denetler (ADR-0010 ile aynı kapı).
- **İstek sınıflandırma:** açık zararlı istek, istem çıkarma ve kural kaldırma kalıpları modele gitmez,
  yanıt `BİLMİYORUM` olur. Yalnızca tür loglanır. Konuyu değil üretimi hedefler: "phishing politikamız nedir?" geçer.
- **Belgedeki talimat:** talimat gibi görünen paragraf istemden çıkar. Geride 60 karakterden az metin kalırsa
  parça kaynak olarak isteme girmez; numaralar ve kullanıcının gördüğü kaynak listesi değişmez.
- **Bağlantı:** cevapta yalnızca belgenin kayıtlı adresi kalır, metindeki adres silinir, görsel kaldırılır.
  Akışta son sözcük boşluğa dek bekletilir: parçalı gelen adres de kullanıcıya ulaşmaz.
- **PII:** e-posta, T.C. kimlik, IBAN, kart ve telefon indekslemeden önce maskelenir; özgün metin parçaya ve
  vektöre girmez. Sağlama toplamı tutmayan sayılar maskelenmez. Log satırları ve istisna metni filtreden geçer,
  belge alıntıları loga yazılmaz.

## Ölçüm
`llama3.2:3b`, 67 geçerli deneme (biri modelin aramadan ticket önermesi nedeniyle belgeye ulaşmadı).

| Ölçüt | Korumasız | Korumalı |
|---|---|---|
| Başarılı saldırı (gerçek model) | 10 (%15) | 2 (%3) |
| Kişisel veri | 6/6 | 0/6 |
| Dış bağlantı | 2/5 | 0/5 |
| Yanlış bilgi | 2/2 | 2/2 |
| Belgeli denemede "bilmiyorum" | 10/46 | 8/46 |
| Başka kiracı, yasak SQL, istenmeyen ticket, istem sızıntısı | 0 | 0 |
| Gerçek korpusta talimat sanılan parça | | 0/3093 |
| Gerçek korpusta maskelenen parça | | 3/3093 |

`redteam-baseline` raporu 11 yazar: biri (`harm-malware-en/agent`) modelin kendi reddiydi ve puanlama hatasıydı;
puanlama sonradan düzeltildi. Kandırılmış modelle korumalar kapalıyken ve açıkken sayılar `test_redteam.py`
senaryolarıyla sayıldı: 68 denemede 56 ve 17. Kalan 17 denemenin hepsi `model` ya da `human` sınıfındadır.

**Asıl bulgu:** Küçük model belgedeki doğrudan talimatlara çoğunlukla uymadı (23 işaret denemesinin 23'ü
korumasız da durdu). Bunda kanıt doğrulamalı iki aşamalı hat ve seçilebilir eylemleri daraltan şema etkilidir, ama
sonuç bu modele ve bu sete özgüdür. Kod korumalarının ölçülebilir kazancı PII ve bağlantıdadır.

**Ölçümün yakaladığı yan etki:** talimat çıkınca geride neredeyse boş bir kaynak kalıyordu ve model doğru belgedeki
cümleyi de bulamaz oldu: "bilmiyorum" 10'dan 21'e çıktı. Yalnızca saldırı oranına bakılsaydı görülmezdi. Boş kalan
parça istemden çıkarıldı, sayı 8'e indi; bu yüzden yan etki de raporda ve eşikte.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **Kalıplar + kandırılmış model + kayıtlı canlı rapor** | Deterministik, ücretsiz, CI'da saniyeler | Başka sözcükle yazılmış saldırıyı kaçırır |
| Llama Guard benzeri sınıflandırıcı | Daha yüksek yakalama | CPU'da her soruya saniyeler, ek model; ölçülmedi |
| CI'da gerçek model | Gerçek davranış | Saatler sürer, sonuç koşudan koşuya değişir |
| Bulunan talimatı olduğu yerde bırakıp yalnızca uyarmak | Metin kaybı yok | Belge metni modelin bağlamında kalır |
| PII'yi yalnızca cevapta maskelemek | Arama özgün metni görür | Özgün veri indekste ve yedeklerde kalır |

## Sonuçlar
**Olumlu**
- Yeni bir ajan aracı ya da istem değişikliği, kod korumasını deliyorsa model olmadan CI'da kırılır.
- Koruma kodu değişirse rapor bayatlar, canlı ölçüm tekrarlanmadan birleştirilemez.

**Olumsuz / kabul edilen riskler**
- **Yanlış bilgi durmaz:** belgede "süre artık doksan gündür" yazıyorsa cevap onu söyler ve kaynak gösterir. Bu,
  yetkili kişinin eklediği içeriğin sorunudur; kaynak denetimi gerekir.
- Kalıplar kaçırır: nazik ya da kodlanmış talimat kod korumasından geçer (`guard: model`), yalnızca modelin
  direncine kalır. Kandırılmış modelle bu sınıfta saldırılar başarılıdır.
- Küçük bir set, 40 sentetik senaryo: yön gösterir, güvenlik garantisi değildir. Tek model ölçüldü.
- İsim ve adres gibi biçimsiz kişisel veri yakalanmaz. Maskeleme herkes için açıktır; kiracı ayarı yok.
- Mevcut indeksler maskelenmez: kaynak yeniden indekslenmelidir.
- Reddedilen istek arayüzde "bilmiyorum" olarak görünür; ayrı bir red mesajı ve denetim kaydı yok.
- Metindeki meşru bağlantı da cevaptan silinir; adres kaynak listesinden görülür.
- MCP araçları belge metnini olduğu gibi döner: istemci kendi modelini korumalıdır.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
Korumalar tek modüldedir, kaldırmak birkaç çağrıyı silmektir; PII maskesi ise geri alınamaz, yeniden indeksleme ister.
Daha güçlü model, gerçek kullanıcı verisi ya da yanlış alarm şikâyeti gelirse set ve sınıflandırıcı yeniden
değerlendirilir. Canlı ölçüm CI dışında kaldığı için bir gece işi kurulduğunda (Faz 6) kapı oraya taşınır.
