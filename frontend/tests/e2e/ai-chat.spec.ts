import { expect, test } from "@playwright/test";

// O widget usa POST /api/v1/ai/chat no backend. Nos testes E2E a resposta e
// mockada no navegador (contrato identico ao backend, cartoes montados pelo
// servidor); NENHUM LLM real e chamado.
const CARD = {
  product_id: "11111111-1111-4111-8111-111111111111",
  name: "Capacete para Soldador",
  sku: "CAP-SOL-001",
  image_url: "/catalog/photos/aud-001.webp",
  image_alt: "Capacete para Soldador",
  link: "/catalog/11111111-1111-4111-8111-111111111111",
  price: null,
  currency: "BRL",
  price_on_request: true,
  min_order_qty: 1,
  ca_status: "VALID",
};

const CHAT_RESPONSE = {
  conversation_id: "22222222-2222-4222-8222-222222222222",
  reply: "Temos opcoes de capacete para soldador.",
  product_cards: [CARD],
  language: "pt-BR",
};

test.use({ locale: "pt-BR" });

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/ai/chat", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(CHAT_RESPONSE),
    });
  });
  // A pagina de produto consulta o backend real (fora do escopo deste teste):
  // devolvemos uma pagina minima para validar a NAVEGACAO disparada pelo cartao.
  await page.route("**/pt-BR/catalog/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: '<!doctype html><html lang="pt-BR"><body><h1>Produto</h1></body></html>',
    });
  });
});

