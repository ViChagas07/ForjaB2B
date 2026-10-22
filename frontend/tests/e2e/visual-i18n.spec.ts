import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const PASSWORD = process.env.DEMO_USER_PASSWORD ?? "";
const SCREENSHOT_DIR = "../docs/validation/v3";

const LOCALES = {
  "pt-BR": {
    catalog: "Catálogo",
    product: "Capacete de Segurança Classe A Aba Frontal",
    dir: "ltr",
  },
  en: {
    catalog: "Catalog",
    product: "Class A Front Brim Safety Helmet",
    dir: "ltr",
  },
  ar: {
    catalog: "الكتالوج",
    product: "خوذة أمان من الفئة أ الأمامية",
    dir: "rtl",
  },
  "zh-CN": {
    catalog: "目录",
    // zh-CN nao e idioma de conteudo: a API entrega en e a nota indica isso.
    product: "Class A Front Brim Safety Helmet",
    dir: "ltr",
  },
} as const;

type Locale = keyof typeof LOCALES;

let session: Record<string, unknown>;
let productId = "";
let productSku = "";

test.skip(!PASSWORD, "DEMO_USER_PASSWORD não definido");
test.describe.configure({ mode: "serial" });

// O backend ainda nao envia cabecalhos CORS (lacuna registrada na V3), entao o
// navegador bloquearia as chamadas a :8000 a partir de :3010. Para a validacao
// VISUAL usamos um Chromium sem a checagem de CORS; isso nao altera o backend
// nem esconde a lacuna, que fica documentada em docs/STATUS.md.
test.use({ launchOptions: { args: ["--disable-web-security"] } });

test.beforeAll(async ({ request }) => {
  if (!PASSWORD) return;
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email: "comprador@exemplo.com.br", password: PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  session = (await login.json()) as Record<string, unknown>;

  const list = await request.get(`${API}/api/v1/catalog/products?q=CAP-002&page_size=5`, {
    headers: { "Accept-Language": "pt-BR" },
  });
  expect(list.ok()).toBeTruthy();
  const body = (await list.json()) as { items: Array<{ id: string; sku: string }> };
  const product = body.items.find((item) => item.sku === "CAP-002") ?? body.items[0];
  expect(product).toBeDefined();
  productId = product?.id ?? "";
  productSku = product?.sku ?? "";

  const token = String(session.access_token);
  const cart = await request.post(`${API}/api/v1/cart/items`, {
    headers: { Authorization: `Bearer ${token}`, "Accept-Language": "pt-BR" },
    data: { product_id: productId, quantity: 1 },
  });
  expect(cart.ok()).toBeTruthy();
});

test.afterAll(async ({ request }) => {
  if (!PASSWORD || !session) return;
  await request.delete(`${API}/api/v1/cart`, {
    headers: {
      Authorization: `Bearer ${String(session.access_token)}`,
      "Accept-Language": "pt-BR",
    },
  });
});

async function authenticatedPage(page: import("@playwright/test").Page) {
  await page.addInitScript((value) => {
    window.localStorage.setItem("forja-auth-session", JSON.stringify(value));
  }, session);
}

for (const locale of Object.keys(LOCALES) as Locale[]) {
  const expected = LOCALES[locale];

  test(`telas do cliente em ${locale}`, async ({ page }) => {
    await authenticatedPage(page);

    await page.goto(`/${locale}/catalog`);
    await expect(page.locator("html")).toHaveAttribute("lang", locale);
    await expect(page.locator("html")).toHaveAttribute("dir", expected.dir);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(expected.catalog);
    await expect(page.locator('main a[href*="/catalog/"]').first()).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/${locale}-catalog.jpg`,
      fullPage: true,
      type: "jpeg",
      quality: 80,
    });

    await page.goto(`/${locale}/catalog?q=capacete`);
    await expect(page.getByTestId("catalog-results-count")).not.toHaveText(/^0\b/);
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/${locale}-search.jpg`,
      fullPage: true,
      type: "jpeg",
      quality: 80,
    });

    await page.goto(`/${locale}/catalog/${productId}`);
    await expect(page.getByText(expected.product, { exact: false }).first()).toBeVisible();
    if (locale === "zh-CN") {
      await expect(page.getByText(/English/).first()).toBeVisible();
    }
    if (locale === "ar") {
      const transform = await page
        .locator(`main a[href$="/catalog"] svg`)
        .first()
        .evaluate((el) => getComputedStyle(el).transform);
      expect(transform).toContain("-1");
    }
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/${locale}-detail.jpg`,
      fullPage: true,
      type: "jpeg",
      quality: 80,
    });

    await page.goto(`/${locale}/cart`);
    await expect(page.getByText(expected.product, { exact: false }).first()).toBeVisible({
      timeout: 20_000,
    });
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/${locale}-cart.jpg`,
      fullPage: true,
      type: "jpeg",
      quality: 80,
    });
  });
}

test("SKU de demonstração usado nas capturas", () => {
  expect(productSku).toBe("CAP-002");
});
