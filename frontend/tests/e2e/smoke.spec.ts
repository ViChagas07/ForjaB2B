import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("redireciona a raiz para o locale padrão", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/pt-BR$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Forja B2B");
});

test("health endpoint responde ok", async ({ request }) => {
  const res = await request.get("/api/health");
  expect(res.status()).toBe(200);
  const body = (await res.json()) as Record<string, unknown>;
  expect(body).toMatchObject({ status: "ok", service: "forja-frontend" });
});

test("locale árabe renderiza RTL", async ({ page }) => {
  await page.goto("/ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
});

test("locale inglês renderiza LTR", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("sem violações sérias de acessibilidade no locale padrão", async ({ page }) => {
  await page.goto("/pt-BR");
  const results = await new AxeBuilder({ page }).analyze();
  const violations = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(violations).toEqual([]);
});
