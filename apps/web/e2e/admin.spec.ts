import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const STUB = "http://localhost:4010";
const BETA = "44444444-4444-4444-8444-444444444444";

test.beforeEach(async ({ request }) => {
  await request.get(`${STUB}/__reset`);
});

async function chooseWorkspace(page: Page, name: string) {
  await page.getByLabel("Çalışma alanı").selectOption({ label: name });
}

test("sohbetten panele geçilir, kaynak eklenir ve durumu canlı izlenir", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Yönetim" }).click();
  await expect(page.getByRole("heading", { name: "Kaynaklar" })).toBeVisible();
  await expect(page.getByText("Henüz kaynak yok.")).toBeVisible();

  await page.locator("summary", { hasText: "Kaynak ekle" }).click();
  await page.getByRole("button", { name: "Kaynak ekle" }).click();
  await expect(page.getByText("Depo sahip/ad biçiminde olmalı.")).toBeVisible();

  await page.getByLabel("Ad", { exact: true }).fill("K8s belgeleri");
  await page.getByLabel("GitHub deposu").fill("kubernetes/website");
  await page.getByRole("button", { name: "Kaynak ekle" }).click();

  const row = page.getByRole("row", { name: /K8s belgeleri/ });
  await expect(row).toContainText("Sırada");
  // Sayfa yenilenmeden durum ilerler: liste işlem sürerken kendini yeniler.
  await expect(row).toContainText("Hazır", { timeout: 15_000 });
  await expect(row).toContainText("12");
});

test("başarısız kaynak hatasını gösterir, yeniden denenir", async ({ page }) => {
  await page.goto("/admin/sources");
  await page.locator("summary", { hasText: "Kaynak ekle" }).click();
  await page.getByLabel("Ad", { exact: true }).fill("bozuk");
  await page.getByLabel("GitHub deposu").fill("yok/yok");
  await page.getByRole("button", { name: "Kaynak ekle" }).click();

  const row = page.getByRole("row", { name: /bozuk/ });
  await expect(row).toContainText("Başarısız", { timeout: 15_000 });
  await expect(row).toContainText("depo veya dal bulunamadı");

  await page.getByRole("button", { name: "Yeniden dene: bozuk" }).click();
  await expect(row).not.toContainText("depo veya dal bulunamadı");
  await expect(row).toContainText("Başarısız", { timeout: 15_000 });
});

test("kaynak onaydan sonra silinir", async ({ page }) => {
  await page.goto("/admin/sources");
  await page.locator("summary", { hasText: "Kaynak ekle" }).click();
  await page.getByLabel("Ad", { exact: true }).fill("silinecek");
  await page.getByLabel("GitHub deposu").fill("a/b");
  await page.getByRole("button", { name: "Kaynak ekle" }).click();
  const row = page.getByRole("row", { name: /silinecek/ });
  await expect(row).toContainText("Hazır", { timeout: 15_000 });

  page.once("dialog", (dialog) => void dialog.dismiss());
  await page.getByRole("button", { name: "Sil: silinecek" }).click();
  await expect(row).toContainText("Hazır");

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Sil: silinecek" }).click();
  await expect(row).toHaveCount(0, { timeout: 15_000 });
});

test("kullanım grafiği, kota ve tablo görünür", async ({ page }) => {
  await page.goto("/admin/usage");
  const meter = page.getByRole("meter", { name: "Bugünkü kota" });
  await expect(meter).toHaveAttribute("aria-valuetext", "%85");
  await expect(page.locator(".stat-value").first()).toContainText("170.000");
  await expect(page.getByRole("img", { name: /Günlük token kullanımı/ })).toBeVisible();

  await page.locator("summary", { hasText: "Tablo olarak göster" }).click();
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(31);
  await expect(page.getByText(/metin uzunluğundan tahmin/)).toBeVisible();
});

test("değerlendirme sürümleri ve eşikler listelenir", async ({ page }) => {
  await page.goto("/admin/evaluation");
  await expect(page.getByRole("columnheader", { name: "v0.4.0 altın set v2" })).toBeVisible();
  await expect(page.getByRole("row", { name: /^Doğru cevap – / })).toContainText("%61");
  await expect(page.getByText(/farklı altın setlerle/)).toBeVisible();
});