test("abre o widget pelo navbar, envia mensagem e mostra cartoes reais", async ({ page }) => {
  await page.goto("/pt-BR");
  await page.getByTestId("ai-chat-trigger").click();
  const panel = page.getByTestId("ai-chat-panel");
  await expect(panel).toBeVisible();
  await expect(page.getByText(/Seja bem-vindo ao ForjaB2B/i)).toBeVisible();

  const input = page.getByLabel(/Pergunte sobre produtos/i);
  await input.fill("capacete para soldador");
  await input.press("Enter");

  await expect(page.getByText(/Temos opcoes de capacete/i)).toBeVisible();
  const link = page.getByRole("link", { name: "Ver produto" });
  await expect(link).toHaveAttribute("href", new RegExp(`/catalog/${CARD.product_id}$`));
  await expect(page.getByText("sob consulta")).toBeVisible();

  await Promise.all([page.waitForURL(/\/catalog\//, { timeout: 30_000 }), link.click()]);
  expect(page.url()).toContain(`/catalog/${CARD.product_id}`);
});

test("teclado: Esc fecha e Shift+Enter nao envia", async ({ page }) => {
  await page.goto("/pt-BR");
  await page.getByTestId("ai-chat-trigger").click();
  const input = page.getByLabel(/Pergunte sobre produtos/i);
  await input.fill("linha 1");
  await input.press("Shift+Enter");
  await expect(page.getByTestId("ai-chat-message-user")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("ai-chat-panel")).toHaveCount(0);
});

test("versao arabe abre em RTL com textos traduzidos", async ({ page }) => {
  await page.goto("/ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByTestId("ai-chat-trigger").click();
  await expect(page.getByTestId("ai-chat-panel")).toBeVisible();
  await expect(page.getByText("مساعد فورجا")).toBeVisible();
});

test("mobile: painel ocupa quase a tela e envia", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto("/pt-BR");
  await page.getByTestId("ai-chat-trigger").click();
  const panel = page.getByTestId("ai-chat-panel");
  await expect(panel).toBeVisible();
  const box = await panel.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThan(330);
  expect(box!.height).toBeGreaterThan(450);

  const input = page.getByLabel(/Pergunte sobre produtos/i);
  await input.fill("capacete para soldador");
  await input.press("Enter");
  await expect(page.getByTestId("ai-chat-cards")).toBeVisible();
});

test("site pt-BR recebe bolhas em arabe e japones com lang/dir e rotulos proprios", async ({
  page,
}) => {
  await page.unroute("**/api/v1/ai/chat");
  await page.route("**/api/v1/ai/chat", async (route) => {
    const body = route.request().postDataJSON() as { message?: string };
    const isArabic = body.message?.includes("مرحبا") ?? false;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        isArabic
          ? {
              ...CHAT_RESPONSE,
              language: "ar",
              reply: "مرحباً! هذه لفات أمان.",
            }
          : {
              ...CHAT_RESPONSE,
              language: "ja",
              reply: "こんにちは! 安全手袋です。",
            },
      ),
    });
  });

  await page.goto("/pt-BR");
  await page.getByTestId("ai-chat-trigger").click();
  const input = page.locator("#ai-chat-input");
  await expect(input).toHaveAttribute("dir", "auto");

  await input.fill("مرحبا");
  await input.press("Enter");
  await expect(page.getByTestId("ai-chat-message-assistant")).toHaveAttribute("lang", "ar");
  await expect(page.getByTestId("ai-chat-message-assistant")).toHaveAttribute("dir", "rtl");
  await expect(page.getByTestId("ai-chat-message-user")).toHaveAttribute("lang", "ar");
  await expect(page.getByTestId("ai-chat-message-user")).toHaveAttribute("dir", "rtl");
  await expect(page.getByTestId("ai-chat-cards")).toHaveAttribute("dir", "rtl");
  const arabicFont = await page
    .getByTestId("ai-chat-message-assistant")
    .evaluate((el) => getComputedStyle(el).fontFamily);
  expect(arabicFont).toContain("Noto Sans Arabic");
  await expect(page.getByText(/السعر عند الطلب/)).toBeVisible();
  const arabicLink = page.getByRole("link", { name: "عرض المنتج" });
  await expect(arabicLink).toHaveAttribute(
    "href",
    new RegExp(`/pt-BR/catalog/${CARD.product_id}$`),
  );

  await input.fill("こんにちは");
  await input.press("Enter");
  await expect(page.getByTestId("ai-chat-message-assistant").last()).toHaveAttribute("lang", "ja");
  await expect(page.getByTestId("ai-chat-message-assistant").last()).toHaveAttribute("dir", "ltr");
  await expect(page.getByTestId("ai-chat-message-user").last()).toHaveAttribute("lang", "ja");
  await expect(page.getByTestId("ai-chat-message-user").last()).toHaveAttribute("dir", "ltr");
  const japaneseFont = await page
    .getByTestId("ai-chat-message-assistant")
    .last()
    .evaluate((el) => getComputedStyle(el).fontFamily);
  expect(japaneseFont).toContain("Noto Sans JP");
  await expect(page.getByText(/価格はお問い合わせください/)).toBeVisible();
  const japaneseLink = page.getByRole("link", { name: "商品を見る" });
  await expect(japaneseLink).toHaveAttribute(
    "href",
    new RegExp(`/pt-BR/catalog/${CARD.product_id}$`),
  );
});

test("site ar recebe bolha em pt-BR com dir ltr e navegacao no locale do site", async ({
  page,
}) => {
  await page.unroute("**/api/v1/ai/chat");
  await page.route("**/api/v1/ai/chat", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...CHAT_RESPONSE,
        language: "pt-BR",
        reply: "Olá! Temos opções de capacete.",
      }),
    });
  });

  await page.goto("/ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByTestId("ai-chat-trigger").click();
  const input = page.locator("#ai-chat-input");
  await input.fill("olá");
  await input.press("Enter");
  await expect(page.getByTestId("ai-chat-message-assistant")).toHaveAttribute("lang", "pt-BR");
  await expect(page.getByTestId("ai-chat-message-assistant")).toHaveAttribute("dir", "ltr");
  await expect(page.getByText(/Preço sob consulta/)).toBeVisible();
  const link = page.getByRole("link", { name: "Ver produto" });
  await expect(link).toHaveAttribute("href", new RegExp(`/ar/catalog/${CARD.product_id}$`));
});
