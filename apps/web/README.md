# Meridian web

Next.js (App Router) arayüzü: giriş, akışlı sohbet, kaynak gösteren cevaplar. Oturum ve API
vekili için [ADR-0013](../../docs/adr/0013-web-session-bff.md).

```bash
cp .env.example .env.local
npm ci
npm run dev        # http://localhost:3000; Keycloak, API ve AI servisi çalışıyor olmalı
```

Yerel kullanıcılar `infra/helm/meridian/files/keycloak/meridian-realm.json` içindedir. Yönetim paneli `/admin`
altındadır: kaynaklar, kullanım ve kota, değerlendirme, API anahtarları, denetim kayıtları. Ajan `/agent`
sayfasındadır; adımları gösterir, yazma işlemlerinde onay ister.

| Komut | İş |
|---|---|
| `npm run lint`, `npm run typecheck` | ESLint ve TypeScript |
| `npm test` | Vitest: SSE ayrıştırma, sohbet durumu, atıflar, oturum çerezi, vekil kuralları, axe |
| `npm run test:e2e` | Playwright: üretim derlemesi + sahte OIDC ve API (`e2e/stub-server.mjs`), sohbet ve panel |
| `make e2e-full` (kökten) | Tam sistem: gerçek Keycloak girişi, API, AI servisi, RabbitMQ, PostgreSQL; ayrı portlar ve atılabilir veri (`e2e-full/`) |
| `npm run gen:eval` | `packages/eval` raporları değişince paneldeki değerlendirme özetini üretir (CI denetler) |
| `npm run gen:api` | `packages/api-contract/openapi.yaml` değişince TypeScript tiplerini üretir (CI denetler) |

## Yapı
- `src/app/`: sayfalar, `auth/*` giriş uçları, `api/v1/*` API vekili
- `src/server/`: yalnızca sunucuda çalışan kod (oturum, OIDC, vekil kuralları)
- `src/features/`: `chat`, `agent`, `admin`, `onboarding`, `shell`
- `src/i18n/`: Türkçe ve İngilizce metinler (dil tarayıcıdan seçilir)

## Sınırlar
- `make e2e-full` modeli, embedding'i ve GitHub'ı sabit parçayla değiştirir (`apps/ai-service/tests/e2e_stack.py`):
  gerçek model kalitesini değil, sistemin birlikte çalışmasını sınar. Akış ve durum ayrıntıları `npm run test:e2e` içindedir.
- Panel canlı ilerlemeyi 3 saniyede bir sorgulayarak gösterir (yüzde yok, olay akışı yok). Takılı kalan
  `pending` kaynak için yeniden deneme yoktur; yalnızca `failed` yeniden denenir.
- Kaynak formu yalnızca GitHub sunar: AI servisinde web ve yükleme çekicileri henüz yok.
- Henüz yok: yeniden bağlanma (`Last-Event-ID`), geri bildirim, belgede satıra gitme, tema seçici
  (tema işletim sisteminden gelir), Storybook, görsel regresyon, Lighthouse CI.