test("API anahtarının gizli değeri bir kez gösterilir, sonra iptal edilir", async ({ page }) => {
  await page.goto("/admin/api-keys");
  await page.locator("summary", { hasText: "Anahtar oluştur" }).click();
  await page.getByRole("button", { name: "Anahtar oluştur" }).click();
  await expect(page.getByText("En az bir kapsam seçin.")).toBeVisible();

  await page.getByLabel("Ad", { exact: true }).fill("CI");
  await page.getByLabel("Kaynakları okuma").check();
  await page.getByRole("button", { name: "Anahtar oluştur" }).click();

  const secret = page.locator(".secret-box code");
  await expect(secret).toHaveText("mrd_gizli-deger");
  const row = page.getByRole("row", { name: /CI/ });
  await expect(row).toContainText("sources:read");
  await expect(row).not.toContainText("mrd_gizli-deger");

  await page.reload();
  await expect(page.getByRole("row", { name: /CI/ })).toBeVisible();
  await expect(page.getByText("mrd_gizli-deger")).toHaveCount(0);

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "İptal et: CI" }).click();
  await expect(page.getByRole("row", { name: /CI/ })).toContainText("İptal edildi");
});

test("denetim kayıtları sayfalanır, ret ve anahtar görünür", async ({ page }) => {
  await page.goto("/admin/audit");
  const table = page.getByRole("table");
  await expect(table.getByRole("row")).toHaveCount(51);
  await expect(table).toContainText("source.delete");
  await expect(table).toContainText("Reddedildi");
  await expect(table).toContainText("alice@acme.test");

  await page.getByRole("button", { name: "Daha fazla" }).click();
  await expect(table.getByRole("row")).toHaveCount(61);
  await expect(page.getByRole("button", { name: "Daha fazla" })).toHaveCount(0);
});

test("üye yönetici sekmelerini görmez, adresle gelirse yetki uyarısı alır", async ({ page }) => {
  await page.goto("/admin/sources");
  await chooseWorkspace(page, "Beta");

  await expect(page.getByRole("link", { name: "Kullanım" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "API anahtarları" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Denetim" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Değerlendirme" })).toBeVisible();

  await page.goto("/admin/audit");
  await expect(page.getByRole("alert").filter({ hasText: "yetkiniz yok" })).toBeVisible();
  await page.goto("/admin/usage");
  await expect(page.getByRole("alert").filter({ hasText: "yetkiniz yok" })).toBeVisible();
});

test("çalışma alanı değişince kaynaklar karışmaz", async ({ page, request }) => {
  await page.goto("/admin/sources");
  await page.locator("summary", { hasText: "Kaynak ekle" }).click();
  await page.getByLabel("Ad", { exact: true }).fill("yalnızca-acme");
  await page.getByLabel("GitHub deposu").fill("a/b");
  await page.getByRole("button", { name: "Kaynak ekle" }).click();
  await expect(page.getByRole("row", { name: /yalnızca-acme/ })).toBeVisible();

  await chooseWorkspace(page, "Beta");
  await expect(page.getByText("Henüz kaynak yok.")).toBeVisible();
  await expect(page.getByRole("row", { name: /yalnızca-acme/ })).toHaveCount(0);
  const state = await (await request.get(`${STUB}/__state`)).json();
  expect(state.sourceTenants).toContain(BETA);
});

test("günlük kota dolunca sohbet saniye değil kota uyarısı gösterir", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Sorunuz").fill("kota dolu");
  await page.getByRole("button", { name: "Gönder" }).click();
  const alert = page.locator(".notice-warn[role=alert]");
  await expect(alert).toContainText("Günlük kullanım kotası doldu");
  await expect(alert).not.toContainText("saniye");
});

test("panel sayfalarında açık ve koyu temada erişilebilirlik ihlali yok", async ({ page }) => {
  for (const colorScheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme });
    await page.goto("/admin/sources");
    await page.locator("summary", { hasText: "Kaynak ekle" }).click();
    await page.getByLabel("Ad", { exact: true }).fill("erişim");
    await page.getByLabel("GitHub deposu").fill("yok/yok");
    await page.getByRole("button", { name: "Kaynak ekle" }).click();
    await expect(page.getByRole("row", { name: /erişim/ }).first()).toContainText("Başarısız", { timeout: 15_000 });

    for (const [path, ready] of [
      ["/admin/sources", "Kaynaklar"],
      ["/admin/usage", "Kullanım"],
      ["/admin/evaluation", "Değerlendirme"],
      ["/admin/api-keys", "API anahtarları"],
      ["/admin/audit", "Denetim"],
    ] as const) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1, name: ready })).toBeVisible();
      await expect(page.getByText("Yükleniyor…")).toHaveCount(0);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
      expect(result.violations, `${path} ${colorScheme}`).toEqual([]);
    }
    await page.request.get(`${STUB}/__reset`);
  }
});

test("telefon genişliğinde sayfa yatay kaymaz", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  for (const path of ["/admin/sources", "/admin/usage", "/admin/evaluation", "/admin/api-keys", "/admin/audit"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByText("Yükleniyor…")).toHaveCount(0);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});
