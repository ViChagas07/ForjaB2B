import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const PASSWORD = process.env.DEMO_USER_PASSWORD ?? "";

test.skip(!PASSWORD, "DEMO_USER_PASSWORD não definido");
test.describe.configure({ mode: "serial" });

let session: Record<string, unknown>;
let token = "";
let couponId = "";
const code = `E2E-${Date.now().toString(36).toUpperCase()}`;

test.beforeAll(async ({ request }) => {
  if (!PASSWORD) return;
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email: "admin@exemplo.com.br", password: PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  session = (await login.json()) as Record<string, unknown>;
  token = String(session.access_token);
});

test.afterAll(async ({ request }) => {
  if (!token || !couponId) return;
  await request.delete(`${API}/api/v1/admin/coupons/${couponId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
});

test("admin cria, lista e desativa um cupom", async ({ page }) => {
  await page.addInitScript((value) => {
    window.localStorage.setItem("forja-auth-session", JSON.stringify(value));
  }, session);

  await page.goto("/pt-BR/admin/cupons");
  await expect(page.getByRole("heading", { level: 1, name: "Cupons" })).toBeVisible();

  await page.getByRole("link", { name: "Novo cupom" }).click();
  await page.getByLabel(/Código/).fill(code);
  await page.getByLabel(/Percentual/).fill("15");
  await page.getByRole("button", { name: "Criar cupom" }).click();

  await page.waitForURL(/\/pt-BR\/admin\/cupons\/[0-9a-f-]+$/);
  couponId = page.url().split("/").at(-1) ?? "";
  expect(couponId).not.toBe("");

  await page.getByRole("link", { name: "Voltar para cupons" }).click();
  const row = page.getByRole("row", { name: new RegExp(code) });
  await expect(row).toBeVisible();

  await row.getByRole("button", { name: "Ações" }).click();
  await page.getByRole("menuitem", { name: "Desativar" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Desativar" }).click();

  await expect(row.getByText("Inativo")).toBeVisible();
});
