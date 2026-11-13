# Faz 6: Dağıtım — tasarım

- Tarih: 2026-11-13
- Durum: Taslak (onay bekliyor)
- İlgili: ADR-0009 (GitOps ile dağıtım, bu işte yazılacak), ADR-0008 (LLM zinciri), ADR-0017/0018 (izleme), ADR-0019 (yük testi), tehdit modeli T9, T19

## Amaç ve neden

Meridian bir portfolyo projesidir. Faz 6'nın amacı, bakan birinin iki şeyi kendi gözüyle görebilmesidir:

1. **Canlı link:** Sistem gerçek bir sunucuda, TLS ile, tıklanabilir bir adreste çalışır; demo kullanıcısıyla
   giriş yapılıp soru sorulabilir, kaynaklı ve hızlı cevap alınır.
2. **Tekrar kurulabilirlik:** Her şey koddan, tek komutla, sıfırdan kurulur ve kaldırılır. Aynı Helm chart'ları
   ve GitOps yapısı yerelde de çalışır ve CI her PR'da bunu sınar.

Canlı ortam sürekli açık değildir: demo öncesi bir komutla açılır, sonra kapatılır. Bulut maliyeti yalnızca açık
kalınan saatler kadardır.

## Hedefler

- `infra/helm`: uygulama ve altyapı için Helm chart'ları (api, ai-service, web; PostgreSQL+pgvector, Redis, RabbitMQ,
  Keycloak; izleme yığını).
- GitOps: Argo CD, repodaki bir ortam dizinini (`infra/gitops/<ortam>`) izler ve kümeyi ona eşitler.
- **Yerel ortam:** `make k8s-up` / `make k8s-down` — kind kümesi, Argo CD, uygulama. CI işi bunu her PR'da kurar ve
  duman testi çalıştırır.
- **Demo ortamı:** `make demo-up` / `make demo-down` — Terraform ile Hetzner Cloud sunucusu, üzerinde k3s, Argo CD,
  uygulama, Let's Encrypt TLS. Kalıcı IPv4 (Primary IP) sayesinde link her kurulumda aynıdır:
  `https://meridian.<ip>.sslip.io` (gerçek IP kurulumda belli olur).
- İmaj hattı: api, ai-service ve web imajları CI'da derlenir, GHCR'a (`ghcr.io/engineer-coding/meridian-*`, herkese
  açık) commit SHA ve sürüm etiketiyle gönderilir.
- **Ön adım — Haiku sağlayıcısı:** AI servisine `anthropic/<model>` sağlayıcısı eklenir; demo zinciri
  `anthropic/claude-haiku-5-5`. Altın sette ölçülür ve CHANGELOG'a yazılır.
- Demo verisi hazır gelir: korpus (Kubernetes belgeleri + KVKK) indekslenmiş olarak açılır, bakan kişi beklemez.
- Faz 6'ya bırakılan tehdit modeli işleri: TLS (T9'un taşıma kısmı), AI servisi iç ucunun NetworkPolicy ile ayrılması
  (T19), iz örnekleme oranının ortama göre ayarlanması (ADR-0017).
- ADR-0009 yazılır; README "Durum" bölümü, CHANGELOG ve tehdit modeli güncellenir. Sürüm 0.7.0.

## Hedef olmayanlar

