import { expect, test } from "@playwright/test";

const enabled = process.env.E2E_PASSWORD_RECOVERY === "1";

test.describe("recuperacao de conta", () => {
  test.skip(!enabled, "Defina E2E_PASSWORD_RECOVERY=1, NEXT_PUBLIC_PASSWORD_RECOVERY_ENABLED=true e NEXT_PUBLIC_TURNSTILE_SITE_KEY=1x00000000000000000000AA no dev server.");

  test("pede codigo, verifica e redefine a senha", async ({ page }) => {
    await page.route("**/api/v1/auth/password-recovery/request", async (route) => {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "accepted" }),
      });
    });
    await page.route("**/api/v1/auth/password-recovery/verify", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ reset_token: "reset-token-e2e", expires_in: 600 }),
      });
    });
    await page.route("**/api/v1/auth/password-recovery/reset", async (route) => {
      await route.fulfill({ status: 204 });
    });

    await page.goto("/pt-BR/forgot-password");
    await page.getByLabel("E-mail").fill("user@example.com");

    const submit = page.getByRole("button", { name: "Enviar código" });
    await expect(submit).toBeEnabled({ timeout: 30_000 });
    await submit.click();

    await expect(
      page.getByText("Se os dados estiverem corretos, enviaremos um código."),
    ).toBeVisible();
    await page.getByLabel("Código de verificação").fill("123456");
    await page.getByRole("button", { name: "Verificar código" }).click();

    await expect(page.getByRole("heading", { name: "Defina uma nova senha" })).toBeVisible();
    await page.getByLabel("Nova senha").fill("SenhaNova123");
    await page.getByLabel("Confirmar nova senha").fill("SenhaNova123");
    await page.getByRole("button", { name: "Salvar nova senha" }).click();

    await expect(page.getByRole("heading", { name: "Senha alterada" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Ir para o login" }).first()).toBeVisible();
  });
});
