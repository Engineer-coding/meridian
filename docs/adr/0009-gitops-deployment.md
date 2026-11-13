# ADR-0009: GitOps ile dağıtım: Helm, Argo CD, kind ve açılıp kapanan demo

- Durum: Kabul edildi
- Tarih: 2026-11-13

## Bağlam
Meridian bir portfolyo projesi. Bakan kişi iki şeyi görebilmeli: sistem canlı bir adreste çalışıyor ve her
şey koddan, tek komutla sıfırdan kuruluyor. Yük ya da yüksek erişilebilirlik hedef değil. Kısıtlar:

- Repo herkese açık. Hiçbir gizli değer repoya, imaja ya da Terraform state'ine girmemeli; şifreli olarak bile.
- Sürekli açık bir sunucu hem para hem saldırı yüzeyi demek.
- Geliştirme makinesi Windows (Git Bash + GNU Make).
- Uygulama kodu tek bir OIDC issuer görür. Tarayıcı ve küme içindeki pod'lar aynı adresi kullanmalı.

Tasarım: [docs/superpowers/specs/2026-11-13-faz6-deployment-design.md](../superpowers/specs/2026-11-13-faz6-deployment-design.md).

## Karar
Ortak bir Helm chart'ını iki ortama kuruyoruz:
- **Yerel ortam:** kind kümesi. CI bu kurulumu her PR'da sınar.
- **Demo ortamı:** Terraform ile açılıp kapanan tek bir sunucu (Faz 6.3).

Kümeyi her iki ortamda da Argo CD repodan senkronlar.

- **Chart** (`infra/helm/meridian`): Üç uygulamayı ve durumlu servisleri resmî imajlarla, kendi sade
  manifestleriyle kurar. Bitnami kullanılmaz, çünkü imajları artık ücretsiz dağıtılmıyor. İzleme yığını
  isteğe bağlıdır. Ortam farkları yalnızca değer dosyalarındadır (`values-local.yaml`, `values-ci.yaml`).
- **Ortak yapılandırma dosyaları:** İzleme ve Postgres yapılandırmaları ile geliştirme realm'i chart'ın
  `files/` dizininde durur, compose da onları oradan bağlar. Böylece tek kaynak olur. Altyapı servisleri
  compose'daki adlarını korur (`postgres`, `rabbitmq`, `tempo`…). Bu yüzden pod'larda
  `enableServiceLinks: false` gerekir; aksi halde `POSTGRES_PORT=tcp://…` gibi değişkenler uygulama
  ayarlarıyla çakışır.
- **Tek adres:** Web `/`, Keycloak `/auth`, MCP `/mcp` yolunda. API ve AI servisinin `/internal` ucu
  dışarıya açık değildir. CoreDNS uygulama adını küme içinde Traefik'e yönlendirir. Böylece pod'lar
  issuer'a tarayıcıyla aynı adresten ulaşır ve uygulama kodu ayrı bir iç adres bilmez.
- **Ingress:** Traefik (k3s ile aynı).
- **Yerel ortamda TLS yok:** Yerel ortam HTTP'dir. Öz-imzalı sertifika, BFF ve API'de ayrı bir güven
  deposu gerektirirdi. TLS demoda gerçek sertifikayla sınanır.
- **Gizli değerler:** `infra/k8s/secrets.sh`, `meridian-secrets` Secret'ını git dışındaki bir env
  dosyasından yalnızca bir kez oluşturur. Secret zaten varsa dokunmaz, çünkü veritabanı rolleri ilk
  açılışta bu parolalarla kurulur.
- **Argo CD ve revision:** Application tanımları `infra/gitops/` altındadır. `up.sh` bunlara revision'ı
  yazar; "app of apps" kökü yoktur, çünkü bir kök Application, alt uygulamaların hangi revision'ı
  izleyeceğini git'ten bilemez. Hızlı deneme için `make k8s-dev`, aynı chart'ı çalışma ağacından
  `helm` ile kurar.
- **Seed işi:** Kiracıyı, koleksiyonu, kaynakları ve izleyici üyeliklerini kurar; tekrar çalıştırmak
  güvenlidir. Argo için bir PostSync kancası olarak çalışır. Aynı pod tanımı, elle yeniden çalıştırmak
  için askıya alınmış bir CronJob olarak da üretilir. API'de üye ekleme ucu olmadığı için izleyiciler
  doğrudan veritabanına yazılır.
