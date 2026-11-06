# Meridian web

Next.js (App Router) arayüzü: giriş, akışlı sohbet, kaynak gösteren cevaplar. Oturum ve API
vekili için [ADR-0013](../../docs/adr/0013-web-session-bff.md).

```bash
cp .env.example .env.local
npm ci
npm run dev        # http://localhost:3000; Keycloak, API ve AI servisi çalışıyor olmalı
```

Yerel kullanıcılar `infra/compose/keycloak/meridian-realm.json` içindedir.

| Komut | İş |
|---|---|
| `npm run lint`, `npm run typecheck` | ESLint ve TypeScript |
| `npm test` | Vitest: SSE ayrıştırma, sohbet durumu, atıflar, oturum çerezi, vekil kuralları, axe |
| `npm run test:e2e` | Playwright: üretim derlemesi + sahte OIDC ve API (`e2e/stub-server.mjs`) |
| `npm run gen:api` | `packages/api-contract/openapi.yaml` değişince TypeScript tiplerini üretir (CI denetler) |

## Yapı
- `src/app/`: sayfalar, `auth/*` giriş uçları, `api/v1/*` API vekili
- `src/server/`: yalnızca sunucuda çalışan kod (oturum, OIDC, vekil kuralları)
- `src/features/`: `chat`, `onboarding`, `shell`
- `src/i18n/`: Türkçe ve İngilizce metinler (dil tarayıcıdan seçilir)

## Sınırlar
- Uçtan uca testler sahte sunucuyla çalışır. Gerçek Keycloak, API ve modelle akış elle doğrulandı;
  tam yığınla otomatik senaryo, Faz 4 kapısı için ayrıca eklenecek.
- Henüz yok: yeniden bağlanma (`Last-Event-ID`), geri bildirim, belgede satıra gitme, tema seçici
  (tema işletim sisteminden gelir), Storybook, görsel regresyon, Lighthouse CI.