- Yüksek erişilebilirlik, çok düğümlü küme, otomatik ölçekleme, sıfır kesintili güncelleme.
- Yönetilen veritabanı ya da yönetilen Kubernetes (EKS/GKE/Hetzner yönetilen k8s yok); veriler sunucunun diskinde.
- Gerçek kullanıcı yükü, yedekleme ve felaket kurtarma. Demo verisi her kurulumda yeniden oluşturulur.
- Kendi alan adı ve DNS yönetimi (alan adı yok; sslip.io kullanılır).
- Demo sunucusunda Ollama ya da GPU.
- Web ve upload kaynak çekicileri, cevap kalitesi iyileştirmeleri (ayrı işler).
- Gece değerlendirme işi (ADR-0016'daki "Faz 6" notu): kapsam dışı bırakılır, ADR-0009'da sonraki adım olarak anılır.

## Başarısızlık sayılacaklar (çalışsa bile)

- Gizli bir değerin (API anahtarı, parola, Anthropic anahtarı) repoya, imaja ya da Terraform state'ine açık metin
  olarak girmesi. Repo herkese açıktır.
- Demonun açık kaldığının fark edilmemesi ve sessizce fatura biriktirmesi.
- Linke tıklayanın cevap için onlarca saniye beklemesi ya da ilk açılışta indeksleme beklemesi.
- Yerel ve demo ortamının ayrı, birbirinden kopuk tanımlar olması (aynı chart'lar, yalnızca değer dosyaları farklı).
- Herkese açık uç üzerinden sınırsız model çağrısı (maliyet saldırısı, T7).

## Kısıtlar

- Geliştirme makinesi Windows; komutlar Git Bash + GNU Make ile çalışır (README'deki mevcut kural).
- Repo herkese açık (`Engineer-coding/meridian`); Argo CD repoyu kimlik bilgisi olmadan okuyabilir, imajlar GHCR'da
  herkese açık olabilir.
- Hetzner fiyatları (2026-11-13, KDV hariç, saatlik ve aylık tavanlı): CPX32 4 vCPU/8 GB ~€0,049/sa (aylık €30–36),
  CPX42 8 vCPU/16 GB ~€0,095/sa (aylık €59–70), CX43 8 vCPU/16 GB €0,026/sa (aylık €16,49, şu an stokta yok).
  Primary IPv4 ayrıca ücretlenir (sayfada rakam yok; kurulumda netleştirilir).
- Haiku: `claude-haiku-5-5`, $0,10 / $0,50 per MTok (100K altı istemler). Soru başı ~$0,0005. Haiku'da sunucu tarafı
  yedek model yoktur; `refusal` durumunu Meridian'ın kendi zinciri karşılar.
- Embedding modeli (`multilingual-e5-large`, ~2,2 GB) sunucuda çalışır; soru gömmek için gereklidir.

## Değerlendirilen yaklaşımlar

| | Yaklaşım | Artı | Eksi |
|---|---|---|---|
| A | Sürekli açık VPS + k3s + Argo CD | Link hep açık | €30–70/ay; açık LLM uç noktası sürekli saldırıya açık |
| B | Yalnızca yerel (kind + Argo CD) | Sıfır maliyet, tam tekrar kurulabilir | Canlı link yok; Terraform yapay kalır |
| **C** | **Ortak chart + GitOps; yerel kind (CI'da sınanır) + Terraform'la açılıp kapanan demo sunucusu** | Gerçek Terraform, gerçek link, demo başına birkaç sent | İki ortam bakımı; kurulum süresi demo öncesi beklenir |

**Seçilen: C.** Kullanıcının kararı: canlı link demo için yeterli; sürekli açık olması gerekmez.

Model için değerlendirilenler: (1) sunucuda CPU Ollama — yeni kod yok ama ~65 sn cevap ve %30 gereksiz "bilmiyorum";
(2) **barındırılan model (Haiku)** — birkaç saniyede cevap, küçük bir kod işi; (3) GPU sunucu — portfolyo için
orantısız. **Seçilen: 2, Haiku** (kullanıcının kararı).

## Kullanıcının verdiği kararlar

- Yaklaşım C; canlı ortam yalnızca demo sırasında açık.
- Demo modeli Claude Haiku (`claude-haiku-5-5`), ayrı bir ön adım olarak.
- Alan adı yok; kalıcı IPv4 + sslip.io ile sabit link.
- Hetzner hesabı henüz yok. Anthropic API için $5 kredi alınacak.
- Haiku eşikleri konusu tasarımcıya bırakıldı (aşağıda "Haiku sağlayıcısı").

## Erişim ve kimin ne yapacağı

- **Kurucu (Claude) bitirir:** tüm kod, chart'lar, Terraform, Makefile hedefleri, CI işleri, belgeler. Doğrulama:
  yerel kind kümesi ve CI; Terraform için `validate` ve `plan` (sahte token'la değil, hesap açıldığında gerçek
  `plan`).
- **Sahibi yapar (runbook `docs/runbooks/demo.md` adım adım anlatır):**
  1. Hetzner hesabı ve **yalnızca Meridian için ayrı bir proje**; o projede okuma-yazma API token'ı. Ayrı proje
     şarttır: otomatik silme işinin token'ı tüm projeyi yönetebilir, kalıcı IP'yi korumanın en sağlam yolu projede
     başka bir şey olmamasıdır. Silme işi ayrıca yalnızca `app=meridian-demo` etiketli sunuculara dokunur.
  2. Anthropic API anahtarı ($5 kredi); konsolda aylık harcama sınırı.
  3. GitHub repo sırrı `HCLOUD_TOKEN` (silme işi için) ve ilk gönderimden sonra GHCR paketlerini "public" yapmak.
  4. İlk gerçek `make demo-up` / `demo-down` ve silme işinin bir kez denenmesi.
- Gerçek servis gerektiren bitti maddeleri (Haiku ölçüm raporları, ≤ 20 dk kurulum, sertifika, silme işi) bu
  adımlar tamamlanınca kapanır. Anahtar gelene kadar Haiku sağlayıcısı birim testleriyle (SDK taklidi) doğrulanır.
- Bütçe: Haiku ölçümleri (altın set + kırmızı takım) ve demo denemeleri $5 kredinin içinde kalmalı; tahmin < $1.
  Ölçüm komutu çalışmadan önce tahmini maliyetini yazar.

## Tasarım

### Bileşenler ve dizinler

```
infra/
  helm/
    meridian/            # şemsiye chart: api, ai-service, web (+ alt chart'lar ya da şablonlar)
  gitops/
    bootstrap/           # Argo CD kurulumu ve "app of apps" kökü
    local/               # kind ortamı: Application tanımları + değer dosyaları
    demo/                # Hetzner ortamı: Application tanımları + değer dosyaları
  terraform/
    demo/                # Hetzner: sunucu, kalıcı Primary IP, güvenlik duvarı, SSH anahtarı, cloud-init
    persistent/          # yalnızca Primary IP (demo-down'da silinmez; ayrı state)
  kind/                  # kind küme yapılandırması
apps/api/Dockerfile, apps/web/Dockerfile   # yeni; ai-service'inki mevcut
```

### İmaj hattı

- Yeni CI işi (ya da ayrı workflow) `main`'e her push'ta ve sürüm etiketinde üç imajı derler, GHCR'a
  `sha-<kısa>` ve `vX.Y.Z` etiketleriyle gönderir. PR'larda imaj derlenir ama gönderilmez (kind ortamına
  `kind load` ile yüklenir).
- Imajlar root olmayan kullanıcıyla çalışır; API için katmanlı jar (Spring Boot), web için Next.js `standalone`.
- Demo ortamı değer dosyasında sabit bir imaj etiketi kullanır; sürüm yükseltmek = o dosyada etiketi değiştiren
  commit (GitOps).

### Kümeler

- **Yerel:** kind, tek düğüm. Giriş için ingress-nginx (ya da k3s ile tutarlılık için Traefik — kurucunun kararı),
  `*.localtest.me` gibi 127.0.0.1'e çözülen bir ad ve öz-imzalı sertifika.
- **Demo:** Hetzner'de tek sunucu, cloud-init ile k3s kurulur (Traefik dahil). cert-manager + Let's Encrypt HTTP-01 ile
  `meridian.<ip>.sslip.io` için sertifika. Güvenlik duvarı yalnızca 80/443'ü herkese, 6443 ve 22'yi yalnızca
  kurulumu yapanın IP'sine açar.
- Let's Encrypt aynı ad için haftada 5 sertifika verir ve ad hiç değişmez. **Karar (tasarımcının):** `make demo-down`
  sertifika Secret'ını git dışı yerel bir dosyaya (`infra/gitops/demo/tls-backup.yaml`, `.gitignore`'da) yedekler,
  `make demo-up` varsa geri yükler; prova kurulumları için `DEMO_TLS=staging` seçeneği vardır.
- Her iki kümede Argo CD aynı şekilde kurulur (`gitops/bootstrap`), sonra ortamın kök Application'ı uygulanır.

### Durumlu servisler

- PostgreSQL+pgvector, Redis, RabbitMQ ve Keycloak kümede, PVC'lerle çalışır (yerel: kind'in yerel diski;
  demo: k3s local-path). Veriler kalıcı değildir: `demo-down` sunucuyu ve verisini siler.
- Mevcut veritabanı rolleri, RLS ve Flyway göçleri aynen kullanılır; compose'daki `postgres/init` betikleri
  chart'ta init betiği olarak yeniden kullanılır.
- RustFS (S3) şu an hiçbir akışta kullanılmıyorsa chart'a alınmaz (kurucu doğrular).

### Gizli değerler

Repo herkese açık olduğu için hiçbir gizli değer git'e girmez — şifreli olarak bile.

- Kurulum betiği gizli değerleri yerel, git'e girmeyen bir dosyadan (`infra/gitops/demo/secrets.env`, `.gitignore`'da)
  ya da ortam değişkenlerinden okur ve kümeye `kubectl create secret` ile yazar. Eksik değer varsa kurulum durur.
