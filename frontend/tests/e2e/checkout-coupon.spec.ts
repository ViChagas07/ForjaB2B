import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const PASSWORD = process.env.DEMO_USER_PASSWORD ?? "";
const code = `E2E-${Date.now().toString(36).toUpperCase()}`;

test.skip(!PASSWORD, "DEMO_USER_PASSWORD não definido");
test.describe.configure({ mode: "serial" });

let buyerSession: Record<string, unknown>;
let couponId = "";
let adminToken = "";

test.beforeAll(async ({ request }) => {
  if (!PASSWORD) return;

  const admin = await request.post(`${API}/api/v1/auth/login`, {
    data: { email: "admin@exemplo.com.br", password: PASSWORD },
  });
  expect(admin.ok()).toBeTruthy();
  adminToken = String(((await admin.json()) as { access_token: string }).access_token);

  const created = await request.post(`${API}/api/v1/admin/coupons`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { code, type: "PRODUCT_TOTAL", percent: "10.00" },
  });
  expect(created.ok()).toBeTruthy();
  couponId = String(((await created.json()) as { id: string }).id);

  const buyer = await request.post(`${API}/api/v1/auth/login`, {
    data: { email: "comprador@exemplo.com.br", password: PASSWORD },
  });
  expect(buyer.ok()).toBeTruthy();
  buyerSession = (await buyer.json()) as Record<string, unknown>;
  const token = String(buyerSession.access_token);

  const products = await request.get(`${API}/api/v1/catalog/products?q=CAP-002&page_size=5`, {
    headers: { "Accept-Language": "pt-BR" },
  });
  const productBody = (await products.json()) as {
    items: Array<{ id: string; sku: string }>;
  };
  const productId = productBody.items.find((item) => item.sku === "CAP-002")?.id ?? "";
  expect(productId).not.toBe("");

  await request.delete(`${API}/api/v1/cart`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const cart = await request.post(`${API}/api/v1/cart/items`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { product_id: productId, quantity: 1 },
  });
  expect(cart.ok()).toBeTruthy();
});

test.afterAll(async ({ request }) => {
  if (!adminToken || !couponId) return;
  await request.delete(`${API}/api/v1/admin/coupons/${couponId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
});

test("aplica e remove cupom no resumo do checkout", async ({ page }) => {
  await page.addInitScript((value) => {
    window.localStorage.setItem("forja-auth-session", JSON.stringify(value));
  }, buyerSession);

  await page.goto("/pt-BR/checkout");
  await page.getByRole("button", { name: /Inserir código de cupom/ }).click();
  await page.getByLabel("Cupom de desconto").fill(code);
  await page.getByRole("button", { name: "Aplicar" }).click();

  await expect(page.getByText("Cupom aplicado")).toBeVisible();
  await expect(page.getByText(`Cupom (${code})`)).toBeVisible();
  await expect(page.locator('[data-testid="checkout-total"]')).toBeVisible();

  await page.getByRole("button", { name: `Remover cupom ${code}` }).click();
  await expect(page.getByRole("button", { name: /Inserir código de cupom/ })).toBeVisible();
});
