import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const PASSWORD = process.env.DEMO_USER_PASSWORD ?? "";
const SCREENSHOT_DIR = "../docs/validation/v4";

test.skip(!PASSWORD, "DEMO_USER_PASSWORD não definido");
test.describe.configure({ mode: "serial" });

let session: Record<string, unknown>;
let productId = "";

test.beforeAll(async ({ request }) => {
  if (!PASSWORD) return;

  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email: "comprador@exemplo.com.br", password: PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  session = (await login.json()) as Record<string, unknown>;
  const token = String(session.access_token);

  const list = await request.get(`${API}/api/v1/catalog/products?q=CAP-002&page_size=5`, {
    headers: { "Accept-Language": "pt-BR" },
  });
  const body = (await list.json()) as { items: Array<{ id: string; sku: string }> };
  productId = body.items.find((item) => item.sku === "CAP-002")?.id ?? "";

  await request.delete(`${API}/api/v1/cart`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const cart = await request.post(`${API}/api/v1/cart/items`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { product_id: productId, quantity: 1 },
  });
  expect(cart.ok()).toBeTruthy();
});

test("checkout com cartão aparece e redireciona ao Stripe", async ({ page }) => {
  await page.addInitScript((value) => {
    window.localStorage.setItem("forja-auth-session", JSON.stringify(value));
  }, session);

  await page.goto("/pt-BR/checkout");
  const cardOption = page.getByRole("radio", { name: /Cartão \(Stripe\)/ });
  await expect(cardOption).toBeVisible({ timeout: 20_000 });
  await cardOption.click();
  await expect(cardOption).toHaveAttribute("aria-checked", "true");
  await page.waitForLoadState("networkidle");
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/pt-BR-checkout-card.jpg`,
    fullPage: true,
    type: "jpeg",
    quality: 80,
  });

  await page.locator('form button[type="submit"]').click();
  await page.waitForURL(/checkout\.stripe\.com/, { timeout: 45_000 });
  expect(page.url()).toContain("checkout.stripe.com");
});
