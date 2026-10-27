import { expect, test } from "@playwright/test";

// Autocomplete da barra de busca (estilo BestBuy). Requer a pilha local de pé
// (backend em :8000 com o índice do Elasticsearch populado). O webServer do
// playwright.config sobe o frontend em :3010.

test.use({ locale: "pt-BR" });

const INPUT = 'input[role="combobox"]';

test("digitar 'cap' abre o painel com termos e produtos", async ({ page }) => {
  await page.goto("/pt-BR");
  const input = page.locator(INPUT).first();
  await input.click();
  await input.fill("cap");

  const listbox = page.getByRole("listbox");
  await expect(listbox).toBeVisible();
  await expect(listbox.getByRole("option").filter({ hasText: "Capacete" }).first()).toBeVisible();
  await expect(listbox.getByText(/Resultados populares/i)).toBeVisible();
  await expect(listbox.getByRole("option").filter({ hasText: "CAP-002" }).first()).toBeVisible();
});

test("setas selecionam e Enter navega para a busca do termo", async ({ page }) => {
  await page.goto("/pt-BR");
  const input = page.locator(INPUT).first();
  await input.click();
  await input.fill("cap");

  const listbox = page.getByRole("listbox");
  await expect(listbox).toBeVisible();
  // O painel abre já no debounce (com skeleton enquanto carrega); setas só
  // selecionam quando há opções (contrato ARIA: lista vazia não seleciona).
  const firstOption = listbox.locator('[role="option"]').first();
  await expect(firstOption).toBeVisible();

  await page.keyboard.press("ArrowDown");
  await expect(firstOption).toHaveAttribute("aria-selected", "true");

  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/catalog\?q=/);
  await expect(page).not.toHaveURL(/\/catalog\?q=cap$/);
});

test("Esc fecha o painel mantendo o texto digitado", async ({ page }) => {
  await page.goto("/pt-BR");
  const input = page.locator(INPUT).first();
  await input.click();
  await input.fill("cap");
  await expect(page.getByRole("listbox")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("listbox")).toBeHidden();
  await expect(input).toHaveValue("cap");
});

test("sem resultados mostra a mensagem com link para o catálogo", async ({ page }) => {
  await page.goto("/pt-BR");
  const input = page.locator(INPUT).first();
  await input.click();
  await input.fill("zzzzqqqq");

  await expect(page.getByText(/Nenhum resultado/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /Ver todos os resultados/i })).toBeVisible();
});

test("clique no produto abre a página do produto", async ({ page }) => {
  await page.goto("/pt-BR");
  const input = page.locator(INPUT).first();
  await input.click();
  await input.fill("cap");
  const listbox = page.getByRole("listbox");
  await expect(listbox).toBeVisible();

  // Options de produto são os únicos com <img>; "CAP-002" também existe como
  // TERMO de SKU na coluna esquerda (clicar nele leva a /catalog?q=CAP-002).
  const productOption = listbox
    .getByRole("option")
    .filter({ has: page.locator("img") })
    .filter({ hasText: "CAP-002" })
    .first();
  await productOption.click();
  await expect(page).toHaveURL(/\/catalog\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("em árabe o painel espelha (html dir=rtl e direção herdada)", async ({ page }) => {
  await page.goto("/ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");

  const input = page.locator(INPUT).first();
  await input.click();
  await input.fill("cap");
  const listbox = page.getByRole("listbox");
  await expect(listbox).toBeVisible();

  const direction = await listbox.evaluate((element) => getComputedStyle(element).direction);
  expect(direction).toBe("rtl");
  await expect(listbox.getByText(/النتائج الشائعة/)).toBeVisible();
});