- Demo için rastgele parolalar kurulumda üretilir (veritabanı rolleri, RabbitMQ, Keycloak yöneticisi,
  `AI_INTERNAL_TOKEN`, web oturum anahtarı). Yalnızca `ANTHROPIC_API_KEY` dışarıdan gelir.
- Terraform state'ine gizli değer yazılmaz: Hetzner token'ı ortam değişkeninden okunur, uygulama sırları
  Terraform'dan geçmez. State yereldedir (`infra/terraform/*/terraform.tfstate`, `.gitignore`'da).
- Değerlendirilen alternatifler: SOPS+age ya da Sealed Secrets ile şifreli sırları repoda tutmak. Reddedildi:
  her kurulumda küme yeniden yaratıldığı için Sealed Secrets anahtarı kaybolur; SOPS Argo CD'ye eklenti ister ve
  demo için yalnızca bir dış sır var.

### Demo verisi ve hazır açılış

- Kurulumun son adımı bir Kubernetes Job'ıdır: demo kiracısını, koleksiyonu ve kaynakları API üzerinden oluşturur,
  indekslemenin bitmesini bekler. Bu iş bitmeden `make demo-up` "hazır" demez.
- CPU'da tam korpus indekslemesi uzun sürüyorsa (ölçülecek), Job önceden hazırlanmış bir veritabanı dökümünü
  (embedding'ler dahil, GitHub sürüm dosyası olarak) geri yükler. Hangisinin kullanılacağına kurulum süresi ölçülerek
  karar verilir; hedef `make demo-up` toplamı ≤ 20 dk.
- Embedding modeli imaja gömülür ya da ilk açılışta indirilip PVC'de tutulur (kurucunun kararı; imaj boyutu ile açılış
  süresi arasındaki denge).

