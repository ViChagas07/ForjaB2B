import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const PASSWORD = process.env.DEMO_USER_PASSWORD ?? "";
const suffix = Date.now().toString(36).toUpperCase();
const productCode = `E2E-PROD-${suffix}`;
const shippingCode = `E2E-FRETE-${suffix}`;

test.skip(!PASSWORD, "DEMO_USER_PASSWORD não definido");
test.describe.configure({ mode: "serial" });

let buyerSession: Record<string, unknown>;
let buyerToken = "";
let adminToken = "";
let productCouponId = "";
let shippingCouponId = "";

async function login(request: APIRequestContext, email: string) {
  const response = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as Record<string, unknown>;
}

async function createCoupon(
  request: APIRequestContext,
  code: string,
  type: "PRODUCT_TOTAL" | "SHIPPING",
  percent: string,
) {
  const response = await request.post(`${API}/api/v1/admin/coupons`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { code, type, percent },
  });
  expect(response.ok()).toBeTruthy();
  return String(((await response.json()) as { id: string }).id);
}

async function productId(request: APIRequestContext) {
  const response = await request.get(`${API}/api/v1/catalog/products?q=CAP-002&page_size=5`, {
    headers: { "Accept-Language": "pt-BR" },
  });
  const body = (await response.json()) as {
    items: Array<{ id: string; sku: string }>;
  };
  return body.items.find((item) => item.sku === "CAP-002")?.id ?? "";
}

async function resetCartWithProduct(request: APIRequestContext) {
  const id = await productId(request);
  expect(id).not.toBe("");
  await request.delete(`${API}/api/v1/cart`, {
    headers: { Authorization: `Bearer ${buyerToken}` },
  });
  const added = await request.post(`${API}/api/v1/cart/items`, {
    headers: { Authorization: `Bearer ${buyerToken}` },
    data: { product_id: id, quantity: 1 },
  });
  expect(added.ok()).toBeTruthy();
}

async function applyCoupon(page: Page, code: string) {
  await page.getByRole("button", { name: /Inserir código de cupom/ }).click();
  await page.getByLabel("Cupom de desconto").fill(code);
  await page.getByRole("button", { name: "Aplicar" }).click();
  await expect(page.getByText("Cupom aplicado")).toBeVisible();
  await expect(page.getByText(code).first()).toBeVisible();
}

async function placeOrder(page: Page) {
  await page.getByRole("button", { name: "Confirmar pedido" }).click();
  await page.waitForURL(/\/pt-BR\/orders\/[0-9a-f-]+$/);
  return page.url().split("/").at(-1) ?? "";
}

async function cancelOrder(page: Page) {
  await page.getByRole("button", { name: "Cancelar pedido" }).click();
  await expect(page.getByText("Cancelado")).toBeVisible();
}

async function couponUsage(request: APIRequestContext, couponId: string) {
  const response = await request.get(`${API}/api/v1/admin/coupons/${couponId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(response.ok()).toBeTruthy();
  return Number(((await response.json()) as { total_uses: number }).total_uses);
}

test.beforeAll(async ({ request }) => {
  if (!PASSWORD) return;
  const admin = await login(request, "admin@exemplo.com.br");
  adminToken = String(admin.access_token);
  productCouponId = await createCoupon(request, productCode, "PRODUCT_TOTAL", "10.00");
  shippingCouponId = await createCoupon(request, shippingCode, "SHIPPING", "100.00");

  buyerSession = await login(request, "comprador@exemplo.com.br");
  buyerToken = String(buyerSession.access_token);
});

test.afterAll(async ({ request }) => {
  if (!adminToken) return;
  for (const couponId of [productCouponId, shippingCouponId]) {
    if (!couponId) continue;
    await request.patch(`${API}/api/v1/admin/coupons/${couponId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { is_active: false },
    });
  }
});

test("cupom de produtos: aplicar, criar, snapshot e cancelar libera o uso", async ({
  page,
  request,
}) => {
  await resetCartWithProduct(request);
  await page.addInitScript((value) => {
    window.localStorage.setItem("forja-auth-session", JSON.stringify(value));
  }, buyerSession);

  await page.goto("/pt-BR/checkout");
  await applyCoupon(page, productCode);
  const orderId = await placeOrder(page);

  const orderResponse = await request.get(`${API}/api/v1/orders/${orderId}`, {
    headers: { Authorization: `Bearer ${buyerToken}` },
  });
  const order = (await orderResponse.json()) as {
    coupon_code: string;
    coupon_type: string;
    coupon_percent: string;
    coupon_discount_amount: string;
    shipping_discount_amount: string;
    total: string;
  };
  expect(order.coupon_code).toBe(productCode);
  expect(order.coupon_type).toBe("PRODUCT_TOTAL");
  expect(order.coupon_percent).toBe("10.00");
  expect(order.coupon_discount_amount).toBe("10.00");
  expect(order.shipping_discount_amount).toBe("0.00");
  expect(order.total).toBe("115.00");
  expect(await couponUsage(request, productCouponId)).toBe(1);

  await cancelOrder(page);
  expect(await couponUsage(request, productCouponId)).toBe(0);
});

test("cupom de frete 100%: aplicar, criar com frete zero e cancelar libera o uso", async ({
  page,
  request,
}) => {
  await resetCartWithProduct(request);
  await page.addInitScript((value) => {
    window.localStorage.setItem("forja-auth-session", JSON.stringify(value));
  }, buyerSession);

  await page.goto("/pt-BR/checkout");
  await applyCoupon(page, shippingCode);
  const orderId = await placeOrder(page);

  const orderResponse = await request.get(`${API}/api/v1/orders/${orderId}`, {
    headers: { Authorization: `Bearer ${buyerToken}` },
  });
  const order = (await orderResponse.json()) as {
    coupon_code: string;
    coupon_type: string;
    coupon_discount_amount: string;
    shipping_discount_amount: string;
    shipping_total: string;
    total: string;
  };
  expect(order.coupon_code).toBe(shippingCode);
  expect(order.coupon_type).toBe("SHIPPING");
  expect(order.coupon_discount_amount).toBe("0.00");
  expect(order.shipping_discount_amount).toBe("25.00");
  expect(order.shipping_total).toBe("0.00");
  expect(order.total).toBe("100.00");
  expect(await couponUsage(request, shippingCouponId)).toBe(1);

  await cancelOrder(page);
  expect(await couponUsage(request, shippingCouponId)).toBe(0);
});
