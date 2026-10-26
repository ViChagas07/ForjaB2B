async (page) => {
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.goto("https://forja-b2b.vercel.app/pt-BR", { waitUntil: "domcontentloaded" });
  await page.locator("article img[src*=\"/catalog/photos/\"]").first().waitFor({ timeout: 30000 });
  await page.getByRole("heading", { name: "Prontos" }).scrollIntoViewIfNeeded();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: "D:\\ForjaB2B\\.playwright-mcp\\prompt10-home-destaques.png", fullPage: false });
  await page.goto("https://forja-b2b.vercel.app/pt-BR/catalog", { waitUntil: "domcontentloaded" });
  await page.locator("article img").first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: "D:\\ForjaB2B\\.playwright-mcp\\prompt10-catalogo.png", fullPage: false });
  return "ok";
}