### Demo erişimi ve kötüye kullanım koruması

- Keycloak'ta tek bir demo kullanıcısı (`demo`, viewer rolü, demo kiracısına üye). Parolası README'de yazılır;
  yalnızca okuma ve soru sorma yapabilir. Kayıt kapalı.
- Demo kiracısının günlük token kotası düşük tutulur (ör. 200 bin token ≈ birkaç yüz soru); mevcut kota ve kullanıcı
  başına oran sınırı aynen geçerlidir. Anthropic konsolunda anahtar için aylık harcama sınırı konur (README'de
  adım olarak).
- Ajan sayfası ve MCP demoda açıktır ama `create_ticket` onay gerektirdiği için demo kullanıcısı yazma işlemi yapamaz.
- Yönetim paneli için ayrı bir `demo-admin` kullanıcısı yalnızca kurulumu yapana verilir (parola `secrets.env`'den).

### Maliyet koruması

- `make demo-up` sonunda adres, açılış zamanı ve "kapatmak için `make demo-down`" uyarısı yazılır.
- Sunucuya `expires-at` etiketi konur (varsayılan açılıştan 4 sa sonra). Bir GitHub Actions zamanlanmış işi saatte
  bir Hetzner API'sini sorar ve süresi geçen demo sunucusunu siler (Hetzner token'ı repo sırrı olarak). Primary IP
  bu işten etkilenmez.
- Sunucu tipi Terraform değişkenidir. Varsayılan, ölçülen bellek ihtiyacına göre seçilir (8 GB CPX32 hedeflenir;
  izleme yığını + embedding modeli sığmazsa 16 GB). Her iki durumda da 3 saatlik demo < €0,50.

### Haiku sağlayıcısı (ön adım)

- `llm.py`'ye resmî `anthropic` Python SDK'sıyla `AnthropicLLM` eklenir; mevcut `LLM` ve `StructuredLLM`
  protokollerini uygular: `stream()` → `messages.stream`, `complete_json()` → yapılandırılmış çıktı
  (`output_config.format`). Düşük gecikme için düşük effort; `refusal` ve 429/5xx/bağlantı hataları ilk token'dan
  önce `LLMUnavailable` olarak zincire döner.
- `LLM_CHAIN=anthropic/claude-haiku-5-5,ollama/llama3.2:3b` biçimi desteklenir; anahtar `ANTHROPIC_API_KEY`
  ortam değişkeninden okunur. Token sayaçları mevcut muhasebeye (`usage`) iletilir.
- Altın set v2 ve kırmızı takım seti Haiku ile ölçülür, raporlar `packages/eval/reports` altına yazılır,
  CHANGELOG'da `llama3.2:3b` ile karşılaştırılır. CI'daki modelsiz testler değişmez.
- **Karar (tasarımcının; kullanıcı bıraktı):** Haiku raporları resmî raporların (`reports/answers.*`,
  `reports/redteam.*`, `history.json`) yerine geçer; yönetim panelinin değerlendirme verisi de onlardan üretilir.
  `llama3.2:3b` raporları ayrı adla saklanır ve karşılaştırma tablosunda kalır. Neden: demoda gösterilen model Haiku.
