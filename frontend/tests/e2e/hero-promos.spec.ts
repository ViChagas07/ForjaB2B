import { expect, test, type Locator } from "@playwright/test";

const EPIS_CATEGORY_URL = /\/pt-BR\/catalog\?category_id=00000000-0000-0000-0000-000000000401$/;

async function selectFirstBanner(region: Locator) {
  await region.getByRole("button").first().click();
}

test.describe("banners promocionais do hero", () => {
  test.use({ locale: "pt-BR", reducedMotion: "reduce" });

  test("toda a área do banner é clicável e o carrossel navega", async ({ page }) => {
    await page.goto("/pt-BR");

    const region = page.getByRole("region", { name: "Promoções em destaque" });
    await expect(region).toBeVisible();
    await selectFirstBanner(region);

    const episLink = region.getByRole("link", {
      name: "Ver EPIs e equipamentos de segurança",
    });
    await expect(episLink).toHaveAttribute(
      "href",
      "/pt-BR/catalog?category_id=00000000-0000-0000-0000-000000000401",
    );

    await region.getByRole("button", { name: "Próxima", exact: true }).click();
    await expect(region.getByRole("link", { name: "Ver ferramentas elétricas" })).toBeVisible();
    await region.getByRole("button", { name: "Anterior", exact: true }).click();
    await expect(episLink).toBeVisible();

    await episLink.click({ position: { x: 6, y: 6 } });
    await expect(page).toHaveURL(EPIS_CATEGORY_URL);

    await page.goBack();
    await expect(page).toHaveURL(/\/pt-BR$/);
    await selectFirstBanner(region);

    await page.getByRole("button", { name: "Próximo banner" }).click();
    await expect(region.getByRole("link", { name: "Ver ferramentas elétricas" })).toBeVisible();

    await page
      .getByRole("button", { name: "Ir para o banner 3: Ver botas e calçados de proteção" })
      .click();
    const botasLink = region.getByRole("link", {
      name: "Ver botas e calçados de proteção",
    });
    await expect(botasLink).toBeVisible();

    await page.getByRole("button", { name: "Banner anterior" }).click();
    await expect(region.getByRole("link", { name: "Ver ferramentas elétricas" })).toBeVisible();

    await page.getByRole("button", { name: "Próximo banner" }).focus();
    await page.keyboard.press("Enter");
    await expect(
      region.getByRole("link", { name: "Ver botas e calçados de proteção" }),
    ).toBeVisible();

    await page.keyboard.press("Tab");
    await botasLink.focus();
    await expect
      .poll(() =>
        botasLink
          .locator('span[aria-hidden="true"]')
          .evaluate((element) => getComputedStyle(element).opacity),
      )
      .toBe("1");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(
      /\/pt-BR\/catalog\?category_id=209f1617-a444-583c-9eea-5cb136a25ffb$/,
    );
  });

  test("sorteia outro banner ao retornar para a aba", async ({ page }) => {
    await page.goto("/pt-BR");

    const region = page.getByRole("region", { name: "Promoções em destaque" });
    await expect(region).toBeVisible();
    await selectFirstBanner(region);

    const firstLabel = await region.getByRole("link").getAttribute("aria-label");
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => "visible",
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    await expect
      .poll(() => region.getByRole("link").getAttribute("aria-label"))
      .not.toBe(firstLabel);
  });
});

test.describe("banners promocionais em inglês", () => {
  test.use({ locale: "en", reducedMotion: "reduce" });

  test("usa as artes em inglês e mantém os destinos das categorias", async ({ page }) => {
    await page.goto("/en");

    const region = page.getByRole("region", { name: "Featured promotions" });
    await expect(region).toBeVisible();
    await selectFirstBanner(region);
    const episLink = region.getByRole("link", {
      name: "View PPE and safety equipment",
    });
    await expect(episLink.locator("img")).toHaveAttribute(
      "src",
      "/catalog/promos/epis-en-1760.webp",
    );

    await region.getByRole("button", { name: "Next banner" }).click();
    const ferramentasLink = region.getByRole("link", { name: "View power tools" });
    await expect(ferramentasLink.locator("img")).toHaveAttribute(
      "src",
      "/catalog/promos/ferramentas-eletricas-en-1760.webp",
    );
    await expect(ferramentasLink).toHaveAttribute(
      "href",
      "/en/catalog?category_id=dbde55e0-48b7-54db-aa25-a4e0162912b4",
    );

    await region.getByRole("button", { name: "Next banner" }).click();
    const botasLink = region.getByRole("link", { name: "View protective boots and footwear" });
    await expect(botasLink.locator("img")).toHaveAttribute(
      "src",
      "/catalog/promos/botas-de-protecao-en-1760.webp",
    );
    await expect(botasLink).toHaveAttribute(
      "href",
      "/en/catalog?category_id=209f1617-a444-583c-9eea-5cb136a25ffb",
    );
  });
});

test.describe("carrossel promocional em RTL", () => {
  test.use({ locale: "ar", reducedMotion: "reduce" });

  test("mantém a contagem em ordem LTR e os controles traduzidos", async ({ page }) => {
    await page.goto("/ar");

    const region = page.getByRole("region", { name: "العروض المميزة" });
    await expect(region).toBeVisible();
    await selectFirstBanner(region);
    await expect(region.locator('span[aria-hidden="true"][dir="ltr"]')).toHaveText("1 / 3");
    await expect(region.getByRole("link").locator("img")).toHaveAttribute(
      "src",
      "/catalog/promos/epis-en-1760.webp",
    );
    await expect(region.getByRole("button", { name: "البانر التالي" })).toBeVisible();
  });
});

test.describe("vídeo de fundo do hero", () => {
  test.use({ locale: "pt-BR", reducedMotion: "no-preference" });

  test("permanece visível atrás da composição promocional", async ({ page }) => {
    await page.goto("/pt-BR");

    const video = page.locator("section video");
    await expect(video).toBeVisible();
    expect(await video.evaluate((element) => (element as HTMLVideoElement).muted)).toBe(true);
    expect(await video.evaluate((element) => (element as HTMLVideoElement).loop)).toBe(true);
    await expect(page.getByRole("region", { name: "Promoções em destaque" })).toBeVisible();
  });
});

test.describe("banners promocionais no mobile", () => {
  test.use({
    locale: "pt-BR",
    reducedMotion: "reduce",
    viewport: { width: 390, height: 844 },
  });

  test("mantém a imagem inteira clicável e sem rolagem horizontal", async ({ page }) => {
    await page.goto("/pt-BR");

    const region = page.getByRole("region", { name: "Promoções em destaque" });
    await expect(region).toBeVisible();
    await selectFirstBanner(region);

    const link = region.getByRole("link", {
      name: "Ver EPIs e equipamentos de segurança",
    });
    const box = await link.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;

    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(390);
    expect(box.height).toBeGreaterThan(190);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
      ),
    ).toBe(false);

    await link.click({ position: { x: box.width - 8, y: 12 } });
    await expect(page).toHaveURL(EPIS_CATEGORY_URL);
  });
});
