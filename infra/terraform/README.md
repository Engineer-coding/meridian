# Terraform: canlı demo (ADR-0009)

İki ayrı state, ikisi de yerel ve git dışında (`terraform.tfstate`):

| Dizin | İçerik | Ömür |
|---|---|---|
| `persistent` | Kalıcı IPv4 (Primary IP), `prevent_destroy` | Bir kez kurulur; link `meridian.<ip>.sslip.io` hep aynı kalır |
| `demo` | k3s sunucusu (CPX32), güvenlik duvarı, SSH anahtarı | `make demo-up` açar, `make demo-down` siler |

Hetzner token'ı yalnızca `HCLOUD_TOKEN` ortam değişkeninden okunur. Uygulama sırları Terraform'dan geçmez; kümeye
`infra/k8s/secrets.sh` yazar. Sunucu `app=meridian-demo` ve `expires-at=<unix saniye>` etiketlerini taşır;
süresi geçeni saatlik iş siler ([`infra/demo/reaper.py`](../demo/reaper.py)).

Doğrudan kullanılmaz: `make demo-up` / `make demo-down` çağırır. Denetim (Terraform kurulu olmadan, Docker ile):

```bash
make tf-check
```

Adım adım kurulum: [docs/runbooks/demo.md](../../docs/runbooks/demo.md).