- **Karar (tasarımcının):** Cevap eşiklerinden (`thresholds.json`) biri aşılırsa Faz 6 durmaz; aşım CHANGELOG'a ve
  ayrı bir işe yazılır, eşik değiştirilmez. İstisna: kırmızı takımda başarılı saldırı eşiği (`attacks_succeeded ≤ 2`)
  aşılırsa demo açılmaz; önce düzeltilir. Neden: kalite eksikliği gösterilebilir, güvenlik gerilemesi gösterilemez.
- Tehdit modelindeki açık soru ("LLM sağlayıcıya hangi alanlar gidiyor?") bir veri akış tablosuyla cevaplanır:
  soru metni ve seçilen parçalar Anthropic'e gider; PII maskeleme indekslemede yapıldığı için parçalar maskelidir.

### Ağ politikaları ve izleme

- NetworkPolicy: AI servisinin iç ucu (`/internal/v1/*`) yalnızca API pod'larından erişilebilir; veritabanına yalnızca
  api ve ai-service; RabbitMQ'ya yalnızca api ve ai-service. Yerelde kind'in varsayılan CNI'ı NetworkPolicy
  uygulamıyorsa Calico kurulur ya da kind'de politika testi atlanıp demo (k3s, flannel + kube-router politikaları)
  üzerinde doğrulanır — kurucu seçer, nedenini ADR-0009'a yazar.
- İzleme yığını (Collector, Tempo, Prometheus, Loki, Grafana) ve mevcut panolar/alarmlar chart'a taşınır. Demoda
  Grafana herkese açık değildir (yalnızca port-forward). Örnekleme oranı ortam değeridir (yerel 1,0, demo 0,2 gibi).

### CI

- Yeni iş `k8s`: kind kümesi kurar, Argo CD'yi ve uygulamayı GitOps ile ayağa kaldırır, Argo'nun "Synced/Healthy"
  olmasını bekler, duman testi çalıştırır (sağlık uçları + sahte modelle bir sohbet akışı; mevcut `e2e-full`
  senaryosunun bir alt kümesi). Gerçek Anthropic ya da Hetzner çağrısı yoktur.
- Sahte parçalar (model, embedding, GitHub çekici) bugün yalnızca `apps/ai-service/tests/e2e_stack.py` içinde.
  **Karar (tasarımcının):** ai-service Dockerfile'ına ayrı bir `test` hedefi eklenir; bu hedef sahte parçaları
  içerir ve yalnızca CI'daki `k8s` işinde, değer dosyasıyla seçilen imaj etiketi olarak kullanılır. Üretim kodu ve
  üretim imajı değişmez. "Aynı chart'lar" kuralı chart'lar içindir; imaj etiketi zaten bir değerdir. Neden:
  CI'a 2,2 GB model indirmek ya da üretime sahte sağlayıcı koymak daha kötü.
- `terraform fmt -check` ve `terraform validate`, `helm lint` ve şablonların `kubeconform` ile doğrulanması.
- İmaj gönderimi yalnızca `main` ve etiketlerde.

## Kurucuya bırakılanlar

- Chart yapısı (şemsiye + alt chart mı, tek chart mı), üçüncü taraf chart kullanımı (Bitnami vb.) ya da kendi
  manifestleri — lisans ve imaj erişilebilirliği kontrol edilerek.
- Yerel ingress denetleyicisi ve ad çözümü.
- Embedding modelinin imaja gömülüp gömülmeyeceği; demo verisinin canlı indeksleme mi döküm mü olacağı (ölçüme göre).
- RustFS'in gerekip gerekmediği.
- Sunucu tipinin varsayılanı (bellek ölçümüne göre).
- Kesin kota rakamları.

## Çıktılar ve bitti tanımı

- `make k8s-up` temiz bir makinede yerel kümeyi kurar; CI'daki `k8s` işi yeşil.
- `make demo-up` → ≤ 20 dk içinde `https://meridian.<ip>.sslip.io` geçerli sertifikayla açılır, demo kullanıcısı
  girip korpustan bir soruya Haiku ile birkaç saniyede kaynaklı cevap alır. `make demo-down` sunucuyu siler, IP kalır;
  tekrar `demo-up` aynı linki verir.
- Süresi geçen demo sunucusu zamanlanmış işle silinir (bir kez denenerek doğrulanır).
- Repoda, imajlarda ve Terraform state'inde gizli değer yok (gitleaks + elle kontrol).
- Haiku ölçüm raporları, ADR-0009, güncel README (kurulum + demo bölümü + maliyet), tehdit modeli (T9 taşıma, T19,
  veri akış tablosu), runbook (`docs/runbooks/demo.md`), CHANGELOG 0.7.0.
