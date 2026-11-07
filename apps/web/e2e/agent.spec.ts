import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const STUB = "http://localhost:4010";

test.beforeEach(async ({ request }) => {
  await request.get(`${STUB}/__reset`);
});

async function start(page: Page, goal: string) {
  await page.getByLabel("Görev").fill(goal);
  await page.getByRole("button", { name: "Başlat" }).click();
}

test("sohbetten ajana geçilir, adımlar akar, kaynaklı cevap gelir", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Ajan" }).click();
  await expect(page.getByRole("heading", { name: "Ajan" })).toBeVisible();

  await start(page, "Başvuru süresi kaç gün?");
  await expect(page.getByText("Belgelerde arama")).toBeVisible();
  await expect(page.getByRole("button", { name: "Durdur" })).toBeVisible();

  const answer = page.getByRole("article", { name: "Cevap" });
  await expect(answer).toContainText("otuz gün");
  await expect(answer.getByRole("button", { name: "Kaynak 1: KVKK" })).toBeVisible();
  await expect(page.getByText("Bu çalıştırma 1115 token harcadı.")).toBeVisible();

  await page.getByText("Belgelerde arama").click();
  await expect(page.locator(".agent-observation")).toContainText("sonuçlandırır");
});

test("ticket onay olmadan oluşmaz; onaylanınca ajan sürer", async ({ page, request }) => {
  await page.goto("/agent");
  await start(page, "ticket aç");

  const approval = page.getByRole("group", { name: "Ticket oluşturulsun mu?" });
  await expect(approval).toContainText("Disk dolu");
  await expect(approval).toContainText("Sunucu diski doldu");
  expect((await (await request.get(`${STUB}/__state`)).json()).tickets).toBe(0);

  await approval.getByRole("button", { name: "Onayla ve oluştur" }).click();
  await expect(page.getByText("Onaylandı")).toBeVisible();
  await expect(page.getByRole("article", { name: "Cevap" })).toContainText("Ticket açıldı");
  await expect(approval).toHaveCount(0);
  expect((await (await request.get(`${STUB}/__state`)).json()).tickets).toBe(1);
});

test("reddedilen ticket oluşmaz, sayfa yenilense de onay kartı durur", async ({ page, request }) => {
  await page.goto("/agent");
  await start(page, "ticket aç");
  await expect(page.getByRole("group", { name: "Ticket oluşturulsun mu?" })).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "ticket aç" }).click();
  const approval = page.getByRole("group", { name: "Ticket oluşturulsun mu?" });
  await expect(approval).toBeVisible();

  await approval.getByRole("button", { name: "Reddet" }).click();
  await expect(page.getByText("Reddedildi")).toBeVisible();
  expect((await (await request.get(`${STUB}/__state`)).json()).tickets).toBe(0);
});

test("bütçe aşımı anlaşılır söylenir", async ({ page }) => {
  await page.goto("/agent");
  await start(page, "bütçe aşımı");
  await expect(page.locator(".notice-warn[role=alert]")).toContainText("adım sınırına");
});

test("eşzamanlı çalıştırma ve kota uyarıları", async ({ page }) => {
  await page.goto("/agent");
  await start(page, "meşgul");
  await expect(page.locator(".notice-warn[role=alert]")).toContainText("Başka bir çalıştırmanız sürüyor");
  await start(page, "kota dolu");
  await expect(page.locator(".notice-warn[role=alert]")).toContainText("Günlük kullanım kotası doldu");
});

test("gözlemdeki zararlı metin çalışmaz, dışarı istek gitmez", async ({ page }) => {
  const external: string[] = [];
  page.on("request", (item) => {
    if (item.url().includes("leak.png")) external.push(item.url());
  });
  await page.goto("/agent");
  await start(page, "zararlı gözlem");
  await page.getByText("Belgelerde arama").click();
  await expect(page.locator(".agent-observation")).toContainText("<img src=x");

  expect(await page.evaluate(() => (window as unknown as { __pwned?: number }).__pwned)).toBeUndefined();
  expect(external).toEqual([]);
});

test("durdur akışı keser", async ({ page, request }) => {
  await page.goto("/agent");
  await start(page, "yavaş görev");
  await expect(page.getByText("Belgelerde arama")).toBeVisible();
  await page.getByRole("button", { name: "Durdur" }).click();
  await expect(page.getByRole("button", { name: "Başlat" })).toBeVisible();
  await expect.poll(async () => (await (await request.get(`${STUB}/__state`)).json()).agentInterrupted).toBe(1);
});

test("açık ve koyu temada erişilebilirlik ihlali yok", async ({ page }) => {
  for (const colorScheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme });
    await page.goto("/agent");
    await start(page, "ticket aç");
    await expect(page.getByRole("group", { name: "Ticket oluşturulsun mu?" })).toBeVisible();
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    expect(result.violations, colorScheme).toEqual([]);
  }
});

test("telefon genişliğinde sayfa yatay kaymaz", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/agent");
  await start(page, "ticket aç");
  await expect(page.getByRole("group", { name: "Ticket oluşturulsun mu?" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
