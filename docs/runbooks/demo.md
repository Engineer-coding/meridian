# Runbook: Canlı demo

Tasarım: [ADR-0009](../adr/0009-gitops-deployment.md). Demo, Hetzner'de tek bir k3s sunucusunda çalışır ve
`https://meridian.<ip>.sslip.io` adresinde açılır. Yalnızca demo sırasında açıktır: `make demo-up` ile açılır,
`make demo-down` ile kapanır. Kapatmayı unutursanız saatlik iş sunucuyu kendisi siler
([`demo-reaper`](../../.github/workflows/demo-reaper.yml)). IP kalıcıdır, bu yüzden link her açılışta aynı kalır.

## 1. Bir kez: hesaplar ve sırlar
1. **Hetzner Cloud hesabı ve yalnızca Meridian için ayrı bir proje.** Ayrı proje şart: silme işinin token'ı
   projedeki her şeyi yönetebilir. Projede başka bir şey olmaması kalıcı IP'yi de korur. Projede
   *Security → API tokens* bölümünden **okuma-yazma** yetkili bir token oluşturun. Bu token `HCLOUD_TOKEN`'dır;
   repoya ya da bir dosyaya yazmayın.
2. **SSH anahtarı.** `~/.ssh/id_ed25519` yoksa `ssh-keygen -t ed25519` ile oluşturun. Başka bir anahtar
   kullanacaksanız `SSH_KEY=<yol>` verin.
3. **Anthropic API anahtarı.** Kökteki `.env` dosyasında `ANTHROPIC_API_KEY=...` satırı olmalı. Konsolda
   *Limits* bölümünden **aylık harcama sınırı** koyun, örneğin $5. Demo kotası kiracı başına günde 200 bin
   token, bu da yaklaşık 50 sent eder.
4. **GitHub.** Bu dal `main`'e birleşince `images` iş akışı GHCR'a üç imaj gönderir. Bu paketleri
   *Packages → Package settings → Change visibility* bölümünden **Public** yapın; demo sunucusu imajları
   kimlik doğrulamadan çeker. Repo *Settings → Secrets → Actions* bölümüne `HCLOUD_TOKEN` ekleyin
   (silme işi için).

## 2. Prova (önerilen; sertifika sınırını harcamaz)
```bash
DEMO_TLS=staging HCLOUD_TOKEN=... make demo-up
```
```bash
DEMO_TLS=staging HCLOUD_TOKEN=... make demo-smoke
```
- Staging sertifikasına tarayıcı da, kümedeki API ve web servisleri de güvenmez. Bu yüzden prova yalnızca
  sunucuyu, k3s'i, Argo CD senkronunu, seed'i ve sertifika almayı sınar. Duman testinin 1–3. adımları geçer;
  giriş gerektiren adımların başarısız olması bu durumda beklenen sonuçtur.
- Bitince kapatın. Kalıcı IP kalır, staging sertifikası da yedeklenir; sonraki üretim kurulumunda yeni bir
  sertifika istenir.

```bash
HCLOUD_TOKEN=... make demo-down
```
`infra/gitops/demo/tls-backup.yaml` dosyası staging sertifikasını tutar. Üretim kurulumundan önce bu dosyayı
silin; yoksa staging sertifikası geri yüklenir.

## 3. Demo
```bash
HCLOUD_TOKEN=... make demo-up
```
- **Ne olur:** Kalıcı IP yoksa bir kez oluşturulur. Ardından sunucu açılır (`DEMO_HOURS`, varsayılan 4 saat)
  ve k3s, Argo CD, Traefik ve cert-manager kurulur. Meridian `main`'in son commit'iyle senkronlanır; seed işi
  `meridian-demo` kiracısını, KVKK ve Kubernetes Pods kaynaklarını kurar.
- **Bitince:** Betik adresi, otomatik silinme saatini ve kapatma komutunu yazar.
- **Giriş:** `demo` / `meridian-demo`. Bu kullanıcı izleyici rolündedir, soru sorabilir ve ajan sayfasını
  görebilir. Yönetim paneli için `demo-admin` kullanılır; parolası `infra/gitops/demo/secrets.env`
  içindeki `DEMO_ADMIN_PASSWORD` değeridir.
- **Doğrulama:**
  ```bash
  HCLOUD_TOKEN=... make demo-smoke
  ```
- **Süreyi uzatmak:** `DEMO_HOURS=2 make demo-up` aynı sunucuda yalnızca süreyi yeniden belirler.
- **Kapatmak:**
  ```bash
  HCLOUD_TOKEN=... make demo-down
  ```

## 4. Maliyet
| Kalem | Fiyat (KDV hariç, 2026-11) |
|---|---|
| CPX32 (4 vCPU, 8 GB), `hel1` | ~€0,049/saat, ay boyu açık kalırsa €30,49 tavan |
| Kalıcı IPv4 | Aylık küçük bir ücret (Hetzner fiyat sayfası); sunucu kapalıyken de ödenir |
| Claude Haiku 5.5 | Soru başına ~$0,0005; günlük kota kiracı başına 200 bin token |

3 saatlik bir demo, IP hariç €0,20'nin altında tutar. Kalıcı IP'yi tamamen bırakmak isterseniz
`infra/terraform/persistent` dizininde `prevent_destroy` kaldırılıp `terraform destroy` çalıştırılır;
bu durumda link değişir.

## 5. İlk gerçek kurulumda ölçülecekler
- **`make demo-up` süresi.** Hedef ≤ 20 dk. İlk indeksleme CPU'da ve embedding modelinin indirilmesi dahil.
  Aşılırsa seed, canlı indeksleme yerine hazır bir veritabanı dökümünü geri yüklemeye geçer (ayrı iş, ADR-0009).
- **Bellek.** `KUBECONFIG=infra/terraform/demo/kubeconfig kubectl top nodes` (k3s'te metrics-server var).
  Yerel kind'da tam yığın ~5,2 GiB kullanıyordu; 7 GiB'ı aşarsa `server_type=cpx42` kullanın.
- **Ağ politikaları.** Duman testinin 5. adımı k3s'in kube-router uygulamasında da geçmeli.

## 6. Sorun giderme
- **Sertifika gelmiyor:**
  ```bash
  kubectl -n meridian describe certificate meridian
  kubectl -n meridian get challenges
  ```
  80 numaralı port herkese açık olmalı (güvenlik duvarı). `meridian.<ip>.sslip.io` sunucunun IP'sine çözülmeli.
  Let's Encrypt aynı ad için haftada 5 sertifika verir; gerekirse prova için `DEMO_TLS=staging` kullanın.
- **Seed başarısız:**
  ```bash
  kubectl -n meridian logs job/meridian-seed
  ```
  - En sık nedeni GitHub'ın kimliksiz API kotası (saatte 60 istek). `.env` dosyasına `GITHUB_TOKEN`
    eklemek kotayı 5000'e çıkarır; anahtar `secrets.env`'e yalnızca ilk kurulumda kopyalanır.
  - Seed'i yeniden çalıştırmak:
    ```bash
    kubectl -n meridian create job seed-now --from=cronjob/meridian-seed
    ```
- **Cevaplar "yalnızca kaynaklar":** Haiku'ya ulaşılamıyor. Anahtarı ve harcama sınırını kontrol edin
  ([llm-outage.md](llm-outage.md)). Demoda yedek model yoktur.
- **k3s hazır olmuyor:**
  ```bash
  ssh -i ~/.ssh/id_ed25519 root@<ip> cloud-init status --long
  ```
- **Sunucu açık kaldı mı:** Hetzner konsolu ya da *Actions → demo-reaper → Run workflow* (dry-run).