- **Ağ politikaları (T19):** Yalnızca gelen trafik kısıtlanır. AI servisine yalnızca API ve Traefik
  erişebilir. Postgres, RabbitMQ ve Redis'e yalnızca onları kullanan bileşenler erişebilir. kind'ın
  varsayılan CNI'ı (kindnet) bu politikaları uygular; ek bir CNI gerekmez. Duman testi bunu her kurulumda
  denetler.
- **Demo (Faz 6.3):** Hetzner Cloud'da, ayrı bir projede tek sunucu. Üzerinde k3s, Let's Encrypt ve
  kalıcı bir IPv4 adresi (`meridian.<ip>.sslip.io`) olur. Demo `make demo-up` ve `make demo-down` ile
  açılıp kapanır; süresi geçen sunucuyu zamanlanmış bir iş siler. Model Claude Haiku'dur (ADR-0008);
  demo sunucusunda Ollama yoktur.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| Sürekli açık VPS + k3s | Link her zaman açık | €30–70/ay; açık bir LLM ucu sürekli saldırıya açık |
| Yalnızca yerel kind | Maliyet yok, tamamen tekrar kurulabilir | Canlı link yok; Terraform yapay kalır |
| **Ortak chart; CI'da sınanan kind ortamı + açılıp kapanan demo** | Gerçek Terraform, gerçek link, demo başına birkaç sent | İki ortamın bakımı; demo öncesi kurulum süresi |
| Bitnami chart'ları | Hazır, ayrıntılı | İmajlar artık ücretsiz değil; davranışları compose'dan ayrışır |
| SOPS/age ya da Sealed Secrets | Sırlar repoda şifreli durur | Küme her kurulumda yeniden yaratıldığı için Sealed Secrets anahtarı kaybolur; SOPS, Argo CD'ye eklenti ister |
| Yerelde öz-imzalı TLS | Demoya daha benzer | BFF'de ve API'de güven deposu gerekir; asıl kanıtı demodaki gerçek sertifika verir |

## Sonuçlar
- **Gereksinimler:** `make images && make k8s-up` temiz bir makinede yerel kümeyi kurar. Gerekli
  araçlar: Docker, kind, kubectl ve helm. Sürümler tek yerde tutulur (`infra/versions.env`). CI'daki
  `k8s` işi, aynı kurulumu sahte model ve sahte GitHub ile her PR'da yapar ve duman testini çalıştırır.
- **Argo CD ve push:** Argo CD dalı GitHub'dan okur. Bu yüzden `make k8s-up` için dalın push edilmiş
  olması gerekir; push edilmemiş bir revision, küme kurulmadan önce reddedilir.
- **Port 80:** Yerel küme 80 numaralı portu kullanır; port doluysa kurulum hiç başlamaz.
- **GitHub kotası:** Kimliksiz GitHub API'si saatte 60 istek verir. Sık yeniden kurulumda seed bu sınıra
  takılabilir. İsteğe bağlı `GITHUB_TOKEN` desteklenir; seed, önceki çalıştırmadan başarısız kalan
  kaynakları yeniden kuyruğa koyar.
- **Keycloak:** `dev-file` veritabanıyla tek pod olarak çalışır ve realm her açılışta değer
  dosyalarından yeniden içe aktarılır. Kullanıcı kimlikleri sabit olduğu için üyelikler yeniden
  başlatmada bozulmaz. Bu kurulum üretim için değildir.
- **Kapsam dışı:** Yüksek erişilebilirlik, yedekleme ve yönetilen servisler. Canlı değerlendirmenin bir
  gece işine taşınması (ADR-0016'daki not) da bu fazın kapsamında değildir.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
- **Dönüş maliyeti:** Düşük. Chart ve betikler, compose tabanlı geliştirmeyi etkilemez.
- **Yeniden değerlendirme tetikleyicileri:**
  - Gerçek kullanıcılar gelirse yönetilen veritabanı, yedekleme ve şifreli sırlar (SOPS ya da harici bir
    sır deposu) gerekir.
  - Demo kurulumu 20 dakikayı aşarsa seed, canlı indeksleme yerine hazır bir veritabanı dökümüne geçer.
