# Yük testi

k6 ile iki senaryo ([ADR-0019](../../docs/adr/0019-load-test.md)). Altyapı atılabilirdir (`compose.e2e.yaml`),
API ve AI servisi gerçektir; model ve embedding sahtedir. Ölçülen, sistemin kapasitesidir, modelin değil.

```bash
make load                      # SCENARIO=chat: 500 eşzamanlı sohbet
SCENARIO=indexing make load    # 50 eşzamanlı indeksleme işi
```

| Ayar | Varsayılan | Ne yapar |
|---|---|---|
| `VUS`, `RAMP`, `HOLD` | 500, 60s, 180s | Sohbet yükünün şekli |
| `JOBS` | 50 | Eşzamanlı indeksleme işi |
| `MODEL_DELAY` | `1,0.5,3` | Sahte modelin kanıt, ilk token ve toplam süresi (saniye) |
| `AI_WORKERS` | 2 | AI servisindeki Python süreci sayısı |
| `DB_POOL_SIZE`, `API_POOL_SIZE` | 4, 20 | AI ve API veritabanı havuzları |
| `SAMPLING` | 0.1 | İz örnekleme oranı |
| `KEEP=1` | | Bitince altyapı ayakta kalır (Grafana `http://127.0.0.1:13001`, Tempo `13201`) |

Raporlar `reports/` altında: k6 özeti (`*-summary.json`, `*-k6.txt`) ve aynı pencerede Prometheus'tan okunan
sunucu ölçümleri (`*-server.json`). Süreç logları `reports/logs/` altındadır ve depoya girmez.

## Sonuç: 500 eşzamanlı sohbet

Ortam: tek geliştirme makinesi (12 çekirdek, Windows 11, Docker Desktop). API JVM'de, AI servisi Linux
kapsayıcısında, altyapı Compose'da; hepsi aynı makinede. Model gecikmesi `1,0.5,3` (kanıt 1 sn, ilk token 0,5 sn,
cevap 3 sn): barındırılan bir modelin hızına yakındır. Her sanal kullanıcı konuşma açar, soru sorar, akışı sonuna
kadar okur, 1 sn bekler.

| Adım | Tam cevap p50 / p95 / p99 | İlk olay p95 | Cevap/sn | Tamamlanan | Arama p95 |
|---|---|---|---|---|---|
| AI servisi Windows'ta | 18,4 / 23,8 / 25,2 sn | 19,9 sn | 23,5 | %99,65 | 28,8 sn |
| AI servisi Linux kapsayıcısında | 8,3 / 13,4 / 14,4 sn | 7,6 sn | 42,4 | %99,88 | 8,8 sn |
| AI havuzu 4 → 20 | 9,2 / 14,3 / 15,6 sn | 9,5 sn | 38,8 | %99,96 | 9,3 sn |
| Talimat taramasına önbellek | 6,4 / 10,0 / 11,7 sn | 5,4 sn | 50,5 | %99,93 | 4,7 sn |
| AI servisi 2 süreç | 5,1 / 8,3 / 9,6 sn | 3,1 sn | 57,3 | %99,94 | 0,10 sn |
| **API havuzu 10 → 20 (son)** | **4,3 / 7,4 / 8,1 sn** | **1,4 sn** | **68,1** | **%99,97** | 0,27 sn |

Son yapılandırmada k6 eşikleri geçer: tam cevap p95 < 8 sn, tamamlanan > %99,5, başarısız HTTP isteği %0
(42.326 istekte 0). Cevabın yaklaşık 4,5 saniyesi sahte modelin kendi süresidir; sistemin eklediği p95 ~3 sn.

### Bulunan darboğazlar, sırayla
1. **Windows'ta select() sınırı.** psycopg'nin asenkron sürücüsü Windows'ta `select()` döngüsü ister; bu ~512
   soketle sınırlı. 500 akışta AI servisi `too many file descriptors in select()` ile istek kaybetti, havuzu
   büyütmek sınıra daha erken vurdu (%32 cevap). Geliştirme makinesinin sınırıdır, üretimin değil: ölçüm AI
   servisini Linux kapsayıcısında çalıştırır (`apps/ai-service/Dockerfile`).
2. **AI havuzu değil, işlemci.** Havuzu 4'ten 20'ye çıkarmak sonucu değiştirmedi; AI süreci 0,88 çekirdekte
   takılıydı. "Arama yavaş" görünüyordu, çünkü dolu olay döngüsünde sorgu cevabı sırada bekliyordu (Tempo izi:
   13 saniyelik bir isteğin 9,2 saniyesi `retrieval.search`, embedding anlık).
3. **Belgedeki talimat taraması işlemcinin %30'u.** `py-spy` profili: `is_instruction_like` (ADR-0016) aynı
   parçaları her istekte, istem başına birkaç kez yeniden tarıyordu. Sonuç yalnızca metne bağlı olduğu için
   önbelleğe alındı: üç kaynak için 4,3 ms → 0,008 ms. Davranış değişmedi; kırmızı takım raporu yeniden üretildi.
4. **Tek Python süreci bir çekirdek.** İki süreçle arama p95 4,7 sn → 0,1 sn. Üretimde `HTTP_WORKERS` ya da
   ek kopya (Kubernetes adımı).
5. **API havuzu.** AI hızlanınca bekleme API'ye kaydı: 10 bağlantıda 239 istek sırada. 20 bağlantıyla p95
   hedefin altına indi; varsayılan 20 oldu. Sırada hâlâ en çok 126 istek görüldü: bir sonraki sınır budur.

## Sonuç: 50 eşzamanlı indeksleme işi

| Ölçüt | Değer |
|---|---|
| Hazır olan kaynak | 50/50 |
| Kabulden "ready"ye p50 / p95 / maks | 3,4 / 5,3 / 5,4 sn (hedef p95 < 60 sn) |
| Gerçek e5-large ile 10 sayfalık belge (41 parça), tek başına | ~42 sn (3 ölçüm: 42,7 / 41,9 / 42,0) |

Bu senaryoda embedding sahtedir; ölçülen outbox, kuyruk, çekme, parçalama ve yazma hattıdır ve hedefin çok
altındadır. Gerçek maliyet embedding'dedir: bu makinede tek belge ~42 sn. Tek belge boş sistemde hedefi tutar,
ama 50 belge aynı anda gelirse işlemci sınırı nedeniyle kuyruk kabaca yarım saatte boşalır (**tahmin**, gerçek
modelle 50 iş koşulmadı). Çözüm GPU'lu ya da ayrı ölçeklenen embedding işçileridir.

## Sınırlar
- Tek makine: yük üreten k6, API, AI servisi ve veritabanı aynı işlemcileri paylaşır. Sayılar bu makineye özgüdür.
- Model ve embedding sahte; gerçek modelle ilk token CPU'da dakikalar sürer (ADR-0018). "İlk token p95 < 1,5 sn"
  hedefi bu donanımda ölçülemez.
- Tek kullanıcıyla yük üretildiği için kullanıcı başına oran sınırı ve günlük kota yük ortamında kapatılır.
- API doğrudan çağrılır; web sunucusundaki oturum vekili bu testte yoktur (ADR-0013'teki vekil darboğazı
  ölçülmedi).
- Belge küçük ve tektir (41 parça); büyük indekste vektör aramasının maliyeti ayrıca ölçülmelidir.
