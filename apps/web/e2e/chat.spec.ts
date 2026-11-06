import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { gzipSync } from "node:zlib";

const STUB = "http://localhost:4010";

test.beforeEach(async ({ request }) => {
  await request.get(`${STUB}/__reset`);
});

async function ask(page: Page, question: string) {
  await page.getByLabel("Sorunuz").fill(question);
  await page.getByRole("button", { name: "Gönder" }).click();
}

test("giriş yapılır, cevap akarak gelir, atıf kaynağa götürür", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Belgelerinize bir soru sorun" })).toBeVisible();

  // Token tarayıcı koduna ulaşmaz.
  const cookie = (await context.cookies()).find((item) => item.name === "meridian_session");
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");
  expect(cookie?.value).not.toContain("erisim-token");

  await ask(page, "Başvuruya ne kadar sürede cevap verilir?");
  const answer = page.getByRole("article", { name: "Cevap" });
  await expect(answer).toContainText("otuz gün");
  await expect(answer.locator("strong")).toHaveText("otuz gün");

  await expect(page.getByRole("button", { name: "Yeniden üret" })).toBeVisible();
  const citation = answer.getByRole("button", { name: "Kaynak 1: KVKK" });
  await citation.hover();
  await expect(page.getByRole("tooltip")).toContainText("sonuçlandırır");
  await citation.click();
  await expect(answer.locator(".source-active")).toContainText("kvkk/6698.md");

  await expect(page.getByRole("button", { name: /Başvuruya ne kadar/ })).toHaveAttribute("aria-current", "page");
});

test("cevap gerçekten parça parça akar (vekil tamponlamaz)", async ({ page }) => {
  await page.goto("/");
  await ask(page, "yavaş bir soru");

  const answer = page.getByRole("article", { name: "Cevap" });
  await expect(answer).toContainText("Başvuru");
  await expect(answer).not.toContainText("sonuçlandırılır");
  await expect(answer).toContainText("sonuçlandırılır", { timeout: 15_000 });
});

test("durdur akışı API'ye kadar keser, yarım cevap işaretlenir", async ({ page, request }) => {
  await page.goto("/");
  await ask(page, "yavaş bir soru");
  await expect(page.getByRole("article", { name: "Cevap" })).toContainText("Başvuru");

  await page.getByRole("button", { name: "Durdur" }).click();

  await expect(page.getByText("Cevap yarıda kesildi.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Gönder" })).toBeVisible();
  await expect.poll(async () => (await (await request.get(`${STUB}/__state`)).json()).interrupted).toBe(1);
});

test("kaynaklarda cevap yoksa bilmiyorum uyarısı gösterilir", async ({ page }) => {
  await page.goto("/");
  await ask(page, "bilinmeyen bir konu");

  await expect(page.getByText("Bu sorunun cevabını kaynaklarda doğrulayamadım")).toBeVisible();
  await expect(page.getByText("BİLMİYORUM")).toHaveCount(0);
});

test("zararlı model çıktısı çalışmaz, dışarı istek gitmez", async ({ page }) => {
  const external: string[] = [];
  page.on("request", (item) => {
    if (item.url().includes("leak.png")) external.push(item.url());
  });
  await page.goto("/");
  await ask(page, "zararlı cevap");

  await expect(page.getByRole("article", { name: "Cevap" })).toContainText("Sonuç");
  expect(await page.evaluate(() => (window as unknown as { __pwned?: number }).__pwned)).toBeUndefined();
  await expect(page.getByRole("article", { name: "Cevap" }).locator("img")).toHaveCount(0);
  expect(external).toEqual([]);
});

test("oran sınırında bekleme süresi söylenir ve yeniden denenebilir", async ({ page }) => {
  await page.goto("/");
  await ask(page, "sınır sorusu");

  await expect(page.locator('.notice[role="alert"]')).toContainText("7 saniye");
  await expect(page.getByRole("button", { name: "Yeniden dene" })).toBeVisible();
});

test("önceki konuşma yeniden açılır, yeni soru yeni cevap ekler", async ({ page }) => {
  await page.goto("/");
  await ask(page, "ilk soru");
  await expect(page.getByRole("button", { name: "Yeniden üret" })).toBeVisible();

  await page.getByRole("button", { name: "Yeni konuşma" }).click();
  await expect(page.getByRole("heading", { name: "Belgelerinize bir soru sorun" })).toBeVisible();

  await page.getByRole("button", { name: "ilk soru" }).click();
  await expect(page.getByRole("article", { name: "Cevap" })).toContainText("otuz gün");

  await page.getByRole("button", { name: "Yeniden üret" }).click();
  await expect(page.getByRole("article", { name: "Cevap" })).toHaveCount(2);
});

test("çalışma alanı değişince konuşma ekranı sıfırlanır, seçim hatırlanır", async ({ page }) => {
  await page.goto("/");
  await ask(page, "acme sorusu");
  await expect(page.getByRole("button", { name: "Yeniden üret" })).toBeVisible();

  await page.getByLabel("Çalışma alanı").selectOption({ label: "Beta" });
  await expect(page.getByRole("heading", { name: "Belgelerinize bir soru sorun" })).toBeVisible();
  await expect(page.getByText("acme sorusu", { exact: true })).toHaveCount(0);

  await page.reload();
  await expect(page.getByLabel("Çalışma alanı")).toHaveValue("44444444-4444-4444-8444-444444444444");
});

test("başka kökenden gelen istek reddedilir", async ({ page, request }) => {
  await page.goto("/");
  const cookies = await page.context().cookies();
  const response = await request.post("/api/v1/tenants", {
    headers: {
      Origin: "https://evil.test",
      Cookie: cookies.map((item) => `${item.name}=${item.value}`).join("; "),
    },
    data: { name: "x", slug: "xyz" },
  });
  expect(response.status()).toBe(403);
});

test("çıkış oturumu kapatır, oturumsuz API isteği 401 alır", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Çıkış" }).click();

  await expect(page.getByRole("heading", { name: "Çıkış yaptınız" })).toBeVisible();
  expect((await page.context().cookies()).some((item) => item.name === "meridian_session")).toBe(false);
  expect((await request.get("/api/v1/me")).status()).toBe(401);
});

test("ilk JS paketi bütçenin altında (200 KB gzip)", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Belgelerinize bir soru sorun" })).toBeVisible();
  const scripts = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .map((entry) => entry.name)
      .filter((name) => name.endsWith(".js")),
  );

  let total = 0;
  for (const url of scripts) total += gzipSync(await (await request.get(url)).body()).length;

  console.log(`ilk JS: ${scripts.length} dosya, ${Math.round(total / 1024)} KB gzip`);
  expect(total).toBeLessThan(200 * 1024);
});

test("açık ve koyu temada erişilebilirlik ihlali yok", async ({ page }) => {
  for (const colorScheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Belgelerinize bir soru sorun" })).toBeVisible();
    await ask(page, "erişilebilirlik sorusu");
    await expect(page.getByRole("button", { name: "Yeniden üret" })).toBeVisible();
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    expect(result.violations).toEqual([]);
    await page.getByRole("button", { name: "Yeni konuşma" }).click();
  }
});
